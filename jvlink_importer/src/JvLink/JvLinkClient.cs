using JvLinkImporter.Configuration;
using Microsoft.Extensions.Logging;

namespace JvLinkImporter.JvLink;

public sealed record JvOpenResult(
    int ReadCount,
    int DownloadCount,
    string LastFileTimestamp,
    int Code);

public sealed class JvLinkClient : IDisposable
{
    private readonly JvLinkSettings _settings;
    private readonly ILogger<JvLinkClient> _logger;
    private readonly dynamic _jvLink;
    private bool _opened;

    public JvLinkClient(JvLinkSettings settings, ILogger<JvLinkClient> logger)
    {
        _settings = settings;
        _logger = logger;
        var type = Type.GetTypeFromProgID("JVDTLab.JVLink")
            ?? throw new InvalidOperationException(
                "JV-Link COM object was not found. Install JV-Link on Windows first.");
        _jvLink = Activator.CreateInstance(type)
            ?? throw new InvalidOperationException("Failed to create JV-Link COM object.");
    }

    public void Initialize()
    {
        var result = (int)_jvLink.JVInit(_settings.Sid);
        if (result < 0)
        {
            throw new InvalidOperationException($"JVInit failed. Code={result}");
        }
        _logger.LogInformation("JVInit succeeded. Code={Code}", result);
    }

    public JvOpenResult Open(string dataSpec, int option, string from)
    {
        var readCount = 0;
        var downloadCount = 0;
        var lastFileTimestamp = "";
        var result = (int)_jvLink.JVOpen(
            dataSpec,
            from,
            option,
            ref readCount,
            ref downloadCount,
            ref lastFileTimestamp);
        if (result < 0)
        {
            throw new InvalidOperationException($"JVOpen failed. Code={result}");
        }
        _opened = true;
        _logger.LogInformation(
            "JVOpen succeeded. DataSpec={DataSpec}, Option={Option}, From={From}, ReadCount={ReadCount}, DownloadCount={DownloadCount}, LastFileTimestamp={LastFileTimestamp}, Code={Code}",
            dataSpec,
            option,
            from,
            readCount,
            downloadCount,
            lastFileTimestamp,
            result);
        return new JvOpenResult(readCount, downloadCount, lastFileTimestamp, result);
    }

    public int OpenRealtime(string dataSpec, string key)
    {
        var result = (int)_jvLink.JVRTOpen(dataSpec, key);
        if (result < 0)
        {
            throw new InvalidOperationException(
                $"JVRTOpen failed. DataSpec={dataSpec}, Key={key}, Code={result}");
        }

        _opened = true;
        _logger.LogInformation(
            "JVRTOpen succeeded. DataSpec={DataSpec}, Key={Key}, Code={Code}",
            dataSpec,
            key,
            result);
        return result;
    }

    public string? Read()
    {
        var waitRetries = 0;

        while (true)
        {
            var buffer = new string('\0', _settings.ReadBufferSize);
            var result = (int)_jvLink.JVRead(out buffer, _settings.ReadBufferSize, out string fileName);

            if (result == 0)
            {
                return null;
            }

            if (result == -1)
            {
                _logger.LogDebug("JVRead reached file boundary: {FileName}", fileName);
                return "";
            }

            if (result == -3)
            {
                waitRetries++;
                if (waitRetries > _settings.MaxDownloadWaitRetries)
                {
                    throw new InvalidOperationException(
                        $"JVRead timed out while waiting for download. Code={result}");
                }

                _logger.LogInformation(
                    "JVRead is waiting for download. Retry={Retry}/{MaxRetry}",
                    waitRetries,
                    _settings.MaxDownloadWaitRetries);
                Thread.Sleep(_settings.DownloadWaitMilliseconds);
                continue;
            }

            if (result < 0)
            {
                throw new InvalidOperationException($"JVRead failed. Code={result}");
            }

            _logger.LogDebug("JVRead returned {Bytes} bytes from {FileName}", result, fileName);
            return buffer[..Math.Min(result, buffer.Length)];
        }
    }

    public void Close()
    {
        if (!_opened)
        {
            return;
        }

        _jvLink.JVClose();
        _opened = false;
        _logger.LogInformation("JVClose completed");
    }

    public void Dispose()
    {
        Close();
    }
}

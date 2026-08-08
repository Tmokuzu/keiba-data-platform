using JvLinkImporter.Configuration;
using JvLinkImporter.Database;
using JvLinkImporter.JvLink;
using JvLinkImporter.Parsing;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using System.Diagnostics;
using System.Text;

namespace JvLinkImporter;

public static class Program
{
    [STAThread]
    public static async Task<int> Main(string[] args)
    {
        Encoding.RegisterProvider(CodePagesEncodingProvider.Instance);

        var configuration = new ConfigurationBuilder()
            .SetBasePath(Directory.GetCurrentDirectory())
            .AddJsonFile("appsettings.json", optional: false)
            .Build();

        using var loggerFactory = LoggerFactory.Create(builder =>
        {
            builder.AddSimpleConsole(options =>
            {
                options.SingleLine = true;
                options.TimestampFormat = "yyyy-MM-dd HH:mm:ss ";
            });
            builder.SetMinimumLevel(LogLevel.Information);
        });

        var logger = loggerFactory.CreateLogger("JvLinkImporter");
        var settings = ImporterSettings.FromConfiguration(configuration);

        if (args.Length == 0)
        {
            PrintUsage();
            return 1;
        }

        try
        {
            var command = args[0];
            if (command == "check")
            {
                using var client = new JvLinkClient(
                    settings.JvLink,
                    loggerFactory.CreateLogger<JvLinkClient>());
                client.Initialize();
                logger.LogInformation("JV-Link initialization OK");
                return 0;
            }

            if (command is "import-setup" or "import-diff")
            {
                var from = RequiredOption(args, "--from");
                var maxRead = int.TryParse(Option(args, "--max-read"), out var parsedMaxRead)
                    ? parsedMaxRead
                    : int.MaxValue;
                var progressEvery = int.TryParse(Option(args, "--progress-every"), out var parsedProgressEvery)
                    ? parsedProgressEvery
                    : 1000;
                var recordTypes = ParseRecordTypes(Option(args, "--types"));
                var dataSpec = Option(args, "--data-spec") ?? settings.JvLink.DataSpec;
                var option = command == "import-setup"
                    ? settings.JvLink.OptionSetup
                    : settings.JvLink.OptionDiff;

                await using var repository = new PostgresRepository(
                    settings.Postgres.ConnectionString,
                    loggerFactory.CreateLogger<PostgresRepository>(),
                    captureMarketOdds: false);
                var parser = new JvRecordParser(loggerFactory.CreateLogger<JvRecordParser>());
                using var client = new JvLinkClient(
                    settings.JvLink,
                    loggerFactory.CreateLogger<JvLinkClient>());

                client.Initialize();
                var stats = await ImportAsync(
                    client,
                    parser,
                    repository,
                    dataSpec,
                    option,
                    from,
                    maxRead,
                    recordTypes,
                    progressEvery,
                    logger);
                logger.LogInformation(
                    "Import finished. Read={Read}, Parsed={Parsed}, Skipped={Skipped}",
                    stats.ReadCount,
                    stats.ParsedCount,
                    stats.SkippedCount);
                return 0;
            }

            if (command is "scan-types-setup" or "scan-types-diff")
            {
                var from = RequiredOption(args, "--from");
                var maxRead = int.TryParse(Option(args, "--max-read"), out var parsedMaxRead)
                    ? parsedMaxRead
                    : 100000;
                var output = Option(args, "--out");
                var dataSpec = Option(args, "--data-spec") ?? settings.JvLink.DataSpec;
                var option = command == "scan-types-setup"
                    ? settings.JvLink.OptionSetup
                    : settings.JvLink.OptionDiff;

                using var client = new JvLinkClient(
                    settings.JvLink,
                    loggerFactory.CreateLogger<JvLinkClient>());
                client.Initialize();
                var counts = ScanTypes(client, dataSpec, option, from, maxRead);
                foreach (var (recordType, count) in counts.OrderBy(item => item.Key))
                {
                    logger.LogInformation("RecordType={RecordType}, Count={Count}", recordType, count);
                }
                if (!string.IsNullOrWhiteSpace(output))
                {
                    WriteTypeCounts(output, counts);
                    logger.LogInformation("Wrote type counts to {Output}", Path.GetFullPath(output));
                }
                return 0;
            }

            if (command == "import-rt-odds")
            {
                var date = DateOnly.ParseExact(RequiredOption(args, "--date"), "yyyy-MM-dd");
                var dataSpec = Option(args, "--data-spec") ?? "0B31";
                var progressEvery = int.TryParse(Option(args, "--progress-every"), out var parsedProgressEvery)
                    ? parsedProgressEvery
                    : 1;

                await using var repository = new PostgresRepository(
                    settings.Postgres.ConnectionString,
                    loggerFactory.CreateLogger<PostgresRepository>(),
                    captureMarketOdds: true);
                var raceIds = await repository.LoadRaceIdsByDateAsync(date);
                if (raceIds.Count == 0)
                {
                    throw new InvalidOperationException($"No races found for date: {date:yyyy-MM-dd}");
                }

                var parser = new JvRecordParser(loggerFactory.CreateLogger<JvRecordParser>());
                using var client = new JvLinkClient(
                    settings.JvLink,
                    loggerFactory.CreateLogger<JvLinkClient>());

                client.Initialize();
                var stats = await ImportRealtimeAsync(
                    client,
                    parser,
                    repository,
                    dataSpec,
                    raceIds,
                    progressEvery,
                    logger);
                logger.LogInformation(
                    "Realtime import finished. Races={Races}, Read={Read}, Parsed={Parsed}, Skipped={Skipped}",
                    stats.RaceCount,
                    stats.ReadCount,
                    stats.ParsedCount,
                    stats.SkippedCount);
                return 0;
            }

            if (command is "dump-raw-setup" or "dump-raw-diff")
            {
                var from = RequiredOption(args, "--from");
                var output = Option(args, "--out") ?? "raw_jv_records.txt";
                var limit = int.TryParse(Option(args, "--limit"), out var parsedLimit)
                    ? parsedLimit
                    : 100;
                var maxRead = int.TryParse(Option(args, "--max-read"), out var parsedMaxRead)
                    ? parsedMaxRead
                    : 10000;
                var recordTypes = ParseRecordTypes(Option(args, "--types"));
                var dataSpec = Option(args, "--data-spec") ?? settings.JvLink.DataSpec;
                var option = command == "dump-raw-setup"
                    ? settings.JvLink.OptionSetup
                    : settings.JvLink.OptionDiff;

                using var client = new JvLinkClient(
                    settings.JvLink,
                    loggerFactory.CreateLogger<JvLinkClient>());
                client.Initialize();
                var stats = DumpRaw(
                    client,
                    dataSpec,
                    option,
                    from,
                    output,
                    limit,
                    maxRead,
                    recordTypes);
                logger.LogInformation(
                    "Dump finished. Written={Written}, Read={Read}, Output={Output}",
                    stats.WrittenCount,
                    stats.ReadCount,
                    Path.GetFullPath(output));
                return 0;
            }

            PrintUsage();
            return 1;
        }
        catch (Exception ex)
        {
            logger.LogError(ex, "Importer failed");
            return 1;
        }
    }

    private static async Task<ImportStats> ImportAsync(
        JvLinkClient client,
        JvRecordParser parser,
        PostgresRepository repository,
        string dataSpec,
        int option,
        string from,
        int maxRead,
        HashSet<string>? recordTypes,
        int progressEvery,
        ILogger logger)
    {
        var stats = new ImportStats();
        var openResult = client.Open(dataSpec, option, from);
        var expectedReadCount = maxRead == int.MaxValue
            ? openResult.ReadCount
            : Math.Min(openResult.ReadCount, maxRead);
        var stopwatch = Stopwatch.StartNew();
        LogImportProgress(logger, stats, expectedReadCount, stopwatch.Elapsed, force: true);

        while (stats.ReadCount < maxRead)
        {
            var raw = client.Read();
            if (raw is null)
            {
                break;
            }
            if (raw.Length == 0)
            {
                continue;
            }

            stats.ReadCount++;
            await repository.StoreRawRecordAsync(dataSpec, raw);
            var recordType = RecordType(raw);
            if (recordTypes is not null && !recordTypes.Contains(recordType))
            {
                stats.SkippedCount++;
                continue;
            }

            var records = parser.Parse(raw);
            if (records.Count == 0)
            {
                stats.SkippedCount++;
                continue;
            }

            foreach (var record in records)
            {
                await repository.UpsertAsync(record);
                stats.ParsedCount++;
            }

            if (progressEvery > 0 && stats.ReadCount % progressEvery == 0)
            {
                LogImportProgress(logger, stats, expectedReadCount, stopwatch.Elapsed, force: false);
            }
        }

        client.Close();
        LogImportProgress(logger, stats, expectedReadCount, stopwatch.Elapsed, force: true);
        return stats;
    }

    private static async Task<ImportStats> ImportRealtimeAsync(
        JvLinkClient client,
        JvRecordParser parser,
        PostgresRepository repository,
        string dataSpec,
        IReadOnlyList<string> raceIds,
        int progressEvery,
        ILogger logger)
    {
        var stats = new ImportStats();
        var stopwatch = Stopwatch.StartNew();

        foreach (var raceId in raceIds)
        {
            stats.RaceCount++;
            client.OpenRealtime(dataSpec, raceId);

            while (true)
            {
                var raw = client.Read();
                if (raw is null)
                {
                    break;
                }
                if (raw.Length == 0)
                {
                    continue;
                }

                stats.ReadCount++;
                await repository.StoreRawRecordAsync(dataSpec, raw);
                var records = parser.Parse(raw);
                if (records.Count == 0)
                {
                    stats.SkippedCount++;
                    continue;
                }

                foreach (var record in records)
                {
                    await repository.UpsertAsync(record);
                    stats.ParsedCount++;
                }
            }

            client.Close();

            if (progressEvery > 0 && stats.RaceCount % progressEvery == 0)
            {
                logger.LogInformation(
                    "Realtime import progress. Races={Races}/{TotalRaces}, Read={Read}, Parsed={Parsed}, Skipped={Skipped}, Elapsed={Elapsed}",
                    stats.RaceCount,
                    raceIds.Count,
                    stats.ReadCount,
                    stats.ParsedCount,
                    stats.SkippedCount,
                    FormatDuration(stopwatch.Elapsed));
            }
        }

        return stats;
    }

    private static void LogImportProgress(
        ILogger logger,
        ImportStats stats,
        int expectedReadCount,
        TimeSpan elapsed,
        bool force)
    {
        if (!force && stats.ReadCount == 0)
        {
            return;
        }

        var recordsPerSecond = elapsed.TotalSeconds > 0
            ? stats.ReadCount / elapsed.TotalSeconds
            : 0;
        var progress = expectedReadCount > 0
            ? Math.Min(100.0, stats.ReadCount * 100.0 / expectedReadCount)
            : 0;
        var remaining = recordsPerSecond > 0 && expectedReadCount > stats.ReadCount
            ? TimeSpan.FromSeconds((expectedReadCount - stats.ReadCount) / recordsPerSecond)
            : TimeSpan.Zero;

        logger.LogInformation(
            "Import progress. Read={Read}/{ExpectedRead} ({Progress:F1}%), Parsed={Parsed}, Skipped={Skipped}, Speed={Speed:F1} records/sec, Elapsed={Elapsed}, ETA={Eta}",
            stats.ReadCount,
            expectedReadCount,
            progress,
            stats.ParsedCount,
            stats.SkippedCount,
            recordsPerSecond,
            FormatDuration(elapsed),
            remaining == TimeSpan.Zero ? "-" : FormatDuration(remaining));
    }

    private static string FormatDuration(TimeSpan value)
    {
        return value.TotalHours >= 1
            ? value.ToString(@"hh\:mm\:ss")
            : value.ToString(@"mm\:ss");
    }

    private static DumpStats DumpRaw(
        JvLinkClient client,
        string dataSpec,
        int option,
        string from,
        string output,
        int limit,
        int maxRead,
        HashSet<string>? recordTypes)
    {
        var outputPath = Path.GetFullPath(output);
        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrWhiteSpace(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        client.Open(dataSpec, option, from);
        using var writer = new StreamWriter(outputPath, append: false, encoding: System.Text.Encoding.UTF8);
        var stats = new DumpStats();

        while (stats.WrittenCount < limit && stats.ReadCount < maxRead)
        {
            var raw = client.Read();
            if (raw is null)
            {
                break;
            }
            if (raw.Length == 0)
            {
                continue;
            }

            stats.ReadCount++;
            var recordType = RecordType(raw);
            if (recordTypes is not null && !recordTypes.Contains(recordType))
            {
                continue;
            }

            writer.WriteLine(raw.Replace("\r", "\\r").Replace("\n", "\\n"));
            stats.WrittenCount++;
        }

        client.Close();
        return stats;
    }

    private static Dictionary<string, int> ScanTypes(
        JvLinkClient client,
        string dataSpec,
        int option,
        string from,
        int maxRead)
    {
        var counts = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        client.Open(dataSpec, option, from);
        var readCount = 0;

        while (readCount < maxRead)
        {
            var raw = client.Read();
            if (raw is null)
            {
                break;
            }
            if (raw.Length == 0)
            {
                continue;
            }

            readCount++;
            var recordType = RecordType(raw);
            counts[recordType] = counts.GetValueOrDefault(recordType) + 1;
        }

        client.Close();
        return counts;
    }

    private static void WriteTypeCounts(string output, Dictionary<string, int> counts)
    {
        var outputPath = Path.GetFullPath(output);
        var outputDirectory = Path.GetDirectoryName(outputPath);
        if (!string.IsNullOrWhiteSpace(outputDirectory))
        {
            Directory.CreateDirectory(outputDirectory);
        }

        using var writer = new StreamWriter(outputPath, append: false, encoding: System.Text.Encoding.UTF8);
        foreach (var (recordType, count) in counts.OrderBy(item => item.Key))
        {
            writer.WriteLine($"{recordType},{count}");
        }
    }

    private static HashSet<string>? ParseRecordTypes(string? value)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            return null;
        }

        return value
            .Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Select(type => type.ToUpperInvariant())
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
    }

    private static string RecordType(string raw)
    {
        var normalized = raw.TrimStart('\ufeff');
        return normalized.Length >= 2 ? normalized[..2].ToUpperInvariant() : "";
    }

    private static string? Option(string[] args, string name)
    {
        var index = Array.IndexOf(args, name);
        if (index < 0 || index + 1 >= args.Length)
        {
            return null;
        }

        return args[index + 1];
    }

    private static string RequiredOption(string[] args, string name)
    {
        return Option(args, name) ?? throw new ArgumentException($"Missing required option: {name}");
    }

    private static void PrintUsage()
    {
        Console.WriteLine("""
        Usage:
          dotnet run -- check
          dotnet run -- import-setup --from yyyyMMddHHmmss [--data-spec RACE] [--types RA,SE,HR,O1] [--max-read 10000] [--progress-every 1000]
          dotnet run -- import-diff --from yyyyMMddHHmmss [--data-spec RACE] [--types RA,SE,HR,O1] [--max-read 10000] [--progress-every 1000]
          dotnet run -- import-rt-odds --date yyyy-MM-dd [--data-spec 0B31] [--progress-every 1]
          dotnet run -- scan-types-setup --from yyyyMMddHHmmss [--max-read 100000] [--out type_counts.csv]
          dotnet run -- scan-types-diff --from yyyyMMddHHmmss [--max-read 100000] [--out type_counts.csv]
          dotnet run -- dump-raw-setup --from yyyyMMddHHmmss [--out raw_jv_records.txt] [--limit 100] [--types RA,SE,HR] [--max-read 10000]
          dotnet run -- dump-raw-diff --from yyyyMMddHHmmss [--out raw_jv_records.txt] [--limit 100] [--types RA,SE,HR] [--max-read 10000]
        """);
    }

    private sealed record ImportStats
    {
        public int RaceCount { get; set; }
        public int ReadCount { get; set; }
        public int ParsedCount { get; set; }
        public int SkippedCount { get; set; }
    }

    private sealed record DumpStats
    {
        public int ReadCount { get; set; }
        public int WrittenCount { get; set; }
    }
}

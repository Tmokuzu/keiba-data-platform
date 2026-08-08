using Microsoft.Extensions.Configuration;

namespace JvLinkImporter.Configuration;

public sealed record ImporterSettings(JvLinkSettings JvLink, PostgresSettings Postgres)
{
    public static ImporterSettings FromConfiguration(IConfiguration configuration)
    {
        var jvLink = configuration.GetSection("JvLink").Get<JvLinkSettings>()
            ?? throw new InvalidOperationException("Missing JvLink settings");
        var postgres = configuration.GetSection("Postgres").Get<PostgresSettings>()
            ?? throw new InvalidOperationException("Missing Postgres settings");
        return new ImporterSettings(jvLink, postgres);
    }
}

public sealed record JvLinkSettings
{
    public string Sid { get; init; } = "";
    public string DataSpec { get; init; } = "RACE";
    public int OptionSetup { get; init; } = 4;
    public int OptionDiff { get; init; } = 1;
    public int ReadBufferSize { get; init; } = 110000;
    public int DownloadWaitMilliseconds { get; init; } = 2000;
    public int MaxDownloadWaitRetries { get; init; } = 300;
}

public sealed record PostgresSettings
{
    public string ConnectionString { get; init; } = "";
}

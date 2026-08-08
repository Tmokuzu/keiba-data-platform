param(
    [string]$From = "19990601000000",
    [int]$ProgressEvery = 1000,
    [switch]$SkipRace,
    [switch]$SkipScan
)

$ErrorActionPreference = "Continue"
$specs = @("RACE", "DIFN", "SNPN", "SLOP", "WOOD", "BLOD", "COMM", "MING")
if ($SkipRace) {
    $specs = $specs | Where-Object { $_ -ne "RACE" }
}

Write-Host "JV-Link archive import starts from $From"
Write-Host "All received records are preserved in raw_jv_records, including unsupported types."

foreach ($spec in $specs) {
    if (-not $SkipScan) {
        Write-Host "`n=== ${spec}: record-type scan ==="
        dotnet run -- scan-types-setup --from $From --data-spec $spec --max-read 100000
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "$spec scan failed or is unavailable for this contract; continuing."
            continue
        }
    }

    Write-Host "=== ${spec}: archive import ==="
    dotnet run -- import-setup --from $From --data-spec $spec --progress-every $ProgressEvery
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "$spec import failed; inspect its log and rerun this data spec separately."
    }
}

Write-Host "Archive import finished. In WSL/Linux run: uv run python main.py validate"

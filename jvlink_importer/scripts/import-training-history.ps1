param(
    [int]$ProgressEvery = 1000,
    [switch]$SkipScan
)

$ErrorActionPreference = "Continue"

# JV-Link availability: HC starts in 2003; WC starts in 2021.
$imports = @(
    @{ Spec = "SLOP"; From = "20030101000000"; Label = "HC (坂路調教)" },
    @{ Spec = "WOOD"; From = "20210727000000"; Label = "WC (ウッドチップ調教)" }
)

Write-Host "JV-Link full training-history import starts."
Write-Host "Existing raw records are deduplicated by hash, so resuming is safe."

foreach ($item in $imports) {
    if (-not $SkipScan) {
        Write-Host "`n=== $($item.Label): record-type scan ==="
        dotnet run -- scan-types-setup --from $item.From --data-spec $item.Spec --max-read 100000
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "$($item.Spec) scan failed; continuing with import."
        }
    }

    Write-Host "=== $($item.Label): archive import from $($item.From) ==="
    dotnet run -- import-setup --from $item.From --data-spec $item.Spec --progress-every $ProgressEvery
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "$($item.Spec) import failed; rerun this script safely after inspecting the log."
    }
}

Write-Host "Training-history archive import finished. In WSL/Linux run:"
Write-Host "  uv run python main.py normalize-jv-training"
Write-Host "  uv run python main.py build-jv-training-features"

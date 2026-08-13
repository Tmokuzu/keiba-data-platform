#!/usr/bin/env bash
set -euo pipefail

# Build race-level HC/WC features in monthly transactions. Re-running any
# completed month is safe because the DB command uses UPSERT.
START_YEAR="${1:-2016}"
END_YEAR="${2:-2026}"

if ! [[ "$START_YEAR" =~ ^[0-9]{4}$ && "$END_YEAR" =~ ^[0-9]{4}$ ]] || (( START_YEAR > END_YEAR )); then
  echo "Usage: $0 [start-year] [end-year]" >&2
  exit 2
fi

for ((year = START_YEAR; year <= END_YEAR; year++)); do
  for month in {1..12}; do
    from=$(printf '%04d-%02d-01' "$year" "$month")
    if (( month == 12 )); then
      to=$(printf '%04d-01-01' "$((year + 1))")
    else
      to=$(printf '%04d-%02d-01' "$year" "$((month + 1))")
    fi
    echo "=== building training features: $from to $to ==="
    uv run python main.py build-jv-training-features --from-date "$from" --to-date "$to"
  done
done

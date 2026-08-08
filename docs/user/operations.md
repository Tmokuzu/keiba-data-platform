# Operations

## Daily Refresh

1. Put current raw CSV files in `data/raw/`.
2. Run:

```bash
uv run python main.py import-csv
uv run python main.py sync-ended
uv run python main.py build-ai-views
uv run python main.py validate
```

3. Review `logs/data_quality_report.json`.

## Expected Raw Files

- `races.csv`
- `entries.csv`
- `results.csv`
- `payouts.csv`
- `odds.csv`

CSV headers should match the SQL table definitions under `sql/`.

## Generated Files

These are local artifacts and are ignored by Git:

- `data/processed/`
- `models/`
- `data/postgres/`
- `logs/*.log`
- `logs/data_quality_report.json`

## Common Troubleshooting

If `check-db` fails inside a managed sandbox but `psql` works in your terminal, rerun DB commands with elevated local access. Local PostgreSQL sockets and TCP ports may be blocked by sandbox policy.

If `init-db` fails while replacing an old view, confirm `sql/003_create_ai_views.sql` drops old AI views before creating new ones.

## Validation Checklist

Before relying on a model output:

- `validate` completed.
- `model-compare` completed.
- `walk-forward-backtest` completed on real year coverage.
- `phase2-report` exists.
- No calibration, threshold, or stake rule was fit on test data.

Backtests and model metrics do not guarantee future profit.

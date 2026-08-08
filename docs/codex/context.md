# Codex Context

This repository is a PostgreSQL-backed JRA racing data platform plus Phase2 place-only modeling.

## Architecture

```text
data/raw CSV
-> raw_* tables
-> sync-ended
-> core tables
-> ai_race_entries / ai_horse_history
-> place model training, prediction, validation
```

Key modules:

- `src/database/`: SQLAlchemy connection and schema runner.
- `src/ingestion/`: raw CSV and temp parquet helpers.
- `src/pipelines/`: raw-to-core and AI view build commands.
- `src/models/`: feature prep, LightGBM/CatBoost/XGBoost, ensemble, prediction.
- `src/agents/`: Safe Agent rules.
- `src/backtesting/`: ROI, hit rate, drawdown metrics.
- `src/validation/`: model compare, walk-forward, ablation, Phase2 report.

## Invariants

- Current ticket scope is place only.
- Core DB contains ended and confirmed races only.
- Same-day temporary data belongs in `temp/`, not core tables.
- `target_place` is the binary place target.
- Isotonic calibration is fit on valid split only.
- Test split is evaluation only.
- Walk-forward folds must be chronological.
- Probability correction is per `race_id`.

## Generated And Heavy Data

Do not commit or casually read:

- `data/postgres/`
- `data/processed/`
- `models/`
- `logs/*.log`
- `.venv/`
- `uv.lock` unless dependency changes are relevant
- full `data/raw/*.csv` unless the task is data inspection

Use `head`, `wc`, targeted SQL, or `rg --files` instead of broad reads.

## DB Note

In managed sandboxes, local PostgreSQL may require elevated command execution. If a DB command fails with socket or TCP permission errors, retry the same command with escalation instead of changing DB code.

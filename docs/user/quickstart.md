# Quickstart

## Setup

```bash
uv sync
cp .env.example .env
```

Edit `.env` for your PostgreSQL connection:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=keiba
POSTGRES_USER=postgres
POSTGRES_PASSWORD=password
```

Check the connection:

```bash
uv run python main.py check-db
```

## Refresh The Database

Place CSV files in `data/raw/`, then run:

```bash
uv run python main.py init-db
uv run python main.py import-csv
uv run python main.py sync-ended
uv run python main.py build-ai-views
uv run python main.py validate
```

`sync-ended` only moves ended and confirmed races into core tables. Same-day or unconfirmed race data should stay outside core DB.

## Phase2 Place Modeling

Train all place models and build ensemble predictions:

```bash
uv run python main.py train-all-models
uv run python main.py predict-ensemble
uv run python main.py safe-agent
uv run python main.py backtest-safe-agent
```

Run validation reports:

```bash
uv run python main.py model-compare
uv run python main.py walk-forward-backtest
uv run python main.py ablation-test
uv run python main.py phase2-report
```

Backtests and model metrics do not guarantee future profit.

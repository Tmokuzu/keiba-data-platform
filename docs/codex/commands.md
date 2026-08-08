# Codex Commands

Use the smallest command set that proves the change.

## Fast Static Check

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m compileall main.py src
```

## DB Refresh

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py check-db
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py init-db
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py import-csv
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py sync-ended
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py build-ai-views
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py validate
```

## Phase2 Modeling

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py train-all-models
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py predict-ensemble
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py safe-agent
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py backtest-safe-agent
```

## Validation Reports

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py model-compare
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py walk-forward-backtest
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py ablation-test
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py phase2-report
```

## Git Hygiene

Before committing:

```bash
git status --short --ignored
git diff --cached --name-only
```

Expected ignored generated paths include `/models/`, `/data/processed/`, `/data/postgres/`, logs, caches, and `.venv/`.

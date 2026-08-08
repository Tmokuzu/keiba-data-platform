# Codex Guide

This file is the lightweight entrypoint for Codex work in this repository. Keep it short; open the linked docs only when the task needs them.

## Read Order

1. `docs/codex/context.md` for architecture, safety rules, and generated-file boundaries.
2. `docs/codex/commands.md` for the smallest command set needed to verify a change.
3. `docs/user/configuration.md` only when changing `config.yaml` behavior.
4. Relevant source files under `src/`; avoid scanning generated data unless explicitly needed.

## Default Boundaries

- Ticket scope is place only. Do not add win, quinella, wide, trifecta, or other bet types unless the user asks.
- Training, calibration, thresholding, and walk-forward validation must respect time order.
- Do not fit calibration, thresholds, or stake rules on test data.
- Core DB stores ended and confirmed races only. Temporary same-day data belongs in `temp/`.
- Do not commit generated artifacts: `/models/`, `/data/processed/`, `/data/postgres/`, logs, caches, or virtualenvs.

## High-Signal Commands

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m compileall main.py src
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py check-db
UV_CACHE_DIR=/tmp/uv-cache uv run python main.py validate
```

DB access may require elevated execution in managed sandboxes because local PostgreSQL sockets and TCP ports can be blocked.

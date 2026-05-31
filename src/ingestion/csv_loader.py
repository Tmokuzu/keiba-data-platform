from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from src.database.connection import get_engine
from src.database.upsert import upsert_dataframe
from src.utils.logger import get_logger


logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"

CSV_SPECS = {
    "races.csv": ("raw_races", ["race_id"]),
    "entries.csv": ("raw_entries", ["race_id", "horse_id"]),
    "results.csv": ("raw_results", ["race_id", "horse_id"]),
    "payouts.csv": ("raw_payouts", ["race_id", "ticket_type", "combination"]),
    "odds.csv": ("raw_odds", ["race_id", "snapshot_time", "ticket_type", "combination"]),
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {"raw_data_dir": "data/raw", "tables": {}}
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])


def import_csv_files() -> dict[str, int]:
    config = load_config()
    raw_data_dir = PROJECT_ROOT / config.get("raw_data_dir", "data/raw")
    tables = config.get("tables", {})
    engine = get_engine()
    imported: dict[str, int] = {}

    for file_name, (table_key, conflict_columns) in CSV_SPECS.items():
        csv_path = raw_data_dir / file_name
        table_name = tables.get(table_key, table_key)

        if not csv_path.exists():
            logger.info("CSV not found, skipped: %s", csv_path)
            imported[table_name] = 0
            continue

        df = read_csv(csv_path)
        count = upsert_dataframe(engine, df, table_name, conflict_columns)
        imported[table_name] = count
        logger.info("Imported CSV: %s -> %s (%s rows affected)", csv_path, table_name, count)

    return imported

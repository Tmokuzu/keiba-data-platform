from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def get_temp_data_dir() -> Path:
    config = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    temp_data_dir = config.get("temp_data_dir", "temp")
    path = PROJECT_ROOT / temp_data_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_temp_parquet(df: pd.DataFrame, name: str) -> Path:
    path = get_temp_data_dir() / name
    if path.suffix != ".parquet":
        path = path.with_suffix(".parquet")
    df.to_parquet(path, index=False)
    return path


def load_temp_parquet(name: str) -> pd.DataFrame:
    path = get_temp_data_dir() / name
    if path.suffix != ".parquet":
        path = path.with_suffix(".parquet")
    return pd.read_parquet(path)

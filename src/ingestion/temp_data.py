from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.utils.config import configured_path, load_yaml_config


def get_temp_data_dir() -> Path:
    config = load_yaml_config()
    path = configured_path(config, "temp_data_dir", "temp")
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

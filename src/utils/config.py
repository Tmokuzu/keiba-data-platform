from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def load_yaml_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}


def configured_path(config: dict[str, Any], key: str, default: str) -> Path:
    paths = config.get("paths", {})
    raw_value = paths.get(key, config.get(key, default))
    path = Path(raw_value)
    return path if path.is_absolute() else PROJECT_ROOT / path

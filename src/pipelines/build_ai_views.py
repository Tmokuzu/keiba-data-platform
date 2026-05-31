from __future__ import annotations

from pathlib import Path

from src.database.schema import run_sql_file
from src.utils.logger import get_logger


logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def build_ai_views() -> None:
    run_sql_file(PROJECT_ROOT / "sql" / "003_create_ai_views.sql")
    logger.info("Built AI views.")

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from src.database.connection import get_engine
from src.utils.logger import get_logger


logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = PROJECT_ROOT / "sql"


def split_sql_statements(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def run_sql_file(path: str | Path) -> None:
    sql_path = Path(path)
    if not sql_path.is_absolute():
        sql_path = PROJECT_ROOT / sql_path
    sql = sql_path.read_text(encoding="utf-8")

    engine = get_engine()
    with engine.begin() as connection:
        for statement in split_sql_statements(sql):
            connection.execute(text(statement))
    logger.info("Executed SQL file: %s", sql_path)


def init_db() -> None:
    sql_files = [
        SQL_DIR / "001_create_raw_tables.sql",
        SQL_DIR / "002_create_core_tables.sql",
        SQL_DIR / "003_create_ai_views.sql",
        SQL_DIR / "004_create_indexes.sql",
        SQL_DIR / "005_create_jv_raw_archive.sql",
    ]
    for sql_file in sql_files:
        run_sql_file(sql_file)

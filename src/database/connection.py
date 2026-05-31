from __future__ import annotations

import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from src.utils.logger import get_logger


logger = get_logger(__name__)


def get_database_url() -> str:
    load_dotenv()
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "keiba")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = quote_plus(os.getenv("POSTGRES_PASSWORD", "password"))
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


def get_engine() -> Engine:
    return create_engine(get_database_url(), pool_pre_ping=True, future=True)


def test_connection() -> bool:
    engine = get_engine()
    with engine.connect() as connection:
        value = connection.execute(text("SELECT 1")).scalar_one()
    logger.info("Database connection OK: SELECT %s", value)
    return True

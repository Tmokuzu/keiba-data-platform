from __future__ import annotations

from sqlalchemy import text

from src.database.connection import get_engine
from src.utils.logger import get_logger


logger = get_logger(__name__)


def normalize_ck_snapshots() -> None:
    """Normalize the as-of horse record block from official CK fixed-width data."""
    sql = """
    INSERT INTO jv_ck_snapshots (
        race_id, horse_id, snapshot_date, flat_prize_yen,
        central_runs, central_wins, central_seconds, central_thirds,
        central_fourths, central_fifths, central_other, source_hash
    )
    SELECT
        substring(raw_payload FROM 12 FOR 4) || substring(raw_payload FROM 16 FOR 4) ||
        substring(raw_payload FROM 20 FOR 2) || substring(raw_payload FROM 22 FOR 2) ||
        substring(raw_payload FROM 24 FOR 2) || substring(raw_payload FROM 26 FOR 2),
        substring(raw_payload FROM 28 FOR 10),
        to_date(substring(raw_payload FROM 12 FOR 8), 'YYYYMMDD'),
        NULLIF(substring(raw_payload FROM 74 FOR 9), '')::bigint * 100,
        COALESCE(NULLIF(substring(raw_payload FROM 146 FOR 3), '')::integer, 0) +
        COALESCE(NULLIF(substring(raw_payload FROM 149 FOR 3), '')::integer, 0) +
        COALESCE(NULLIF(substring(raw_payload FROM 152 FOR 3), '')::integer, 0) +
        COALESCE(NULLIF(substring(raw_payload FROM 155 FOR 3), '')::integer, 0) +
        COALESCE(NULLIF(substring(raw_payload FROM 158 FOR 3), '')::integer, 0) +
        COALESCE(NULLIF(substring(raw_payload FROM 161 FOR 3), '')::integer, 0),
        NULLIF(substring(raw_payload FROM 146 FOR 3), '')::integer,
        NULLIF(substring(raw_payload FROM 149 FOR 3), '')::integer,
        NULLIF(substring(raw_payload FROM 152 FOR 3), '')::integer,
        NULLIF(substring(raw_payload FROM 155 FOR 3), '')::integer,
        NULLIF(substring(raw_payload FROM 158 FOR 3), '')::integer,
        NULLIF(substring(raw_payload FROM 161 FOR 3), '')::integer,
        record_hash
    FROM (
        SELECT DISTINCT ON (
            substring(raw_payload FROM 12 FOR 4) || substring(raw_payload FROM 16 FOR 4) ||
            substring(raw_payload FROM 20 FOR 2) || substring(raw_payload FROM 22 FOR 2) ||
            substring(raw_payload FROM 24 FOR 2) || substring(raw_payload FROM 26 FOR 2),
            substring(raw_payload FROM 28 FOR 10)
        ) raw_payload, record_hash
        FROM raw_jv_records
        WHERE data_spec = 'SNPN' AND record_type = 'CK'
        ORDER BY
            substring(raw_payload FROM 12 FOR 4) || substring(raw_payload FROM 16 FOR 4) ||
            substring(raw_payload FROM 20 FOR 2) || substring(raw_payload FROM 22 FOR 2) ||
            substring(raw_payload FROM 24 FOR 2) || substring(raw_payload FROM 26 FOR 2),
            substring(raw_payload FROM 28 FOR 10),
            received_at DESC
    ) AS latest
    ON CONFLICT (race_id, horse_id) DO UPDATE SET
        snapshot_date = EXCLUDED.snapshot_date,
        flat_prize_yen = EXCLUDED.flat_prize_yen,
        central_runs = EXCLUDED.central_runs,
        central_wins = EXCLUDED.central_wins,
        central_seconds = EXCLUDED.central_seconds,
        central_thirds = EXCLUDED.central_thirds,
        central_fourths = EXCLUDED.central_fourths,
        central_fifths = EXCLUDED.central_fifths,
        central_other = EXCLUDED.central_other,
        source_hash = EXCLUDED.source_hash
    """
    with get_engine().begin() as connection:
        connection.execute(text(sql))
    logger.info("Normalized CK as-of snapshots.")

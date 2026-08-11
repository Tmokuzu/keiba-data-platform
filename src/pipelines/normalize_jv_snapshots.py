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


def normalize_training_sessions() -> None:
    """Normalize HC/WC training records using the official fixed-width layout.

    Training dates are intentionally retained separately from creation dates;
    race features must only select records strictly before the race date.
    """
    sql = """
    INSERT INTO jv_training_sessions (
        source_hash, record_type, created_date, training_date, training_center,
        horse_id, course_code, direction_code, time_4f_seconds,
        time_3f_seconds, time_2f_seconds, lap_800_600_seconds,
        lap_600_400_seconds, lap_400_200_seconds, lap_200_0_seconds
    )
    SELECT
        record_hash,
        record_type,
        to_date(substring(raw_payload FROM 4 FOR 8), 'YYYYMMDD'),
        to_date(substring(raw_payload FROM 13 FOR 8), 'YYYYMMDD'),
        CASE substring(raw_payload FROM 12 FOR 1) WHEN '0' THEN 'miho' WHEN '1' THEN 'ritto' END,
        substring(raw_payload FROM 25 FOR 10),
        CASE WHEN record_type = 'WC' THEN substring(raw_payload FROM 35 FOR 1) END,
        CASE WHEN record_type = 'WC' THEN substring(raw_payload FROM 36 FOR 1) END,
        NULLIF(CASE WHEN record_type = 'HC' THEN substring(raw_payload FROM 35 FOR 4) ELSE substring(raw_payload FROM 80 FOR 4) END, '0000')::numeric / 10,
        NULLIF(CASE WHEN record_type = 'HC' THEN substring(raw_payload FROM 42 FOR 4) ELSE substring(raw_payload FROM 87 FOR 4) END, '0000')::numeric / 10,
        NULLIF(CASE WHEN record_type = 'HC' THEN substring(raw_payload FROM 49 FOR 4) ELSE substring(raw_payload FROM 94 FOR 4) END, '0000')::numeric / 10,
        NULLIF(CASE WHEN record_type = 'HC' THEN substring(raw_payload FROM 39 FOR 3) ELSE substring(raw_payload FROM 84 FOR 3) END, '000')::numeric / 10,
        NULLIF(CASE WHEN record_type = 'HC' THEN substring(raw_payload FROM 46 FOR 3) ELSE substring(raw_payload FROM 91 FOR 3) END, '000')::numeric / 10,
        NULLIF(CASE WHEN record_type = 'HC' THEN substring(raw_payload FROM 53 FOR 3) ELSE substring(raw_payload FROM 98 FOR 3) END, '000')::numeric / 10,
        NULLIF(CASE WHEN record_type = 'HC' THEN substring(raw_payload FROM 56 FOR 3) ELSE substring(raw_payload FROM 101 FOR 3) END, '000')::numeric / 10
    FROM raw_jv_records
    WHERE record_type IN ('HC', 'WC')
      AND substring(raw_payload FROM 3 FOR 1) <> '0'
    ON CONFLICT (source_hash) DO NOTHING
    """
    with get_engine().begin() as connection:
        connection.execute(text(sql))
    logger.info("Normalized HC/WC training sessions.")


def build_race_training_features() -> None:
    """Build conservative as-of training features for each historical starter."""
    sql = """
    INSERT INTO jv_race_training_features (
        race_id, horse_id, sessions_7d, sessions_14d, days_since_latest,
        latest_4f_seconds, latest_3f_seconds, latest_1f_seconds,
        best_3f_14d_seconds, latest_training_type, updated_at
    )
    SELECT
        r.race_id, e.horse_id,
        COALESCE(stats.sessions_7d, 0), COALESCE(stats.sessions_14d, 0),
        latest.days_since_latest, latest.time_4f_seconds, latest.time_3f_seconds,
        latest.lap_200_0_seconds, stats.best_3f_14d_seconds, latest.record_type,
        CURRENT_TIMESTAMP
    FROM races r
    JOIN entries e ON e.race_id = r.race_id
    LEFT JOIN LATERAL (
        SELECT
            COUNT(*) FILTER (WHERE t.training_date >= r.race_date - INTERVAL '7 days')::integer AS sessions_7d,
            COUNT(*)::integer AS sessions_14d,
            MIN(t.time_3f_seconds) AS best_3f_14d_seconds
        FROM jv_training_sessions t
        WHERE t.horse_id = e.horse_id
          AND t.training_date < r.race_date
          AND t.created_date < r.race_date
          AND t.training_date >= r.race_date - INTERVAL '14 days'
    ) stats ON TRUE
    LEFT JOIN LATERAL (
        SELECT
            (r.race_date - t.training_date)::integer AS days_since_latest,
            t.time_4f_seconds, t.time_3f_seconds, t.lap_200_0_seconds, t.record_type
        FROM jv_training_sessions t
        WHERE t.horse_id = e.horse_id
          AND t.training_date < r.race_date
          AND t.created_date < r.race_date
        ORDER BY t.training_date DESC, t.created_date DESC
        LIMIT 1
    ) latest ON TRUE
    WHERE r.race_date > DATE '2023-08-01'
    ON CONFLICT (race_id, horse_id) DO UPDATE SET
        sessions_7d = EXCLUDED.sessions_7d,
        sessions_14d = EXCLUDED.sessions_14d,
        days_since_latest = EXCLUDED.days_since_latest,
        latest_4f_seconds = EXCLUDED.latest_4f_seconds,
        latest_3f_seconds = EXCLUDED.latest_3f_seconds,
        latest_1f_seconds = EXCLUDED.latest_1f_seconds,
        best_3f_14d_seconds = EXCLUDED.best_3f_14d_seconds,
        latest_training_type = EXCLUDED.latest_training_type,
        updated_at = CURRENT_TIMESTAMP
    """
    with get_engine().begin() as connection:
        connection.execute(text(sql))
    logger.info("Built conservative as-of race training features.")

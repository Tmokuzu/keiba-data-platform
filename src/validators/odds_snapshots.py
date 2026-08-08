from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import text

from src.database.connection import get_engine
from src.models.common import PROCESSED_DIR, load_config
from src.utils.logger import get_logger


logger = get_logger(__name__)


def check_odds_snapshot_coverage(
    race_date: str,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Report whether a day's entries have usable pre-start place odds.

    The report reads the raw ingestion layer so same-day entries remain outside
    the core tables. It is therefore safe to run before a race day prediction.
    """
    cutoff_minutes = int(
        load_config().get("data", {}).get("odds_snapshot_cutoff_minutes_before_start", 1)
    )
    summary_sql = """
        WITH target_entries AS (
            SELECT
                r.race_id,
                r.start_time,
                e.horse_no,
                (
                    r.race_date::timestamp
                    + CASE
                        WHEN COALESCE(r.start_time, '') ~ '^[0-9]{4}$'
                            THEN to_timestamp(r.start_time, 'HH24MI')::time
                        WHEN COALESCE(r.start_time, '') ~ '^[0-9]{1,2}:[0-9]{2}'
                            THEN r.start_time::time
                      END
                    - (:cutoff_minutes * INTERVAL '1 minute')
                ) AS cutoff_time
            FROM raw_races r
            JOIN raw_entries e ON e.race_id = r.race_id
            WHERE r.race_date = :race_date
        ),
        latest AS (
            SELECT te.*, odds.snapshot_time
            FROM target_entries te
            LEFT JOIN LATERAL (
                SELECT snapshot_time
                FROM raw_odds os
                WHERE os.race_id = te.race_id
                  AND os.ticket_type IN ('place', '複勝')
                  AND os.combination IN (CAST(te.horse_no AS TEXT), LPAD(CAST(te.horse_no AS TEXT), 2, '0'))
                  AND os.snapshot_time <= te.cutoff_time
                ORDER BY os.snapshot_time DESC
                LIMIT 1
            ) odds ON TRUE
        )
        SELECT
            COUNT(*) AS entries,
            COUNT(snapshot_time) AS covered_entries,
            COUNT(*) - COUNT(snapshot_time) AS missing_entries,
            COUNT(DISTINCT race_id) AS races,
            COUNT(DISTINCT race_id) FILTER (WHERE snapshot_time IS NOT NULL) AS covered_races,
            COUNT(*) FILTER (WHERE cutoff_time IS NULL) AS entries_without_valid_start_time,
            MIN(snapshot_time) AS min_snapshot_time,
            MAX(snapshot_time) AS max_snapshot_time
        FROM latest
    """
    examples_sql = """
        WITH target_entries AS (
            SELECT
                r.race_id, r.course, r.race_no, e.horse_no, e.horse_name,
                (
                    r.race_date::timestamp
                    + CASE
                        WHEN COALESCE(r.start_time, '') ~ '^[0-9]{4}$'
                            THEN to_timestamp(r.start_time, 'HH24MI')::time
                        WHEN COALESCE(r.start_time, '') ~ '^[0-9]{1,2}:[0-9]{2}'
                            THEN r.start_time::time
                      END
                    - (:cutoff_minutes * INTERVAL '1 minute')
                ) AS cutoff_time
            FROM raw_races r JOIN raw_entries e ON e.race_id = r.race_id
            WHERE r.race_date = :race_date
        )
        SELECT race_id, course, race_no, horse_no, horse_name, cutoff_time
        FROM target_entries te
        WHERE cutoff_time IS NULL OR NOT EXISTS (
            SELECT 1 FROM raw_odds os
            WHERE os.race_id = te.race_id
              AND os.ticket_type IN ('place', '複勝')
              AND os.combination IN (CAST(te.horse_no AS TEXT), LPAD(CAST(te.horse_no AS TEXT), 2, '0'))
              AND os.snapshot_time <= te.cutoff_time
        )
        ORDER BY race_id, horse_no
        LIMIT 30
    """
    params = {"race_date": race_date, "cutoff_minutes": cutoff_minutes}
    with get_engine().connect() as conn:
        summary = dict(conn.execute(text(summary_sql), params).mappings().one())
        entries = int(summary["entries"] or 0)
        covered = int(summary["covered_entries"] or 0)
        report: dict[str, Any] = {
            "race_date": race_date,
            "cutoff_minutes_before_start": cutoff_minutes,
            "coverage": covered / entries if entries else 0.0,
            "ready": entries > 0 and covered / entries >= 0.95,
            "summary": summary,
            "missing_examples": [
                dict(row) for row in conn.execute(text(examples_sql), params).mappings().all()
            ],
        }

    output = output_path or PROCESSED_DIR / f"odds_snapshot_coverage_{race_date.replace('-', '')}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    logger.info("Saved odds snapshot coverage report: %s", output)
    return report

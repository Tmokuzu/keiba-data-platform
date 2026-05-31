from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from src.database.connection import get_engine
from src.utils.logger import get_logger


logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / "logs" / "data_quality_report.json"


QUALITY_SQL = {
    "races_count": "SELECT COUNT(*) FROM races",
    "entries_count": "SELECT COUNT(*) FROM entries",
    "results_count": "SELECT COUNT(*) FROM results",
    "race_id_duplicates": """
        SELECT COALESCE(SUM(dup_count - 1), 0)
        FROM (
            SELECT race_id, COUNT(*) AS dup_count
            FROM races
            GROUP BY race_id
            HAVING COUNT(*) > 1
        ) duplicated
    """,
    "entries_missing_races": """
        SELECT COUNT(*)
        FROM entries e
        LEFT JOIN races r ON e.race_id = r.race_id
        WHERE r.race_id IS NULL
    """,
    "results_missing_entries": """
        SELECT COUNT(*)
        FROM results res
        LEFT JOIN entries e
            ON res.race_id = e.race_id
            AND res.horse_id = e.horse_id
        WHERE e.race_id IS NULL
    """,
    "field_size_mismatches": """
        SELECT COUNT(*)
        FROM races r
        LEFT JOIN (
            SELECT race_id, COUNT(*) AS entry_count
            FROM entries
            GROUP BY race_id
        ) counts ON r.race_id = counts.race_id
        WHERE r.field_size IS NOT NULL
          AND r.field_size <> COALESCE(counts.entry_count, 0)
    """,
    "odds_win_non_positive": "SELECT COUNT(*) FROM entries WHERE odds_win <= 0",
    "odds_place_min_non_positive": "SELECT COUNT(*) FROM entries WHERE odds_place_min <= 0",
    "payout_place_missing": "SELECT COUNT(*) FROM ai_race_entries WHERE payout_place IS NULL",
    "horse_id_missing": "SELECT COUNT(*) FROM entries WHERE horse_id IS NULL OR horse_id = ''",
}


def run_data_quality_checks() -> dict[str, int]:
    engine = get_engine()
    report: dict[str, int] = {}
    with engine.connect() as connection:
        for name, sql in QUALITY_SQL.items():
            value = connection.execute(text(sql)).scalar_one()
            report[name] = int(value or 0)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    logger.info("Saved data quality report: %s", REPORT_PATH)
    return report

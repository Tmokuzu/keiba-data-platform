from __future__ import annotations

from sqlalchemy import text

from src.database.connection import get_engine
from src.database.schema import split_sql_statements
from src.utils.logger import get_logger


logger = get_logger(__name__)


SYNC_ENDED_SQL = """
WITH ended_races AS (
    SELECT rr.race_id
    FROM raw_races rr
    WHERE rr.race_id IS NOT NULL
      AND rr.race_date IS NOT NULL
      AND rr.course IS NOT NULL
      AND rr.race_no IS NOT NULL
      AND EXISTS (
          SELECT 1
          FROM raw_entries entry
          WHERE entry.race_id = rr.race_id
            AND entry.horse_id IS NOT NULL
      )
      AND EXISTS (
          SELECT 1
          FROM raw_results res
          WHERE res.race_id = rr.race_id
      )
      AND NOT EXISTS (
          SELECT 1
          FROM raw_entries entry
          WHERE entry.race_id = rr.race_id
            AND entry.horse_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1
                FROM raw_results res
                WHERE res.race_id = entry.race_id
                  AND res.horse_id = entry.horse_id
            )
      )
      AND EXISTS (
          SELECT 1
          FROM raw_payouts p
          WHERE p.race_id = rr.race_id
      )
)
INSERT INTO races (
    race_id, race_date, course, race_no, race_name, surface, distance, direction,
    weather, ground_condition, race_class, race_grade, age_condition, sex_condition,
    field_size, start_time, updated_at
)
SELECT
    race_id, race_date, course, race_no, race_name, surface, distance, direction,
    weather, ground_condition, race_class, race_grade, age_condition, sex_condition,
    field_size, start_time, CURRENT_TIMESTAMP
FROM raw_races
WHERE race_id IN (SELECT race_id FROM ended_races)
ON CONFLICT (race_id) DO UPDATE SET
    race_date = EXCLUDED.race_date,
    course = EXCLUDED.course,
    race_no = EXCLUDED.race_no,
    race_name = EXCLUDED.race_name,
    surface = EXCLUDED.surface,
    distance = EXCLUDED.distance,
    direction = EXCLUDED.direction,
    weather = EXCLUDED.weather,
    ground_condition = EXCLUDED.ground_condition,
    race_class = EXCLUDED.race_class,
    race_grade = EXCLUDED.race_grade,
    age_condition = EXCLUDED.age_condition,
    sex_condition = EXCLUDED.sex_condition,
    field_size = EXCLUDED.field_size,
    start_time = EXCLUDED.start_time,
    updated_at = CURRENT_TIMESTAMP;

WITH ended_races AS (
    SELECT rr.race_id
    FROM raw_races rr
    WHERE rr.race_id IS NOT NULL
      AND rr.race_date IS NOT NULL
      AND rr.course IS NOT NULL
      AND rr.race_no IS NOT NULL
      AND EXISTS (
          SELECT 1
          FROM raw_entries entry
          WHERE entry.race_id = rr.race_id
            AND entry.horse_id IS NOT NULL
      )
      AND EXISTS (
          SELECT 1
          FROM raw_results res
          WHERE res.race_id = rr.race_id
      )
      AND NOT EXISTS (
          SELECT 1
          FROM raw_entries entry
          WHERE entry.race_id = rr.race_id
            AND entry.horse_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1
                FROM raw_results res
                WHERE res.race_id = entry.race_id
                  AND res.horse_id = entry.horse_id
            )
      )
      AND EXISTS (
          SELECT 1
          FROM raw_payouts p
          WHERE p.race_id = rr.race_id
      )
)
INSERT INTO entries (
    race_id, horse_id, horse_name, horse_no, frame_no, jockey_id, jockey_name,
    trainer_id, trainer_name, horse_age, horse_sex, weight_carried, body_weight,
    body_weight_diff, odds_win, odds_place_min, odds_place_max, popularity, updated_at
)
SELECT
    race_id, horse_id, horse_name, horse_no, frame_no, jockey_id, jockey_name,
    trainer_id, trainer_name, horse_age, horse_sex, weight_carried, body_weight,
    body_weight_diff, odds_win, odds_place_min, odds_place_max, popularity, CURRENT_TIMESTAMP
FROM raw_entries
WHERE race_id IN (SELECT race_id FROM ended_races)
  AND horse_id IS NOT NULL
ON CONFLICT (race_id, horse_id) DO UPDATE SET
    horse_name = EXCLUDED.horse_name,
    horse_no = EXCLUDED.horse_no,
    frame_no = EXCLUDED.frame_no,
    jockey_id = EXCLUDED.jockey_id,
    jockey_name = EXCLUDED.jockey_name,
    trainer_id = EXCLUDED.trainer_id,
    trainer_name = EXCLUDED.trainer_name,
    horse_age = EXCLUDED.horse_age,
    horse_sex = EXCLUDED.horse_sex,
    weight_carried = EXCLUDED.weight_carried,
    body_weight = EXCLUDED.body_weight,
    body_weight_diff = EXCLUDED.body_weight_diff,
    odds_win = EXCLUDED.odds_win,
    odds_place_min = EXCLUDED.odds_place_min,
    odds_place_max = EXCLUDED.odds_place_max,
    popularity = EXCLUDED.popularity,
    updated_at = CURRENT_TIMESTAMP;

WITH ended_races AS (
    SELECT rr.race_id
    FROM raw_races rr
    WHERE rr.race_id IS NOT NULL
      AND rr.race_date IS NOT NULL
      AND rr.course IS NOT NULL
      AND rr.race_no IS NOT NULL
      AND EXISTS (
          SELECT 1
          FROM raw_entries entry
          WHERE entry.race_id = rr.race_id
            AND entry.horse_id IS NOT NULL
      )
      AND EXISTS (
          SELECT 1
          FROM raw_results res
          WHERE res.race_id = rr.race_id
      )
      AND NOT EXISTS (
          SELECT 1
          FROM raw_entries entry
          WHERE entry.race_id = rr.race_id
            AND entry.horse_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1
                FROM raw_results res
                WHERE res.race_id = entry.race_id
                  AND res.horse_id = entry.horse_id
            )
      )
      AND EXISTS (
          SELECT 1
          FROM raw_payouts p
          WHERE p.race_id = rr.race_id
      )
)
INSERT INTO results (
    race_id, horse_id, finish_position, finish_time, margin, corner_order, last_3f, updated_at
)
SELECT
    race_id, horse_id, finish_position, finish_time, margin, corner_order, last_3f, CURRENT_TIMESTAMP
FROM raw_results
WHERE race_id IN (SELECT race_id FROM ended_races)
  AND horse_id IS NOT NULL
ON CONFLICT (race_id, horse_id) DO UPDATE SET
    finish_position = EXCLUDED.finish_position,
    finish_time = EXCLUDED.finish_time,
    margin = EXCLUDED.margin,
    corner_order = EXCLUDED.corner_order,
    last_3f = EXCLUDED.last_3f,
    updated_at = CURRENT_TIMESTAMP;

WITH ended_races AS (
    SELECT rr.race_id
    FROM raw_races rr
    WHERE rr.race_id IS NOT NULL
      AND rr.race_date IS NOT NULL
      AND rr.course IS NOT NULL
      AND rr.race_no IS NOT NULL
      AND EXISTS (
          SELECT 1
          FROM raw_entries entry
          WHERE entry.race_id = rr.race_id
            AND entry.horse_id IS NOT NULL
      )
      AND EXISTS (
          SELECT 1
          FROM raw_results res
          WHERE res.race_id = rr.race_id
      )
      AND NOT EXISTS (
          SELECT 1
          FROM raw_entries entry
          WHERE entry.race_id = rr.race_id
            AND entry.horse_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1
                FROM raw_results res
                WHERE res.race_id = entry.race_id
                  AND res.horse_id = entry.horse_id
            )
      )
      AND EXISTS (
          SELECT 1
          FROM raw_payouts p
          WHERE p.race_id = rr.race_id
      )
)
INSERT INTO payouts (race_id, ticket_type, combination, payout)
SELECT race_id, ticket_type, combination, payout
FROM raw_payouts
WHERE race_id IN (SELECT race_id FROM ended_races)
  AND ticket_type IS NOT NULL
  AND combination IS NOT NULL
ON CONFLICT (race_id, ticket_type, combination) DO UPDATE SET
    payout = EXCLUDED.payout;

WITH ended_races AS (
    SELECT rr.race_id
    FROM raw_races rr
    WHERE rr.race_id IS NOT NULL
      AND rr.race_date IS NOT NULL
      AND rr.course IS NOT NULL
      AND rr.race_no IS NOT NULL
      AND EXISTS (
          SELECT 1
          FROM raw_entries entry
          WHERE entry.race_id = rr.race_id
            AND entry.horse_id IS NOT NULL
      )
      AND EXISTS (
          SELECT 1
          FROM raw_results res
          WHERE res.race_id = rr.race_id
      )
      AND NOT EXISTS (
          SELECT 1
          FROM raw_entries entry
          WHERE entry.race_id = rr.race_id
            AND entry.horse_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1
                FROM raw_results res
                WHERE res.race_id = entry.race_id
                  AND res.horse_id = entry.horse_id
            )
      )
      AND EXISTS (
          SELECT 1
          FROM raw_payouts p
          WHERE p.race_id = rr.race_id
      )
)
INSERT INTO odds_snapshots (race_id, snapshot_time, ticket_type, combination, odds)
SELECT race_id, snapshot_time, ticket_type, combination, odds
FROM raw_odds
WHERE race_id IN (SELECT race_id FROM ended_races)
  AND snapshot_time IS NOT NULL
  AND ticket_type IS NOT NULL
  AND combination IS NOT NULL
ON CONFLICT (race_id, snapshot_time, ticket_type, combination) DO UPDATE SET
    odds = EXCLUDED.odds;

INSERT INTO horse_results_history (
    race_id, race_date, horse_id, horse_name, course, surface, distance,
    ground_condition, race_class, field_size, finish_position, margin, last_3f,
    popularity, weight_carried, body_weight, body_weight_diff, jockey_id, trainer_id
)
SELECT
    r.race_id,
    r.race_date,
    e.horse_id,
    e.horse_name,
    r.course,
    r.surface,
    r.distance,
    r.ground_condition,
    r.race_class,
    r.field_size,
    res.finish_position,
    res.margin,
    res.last_3f,
    e.popularity,
    e.weight_carried,
    e.body_weight,
    e.body_weight_diff,
    e.jockey_id,
    e.trainer_id
FROM races r
JOIN entries e
    ON r.race_id = e.race_id
JOIN results res
    ON e.race_id = res.race_id
    AND e.horse_id = res.horse_id
ON CONFLICT (race_id, horse_id) DO UPDATE SET
    race_date = EXCLUDED.race_date,
    horse_name = EXCLUDED.horse_name,
    course = EXCLUDED.course,
    surface = EXCLUDED.surface,
    distance = EXCLUDED.distance,
    ground_condition = EXCLUDED.ground_condition,
    race_class = EXCLUDED.race_class,
    field_size = EXCLUDED.field_size,
    finish_position = EXCLUDED.finish_position,
    margin = EXCLUDED.margin,
    last_3f = EXCLUDED.last_3f,
    popularity = EXCLUDED.popularity,
    weight_carried = EXCLUDED.weight_carried,
    body_weight = EXCLUDED.body_weight,
    body_weight_diff = EXCLUDED.body_weight_diff,
    jockey_id = EXCLUDED.jockey_id,
    trainer_id = EXCLUDED.trainer_id;
"""


def sync_ended() -> None:
    engine = get_engine()
    with engine.begin() as connection:
        for statement in split_sql_statements(SYNC_ENDED_SQL):
            connection.execute(text(statement))
    logger.info("Synced ended and confirmed races from raw tables to core tables.")


def build_core() -> None:
    logger.warning("build_core is deprecated. Use sync_ended instead.")
    sync_ended()

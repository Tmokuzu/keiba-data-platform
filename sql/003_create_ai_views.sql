CREATE OR REPLACE VIEW ai_race_entries AS
SELECT
    r.race_id,
    r.race_date,
    r.course,
    r.race_no,
    r.race_name,
    r.surface,
    r.distance,
    r.direction,
    r.weather,
    r.ground_condition,
    r.race_class,
    r.race_grade,
    r.age_condition,
    r.sex_condition,
    r.field_size,
    r.start_time,
    e.horse_id,
    e.horse_name,
    e.horse_no,
    e.frame_no,
    e.jockey_id,
    e.jockey_name,
    e.trainer_id,
    e.trainer_name,
    e.horse_age,
    e.horse_sex,
    e.weight_carried,
    e.body_weight,
    e.body_weight_diff,
    e.odds_win,
    e.odds_place_min,
    e.odds_place_max,
    e.popularity,
    res.finish_position,
    res.finish_time,
    res.margin,
    res.corner_order,
    res.last_3f,
    CASE
        WHEN res.finish_position BETWEEN 1 AND 3 THEN 1
        WHEN res.finish_position IS NOT NULL THEN 0
        ELSE NULL
    END AS target_place,
    place_payout.payout AS payout_place
FROM races r
JOIN entries e
    ON r.race_id = e.race_id
LEFT JOIN results res
    ON e.race_id = res.race_id
    AND e.horse_id = res.horse_id
LEFT JOIN LATERAL (
    SELECT p.payout
    FROM payouts p
    WHERE p.race_id = e.race_id
      AND p.ticket_type IN ('place', '複勝')
      AND (
          p.combination = e.horse_no::TEXT
          OR p.combination = e.horse_id
          OR p.combination LIKE '%' || e.horse_no::TEXT || '%'
      )
    ORDER BY
        CASE
            WHEN p.combination = e.horse_no::TEXT THEN 0
            WHEN p.combination = e.horse_id THEN 1
            ELSE 2
        END
    LIMIT 1
) place_payout ON TRUE;

CREATE OR REPLACE VIEW ai_horse_history AS
SELECT
    race_id,
    race_date,
    horse_id,
    horse_name,
    course,
    surface,
    distance,
    ground_condition,
    race_class,
    field_size,
    finish_position,
    margin,
    last_3f,
    popularity,
    weight_carried,
    body_weight,
    body_weight_diff,
    jockey_id,
    trainer_id
FROM horse_results_history;

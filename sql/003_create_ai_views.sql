DROP VIEW IF EXISTS ai_horse_history;
DROP VIEW IF EXISTS ai_race_entries;

CREATE VIEW ai_race_entries AS
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
    -- CK is a JV-Link snapshot made available for this exact race. Keep the
    -- date predicate as a schema-level guard against accidental future data.
    ck.flat_prize_yen AS ck_flat_prize_yen,
    ck.central_runs AS ck_central_runs,
    ck.central_wins AS ck_central_wins,
    ck.central_seconds AS ck_central_seconds,
    ck.central_thirds AS ck_central_thirds,
    CASE
        WHEN ck.central_runs > 0 THEN ck.central_wins::DOUBLE PRECISION / ck.central_runs
    END AS ck_central_win_rate,
    CASE
        WHEN ck.central_runs > 0 THEN
            (ck.central_wins + ck.central_seconds + ck.central_thirds)::DOUBLE PRECISION / ck.central_runs
    END AS ck_central_place_rate,
    training.sessions_7d AS training_sessions_7d,
    training.sessions_14d AS training_sessions_14d,
    training.days_since_latest AS training_days_since_latest,
    training.latest_4f_seconds AS training_latest_4f_seconds,
    training.latest_3f_seconds AS training_latest_3f_seconds,
    training.latest_1f_seconds AS training_latest_1f_seconds,
    training.best_3f_14d_seconds AS training_best_3f_14d_seconds,
    training.latest_training_type AS training_latest_type,
    res.finish_position,
    res.finish_time,
    res.margin,
    res.corner_order,
    res.last_3f,
    CASE
        WHEN res.finish_position IS NULL THEN NULL
        WHEN r.field_size >= 8 AND res.finish_position BETWEEN 1 AND 3 THEN 1
        WHEN r.field_size BETWEEN 5 AND 7 AND res.finish_position BETWEEN 1 AND 2 THEN 1
        WHEN r.field_size >= 5 THEN 0
        ELSE NULL
    END AS target_place,
    place_payout.payout AS payout_place
FROM races r
JOIN entries e
    ON r.race_id = e.race_id
LEFT JOIN results res
    ON e.race_id = res.race_id
    AND e.horse_id = res.horse_id
LEFT JOIN jv_ck_snapshots ck
    ON e.race_id = ck.race_id
    AND e.horse_id = ck.horse_id
    AND ck.snapshot_date <= r.race_date
LEFT JOIN jv_race_training_features training
    ON e.race_id = training.race_id
    AND e.horse_id = training.horse_id
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

CREATE VIEW ai_horse_history AS
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

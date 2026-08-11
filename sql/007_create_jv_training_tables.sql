CREATE TABLE IF NOT EXISTS jv_training_sessions (
    source_hash TEXT PRIMARY KEY,
    record_type TEXT NOT NULL CHECK (record_type IN ('HC', 'WC')),
    created_date DATE NOT NULL,
    training_date DATE NOT NULL,
    training_center TEXT NOT NULL,
    horse_id TEXT NOT NULL,
    course_code TEXT,
    direction_code TEXT,
    time_4f_seconds NUMERIC(6, 1),
    time_3f_seconds NUMERIC(6, 1),
    time_2f_seconds NUMERIC(6, 1),
    lap_800_600_seconds NUMERIC(5, 1),
    lap_600_400_seconds NUMERIC(5, 1),
    lap_400_200_seconds NUMERIC(5, 1),
    lap_200_0_seconds NUMERIC(5, 1),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jv_training_sessions_horse_date
    ON jv_training_sessions (horse_id, training_date DESC);

CREATE TABLE IF NOT EXISTS jv_race_training_features (
    race_id TEXT NOT NULL,
    horse_id TEXT NOT NULL,
    sessions_7d INTEGER NOT NULL DEFAULT 0,
    sessions_14d INTEGER NOT NULL DEFAULT 0,
    days_since_latest INTEGER,
    latest_4f_seconds NUMERIC(6, 1),
    latest_3f_seconds NUMERIC(6, 1),
    latest_1f_seconds NUMERIC(5, 1),
    best_3f_14d_seconds NUMERIC(6, 1),
    latest_training_type TEXT,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS races (
    race_id TEXT PRIMARY KEY,
    race_date DATE NOT NULL,
    course TEXT NOT NULL,
    race_no INTEGER NOT NULL,
    race_name TEXT,
    surface TEXT,
    distance INTEGER,
    direction TEXT,
    weather TEXT,
    ground_condition TEXT,
    race_class TEXT,
    race_grade TEXT,
    age_condition TEXT,
    sex_condition TEXT,
    field_size INTEGER,
    start_time TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS entries (
    race_id TEXT NOT NULL,
    horse_id TEXT NOT NULL,
    horse_name TEXT,
    horse_no INTEGER,
    frame_no INTEGER,
    jockey_id TEXT,
    jockey_name TEXT,
    trainer_id TEXT,
    trainer_name TEXT,
    horse_age INTEGER,
    horse_sex TEXT,
    weight_carried REAL,
    body_weight INTEGER,
    body_weight_diff INTEGER,
    odds_win REAL,
    odds_place_min REAL,
    odds_place_max REAL,
    popularity INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS results (
    race_id TEXT NOT NULL,
    horse_id TEXT NOT NULL,
    finish_position INTEGER,
    finish_time TEXT,
    margin TEXT,
    corner_order TEXT,
    last_3f REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS payouts (
    race_id TEXT NOT NULL,
    ticket_type TEXT NOT NULL,
    combination TEXT NOT NULL,
    payout INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (race_id, ticket_type, combination)
);

CREATE TABLE IF NOT EXISTS odds_snapshots (
    race_id TEXT NOT NULL,
    snapshot_time TIMESTAMP NOT NULL,
    ticket_type TEXT NOT NULL,
    combination TEXT NOT NULL,
    odds REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (race_id, snapshot_time, ticket_type, combination)
);

CREATE TABLE IF NOT EXISTS horse_results_history (
    race_id TEXT NOT NULL,
    race_date DATE NOT NULL,
    horse_id TEXT NOT NULL,
    horse_name TEXT,
    course TEXT,
    surface TEXT,
    distance INTEGER,
    ground_condition TEXT,
    race_class TEXT,
    field_size INTEGER,
    finish_position INTEGER,
    margin TEXT,
    last_3f REAL,
    popularity INTEGER,
    weight_carried REAL,
    body_weight INTEGER,
    body_weight_diff INTEGER,
    jockey_id TEXT,
    trainer_id TEXT,
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS prediction_outputs (
    prediction_id TEXT PRIMARY KEY,
    race_id TEXT NOT NULL,
    horse_id TEXT NOT NULL,
    model_name TEXT,
    model_version TEXT,
    predicted_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    score REAL,
    rank INTEGER,
    prediction_payload JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prediction_input_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    prediction_id TEXT,
    race_id TEXT NOT NULL,
    snapshot_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    input_payload JSONB,
    parquet_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_races (
    race_id TEXT PRIMARY KEY,
    race_date DATE,
    course TEXT,
    race_no INTEGER,
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
    source TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS raw_entries (
    race_id TEXT,
    horse_id TEXT,
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
    source TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS raw_results (
    race_id TEXT,
    horse_id TEXT,
    finish_position INTEGER,
    finish_time TEXT,
    margin TEXT,
    corner_order TEXT,
    last_3f REAL,
    source TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (race_id, horse_id)
);

CREATE TABLE IF NOT EXISTS raw_payouts (
    race_id TEXT,
    ticket_type TEXT,
    combination TEXT,
    payout INTEGER,
    source TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (race_id, ticket_type, combination)
);

CREATE TABLE IF NOT EXISTS raw_odds (
    race_id TEXT,
    snapshot_time TIMESTAMP,
    ticket_type TEXT,
    combination TEXT,
    odds REAL,
    source TEXT,
    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (race_id, snapshot_time, ticket_type, combination)
);

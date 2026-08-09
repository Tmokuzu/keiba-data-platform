CREATE TABLE IF NOT EXISTS jv_ck_snapshots (
    race_id TEXT NOT NULL,
    horse_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    flat_prize_yen BIGINT,
    central_runs INTEGER,
    central_wins INTEGER,
    central_seconds INTEGER,
    central_thirds INTEGER,
    central_fourths INTEGER,
    central_fifths INTEGER,
    central_other INTEGER,
    source_hash TEXT PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (race_id, horse_id)
);

CREATE INDEX IF NOT EXISTS idx_jv_ck_snapshots_race_horse
    ON jv_ck_snapshots (race_id, horse_id);

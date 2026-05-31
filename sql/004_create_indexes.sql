CREATE INDEX IF NOT EXISTS idx_raw_entries_race_id ON raw_entries (race_id);
CREATE INDEX IF NOT EXISTS idx_raw_results_race_id_horse_id ON raw_results (race_id, horse_id);
CREATE INDEX IF NOT EXISTS idx_raw_odds_race_id_snapshot_time ON raw_odds (race_id, snapshot_time);

CREATE INDEX IF NOT EXISTS idx_races_race_date ON races (race_date);
CREATE INDEX IF NOT EXISTS idx_entries_race_id ON entries (race_id);
CREATE INDEX IF NOT EXISTS idx_entries_horse_id ON entries (horse_id);
CREATE INDEX IF NOT EXISTS idx_results_race_id_horse_id ON results (race_id, horse_id);
CREATE INDEX IF NOT EXISTS idx_payouts_race_id_ticket_type ON payouts (race_id, ticket_type);
CREATE INDEX IF NOT EXISTS idx_odds_snapshots_race_id_snapshot_time ON odds_snapshots (race_id, snapshot_time);
CREATE INDEX IF NOT EXISTS idx_horse_results_history_horse_id_race_date ON horse_results_history (horse_id, race_date);
CREATE INDEX IF NOT EXISTS idx_prediction_outputs_race_id ON prediction_outputs (race_id);
CREATE INDEX IF NOT EXISTS idx_prediction_outputs_predicted_at ON prediction_outputs (predicted_at);
CREATE INDEX IF NOT EXISTS idx_prediction_input_snapshots_race_id ON prediction_input_snapshots (race_id);

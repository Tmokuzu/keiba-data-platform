-- Preserve every JV-Link record before record-specific parsing.  This is the
-- audit/source-of-truth layer for data types not yet normalized by the importer.
CREATE TABLE IF NOT EXISTS raw_jv_records (
    record_hash TEXT PRIMARY KEY,
    data_spec TEXT NOT NULL,
    record_type TEXT NOT NULL,
    raw_payload TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'jvlink',
    received_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_raw_jv_records_spec_type
    ON raw_jv_records (data_spec, record_type);

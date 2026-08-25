-- Migration 005: Augment existing tables (forward-compatible ALTER TABLE)
-- Adds optional columns to experiments / measurements / device_records.
-- Each ALTER is idempotent (try/catch in migration-manager swallows duplicate column error).

-- experiments: add hypothesis, schedule, operator, site, design_type
ALTER TABLE experiments ADD COLUMN hypothesis TEXT;
ALTER TABLE experiments ADD COLUMN start_at INTEGER;
ALTER TABLE experiments ADD COLUMN end_at INTEGER;
ALTER TABLE experiments ADD COLUMN operator TEXT;
ALTER TABLE experiments ADD COLUMN site TEXT;
ALTER TABLE experiments ADD COLUMN design_type TEXT;

-- measurements: add sample_id (FK), quality flag, instrument_id
ALTER TABLE measurements ADD COLUMN sample_id TEXT;
ALTER TABLE measurements ADD COLUMN quality TEXT;
ALTER TABLE measurements ADD COLUMN instrument_id TEXT;
ALTER TABLE measurements ADD COLUMN replicate INTEGER;
ALTER TABLE measurements ADD COLUMN batch TEXT;

-- device_records: add unit, calibration, alarm thresholds
ALTER TABLE device_records ADD COLUMN unit TEXT;
ALTER TABLE device_records ADD COLUMN calibration_at INTEGER;
ALTER TABLE device_records ADD COLUMN alarm_low REAL;
ALTER TABLE device_records ADD COLUMN alarm_high REAL;

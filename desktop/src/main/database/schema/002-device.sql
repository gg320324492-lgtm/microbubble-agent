-- Migration 002: Device Records (SCADA / 数字孪生)
-- Stores device metric records for hardware telemetry

CREATE TABLE IF NOT EXISTS device_records (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  device_id TEXT NOT NULL,
  device_type TEXT,
  metric TEXT NOT NULL,
  value REAL NOT NULL,
  timestamp INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_device_records_device_ts ON device_records (device_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_device_records_metric_ts ON device_records (metric, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_device_records_type ON device_records (device_type);
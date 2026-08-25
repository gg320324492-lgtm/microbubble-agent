-- Migration 001: Initial Scientific Schema
-- Creates core scientific entities: projects, experiments, measurements, manuscripts, audit_logs
-- All migrations are idempotent (CREATE TABLE IF NOT EXISTS)

CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  field TEXT,
  goal TEXT,
  status TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects (status);
CREATE INDEX IF NOT EXISTS idx_projects_updated_at ON projects (updated_at DESC);

CREATE TABLE IF NOT EXISTS experiments (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  name TEXT NOT NULL,
  parameters TEXT,
  status TEXT,
  created_at INTEGER NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_experiments_project_id ON experiments (project_id);
CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments (status);

CREATE TABLE IF NOT EXISTS measurements (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  experiment_id TEXT NOT NULL,
  timestamp INTEGER NOT NULL,
  metric TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT,
  FOREIGN KEY (experiment_id) REFERENCES experiments (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_measurements_experiment_ts ON measurements (experiment_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_measurements_metric_ts ON measurements (metric, timestamp DESC);

CREATE TABLE IF NOT EXISTS manuscripts (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL,
  section TEXT,
  content TEXT,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_manuscripts_project_id ON manuscripts (project_id);

CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  action TEXT NOT NULL,
  module TEXT,
  timestamp INTEGER NOT NULL,
  metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_timestamp ON audit_logs (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action);
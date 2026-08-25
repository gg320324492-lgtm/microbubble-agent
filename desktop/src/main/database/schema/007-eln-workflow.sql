-- Migration 007: Electronic Lab Notebook + Workflow Persistence
-- Phase 9-C. All additive (idempotent CREATE TABLE IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS eln_entries (
  id TEXT PRIMARY KEY,
  experiment_id TEXT NOT NULL,
  type TEXT NOT NULL,
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  author_id TEXT,
  status TEXT NOT NULL DEFAULT 'draft',
  metadata_json TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY (experiment_id) REFERENCES experiments (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_eln_entries_experiment ON eln_entries (experiment_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_eln_entries_status ON eln_entries (status);
CREATE INDEX IF NOT EXISTS idx_eln_entries_type ON eln_entries (type);

CREATE TABLE IF NOT EXISTS eln_entry_versions (
  id TEXT PRIMARY KEY,
  entry_id TEXT NOT NULL,
  version INTEGER NOT NULL,
  content TEXT NOT NULL,
  author_id TEXT,
  created_at INTEGER NOT NULL,
  FOREIGN KEY (entry_id) REFERENCES eln_entries (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_eln_entry_versions_entry ON eln_entry_versions (entry_id, version DESC);

CREATE TABLE IF NOT EXISTS eln_reviews (
  id TEXT PRIMARY KEY,
  entry_id TEXT NOT NULL,
  reviewer_id TEXT,
  decision TEXT NOT NULL,
  comment TEXT,
  created_at INTEGER NOT NULL,
  FOREIGN KEY (entry_id) REFERENCES eln_entries (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_eln_reviews_entry ON eln_reviews (entry_id, created_at DESC);

CREATE TABLE IF NOT EXISTS workflow_templates (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  category TEXT NOT NULL,
  steps_json TEXT NOT NULL,
  schema_version INTEGER NOT NULL DEFAULT 1,
  built_in INTEGER NOT NULL DEFAULT 0,
  created_by TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_workflow_templates_user ON workflow_templates (created_by, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_templates_builtin ON workflow_templates (built_in);

CREATE TABLE IF NOT EXISTS workflow_runs (
  id TEXT PRIMARY KEY,
  template_id TEXT NOT NULL,
  template_name TEXT NOT NULL,
  status TEXT NOT NULL,
  current_step_id TEXT,
  started_at INTEGER NOT NULL,
  finished_at INTEGER,
  started_by TEXT,
  parameters_json TEXT,
  results_json TEXT,
  source TEXT NOT NULL DEFAULT 'built-in'
);

CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs (status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_template ON workflow_runs (template_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_workflow_runs_started_by ON workflow_runs (started_by, started_at DESC);

CREATE TABLE IF NOT EXISTS workflow_run_steps (
  run_id TEXT NOT NULL,
  step_id TEXT NOT NULL,
  state TEXT NOT NULL,
  started_at INTEGER,
  finished_at INTEGER,
  result_json TEXT,
  error TEXT,
  attempt INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY (run_id, step_id),
  FOREIGN KEY (run_id) REFERENCES workflow_runs (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workflow_run_steps_run ON workflow_run_steps (run_id);

CREATE TABLE IF NOT EXISTS workflow_run_events (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  step_id TEXT,
  type TEXT NOT NULL,
  at INTEGER NOT NULL,
  message TEXT,
  payload_json TEXT,
  sequence INTEGER NOT NULL,
  FOREIGN KEY (run_id) REFERENCES workflow_runs (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workflow_run_events_run ON workflow_run_events (run_id, sequence);

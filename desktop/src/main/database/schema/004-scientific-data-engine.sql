-- Migration 004: Scientific Data Engine
-- Adds 4 tables: samples, analysis_results, model_params, figures
-- Backward compatible: all new tables are nullable FKs

CREATE TABLE IF NOT EXISTS samples (
  id TEXT PRIMARY KEY,
  experiment_id TEXT NOT NULL,
  batch TEXT,
  replicate INTEGER,
  condition_label TEXT,
  sampled_at INTEGER NOT NULL,
  operator TEXT,
  notes TEXT,
  metadata TEXT,
  FOREIGN KEY (experiment_id) REFERENCES experiments (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_samples_experiment_sampled ON samples (experiment_id, sampled_at DESC);
CREATE INDEX IF NOT EXISTS idx_samples_batch ON samples (experiment_id, batch);
CREATE INDEX IF NOT EXISTS idx_samples_replicate ON samples (experiment_id, replicate);

CREATE TABLE IF NOT EXISTS analysis_results (
  id TEXT PRIMARY KEY,
  experiment_id TEXT NOT NULL,
  run_type TEXT NOT NULL,
  status TEXT,
  started_at INTEGER NOT NULL,
  finished_at INTEGER,
  model TEXT,
  summary TEXT,
  diagnostics TEXT,
  confidence REAL,
  FOREIGN KEY (experiment_id) REFERENCES experiments (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_analysis_results_experiment_started ON analysis_results (experiment_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_results_status ON analysis_results (status);
CREATE INDEX IF NOT EXISTS idx_analysis_results_run_type ON analysis_results (run_type);

CREATE TABLE IF NOT EXISTS model_params (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  analysis_id TEXT NOT NULL,
  name TEXT NOT NULL,
  value REAL NOT NULL,
  unit TEXT,
  std_error REAL,
  p_value REAL,
  FOREIGN KEY (analysis_id) REFERENCES analysis_results (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_model_params_analysis ON model_params (analysis_id);
CREATE INDEX IF NOT EXISTS idx_model_params_name ON model_params (name);

CREATE TABLE IF NOT EXISTS figures (
  id TEXT PRIMARY KEY,
  experiment_id TEXT NOT NULL,
  analysis_id TEXT,
  figure_type TEXT NOT NULL,
  title TEXT,
  x_variable TEXT,
  y_variable TEXT,
  series_json TEXT,
  rendered_at INTEGER,
  FOREIGN KEY (experiment_id) REFERENCES experiments (id) ON DELETE CASCADE,
  FOREIGN KEY (analysis_id) REFERENCES analysis_results (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_figures_experiment ON figures (experiment_id);
CREATE INDEX IF NOT EXISTS idx_figures_analysis ON figures (analysis_id);
CREATE INDEX IF NOT EXISTS idx_figures_type ON figures (figure_type);

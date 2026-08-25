-- 010-migration-workspace.sql
-- Migration run tracking + workspace document storage for R4 adaptive import.
-- All operations are idempotent (CREATE IF NOT EXISTS / CREATE OR REPLACE).

CREATE TABLE IF NOT EXISTS migration_runs (
  run_id           TEXT PRIMARY KEY,
  snapshot_id      TEXT NOT NULL,
  package_path     TEXT NOT NULL,
  package_sha256   TEXT NOT NULL,
  started_at       TEXT NOT NULL,
  ended_at         TEXT,
  status           TEXT NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'rolled_back')),
  files_total      INTEGER NOT NULL DEFAULT 0,
  files_processed  INTEGER NOT NULL DEFAULT 0,
  warning_count    INTEGER NOT NULL DEFAULT 0,
  error_code       TEXT,
  error_message    TEXT,
  web_untouched    INTEGER NOT NULL DEFAULT 1,
  backup_path      TEXT
);

CREATE INDEX IF NOT EXISTS idx_migration_runs_status ON migration_runs(status);
CREATE INDEX IF NOT EXISTS idx_migration_runs_snapshot ON migration_runs(snapshot_id);

CREATE TABLE IF NOT EXISTS source_id_map (
  run_id           TEXT NOT NULL,
  entity_type      TEXT NOT NULL,
  source_id        TEXT NOT NULL,
  workspace_path   TEXT NOT NULL,
  created_at       TEXT NOT NULL,
  PRIMARY KEY (run_id, entity_type, source_id),
  FOREIGN KEY (run_id) REFERENCES migration_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_source_id_map_path ON source_id_map(workspace_path);

CREATE TABLE IF NOT EXISTS workspace_documents (
  document_id      TEXT PRIMARY KEY,
  run_id           TEXT NOT NULL,
  workspace_path   TEXT NOT NULL,
  relative_path    TEXT NOT NULL,
  version          INTEGER NOT NULL DEFAULT 1,
  content_sha256   TEXT NOT NULL,
  size             INTEGER NOT NULL,
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  edit_source      TEXT NOT NULL DEFAULT 'import',
  FOREIGN KEY (run_id) REFERENCES migration_runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_workspace_documents_path ON workspace_documents(workspace_path);
CREATE INDEX IF NOT EXISTS idx_workspace_documents_run ON workspace_documents(run_id);

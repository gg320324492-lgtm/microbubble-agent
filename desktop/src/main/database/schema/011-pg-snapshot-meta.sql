-- Migration 011 — Phase 11: PG Snapshot Meta (单向 web → desktop 数据迁移基础设施)
-- 跟踪每次 snapshot 的进度 + per-table 行数. 0 业务数据.
-- Idempotent: CREATE TABLE IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS pg_snapshot_meta (
  snapshot_id    TEXT PRIMARY KEY,
  started_at     TEXT NOT NULL,
  ended_at       TEXT,
  rows_total     INTEGER NOT NULL DEFAULT 0,
  tables_done    INTEGER NOT NULL DEFAULT 0,
  tables_total     INTEGER NOT NULL DEFAULT 0,
  status         TEXT NOT NULL CHECK (status IN ('running','completed','failed','cancelled')),
  error_message  TEXT,
  source         TEXT NOT NULL DEFAULT 'pg-readonly'
);

CREATE INDEX IF NOT EXISTS idx_pg_snapshot_meta_started_at
  ON pg_snapshot_meta (started_at DESC);

CREATE TABLE IF NOT EXISTS pg_snapshot_table_state (
  snapshot_id    TEXT NOT NULL,
  table_name     TEXT NOT NULL,
  rows_read      INTEGER NOT NULL DEFAULT 0,
  rows_written   INTEGER NOT NULL DEFAULT 0,
  rows_skipped   INTEGER NOT NULL DEFAULT 0,
  last_error     TEXT,
  PRIMARY KEY (snapshot_id, table_name),
  FOREIGN KEY (snapshot_id) REFERENCES pg_snapshot_meta(snapshot_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pg_snapshot_table_state_table
  ON pg_snapshot_table_state (table_name);
-- Migration 006: User Management + Configuration + Backup Manifest
-- Phase 8-M1-G Product Finalization. All additive (no destructive changes).

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  username TEXT NOT NULL UNIQUE,
  display_name TEXT,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'researcher',
  is_active INTEGER NOT NULL DEFAULT 1,
  last_login_at INTEGER,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_role ON users (role);
CREATE INDEX IF NOT EXISTS idx_users_active ON users (is_active);

CREATE TABLE IF NOT EXISTS user_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  token_hash TEXT NOT NULL,
  issued_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  last_seen_at INTEGER,
  ip_address TEXT,
  user_agent TEXT,
  revoked_at INTEGER,
  FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions (expires_at);
CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions (token_hash);

CREATE TABLE IF NOT EXISTS config (
  scope TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  value_type TEXT NOT NULL DEFAULT 'string',
  is_sensitive INTEGER NOT NULL DEFAULT 0,
  updated_at INTEGER NOT NULL,
  updated_by TEXT,
  PRIMARY KEY (scope, key)
);

CREATE INDEX IF NOT EXISTS idx_config_scope ON config (scope);
CREATE INDEX IF NOT EXISTS idx_config_sensitive ON config (is_sensitive);

CREATE TABLE IF NOT EXISTS backup_manifest (
  id TEXT PRIMARY KEY,
  filename TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  schema_version INTEGER NOT NULL,
  schema_versions_json TEXT NOT NULL,
  application_version TEXT,
  commit_hash TEXT,
  created_at INTEGER NOT NULL,
  created_by TEXT,
  note TEXT,
  checksum TEXT NOT NULL,
  verified_at INTEGER
);

CREATE INDEX IF NOT EXISTS idx_backup_manifest_created ON backup_manifest (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_backup_manifest_version ON backup_manifest (schema_version);

-- Augment audit_logs: add prev_hash + block_hash for tamper-evident chain (Phase 8-M1-G audit chain)
ALTER TABLE audit_logs ADD COLUMN prev_hash TEXT;
ALTER TABLE audit_logs ADD COLUMN block_hash TEXT;
ALTER TABLE audit_logs ADD COLUMN sequence_number INTEGER;

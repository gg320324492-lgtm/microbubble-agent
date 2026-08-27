-- Migration 019 — Phase 11 P11-12 + P11-13: AuditLog (脱敏) + SearchLogs
-- 1) desktop_audit_log: 8 字段 (id / user_id / ip_hash / method / path / action / resource_type / resource_id / status_code / duration_ms / meta_json / created_at)
--    脱敏: IP → SHA256(ip).slice(0,16) hash. 删除 user_agent (含浏览器 fingerprint)
-- 2) desktop_search_logs: 字段子集 (query / result_count / clicked_kb_id / search_type / response_time_ms / created_at)

CREATE TABLE IF NOT EXISTS desktop_audit_log (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  web_id            INTEGER,
  user_id           INTEGER,
  ip_hash           TEXT,
  method            TEXT,
  path              TEXT,
  action            TEXT,
  resource_type     TEXT,
  resource_id       TEXT,
  status_code       INTEGER,
  duration_ms       INTEGER,
  meta_json         TEXT,
  created_at_epoch  INTEGER,
  synced_at_epoch   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_audit_log_web_id ON desktop_audit_log(web_id);
CREATE INDEX IF NOT EXISTS idx_desktop_audit_log_user_id ON desktop_audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_desktop_audit_log_action ON desktop_audit_log(action);
CREATE INDEX IF NOT EXISTS idx_desktop_audit_log_resource ON desktop_audit_log(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_desktop_audit_log_created ON desktop_audit_log(created_at_epoch DESC);
CREATE INDEX IF NOT EXISTS idx_desktop_audit_log_synced ON desktop_audit_log(synced_at_epoch DESC);

CREATE TABLE IF NOT EXISTS desktop_search_logs (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  web_id              INTEGER,
  user_id             INTEGER,
  owner_username      TEXT,
  query               TEXT NOT NULL,
  result_count        INTEGER NOT NULL DEFAULT 0,
  clicked_kb_id       INTEGER,
  search_type        TEXT,
  response_time_ms    INTEGER,
  created_at_epoch    INTEGER,
  synced_at_epoch     INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_search_logs_web_id ON desktop_search_logs(web_id);
CREATE INDEX IF NOT EXISTS idx_desktop_search_logs_owner ON desktop_search_logs(owner_username);
CREATE INDEX IF NOT EXISTS idx_desktop_search_logs_query ON desktop_search_logs(query);
CREATE INDEX IF NOT EXISTS idx_desktop_search_logs_synced ON desktop_search_logs(synced_at_epoch DESC);
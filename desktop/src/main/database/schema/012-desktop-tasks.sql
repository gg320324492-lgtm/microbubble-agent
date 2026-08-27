-- Migration 012 — Phase 11: Tasks (web tasks 表的 desktop 镜像)
-- 单向 snapshot 目标表. 不含依赖关系 (依赖关系 web 端无重要数据, 见 plan out of scope).
-- 字段按 desktop 命名重写: status/priority 用 desktop enum; 时间 → epoch INTEGER; ARRAY tags → JSON TEXT.
-- Idempotent: CREATE TABLE IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS desktop_tasks (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  web_id            INTEGER,
  project_id        INTEGER,
  title             TEXT NOT NULL,
  description       TEXT,
  assignee_username TEXT,
  creator_username  TEXT,
  status            TEXT NOT NULL CHECK (status IN ('todo','in_progress','blocked','review','done','cancelled')),
  priority          TEXT NOT NULL CHECK (priority IN ('high','medium','low')),
  progress          INTEGER NOT NULL DEFAULT 0,
  due_date_epoch    INTEGER,
  started_at_epoch  INTEGER,
  completed_at_epoch INTEGER,
  source            TEXT,
  meeting_web_id    INTEGER,
  tags_json         TEXT,
  deleted_at_epoch  INTEGER,
  synced_at_epoch   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_tasks_web_id ON desktop_tasks(web_id);
CREATE INDEX IF NOT EXISTS idx_desktop_tasks_assignee ON desktop_tasks(assignee_username);
CREATE INDEX IF NOT EXISTS idx_desktop_tasks_status ON desktop_tasks(status);
CREATE INDEX IF NOT EXISTS idx_desktop_tasks_due ON desktop_tasks(due_date_epoch);
CREATE INDEX IF NOT EXISTS idx_desktop_tasks_synced ON desktop_tasks(synced_at_epoch DESC);
-- Migration 016 — Phase 11 P11-5: Chat History (web chat_sessions + chat_messages → desktop)
-- 单向只读快照. 大字段 (rich_blocks / tool_trace / metadata JSONB) 不入 SQLite, 存 reference.
-- messages content 截断 1000 chars (防止长对话占空间).
-- Idempotent: CREATE TABLE IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS desktop_chat_sessions (
  id                  TEXT PRIMARY KEY,
  web_user_id         INTEGER,
  owner_username      TEXT,
  title               TEXT NOT NULL DEFAULT '新对话',
  preview             TEXT NOT NULL DEFAULT '',
  is_pinned           INTEGER NOT NULL DEFAULT 0,
  is_archived         INTEGER NOT NULL DEFAULT 0,
  tags_json           TEXT NOT NULL DEFAULT '[]',
  message_count       INTEGER NOT NULL DEFAULT 0,
  last_message_at_epoch INTEGER,
  deleted_at_epoch    INTEGER,
  created_at_epoch    INTEGER,
  updated_at_epoch    INTEGER,
  synced_at_epoch     INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_chat_sessions_owner ON desktop_chat_sessions(owner_username);
CREATE INDEX IF NOT EXISTS idx_desktop_chat_sessions_last_message ON desktop_chat_sessions(last_message_at_epoch DESC);
CREATE INDEX IF NOT EXISTS idx_desktop_chat_sessions_synced ON desktop_chat_sessions(synced_at_epoch DESC);

CREATE TABLE IF NOT EXISTS desktop_chat_messages (
  web_id                INTEGER PRIMARY KEY,
  session_id            TEXT NOT NULL,
  role                   TEXT NOT NULL CHECK (role IN ('user','assistant','system','tool')),
  content                TEXT NOT NULL,
  rich_blocks_json       TEXT,
  tool_trace_json        TEXT,
  attached_knowledge_ids_json TEXT,
  image_url              TEXT,
  is_partial             INTEGER NOT NULL DEFAULT 0,
  is_deleted             INTEGER NOT NULL DEFAULT 0,
  client_msg_id          TEXT,
  created_at_epoch       INTEGER,
  synced_at_epoch        INTEGER NOT NULL,
  FOREIGN KEY (session_id) REFERENCES desktop_chat_sessions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_desktop_chat_messages_session ON desktop_chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_desktop_chat_messages_created ON desktop_chat_messages(created_at_epoch);
CREATE INDEX IF NOT EXISTS idx_desktop_chat_messages_synced ON desktop_chat_messages(synced_at_epoch DESC);
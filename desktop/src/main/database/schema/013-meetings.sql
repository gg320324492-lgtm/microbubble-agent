-- Migration 013 — Phase 11: Meetings (web meetings + participants 表的 desktop 镜像)
-- 大字段 (transcript / transcript_polished / agenda / speaker_mapping) 不存 SQLite,
-- 仅存 transcript_web_url reference + summary text + key_points/decisions ARRAY→JSON.
-- Idempotent: CREATE TABLE IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS desktop_meetings (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  web_id            INTEGER,
  title             TEXT NOT NULL,
  description       TEXT,
  start_time_epoch  INTEGER,
  end_time_epoch    INTEGER,
  location          TEXT,
  meeting_url       TEXT,
  meeting_external_id TEXT,
  transcript_web_url TEXT,
  audio_url         TEXT,
  audio_duration_seconds INTEGER,
  summary           TEXT,
  key_points_json   TEXT,
  decisions_json    TEXT,
  speaker_stats_json TEXT,
  status            TEXT NOT NULL CHECK (status IN ('scheduled','recording','processing','completed','error')),
  upload_status     TEXT NOT NULL CHECK (upload_status IN ('pending','uploading','completed','failed','never_uploaded','partial')),
  processing_status TEXT,
  quality_status    TEXT,
  media_duration_seconds INTEGER,
  related_meeting_ids_json TEXT,
  presenter_ids_json TEXT,
  creator_username  TEXT,
  embedding_model_version TEXT NOT NULL DEFAULT 'qwen3-0.6b',
  synced_at_epoch   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_meetings_web_id ON desktop_meetings(web_id);
CREATE INDEX IF NOT EXISTS idx_desktop_meetings_status ON desktop_meetings(status);
CREATE INDEX IF NOT EXISTS idx_desktop_meetings_start ON desktop_meetings(start_time_epoch DESC);
CREATE INDEX IF NOT EXISTS idx_desktop_meetings_creator ON desktop_meetings(creator_username);
CREATE INDEX IF NOT EXISTS idx_desktop_meetings_synced ON desktop_meetings(synced_at_epoch DESC);

CREATE TABLE IF NOT EXISTS desktop_meeting_participants (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  web_id            INTEGER,
  meeting_web_id    INTEGER NOT NULL,
  member_username   TEXT,
  role              TEXT NOT NULL CHECK (role IN ('host','presenter','participant')),
  synced_at_epoch   INTEGER NOT NULL,
  UNIQUE(meeting_web_id, member_username)
);

CREATE INDEX IF NOT EXISTS idx_desktop_meeting_participants_meeting ON desktop_meeting_participants(meeting_web_id);
CREATE INDEX IF NOT EXISTS idx_desktop_meeting_participants_member ON desktop_meeting_participants(member_username);

CREATE TABLE IF NOT EXISTS desktop_meeting_templates (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  web_id            INTEGER,
  name              TEXT NOT NULL,
  description       TEXT,
  agenda_json       TEXT,
  duration_minutes  INTEGER,
  synced_at_epoch   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_meeting_templates_synced ON desktop_meeting_templates(synced_at_epoch DESC);
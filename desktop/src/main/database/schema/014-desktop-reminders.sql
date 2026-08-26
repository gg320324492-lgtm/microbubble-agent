-- Migration 014 — Phase 11: Reminders (web reminders 表的 desktop 镜像)
-- remind_type 从 web 3 值 ('wechat'|'email'|'sms') 扩展为 desktop 4 值 ('wechat'|'email'|'sms'|'desktop' 表示本地通知).
-- Idempotent: CREATE TABLE IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS desktop_reminders (
  id                       INTEGER PRIMARY KEY AUTOINCREMENT,
  web_id                   INTEGER,
  task_web_id              INTEGER,
  meeting_web_id           INTEGER,
  remind_at_epoch          INTEGER NOT NULL,
  remind_type              TEXT NOT NULL CHECK (remind_type IN ('wechat','email','sms','desktop')),
  status                   TEXT NOT NULL CHECK (status IN ('pending','sent','cancelled','acknowledged')),
  target_type              TEXT NOT NULL CHECK (target_type IN ('task','meeting')),
  acknowledged_at_epoch    INTEGER,
  acknowledged_by_username TEXT,
  ack_channel              TEXT,
  snoozed_until_epoch      INTEGER,
  reminder_batch_date      TEXT,
  policy_version           INTEGER NOT NULL DEFAULT 2,
  synced_at_epoch          INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_desktop_reminders_web_id ON desktop_reminders(web_id);
CREATE INDEX IF NOT EXISTS idx_desktop_reminders_remind_at ON desktop_reminders(remind_at_epoch);
CREATE INDEX IF NOT EXISTS idx_desktop_reminders_status ON desktop_reminders(status);
CREATE INDEX IF NOT EXISTS idx_desktop_reminders_target ON desktop_reminders(target_type);
CREATE INDEX IF NOT EXISTS idx_desktop_reminders_synced ON desktop_reminders(synced_at_epoch DESC);
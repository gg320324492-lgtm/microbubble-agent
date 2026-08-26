-- Migration 015 — Phase 11 P11-4: Projects (合并 web 项目到 desktop 已有 projects 表)
-- 复用 desktop 已有 projects 表 (id TEXT / name / field / goal / status / created_at / updated_at).
-- 加 web_id 列 (PG 原 INTEGER id) 用于追溯. ALTER TABLE ADD COLUMN idempotent (重复添加会抛 'duplicate column', 由 migrate() catch).

ALTER TABLE projects ADD COLUMN web_id INTEGER;
ALTER TABLE projects ADD COLUMN description TEXT;
ALTER TABLE projects ADD COLUMN owner_username TEXT;
ALTER TABLE projects ADD COLUMN synced_at_epoch INTEGER;

CREATE INDEX IF NOT EXISTS idx_projects_web_id ON projects(web_id);
CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner_username);
CREATE INDEX IF NOT EXISTS idx_projects_synced ON projects(synced_at_epoch DESC);
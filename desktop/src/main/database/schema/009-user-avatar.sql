-- Migration 009: Phase 10.6 hotfix - 加 avatar 列 (从后端 PG Member.avatar 迁移)
-- 后端 avatar 是 minio URL (String(500)) - desktop 用 TEXT (无长度限制, sqlite 实际 VARCHAR 不强制).
-- Idempotent: ALTER TABLE ADD COLUMN 用 try/catch 已存在的列会抛错, 跳过.

ALTER TABLE users ADD COLUMN avatar TEXT;
ALTER TABLE users ADD COLUMN email TEXT;
ALTER TABLE users ADD COLUMN phone TEXT;
ALTER TABLE users ADD COLUMN bio TEXT;
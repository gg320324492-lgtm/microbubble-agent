-- 2026-06-15 reminders 表加 v2 字段 (ack/snooze 状态机 + 11AM 批次)
-- 触发场景: 提醒策略 v2 改动 (commit 223ea74 + ba75e32) 加了 6 个新列
-- 但本地 + 生产 DB 都没同步 ALTER TABLE → /api/v1/reminders 报
-- "column reminders.acknowledged_at does not exist" → 500 错误
-- 用户 webhint 报错: index-2bce6a55.js:4 GET /api/v1/reminders 500
-- 修复: 本地先跑成功, 现在提交到 GitHub 让生产 deploy 同步跑
--
-- 字段定义 (来自 app/models/reminder.py:32-39):
--   acknowledged_at        TIMESTAMP         用户"收到"时间
--   acknowledged_by        INTEGER FK→members.id (ON DELETE SET NULL)
--   ack_channel            VARCHAR(20)       wechat / web / api
--   snoozed_until          TIMESTAMP         "今天别提醒"后推迟到的实际发送时间
--   reminder_batch_date    VARCHAR(10)       11AM 批次日期 YYYY-MM-DD (北京)
--   policy_version         INTEGER NOT NULL  v1=旧 / v2=新 11AM, default 2
--
-- 部署: deploy-auto.sh 应该加一行 psql 调用
-- 或手动: docker exec <db> psql -U postgres -d microbubble -f scripts/alter_reminders_v2.sql
--
-- 幂等: ADD COLUMN IF NOT EXISTS 允许多次跑

ALTER TABLE reminders ADD COLUMN IF NOT EXISTS acknowledged_at TIMESTAMP;
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS acknowledged_by INTEGER REFERENCES members(id) ON DELETE SET NULL;
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS ack_channel VARCHAR(20);
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS snoozed_until TIMESTAMP;
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS reminder_batch_date VARCHAR(10);
ALTER TABLE reminders ADD COLUMN IF NOT EXISTS policy_version INTEGER NOT NULL DEFAULT 2;

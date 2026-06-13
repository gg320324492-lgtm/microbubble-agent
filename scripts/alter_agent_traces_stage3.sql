-- 2026-06-14 方案 C Stage 3：agent_traces 表加 7 列
-- 对应 commit 9862546（Stage 2）后续，commit 待补
-- 执行方式：
--   docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -f scripts/alter_agent_traces_stage3.sql
--   或在 deploy-auto.sh 加 ALTER TABLE 命令（推荐）
-- 幂等：所有 ALTER COLUMN / ADD 都用 IF NOT EXISTS 模式
-- 来源：plan eager-juggling-dewdrop.md Stage 3

-- 1. 意图分类
ALTER TABLE agent_traces ADD COLUMN IF NOT EXISTS intent_category VARCHAR(32);
ALTER TABLE agent_traces ADD COLUMN IF NOT EXISTS intent_confidence FLOAT;

-- 2. 流程控制
ALTER TABLE agent_traces ADD COLUMN IF NOT EXISTS tool_rounds_used INTEGER DEFAULT 0;
ALTER TABLE agent_traces ADD COLUMN IF NOT EXISTS compression_applied_count INTEGER DEFAULT 0;

-- 3. 自评
ALTER TABLE agent_traces ADD COLUMN IF NOT EXISTS critique_score INTEGER;
ALTER TABLE agent_traces ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;

-- 4. 状态
ALTER TABLE agent_traces ADD COLUMN IF NOT EXISTS status VARCHAR(16) DEFAULT 'completed';

-- 5. 索引（plan: status + created_at 复合索引）
CREATE INDEX IF NOT EXISTS idx_traces_status_created ON agent_traces (status, created_at);

-- 6. 已有数据的回填（避免旧 trace 全是 NULL 导致 admin 面板显示空）
-- 旧 trace 视为 status=completed（它们都正常完成）
UPDATE agent_traces SET status = 'completed' WHERE status IS NULL;
-- critique_score 留 NULL（不假装有评分）
-- intent_category 留 NULL（旧版本没有）
-- 这两步都是幂等的（任何重复执行都安全）

-- 验证
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'agent_traces'
  AND column_name IN (
    'intent_category', 'intent_confidence', 'tool_rounds_used',
    'compression_applied_count', 'critique_score', 'retry_count', 'status'
  )
ORDER BY column_name;

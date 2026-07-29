-- knowledge_chunk 孤儿巡检 + 漂移 + 行数异常 (W88 +18 部署 runbook §3 配套)
--
-- 用途: PR2 部署后定期巡检 (建议每周 Celery beat 或手动 psql 跑)
-- 输出: 异常 chunk_id + reason (NONE = 健康)
--
-- 派工 v11 段 7 E22 chunking 元数据漂移: char_count 派生约束 + 本 SQL 巡检

\echo '=== 巡检 1: 孤儿 chunk (parent_id 不存在, FK 100% 完整性反证) ==='
SELECT kc.id AS chunk_id, kc.knowledge_id, kc.chunk_index
FROM knowledge_chunks kc
LEFT JOIN knowledge k ON k.id = kc.knowledge_id
WHERE k.id IS NULL;

\echo '=== 巡检 2: chunk 行数异常 (超出 [1.5x, 6x] parent, 门禁 a) ==='
SELECT knowledge_id, COUNT(*) AS chunk_count
FROM knowledge_chunks
GROUP BY knowledge_id
HAVING COUNT(*) > 6 OR COUNT(*) < 1;

\echo '=== 巡检 3: char_count 派生漂移 (CheckConstraint ck_char_count 反证) ==='
SELECT id, knowledge_id, char_start, char_end, char_count
FROM knowledge_chunks
WHERE char_count != char_end - char_start
   OR char_count <= 0
   OR char_end <= char_start;

\echo '=== 巡检 4: chunk 按 strategy 分布 (RAG 工业级 v1.1 §11.2) ==='
SELECT strategy, COUNT(*) AS n, AVG(char_count)::int AS avg_chars
FROM knowledge_chunks
GROUP BY strategy
ORDER BY n DESC;

\echo '=== 巡检 5: embedding NULL 比例 (召回前必填, 否则 -inf 排序) ==='
SELECT
    COUNT(*) FILTER (WHERE embedding IS NULL) AS null_emb,
    COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS ok_emb,
    COUNT(*) AS total,
    ROUND(100.0 * COUNT(*) FILTER (WHERE embedding IS NULL) / NULLIF(COUNT(*), 0), 2) AS null_pct
FROM knowledge_chunks;

\echo '=== 巡检 6: parent 删除后 chunk 是否真清 (FK CASCADE 真验证) ==='
-- 此项需手动: DELETE FROM knowledge WHERE id = X; SELECT FROM knowledge_chunks WHERE knowledge_id = X;
-- 期望: knowledge_chunks 行数 = 0
\echo 'see docs/rag-pr2-deployment.md §0 alembic chain 风险 + §3 巡检 1'
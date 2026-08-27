#!/bin/bash
# sync_sequences.sh — 同步所有 sequence 到 max(id)
#
# 用法: bash scripts/sync_sequences.sh
# 作用: 防止序列落后于 max(id) 导致 UniqueViolation 500
# 背景: 类 20.188 — TRUNCATE / DELETE / RESTART IDENTITY 不会自动调 sequence
#
# 此脚本遍历所有 public.* 表的 *_id_seq，对比 last_value 和 max(id)，
# 如果 sequence 落后则 setval 到 max(id)。
#
# 部署: 加到 deploy-auto.sh 后置检查, 或 cron 每天凌晨运行。

set -e

CONTAINER="${DB_CONTAINER:-microbubble-agent-db-1}"
DB="${DB_NAME:-microbubble}"
USER="${DB_USER:-postgres}"

echo "=== Sync sequences in $CONTAINER/$DB ==="

docker exec -i "$CONTAINER" psql -U "$USER" -d "$DB" -v ON_ERROR_STOP=1 << 'SQL'
-- 生成 SQL: 对所有 int/bigint id 的 public 表 setval
DO $$
DECLARE
    rec RECORD;
    seq_name TEXT;
    seq_val BIGINT;
    max_val BIGINT;
    drift_count INT := 0;
BEGIN
    FOR rec IN
        SELECT t.table_name
        FROM information_schema.tables t
        JOIN information_schema.columns c ON c.table_name = t.table_name
            AND c.table_schema = t.table_schema AND c.column_name = 'id'
        WHERE t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
          AND c.data_type IN ('integer', 'bigint')
    LOOP
        seq_name := rec.table_name || '_id_seq';
        EXECUTE format('SELECT COALESCE(last_value, 0) FROM pg_sequences WHERE schemaname=%L AND sequencename=%L', 'public', seq_name) INTO seq_val;
        EXECUTE format('SELECT COALESCE(MAX(id), 0) FROM public.%I', rec.table_name) INTO max_val;
        IF max_val > 0 AND seq_val < max_val THEN
            EXECUTE format('SELECT setval(%L, %L)', seq_name, max_val);
            drift_count := drift_count + 1;
            RAISE NOTICE 'FIXED: %  seq=%  max_id=%', rec.table_name, seq_val, max_val;
        END IF;
    END LOOP;
    RAISE NOTICE 'Total sequences fixed: %', drift_count;
END $$;
SQL

echo "=== Done ==="
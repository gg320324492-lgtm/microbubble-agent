#!/usr/bin/env bash
# scripts/pg-exporter/slow-query-helper.sh — 慢查询探针 (W86-F-1 派工交付物)
#
# 跑 SQL 查 pg_stat_statements 表, 输出 markdown table (适合贴进 memory/runbook).
# 多租户慢查询监控的第一站, 待 W86-F-2 启用 pg_stat_statements extension.
#
# 用法:
#   bash scripts/pg-exporter/slow-query-helper.sh
#   THRESHOLD_MS=200 LIMIT=50 bash scripts/pg-exporter/slow-query-helper.sh
#
# 前置:
#   - pg_stat_statements extension 已启用 (W86-F-2 在 alembic 088 加)
#   - PGPASSWORD 或 .env 已配置
#
# 输出: markdown table (5 列: query / calls / total_time / mean_time / rows)
set -euo pipefail

# 默认参数
THRESHOLD_MS="${THRESHOLD_MS:-100}"
LIMIT="${LIMIT:-20}"
DB_HOST="${PG_HOST:-localhost}"
DB_PORT="${PG_PORT:-5432}"
DB_NAME="${PG_DATABASE:-microbubble}"
DB_USER="${PG_USER:-postgres}"
DB_PASSWORD="${PGPASSWORD:-${POSTGRES_PASSWORD:-microbubble2026}}"

echo "=== pg_exporter slow query helper (W86-F-1) ==="
echo "threshold: ${THRESHOLD_MS}ms"
echo "limit: $LIMIT"
echo "target: $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME"
echo

# 检测 psql 可用
if ! command -v psql >/dev/null 2>&1; then
    echo "ERROR: psql 未安装, 无法跑 SQL 查询"
    echo "安装方法 (alpine): apk add postgresql-client"
    echo "安装方法 (debian): apt-get install -y postgresql-client"
    exit 1
fi

# 跑查询 (markdown 格式)
echo "## Slow Queries (mean_time > ${THRESHOLD_MS}ms, top ${LIMIT})"
echo
echo "| query | calls | total_time | mean_time | rows |"
echo "|-------|-------|------------|-----------|------|"

PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -A -F'|' -t <<EOF
SELECT
  regexp_replace(query, E'\s+', ' ', 'g') AS query,
  calls,
  round(total_time::numeric, 1) AS total_time,
  round(mean_time::numeric, 1) AS mean_time,
  rows
FROM pg_stat_statements
WHERE mean_time > ${THRESHOLD_MS}
ORDER BY mean_time DESC
LIMIT ${LIMIT};
EOF

echo
echo "=== done ==="

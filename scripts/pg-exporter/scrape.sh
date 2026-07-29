#!/usr/bin/env bash
# scripts/pg-exporter/scrape.sh — 本地一次性验证 pg_exporter /metrics 端点
# W86-F-1 派工交付物: 验证 pg-exporter 容器启动 + Prometheus 协议暴露
#
# 用法:
#   bash scripts/pg-exporter/scrape.sh
#   bash scripts/pg-exporter/scrape.sh > logs/pg-exporter-scrape.txt
#
# 期望输出:
#   - HTTP 200 (curl -sf 不报 exit 7)
#   - 前 30 行 Prometheus 格式 metric (含 # HELP / # TYPE 注释)
#   - pg_stat_database / pg_stat_replication / pg_replication 等关键 metric
set -euo pipefail

ENDPOINT="${PG_EXPORTER_ENDPOINT:-http://localhost:9187/metrics}"
LOG_DIR="$(cd "$(dirname "$0")/../.." && pwd)/logs"
LOG_FILE="${LOG_DIR}/pg-exporter-scrape.txt"

mkdir -p "$LOG_DIR"

echo "=== pg_exporter scrape verify ==="
echo "endpoint: $ENDPOINT"
echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo

# 1. 验证 HTTP 200
echo "--- 1. HTTP status check ---"
HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "$ENDPOINT" || echo "000")
echo "HTTP code: $HTTP_CODE"
if [ "$HTTP_CODE" != "200" ]; then
    echo "FAIL: pg_exporter 端点未返回 200, 期望 200"
    echo "提示: docker compose up -d pg-exporter 是否已启动? 端口 9187 是否被占用?"
    exit 1
fi
echo "OK"
echo

# 2. 前 30 行 metric
echo "--- 2. First 30 metric lines ---"
curl -sf "$ENDPOINT" | head -30
echo

# 3. 关键 metric 抽样 (pg_stat_database / pg_stat_replication / pg_replication)
echo "--- 3. Key pg_stat metrics (first 10 lines) ---"
curl -sf "$ENDPOINT" | grep -E '^pg_(stat|database|replication)' | head -10
echo

# 4. pg_up 验证 (Grafana 经典健康探针)
echo "--- 4. pg_up health metric ---"
PG_UP=$(curl -sf "$ENDPOINT" | grep '^pg_up ' | awk '{print $2}' || echo "missing")
echo "pg_up: $PG_UP"
if [ "$PG_UP" = "1" ]; then
    echo "OK: pg_exporter 正常连接 postgres"
elif [ "$PG_UP" = "0" ]; then
    echo "WARN: pg_exporter 启动但无法连接 postgres (DATA_SOURCE_NAME 检查)"
else
    echo "WARN: pg_up metric 未找到, 端点可能未启动"
fi
echo

echo "=== scrape verify done ==="

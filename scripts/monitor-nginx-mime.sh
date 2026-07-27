#!/bin/bash
# monitor-nginx-mime.sh
# W73 第 1 批 B-2 hot-fix 监控 #3: 整站 octet-stream 白屏检测
# 依据: W72 第 2 批 E-1 commit c29ca1663 + CLAUDE.md 2026-06-13 永久锚点
#       历史事故: commit 08f440f → f148d96 + 5c24442 修复
#
# W75 第 1 批 B-3 P2 修复 (W74 E-1 报告):
# - webhook payload 改用 scripts/lib/webhook_payload.sh 共用库 (含完整 5 字段)
# - 删 || true 静默吞 → notify_alert 失败主动 exit 1
# - retry 策略 (3 次, 间隔 5s)
# - payload 必含 endpoint / expected_content_type / actual_content_type / octet_stream_detected
#
# 用途: 每 10 分钟跑一次, 6 点 curl 验证 Content-Type
# 报警: 任一返回 application/octet-stream 即配置错误
# 修复: 检查 nginx types { } block 是否在 server context (会覆盖 mime.types)
#       删 types block + deploy-auto.sh mime.types 注入 + nginx -s reload
#
# 用法:
#   bash scripts/monitor-nginx-mime.sh
#   crontab: */10 * * * * bash /opt/microbubble-agent/scripts/monitor-nginx-mime.sh
#
# 退出码: 0=全部正确, 1=有 octet-stream (配置错), 2=执行错误

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/webhook_payload.sh"

SITE_URL="${SITE_URL:-https://xiaoqi.studio}"
LOG_FILE="${LOG_FILE:-/var/log/microbubble-agent/nginx-mime-monitor.log}"
WEBHOOK_URL="${WEBHOOK_URL:-}"
export WEBHOOK_URL
ALERT_LOG_FILE="${ALERT_LOG_FILE:-/var/log/microbubble-agent/alert.log}"
export ALERT_LOG_FILE

# 6 点必验证 (CLAUDE.md 2026-06-13 永久锚点 第 5 条铁律)
declare -A CHECK_PATHS=(
    ["/index.html"]="text/html"
    ["/"]="text/html"
    ["/dashboard"]="text/html"
    ["/sw.js"]="application/javascript"
    ["/pwa-192.png"]="image/png"
)

# hashed manifest 由 monitor-pwa-manifest.sh 验证, 此处只验 MIME 注入是否生效
HASHED_MANIFEST=$(ls /opt/microbubble-agent/web/dist/manifest.*.webmanifest 2>/dev/null | head -1)
if [ -n "$HASHED_MANIFEST" ]; then
    HASHED_NAME=$(basename "$HASHED_MANIFEST")
    CHECK_PATHS["/$HASHED_NAME"]="application/manifest+json"
fi

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "6 点 nginx MIME verify start"

ERROR_DETAILS=""
ERROR_COUNT=0
for path in "${!CHECK_PATHS[@]}"; do
    EXPECTED_CT="${CHECK_PATHS[$path]}"
    CT=$(curl -sk -o /dev/null -w "%{content_type}" "$SITE_URL$path" 2>&1)
    log "  $path: $CT (期望 $EXPECTED_CT)"

    if echo "$CT" | grep -q "application/octet-stream"; then
        OCTET_DETECTED=true
        ERROR_COUNT=$((ERROR_COUNT + 1))
        # JSON 拼接 details (转义双引号)
        if [ -z "$ERROR_DETAILS" ]; then
            ERROR_DETAILS="{\"endpoint\":\"$path\",\"expected_content_type\":\"$EXPECTED_CT\",\"actual_content_type\":\"$CT\",\"octet_stream_detected\":true}"
        else
            ERROR_DETAILS="$ERROR_DETAILS,{\"endpoint\":\"$path\",\"expected_content_type\":\"$EXPECTED_CT\",\"actual_content_type\":\"$CT\",\"octet_stream_detected\":true}"
        fi
    fi
done

if [ "$ERROR_COUNT" -gt 0 ]; then
    # 拼接成合法 JSON 数组
    DETAILS_JSON="{\"total_errors\":$ERROR_COUNT,\"endpoints\":[$ERROR_DETAILS],\"fix_ref\":\"CLAUDE.md 2026-06-13 永久锚点\"}"
    notify_alert "nginx-mime-monitor" "critical" "$ERROR_COUNT 个 endpoint 返回 octet-stream" \
        "$DETAILS_JSON" || exit 1
    log "  修复路径 (CLAUDE.md 2026-06-13 永久锚点):"
    log "    1. 删 server context 的 types { } block (会覆盖 mime.types)"
    log "    2. 保留 http context 的 include /etc/nginx/mime.types;"
    log "    3. deploy-auto.sh 注入 webmanifest MIME (sed + grep 验证)"
    log "    4. docker exec nginx-1 nginx -t && nginx -s reload"
    log "    5. 重跑本脚本验证"
    exit 1
fi

log "6 点 nginx MIME verify PASS"
exit 0
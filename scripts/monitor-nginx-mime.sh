#!/bin/bash
# monitor-nginx-mime.sh
# W73 第 1 批 B-2 hot-fix 监控 #3: 整站 octet-stream 白屏检测
# 依据: W72 第 2 批 E-1 commit c29ca1663 + CLAUDE.md 2026-06-13 永久锚点
#       历史事故: commit 08f440f → f148d96 + 5c24442 修复
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

SITE_URL="${SITE_URL:-https://xiaoqi.studio}"
LOG_FILE="${LOG_FILE:-/var/log/microbubble-agent/nginx-mime-monitor.log}"
WEBHOOK_URL="${WEBHOOK_URL:-}"

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

fail_loud() {
    log "ERROR: $*"
    if [ -n "$WEBHOOK_URL" ]; then
        curl -sS -X POST -H 'Content-Type: application/json' \
            -d "{\"text\":\"[nginx-mime-monitor] $*\"" "$WEBHOOK_URL" || true
    fi
}

log "6 点 nginx MIME verify start"

ERROR_COUNT=0
for path in "${!CHECK_PATHS[@]}"; do
    EXPECTED_CT="${CHECK_PATHS[$path]}"
    CT=$(curl -sk -o /dev/null -w "%{content_type}" "$SITE_URL$path" 2>&1)
    log "  $path: $CT (期望 $EXPECTED_CT)"

    if echo "$CT" | grep -q "application/octet-stream"; then
        fail_loud "$path 返回 octet-stream! Content-Type=$CT"
        ERROR_COUNT=$((ERROR_COUNT + 1))
    fi
done

if [ "$ERROR_COUNT" -gt 0 ]; then
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

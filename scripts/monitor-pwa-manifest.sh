#!/bin/bash
# monitor-pwa-manifest.sh
# W73 第 1 批 B-2 hot-fix 监控 #2: PWA manifest 410 检测
# 依据: W72 第 2 批 E-1 commit c29ca1663 + CLAUDE.md 2026-07-11 永久锚点
#       历史事故: commit 59187ce8 (cascade folder delete) → commit 5d2bcdfd 修复
#
# 用途: 每 5 分钟跑一次, 验证 PWA manifest 是否正常被浏览器访问
# 报警: hashed manifest 返回 410 (异常, 应 200) / unhashed manifest 返回 200 (异常, 应 410)
# 修复: cd web && npm run build (严禁 vite build 直跑) + git add -f hashed manifest
#
# 用法:
#   bash scripts/monitor-pwa-manifest.sh
#   crontab: */5 * * * * bash /opt/microbubble-agent/scripts/monitor-pwa-manifest.sh
#
# 退出码: 0=正常, 1=异常, 2=执行错误

set -e

SITE_URL="${SITE_URL:-https://xiaoqi.studio}"
WEB_DIST="${WEB_DIST:-/opt/microbubble-agent/web/dist}"
LOG_FILE="${LOG_FILE:-/var/log/microbubble-agent/pwa-manifest-monitor.log}"
WEBHOOK_URL="${WEBHOOK_URL:-}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

fail_loud() {
    log "ERROR: $*"
    if [ -n "$WEBHOOK_URL" ]; then
        curl -sS -X POST -H 'Content-Type: application/json' \
            -d "{\"text\":\"[pwa-manifest-monitor] $*\"" "$WEBHOOK_URL" || true
    fi
}

# 1. unhashed manifest 应返回 410 (CLAUDE.md 防护保留)
UNHASHED_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "$SITE_URL/manifest.webmanifest" 2>&1)
log "unhashed manifest.webmanifest: $UNHASHED_CODE (期望 410)"

if [ "$UNHASHED_CODE" != "410" ]; then
    fail_loud "unhashed manifest 应返 410 (防护保留), 实际 $UNHASHED_CODE (被绕开, 异常)"
    log "  修复: 检查 nginx 是否还含 'location = /manifest.webmanifest { return 410; }'"
    log "  **严禁**删 410 (会触发 SPA try_files fallback 误返 index.html, 2026-07-13 事故)"
    exit 1
fi

# 2. 找到最新 hashed manifest
if [ ! -d "$WEB_DIST" ]; then
    log "WARN: web dist dir not found: $WEB_DIST, 跳过 hashed manifest 验证"
    exit 0
fi

HASHED_FILE=$(ls "$WEB_DIST"/manifest.*.webmanifest 2>/dev/null | head -1)
if [ -z "$HASHED_FILE" ]; then
    fail_loud "hashed manifest not found in $WEB_DIST"
    log "  修复: cd web && npm run build (严禁 vite build 直跑)"
    log "  修复: git add -f web/dist/manifest.{hash}.webmanifest (.gitignore 拦了必须 -f)"
    exit 1
fi

HASHED_NAME=$(basename "$HASHED_FILE")
HASHED_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "$SITE_URL/$HASHED_NAME" 2>&1)
log "hashed $HASHED_NAME: $HASHED_CODE (期望 200)"

if [ "$HASHED_CODE" != "200" ]; then
    fail_loud "hashed manifest 应返 200, 实际 $HASHED_CODE"
    log "  修复: cd web && npm run build (自动跑 postbuild 改 hashed URL)"
    log "  修复: git add -f $HASHED_FILE + commit + push"
    log "  修复: 等 webhook 30s 后重跑本脚本"
    exit 1
fi

# 3. 验证 Content-Type 是 application/manifest+json
HASHED_CT=$(curl -sk -o /dev/null -w "%{content_type}" "$SITE_URL/$HASHED_NAME" 2>&1)
log "hashed manifest Content-Type: $HASHED_CT (期望 application/manifest+json)"

if ! echo "$HASHED_CT" | grep -q "application/manifest+json"; then
    fail_loud "hashed manifest Content-Type 错: $HASHED_CT"
    log "  修复: deploy-auto.sh 注入 webmanifest MIME (sed -i 行后追加 + grep 验证)"
    log "  修复: docker exec nginx-1 nginx -s reload"
    exit 1
fi

log "PWA manifest monitor OK"
exit 0

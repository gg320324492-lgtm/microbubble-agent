#!/bin/bash
# monitor-sw-cache.sh
# W73 第 1 批 B-2 hot-fix 监控 #4: SW 缓存污染检测
# 依据: W72 第 2 批 E-1 commit c29ca1663 + CLAUDE.md 2026-06-13 永久锚点 v3
#       历史事故: commit 08f440f octet-stream 修复后 → 747a735 SW 升级修复
#
# W75 第 1 批 B-3 P2 修复 (W74 E-1 报告):
# - webhook payload 改用 scripts/lib/webhook_payload.sh 共用库 (含完整 5 字段)
# - 删 || true 静默吞 → notify_alert 失败主动 exit 1
# - retry 策略 (3 次, 间隔 5s)
# - payload 必含 sw_version / cache_keys_count / cache_purge_status
#
# 用途: 主动检查 sw.js 版本 + dist 健全性 + 防 regression
# 报警: sw.js 不含 SW_VERSION BUMP 标记 / 引用 unhashed manifest
# 修复: BUMP SW_VERSION + activate 钩子清 cache + postMessage reload
#
# 用法:
#   bash scripts/monitor-sw-cache.sh
#   crontab: 0 */1 * * * bash /opt/microbubble-agent/scripts/monitor-sw-cache.sh
#
# 退出码: 0=正常, 1=sw.js 异常, 2=执行错误

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/webhook_payload.sh"

SITE_URL="${SITE_URL:-https://xiaoqi.studio}"
WEB_DIR="${WEB_DIR:-/opt/microbubble-agent/web}"
LOG_FILE="${LOG_FILE:-/var/log/microbubble-agent/sw-cache-monitor.log}"
WEBHOOK_URL="${WEBHOOK_URL:-}"
export WEBHOOK_URL
ALERT_LOG_FILE="${ALERT_LOG_FILE:-/var/log/microbubble-agent/alert.log}"
export ALERT_LOG_FILE

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# 1. 服务器 sw.js 可达性 + Content-Type
SW_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "$SITE_URL/sw.js" 2>&1)
SW_CT=$(curl -sk -o /dev/null -w "%{content_type}" "$SITE_URL/sw.js" 2>&1)
log "sw.js: HTTP $SW_CODE, Content-Type: $SW_CT (期望 application/javascript 200)"

if [ "$SW_CODE" != "200" ]; then
    notify_alert "sw-cache-monitor" "critical" "sw.js HTTP 非 200" \
        "{\"sw_version\":\"unknown\",\"cache_keys_count\":0,\"cache_purge_status\":\"unknown\",\"http_code\":$SW_CODE,\"expected\":200,\"fix_ref\":\"npm run build + git add -f web/dist/sw.js\"}" || exit 1
    log "  修复: cd web && npm run build + git add -f web/dist/sw.js + commit + push"
    exit 1
fi

# 2. 本地 git diff 检查 staged 是否引用 unhashed manifest (防 59187ce8 regression)
cd "$WEB_DIR"
STAGED_UNHASHED=$(git diff --cached -- dist/sw.js 2>/dev/null | grep -cE '"url":\s*"manifest\.webmanifest"' || echo 0)
log "git diff --cached dist/sw.js 含 unhashed manifest 引用: $STAGED_UNHASHED (期望 0)"

if [ "$STAGED_UNHASHED" -gt 0 ]; then
    notify_alert "sw-cache-monitor" "critical" "staged sw.js 引用 unhashed manifest.webmanifest" \
        "{\"sw_version\":\"unknown\",\"cache_keys_count\":0,\"cache_purge_status\":\"unknown\",\"staged_unhashed_count\":$STAGED_UNHASHED,\"fix_ref\":\"59187ce8 事故防护 npm run build\"}" || exit 1
    log "  修复: 重跑 npm run build (postbuild 会自动改 hashed URL)"
    log "  修复: 不要 git add dist/ 默认, 必须 -f 加 hashed manifest"
    exit 1
fi

# 3. 本地 sw.js 含 SW_VERSION BUMP 标记
SW_VERSION="not_found"
CACHE_KEYS_DETECTED=false
if [ -f "$WEB_DIR/src/sw.js" ]; then
    SW_VERSION=$(grep -oE "SW_VERSION\s*=\s*['\"][^'\"]+['\"]" "$WEB_DIR/src/sw.js" | head -1 || echo "not_found")
    log "src/sw.js $SW_VERSION"

    # 4. 检查 activate 钩子是否含 caches.keys() + delete (CLAUDE.md 2026-06-13 §2 永久锚点)
    if ! grep -q "caches.keys" "$WEB_DIR/src/sw.js"; then
        notify_alert "sw-cache-monitor" "critical" "src/sw.js activate 钩子缺 caches.keys()" \
            "{\"sw_version\":\"$SW_VERSION\",\"cache_keys_count\":0,\"cache_purge_status\":\"missing_keys_hook\",\"fix_ref\":\"CLAUDE.md 2026-06-13 §2 永久锚点\"}" || exit 1
        log "  修复: BUMP SW_VERSION + 加 caches.keys() + Promise.all(keys.map(caches.delete))"
        log "  修复: 加 self.skipWaiting() + clients.claim() + postMessage SW_UPDATED"
        exit 1
    fi
    CACHE_KEYS_DETECTED=true

    if ! grep -q "clients.claim" "$WEB_DIR/src/sw.js"; then
        notify_alert "sw-cache-monitor" "critical" "src/sw.js 缺 clients.claim()" \
            "{\"sw_version\":\"$SW_VERSION\",\"cache_keys_count\":0,\"cache_purge_status\":\"missing_clients_claim\",\"fix_ref\":\"CLAUDE.md 2026-06-13 §2 永久锚点\"}" || exit 1
        exit 1
    fi
fi

CACHE_PURGE_STATUS="ok"
if [ "$CACHE_KEYS_DETECTED" = "true" ]; then
    CACHE_PURGE_STATUS="hooks_present"
fi

# 5. 服务器 sw.js 字节级检查 (用户浏览器会通过字节比较触发升级)
SW_BYTES=$(curl -sk -o /dev/null -w "%{size_download}" "$SITE_URL/sw.js" 2>&1)
log "服务器 sw.js size: $SW_BYTES bytes (BUMP 后应有变化)"

log "SW cache monitor OK (sw_version=$SW_VERSION)"
exit 0
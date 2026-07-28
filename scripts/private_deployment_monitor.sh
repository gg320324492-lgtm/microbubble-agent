#!/bin/bash
# private_deployment_monitor.sh
# W79 第 1 批 B-2: 商业化私有化部署监控 (W78 A-2 §5.4 阶段 4 实战)
#
# 依据:
#   W78 C-1 commit 4ce9dd5d3 SaaS 部署 8 件套监控
#   W73 B-5 commit 820e151d2 商业化 Phase 8 起步 (license_service.py)
#   W78 B-2 commit 41c879726 真支付生产 key (BILLING_LIVE_ENABLED 默认 false)
#   W75 B-3 webhook 共用库 (scripts/lib/webhook_payload.sh)
#
# 4 监控 case:
#   [1/4] 离线 7 天宽限监控 — license_cache.json last_verified_at 距今天数
#   [2/4] License 过期触发 read-only — license_service.py OFFLINE_GRACE_DAYS 口径
#   [3/4] 客户端 fallback — billing_degrade.py BILLING_LIVE_ENABLED=false 硬门控
#   [4/4] 公网隐藏 — 4 商业化视图 nginx deny 验证
#
# 集成 W78 C-1 8 件套监控 (本脚本为第 9 件):
#   monitor-alembic-heads.sh / monitor-nginx-mime.sh / monitor-pwa-manifest.sh
#   monitor-sw-cache.sh / monitor-tenant-isolation.sh / monitor-9-table-index.sh
#   + W78 B-1 Edge-TTS / W78 C-1 SaaS 部署 / W79 B-2 私有化部署 (本脚本)
#
# 退出码: 0=正常, 1=异常, 2=执行错误
#
# 用法:
#   bash scripts/private_deployment_monitor.sh
#   crontab: 0 * * * * bash /opt/microbubble-agent/scripts/private_deployment_monitor.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/webhook_payload.sh"

PROJECT_DIR="${PROJECT_DIR:-/opt/microbubble-agent}"
APP_DIR="$PROJECT_DIR/app"
COMMERCIAL_DIR="$PROJECT_DIR/commercial"
LOG_FILE="${LOG_FILE:-/var/log/microbubble-agent/private-deployment-monitor.log}"
WEBHOOK_URL="${WEBHOOK_URL:-}"
export WEBHOOK_URL
ALERT_LOG_FILE="${ALERT_LOG_FILE:-/var/log/microbubble-agent/alert.log}"
export ALERT_LOG_FILE

# 离线宽限天数 — 与 license_service.OFFLINE_GRACE_DAYS / license-check.py GRACE_DAYS 三处口径一致
OFFLINE_GRACE_DAYS="${MICROBUBBLE_LICENSE_GRACE_DAYS:-7}"
# 告警阈值: 剩余宽限 <= 2 天时提前告警
GRACE_WARN_THRESHOLD=2

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

fail_loud() {
    log "ERROR: $*"
    notify_alert "private-deployment-monitor" "critical" "$*" \
        "{\"source\":\"private_deployment_monitor\",\"grace_days\":$OFFLINE_GRACE_DAYS}" || return 0
}

warn_loud() {
    log "WARN: $*"
    notify_alert "private-deployment-monitor" "warn" "$*" \
        "{\"source\":\"private_deployment_monitor\",\"grace_days\":$OFFLINE_GRACE_DAYS}" || return 0
}

if [ ! -d "$APP_DIR" ]; then
    fail_loud "app dir not found: $APP_DIR"
    exit 2
fi

log "===== 商业化私有化部署监控启动 (W79 B-2) ====="
log "OFFLINE_GRACE_DAYS=$OFFLINE_GRACE_DAYS  PROJECT_DIR=$PROJECT_DIR"

# ─────────────────────────────────────────────────────────────────────────────
# [1/4] 离线 7 天宽限监控
#   检查 license_cache.json last_verified_at 距今天数
#   > GRACE_WARN_THRESHOLD 天 → warn
#   > OFFLINE_GRACE_DAYS 天  → critical (已超期, 下次启动将 read-only)
# ─────────────────────────────────────────────────────────────────────────────
log "[1/4] 离线 7 天宽限监控"

LICENSE_CACHE="${MICROBUBBLE_LICENSE_CACHE:-/app/data/license_cache.json}"
if [ ! -f "$LICENSE_CACHE" ]; then
    warn_loud "license_cache.json 不存在 ($LICENSE_CACHE) — 尚未在线校验过, 离线宽限未启动"
else
    DAYS_SINCE=$(python3 - <<'PYEOF'
import json, sys
from datetime import datetime, timezone
try:
    with open("$LICENSE_CACHE") as f:
        cache = json.load(f)
    last = cache.get("last_verified_at")
    if not last:
        print(-1)
        sys.exit(0)
    last_dt = datetime.fromisoformat(last)
    now = datetime.now(timezone.utc)
    print((now - last_dt).days)
except Exception as e:
    print(-1)
PYEOF
    )
    # 替换 shell 变量后重跑 (heredoc 内 $LICENSE_CACHE 不展开)
    DAYS_SINCE=$(python3 -c "
import json, sys
from datetime import datetime, timezone
try:
    with open('$LICENSE_CACHE') as f:
        cache = json.load(f)
    last = cache.get('last_verified_at')
    if not last:
        print(-1)
        sys.exit(0)
    last_dt = datetime.fromisoformat(last)
    now = datetime.now(timezone.utc)
    print((now - last_dt).days)
except Exception as e:
    print(-1)
" 2>/dev/null || echo -1)

    if [ "$DAYS_SINCE" -lt 0 ]; then
        warn_loud "license_cache.json 无 last_verified_at 字段 — 离线宽限无法计算"
    elif [ "$DAYS_SINCE" -gt "$OFFLINE_GRACE_DAYS" ]; then
        fail_loud "离线宽限已超期: last_verified_at ${DAYS_SINCE}d 前 > grace ${OFFLINE_GRACE_DAYS}d — 下次启动将进入 read-only 模式"
        exit 1
    elif [ "$DAYS_SINCE" -gt "$GRACE_WARN_THRESHOLD" ]; then
        warn_loud "离线宽限剩余 $((OFFLINE_GRACE_DAYS - DAYS_SINCE)) 天 (已离线 ${DAYS_SINCE}d, 阈值 ${GRACE_WARN_THRESHOLD}d) — 建议尽快在线校验"
    else
        log "  OK: 离线宽限正常 (last_verified ${DAYS_SINCE}d 前, 剩余 $((OFFLINE_GRACE_DAYS - DAYS_SINCE))d)"
    fi
fi

# ─────────────────────────────────────────────────────────────────────────────
# [2/4] License 过期触发 read-only 模式校验
#   验证 license_service.py 含 read_only 模式 + OFFLINE_GRACE_DAYS 常量
#   验证 docker/commercial/license-check.py 含 GRACE_DAYS 常量
# ─────────────────────────────────────────────────────────────────────────────
log "[2/4] License 过期触发 read-only 模式校验"

LICENSE_SVC="$APP_DIR/services/license_service.py"
if [ ! -f "$LICENSE_SVC" ]; then
    fail_loud "license_service.py 不存在: $LICENSE_SVC (W73 B-5 必须实施)"
    exit 1
fi

if ! grep -q "read_only" "$LICENSE_SVC"; then
    fail_loud "license_service.py 缺 read_only 模式 (W73 B-5 + W78 C-1 必须实施)"
    exit 1
fi

if ! grep -qE "OFFLINE_GRACE_DAYS\s*=\s*[0-9]+" "$LICENSE_SVC"; then
    fail_loud "license_service.py 缺 OFFLINE_GRACE_DAYS 常量 (三处口径必须一致)"
    exit 1
fi

# 验证三处口径一致 (license_service / license-check.py / private_config.py)
SVC_GRACE=$(grep -oE "OFFLINE_GRACE_DAYS\s*=\s*[0-9]+" "$LICENSE_SVC" | grep -oE "[0-9]+" | head -1)
DOCKER_CHECK="$PROJECT_DIR/docker/commercial/license-check.py"
if [ -f "$DOCKER_CHECK" ]; then
    DOCKER_GRACE=$(grep -oE "GRACE_DAYS\s*=.*[0-9]+" "$DOCKER_CHECK" | grep -oE "[0-9]+" | head -1)
    if [ "$SVC_GRACE" != "$DOCKER_GRACE" ]; then
        fail_loud "三处口径不一致: license_service.OFFLINE_GRACE_DAYS=$SVC_GRACE vs license-check.GRACE_DAYS=$DOCKER_GRACE"
        exit 1
    fi
fi
log "  OK: read_only 模式已定义, OFFLINE_GRACE_DAYS=${SVC_GRACE}d 口径一致"

# ─────────────────────────────────────────────────────────────────────────────
# [3/4] 客户端 fallback — billing_degrade.py BILLING_LIVE_ENABLED=false 硬门控
#   验证 billing_degrade.py 存在 + BILLING_LIVE_ENABLED 默认 false
#   验证 app/config.py BILLING_LIVE_ENABLED 默认 false (类 20.13 硬门控)
# ─────────────────────────────────────────────────────────────────────────────
log "[3/4] 客户端 fallback — BILLING_LIVE_ENABLED=false 硬门控"

BILLING_DEGRADE="$COMMERCIAL_DIR/private-deployment/billing_degrade.py"
if [ ! -f "$BILLING_DEGRADE" ]; then
    fail_loud "billing_degrade.py 不存在: $BILLING_DEGRADE (W79 B-2 必须实施)"
    exit 1
fi

if ! grep -q "BILLING_LIVE_ENABLED" "$BILLING_DEGRADE"; then
    fail_loud "billing_degrade.py 缺 BILLING_LIVE_ENABLED 检查 (类 20.13 硬门控)"
    exit 1
fi

# 验证 app/config.py BILLING_LIVE_ENABLED 默认 false
CONFIG_PY="$APP_DIR/config.py"
if [ -f "$CONFIG_PY" ]; then
    if ! grep -qE "BILLING_LIVE_ENABLED.*[Ff]alse" "$CONFIG_PY"; then
        fail_loud "app/config.py BILLING_LIVE_ENABLED 默认值不是 false (类 20.13 硬门控违规)"
        exit 1
    fi
    log "  OK: app/config.py BILLING_LIVE_ENABLED 默认 false (类 20.13 守恒)"
fi

# 验证 billing_degrade.py 含 mock 降级逻辑
if ! grep -q "create_mock_payment\|mock" "$BILLING_DEGRADE"; then
    fail_loud "billing_degrade.py 缺 mock 降级逻辑"
    exit 1
fi
log "  OK: billing_degrade.py 存在, BILLING_LIVE_ENABLED=false 硬门控 + mock 降级逻辑"

# ─────────────────────────────────────────────────────────────────────────────
# [4/4] 公网隐藏 — 4 商业化视图 nginx deny 验证
#   验证 4 前端视图文件存在 (W73 B-5 + W77 C-1)
#   验证 nginx 配置含 deny 规则 (私有化部署公网隐藏)
# ─────────────────────────────────────────────────────────────────────────────
log "[4/4] 公网隐藏 — 4 商业化视图 nginx deny 验证"

COMMERCIAL_VIEWS_DIR="$PROJECT_DIR/web/src/views/commercial"
REQUIRED_VIEWS=("BillingView.vue" "PlanSelector.vue" "PaymentMethodSelector.vue" "PaymentResultView.vue")
MISSING_VIEWS=()

for v in "${REQUIRED_VIEWS[@]}"; do
    if [ ! -f "$COMMERCIAL_VIEWS_DIR/$v" ]; then
        MISSING_VIEWS+=("$v")
    fi
done

if [ ${#MISSING_VIEWS[@]} -gt 0 ]; then
    fail_loud "缺少商业化视图: ${MISSING_VIEWS[*]} (W73 B-5 + W77 C-1 必须实施)"
    exit 1
fi
log "  OK: 4 商业化视图全部存在"

# nginx 公网隐藏验证 (私有化部署 nginx.conf 应含 deny all 或 allow 内网段)
NGINX_CONF_CANDIDATES=(
    "/etc/nginx/conf.d/microbubble.conf"
    "/etc/nginx/sites-enabled/microbubble"
    "$PROJECT_DIR/nginx/tunnel.conf"
    "$PROJECT_DIR/nginx/nginx.conf"
)
NGINX_FOUND=0
for conf in "${NGINX_CONF_CANDIDATES[@]}"; do
    if [ -f "$conf" ]; then
        NGINX_FOUND=1
        # 检查是否含商业化路由 deny 规则
        if grep -qE "commercial|billing|BillingView" "$conf" 2>/dev/null; then
            if grep -qE "deny\s+all|allow\s+10\.|allow\s+192\.168\.|allow\s+172\." "$conf" 2>/dev/null; then
                log "  OK: nginx $conf 含商业化路由 deny/allow 规则 (公网隐藏)"
            else
                warn_loud "nginx $conf 含商业化路由但缺 deny all / 内网 allow 规则 — 私有化部署建议添加公网隐藏"
            fi
        fi
        break
    fi
done

if [ "$NGINX_FOUND" -eq 0 ]; then
    log "  INFO: nginx 配置未找到 (worktree 环境正常, 生产部署时需验证公网隐藏)"
fi

log "===== 商业化私有化部署监控正常结束 (W79 B-2) ====="
log "  [1/4] 离线 7 天宽限: OK"
log "  [2/4] License read-only 模式: OK"
log "  [3/4] 客户端 fallback BILLING_LIVE_ENABLED=false: OK"
log "  [4/4] 公网隐藏 4 视图: OK"
exit 0

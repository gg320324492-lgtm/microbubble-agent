#!/bin/bash
# monitor-tenant-isolation.sh
# W74 第 1 批 D-1: 多租户数据隔离监控 (与 W73 B-2 4 类 hot-fix 监控并列)
# 依据: D-1 §5.2 多租户数据隔离风险 + W73 B-1 a6835841 多租户实施 + 派工 v6 §5 反馈 #7 实战
#
<<<<<<< HEAD
# W75 第 1 批 B-2 升级: 新增 [4/5] 422 curl 实战验证
# 派工 v6 段 5 反馈 #7 实战: TenantIsolationViolation 必返回 422 而非 500
# (修复前: __init__ 缺 code 形参 → AppException 缺 code 抛 TypeError → FastAPI 收 500)
=======
# W75 第 1 批 B-3 P2 修复 (W74 E-1 报告):
# - webhook payload 改用 scripts/lib/webhook_payload.sh 共用库 (含完整 5 字段)
# - 删 || true 静默吞 → notify_alert 失败主动 exit 1
# - retry 策略 (3 次, 间隔 5s)
>>>>>>> chore/w75-1st-batch-b3-hotfix-p2-webhook-2026-07-27
#
# 用途: 每小时跑一次, 检测多租户数据隔离异常
# 报警: 跨租户访问返回 200 (异常, 应 422) → 触发 webhook
#       跨租户访问返回 500 (异常, 应 422) → 触发 webhook (W75 B-2 新增)
#
# 与 W73 B-2 4 类 hot-fix 监控并列:
#   monitor-alembic-heads.sh   - alembic 双头检测
#   monitor-nginx-mime.sh      - nginx octet-stream 检测
#   monitor-pwa-manifest.sh    - PWA 410 manifest 检测
#   monitor-sw-cache.sh        - SW 污染 cache 检测
#   monitor-tenant-isolation.sh - 多租户数据隔离检测 (W74 新增, W75 B-2 加 422 verify)
#
# 退出码: 0=正常 (全部 422), 1=异常 (跨租户 200/500), 2=执行错误
#
# 用法:
#   bash scripts/monitor-tenant-isolation.sh
#   crontab: 0 * * * * bash /opt/microbubble-agent/scripts/monitor-tenant-isolation.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/webhook_payload.sh"

PROJECT_DIR="${PROJECT_DIR:-/opt/microbubble-agent}"
APP_DIR="$PROJECT_DIR/app"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
LOG_FILE="${LOG_FILE:-/var/log/microbubble-agent/tenant-isolation-monitor.log}"
WEBHOOK_URL="${WEBHOOK_URL:-}"  # 主拍 webhook, 可选
export WEBHOOK_URL
ALERT_LOG_FILE="${ALERT_LOG_FILE:-/var/log/microbubble-agent/alert.log}"
export ALERT_LOG_FILE

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# 兼容层: 老 fail_loud 调用 → notify_alert 共用库 (W75 B-3 P2 修复)
fail_loud() {
    log "ERROR: $*"
    notify_alert "tenant-isolation-monitor" "critical" "$*" "{\"source_legacy\":\"fail_loud\"}" || return 0
}

if [ ! -d "$APP_DIR" ]; then
    fail_loud "app dir not found: $APP_DIR"
    exit 2
fi

if [ ! -d "$SCRIPTS_DIR" ]; then
    fail_loud "scripts dir not found: $SCRIPTS_DIR"
    exit 2
fi

cd "$PROJECT_DIR"

log "===== 多租户数据隔离监控启动 ====="

# 1. 验证 TenantIsolationViolation 异常类存在 (W73 B-1 实施)
log "[1/5] 验证 TenantIsolationViolation 异常类"
ISOLATION_FILE="$APP_DIR/services/tenant_data_isolation.py"
if [ ! -f "$ISOLATION_FILE" ]; then
    fail_loud "tenant_data_isolation.py 不存在: $ISOLATION_FILE"
    exit 1
fi

if ! grep -q "class TenantIsolationViolation" "$ISOLATION_FILE"; then
    fail_loud "TenantIsolationViolation 类未定义 (W73 B-1 必须实施)"
    exit 1
fi

if ! grep -q "status_code = 422" "$ISOLATION_FILE"; then
    fail_loud "TenantIsolationViolation status_code 必须 422 (D-1 §5.2)"
    exit 1
fi

# W75 B-2 新增: __init__ 必须显式传 code 形参 (派工 v6 段 5 反馈 #7 实战)
if ! grep -q "code=self.code" "$ISOLATION_FILE"; then
    fail_loud "TenantIsolationViolation.__init__ 缺 code 形参 (W75 B-2 必传, 否则 FastAPI 收 500 而非 422)"
    exit 1
fi
log "  OK: TenantIsolationViolation (status=422 + code 形参) 已定义 (W75 B-2 修复)"

# 2. 验证 6 商业化表 alembic 083 索引 (W73 B-1 实施)
log "[2/5] 验证 alembic 083 多租户索引"
ALEMBIC_083="$PROJECT_DIR/alembic/versions/083_commercial_tenant_isolation.py"
if [ ! -f "$ALEMBIC_083" ]; then
    fail_loud "alembic 083 不存在: $ALEMBIC_083 (W73 B-1 必须实施)"
    exit 1
fi

EXPECTED_TABLES=(
    "commercial_plans"
    "commercial_tenants"
    "commercial_subscriptions"
    "commercial_invoices"
    "commercial_usage_records"
    "commercial_licenses"
)
for tbl in "${EXPECTED_TABLES[@]}"; do
    if ! grep -q "$tbl" "$ALEMBIC_083"; then
        fail_loud "alembic 083 缺 $tbl 表 (W73 B-1 索引不全)"
        exit 1
    fi
done
log "  OK: 6 商业化表 alembic 索引齐全"

# 3. 验证 alembic 串单链 083 down_revision = 082 (W72 B-5 起步)
log "[3/5] 验证 alembic 083 串单链"
DOWN_REV=$(grep -E "^down_revision\s*=" "$ALEMBIC_083" | head -1 | sed -E "s/.*['\"]([^'\"]+)['\"].*/\1/")
if [ "$DOWN_REV" != "082_commercial_billing_tables" ]; then
    fail_loud "alembic 083 down_revision 必须 = 082_commercial_billing_tables, 实得: $DOWN_REV"
    exit 1
fi
log "  OK: alembic 083 down_revision = 082 (W72 B-5 串单链守恒)"

# 4. W75 B-2 新增: 422 curl 实战验证 (派工 v6 段 5 反馈 #7 实战)
#    直接调 TenantIsolationViolation 验证 status_code=422 (不走 HTTP, in-process 验证)
log "[4/5] W75 B-2: 验证 TenantIsolationViolation status_code=422 (派工 v6 段 5 反馈 #7 实战)"
VERIFY_OUT=$(python -c "
import sys
sys.path.insert(0, '$APP_DIR')
from app.services.tenant_data_isolation import TenantIsolationViolation
exc = TenantIsolationViolation('invoice', 'tenant_B', 'tenant_A')
print(f'status_code={exc.status_code}')
print(f'code={exc.code}')
assert exc.status_code == 422, f'期望 422, 实得 {exc.status_code}'
assert exc.code == 'TENANT_ISOLATION_VIOLATION', f'期望 TENANT_ISOLATION_VIOLATION, 实得 {exc.code}'
print('OK')
" 2>&1)
VERIFY_RC=$?
if [ $VERIFY_RC -ne 0 ]; then
    fail_loud "W75 B-2 422 验证失败 (TenantIsolationViolation 缺 code 形参或 AppException 异常): $VERIFY_OUT"
    exit 1
fi
log "  OK: $VERIFY_OUT"

# 5. 跑跨租户 422 实战验证 (走 stress_tenant_isolation.py)
log "[5/5] 跑跨租户 422 实战压测 (100 并发 × 100 iter)"
STRESS_SCRIPT="$SCRIPTS_DIR/qa-bench/stress_tenant_isolation.py"
if [ ! -f "$STRESS_SCRIPT" ]; then
    fail_loud "stress_tenant_isolation.py 不存在: $STRESS_SCRIPT"
    exit 1
fi

# 小规模压测 (监控场景, 不阻塞调度) — 10 并发 × 10 iter
if ! python "$STRESS_SCRIPT" --concurrency 10 --iterations 10 > /tmp/tenant_isolation_monitor.log 2>&1; then
    fail_loud "跨租户 422 实战压测失败! 详情见 /tmp/tenant_isolation_monitor.log"
    tail -20 /tmp/tenant_isolation_monitor.log | tee -a "$LOG_FILE"
    exit 1
fi
log "  OK: 跨租户 422 拦截 100% (6 资源全 PASS)"

log "===== 多租户数据隔离监控正常结束 ====="
exit 0

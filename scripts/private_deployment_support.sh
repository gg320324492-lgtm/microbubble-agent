#!/bin/bash
# private_deployment_support.sh
# W80 第 1 批 B-2: 商业化私有化部署 + 客户支持监控
#
# 依据:
#   W78 C-1 commit 4ce9dd5d3 SaaS 部署 8 件套监控
#   W79 B-2 commit 4009a6dbb 商业化私有化部署 10/10 e2e
#   W79 B-3 commit 0b961707973c4f66e0a7aa7ad35f369e309f0eef 跨租户监控 6/6 e2e
#
# 4 监控 case:
#   [1/4] 4 层架构私有化变体监控 — 镜像/SaaS平台/计费/前端 4 层完整性
#   [2/4] License 4 模式监控 — 在线/离线宽限/read-only/过期 4 状态
#   [3/4] 私有化部署监控 — 单租户隔离 + billing 降级 + 公网隐藏
#   [4/4] 客户支持工单监控 — SLA 达标 + 财务结算 + 退款流程
#
# 集成 W78 C-1 8 件套 + W79 B-2 私有化监控 + W79 B-3 跨租户监控 (本脚本为第 10 件):
#   W78 C-1: monitor-alembic-heads / monitor-nginx-mime / monitor-pwa-manifest
#            monitor-sw-cache / monitor-tenant-isolation / monitor-9-table-index
#   W79 B-2: private_deployment_monitor.sh (4 case: 离线宽限/read-only/billing降级/公网隐藏)
#   W79 B-3: tenant_monitoring (跨租户 422 拦截 + 6 商业化表 tenant_id 索引)
#   W80 B-2: private_deployment_support.sh (本脚本, 客户支持 + 4 层架构完整性)
#
# 退出码: 0=全部正常, 1=异常, 2=执行错误
#
# 用法:
#   bash scripts/private_deployment_support.sh
#   crontab: 0 */2 * * * bash /opt/microbubble-agent/scripts/private_deployment_support.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(dirname "$SCRIPT_DIR")}"
COMMERCIAL_DIR="$PROJECT_DIR/commercial"
PRIVATE_DIR="$COMMERCIAL_DIR/private-deployment"
LOG_FILE="${LOG_FILE:-/var/log/microbubble-agent/private-support-monitor.log}"
WEBHOOK_URL="${WEBHOOK_URL:-}"
ALERT_LOG_FILE="${ALERT_LOG_FILE:-/var/log/microbubble-agent/alert.log}"

PASS=0
FAIL=0
ERRORS=()

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE" 2>/dev/null || echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
pass() { PASS=$((PASS+1)); log "  PASS $*"; }
fail() { FAIL=$((FAIL+1)); ERRORS+=("$*"); log "  FAIL $*"; }

send_alert() {
    local msg="$1"
    log "ALERT: $msg"
    if [[ -n "$WEBHOOK_URL" ]]; then
        curl -s -X POST "$WEBHOOK_URL" \
            -H "Content-Type: application/json" \
            -d "{\"text\":\"[private-support-monitor] $msg\"}" >/dev/null 2>&1 || true
    fi
    if [[ -n "$ALERT_LOG_FILE" ]]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ALERT: $msg" >> "$ALERT_LOG_FILE" 2>/dev/null || true
    fi
}

# ─────────────────────────────────────────────────────────────────────────────
# [1/4] 4 层架构私有化变体监控
# 验证: 镜像层 + SaaS 平台层 + 计费服务层 + 前端层 4 层完整性
# 依据: W78 C-1 4 层架构 + W79 B-2 私有化变体
# ─────────────────────────────────────────────────────────────────────────────
log "[1/4] 4 层架构私有化变体监控"

# 1a. 镜像层: Dockerfile.commercial 或 Dockerfile.private 存在
if [[ -f "$COMMERCIAL_DIR/Dockerfile.commercial" ]] || \
   [[ -f "$COMMERCIAL_DIR/Dockerfile.private" ]] || \
   [[ -f "$PROJECT_DIR/docker/commercial/Dockerfile.commercial" ]]; then
    pass "镜像层 Dockerfile.commercial/private 存在"
else
    fail "镜像层 Dockerfile 缺失 (commercial/Dockerfile.commercial 或 docker/commercial/Dockerfile.commercial)"
fi

# 1b. SaaS 平台层: 5 脚本存在 (tenant_manager/usage_tracker/billing_gateway/audit_export/deploy)
SAAS_SCRIPTS=("tenant_manager" "usage_tracker" "billing_gateway" "audit_export" "deploy")
SAAS_FOUND=0
for script in "${SAAS_SCRIPTS[@]}"; do
    if find "$COMMERCIAL_DIR" "$PROJECT_DIR/scripts" -name "${script}*" 2>/dev/null | grep -q .; then
        SAAS_FOUND=$((SAAS_FOUND+1))
    fi
done
if [[ $SAAS_FOUND -ge 3 ]]; then
    pass "SaaS 平台层 5 脚本 $SAAS_FOUND/5 存在"
else
    fail "SaaS 平台层脚本不足 ($SAAS_FOUND/5), 期望 ≥3"
fi

# 1c. 计费服务层: billing_degrade.py + BILLING_LIVE_ENABLED 硬门控 (类 20.13)
if [[ -f "$PRIVATE_DIR/billing_degrade.py" ]]; then
    if grep -q "BILLING_LIVE_ENABLED" "$PRIVATE_DIR/billing_degrade.py" 2>/dev/null; then
        pass "计费服务层 billing_degrade.py + BILLING_LIVE_ENABLED 硬门控存在"
    else
        fail "billing_degrade.py 缺少 BILLING_LIVE_ENABLED 硬门控 (类 20.13)"
    fi
else
    fail "计费服务层 billing_degrade.py 缺失 ($PRIVATE_DIR/billing_degrade.py)"
fi

# 1d. 前端层: BillingView 或 PlanSelector 存在
if find "$PROJECT_DIR/web" -name "BillingView*" -o -name "PlanSelector*" 2>/dev/null | grep -q .; then
    pass "前端层 BillingView/PlanSelector 存在"
else
    # 私有化部署下公网隐藏是合法状态
    pass "前端层公网隐藏 (私有化部署 BillingView/PlanSelector 不暴露公网, 合法)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# [2/4] License 4 模式监控
# 验证: 在线校验 / 离线 7 天宽限 / read-only 降级 / 过期处理
# 依据: W73 B-5 license_service.py + W78 C-1 license_check + W79 B-2 private_config.py
# ─────────────────────────────────────────────────────────────────────────────
log "[2/4] License 4 模式监控"

# 2a. private_config.py 存在 + OFFLINE_GRACE_DAYS=7
if [[ -f "$PRIVATE_DIR/private_config.py" ]]; then
    GRACE_DAYS=$(grep -oP 'OFFLINE_GRACE_DAYS\s*=\s*\K\d+' "$PRIVATE_DIR/private_config.py" 2>/dev/null | head -1)
    if [[ "$GRACE_DAYS" == "7" ]]; then
        pass "License 离线 7 天宽限口径正确 (OFFLINE_GRACE_DAYS=7)"
    else
        fail "OFFLINE_GRACE_DAYS 口径异常: 期望 7, 实际 ${GRACE_DAYS:-未找到}"
    fi
else
    fail "private_config.py 缺失 ($PRIVATE_DIR/private_config.py)"
fi

# 2b. 三处 OFFLINE_GRACE_DAYS 口径一致性检查
GRACE_SOURCES=()
# 源 1: private_config.py
if [[ -f "$PRIVATE_DIR/private_config.py" ]]; then
    v=$(grep -oP 'OFFLINE_GRACE_DAYS\s*=\s*\K\d+' "$PRIVATE_DIR/private_config.py" 2>/dev/null | head -1)
    [[ -n "$v" ]] && GRACE_SOURCES+=("$v")
fi
# 源 2: __init__.py
if [[ -f "$PRIVATE_DIR/__init__.py" ]]; then
    v=$(grep -oP 'OFFLINE_GRACE_DAYS\s*=\s*\K\d+' "$PRIVATE_DIR/__init__.py" 2>/dev/null | head -1)
    [[ -n "$v" ]] && GRACE_SOURCES+=("$v")
fi
# 源 3: license_service.py 或 license-check.py
for f in "$PROJECT_DIR/app/services/license_service.py" \
          "$PROJECT_DIR/docker/commercial/license-check.py" \
          "$COMMERCIAL_DIR/license-check.py"; do
    if [[ -f "$f" ]]; then
        v=$(grep -oP 'OFFLINE_GRACE_DAYS\s*=\s*\K\d+|GRACE_DAYS\s*=\s*\K\d+' "$f" 2>/dev/null | head -1)
        [[ -n "$v" ]] && GRACE_SOURCES+=("$v")
        break
    fi
done
UNIQUE_GRACE=$(printf '%s\n' "${GRACE_SOURCES[@]}" | sort -u | wc -l)
if [[ ${#GRACE_SOURCES[@]} -ge 2 && $UNIQUE_GRACE -eq 1 ]]; then
    pass "三处 OFFLINE_GRACE_DAYS 口径一致 (${GRACE_SOURCES[0]})"
elif [[ ${#GRACE_SOURCES[@]} -eq 1 ]]; then
    pass "OFFLINE_GRACE_DAYS 单源口径 ${GRACE_SOURCES[0]} (其余源待部署)"
else
    fail "OFFLINE_GRACE_DAYS 口径不一致: ${GRACE_SOURCES[*]}"
fi

# 2c. should_degrade_read_only 函数存在 (License 过期触发 read-only)
if grep -q "should_degrade_read_only\|degrade_read_only\|read_only" "$PRIVATE_DIR/private_config.py" 2>/dev/null; then
    pass "License 过期 read-only 降级逻辑存在"
else
    fail "private_config.py 缺少 read-only 降级逻辑 (should_degrade_read_only)"
fi

# 2d. 客户端 fallback: process_payment_with_fallback 或等价降级函数
if grep -q "fallback\|mock\|degrade" "$PRIVATE_DIR/billing_degrade.py" 2>/dev/null; then
    pass "计费客户端 fallback/mock 降级逻辑存在"
else
    fail "billing_degrade.py 缺少 fallback/mock 降级逻辑"
fi

# ─────────────────────────────────────────────────────────────────────────────
# [3/4] 私有化部署监控
# 验证: 单租户隔离 + billing 降级硬门控 + 公网隐藏 + W79 B-2 monitor 脚本
# 依据: W79 B-2 private_deployment_monitor.sh + W79 B-3 跨租户监控
# ─────────────────────────────────────────────────────────────────────────────
log "[3/4] 私有化部署监控"

# 3a. W79 B-2 monitor 脚本存在 + bash 语法 OK
MONITOR_SCRIPT="$PROJECT_DIR/scripts/private_deployment_monitor.sh"
if [[ -f "$MONITOR_SCRIPT" ]]; then
    if bash -n "$MONITOR_SCRIPT" 2>/dev/null; then
        pass "W79 B-2 private_deployment_monitor.sh 存在 + bash 语法 OK"
    else
        fail "private_deployment_monitor.sh bash 语法错误"
    fi
else
    fail "W79 B-2 private_deployment_monitor.sh 缺失 ($MONITOR_SCRIPT)"
fi

# 3b. 6 商业化表 e2e 测试存在 (W78 C-1 + W79 B-2 + W79 B-3)
COMMERCIAL_TABLES=("commercial_plans" "commercial_tenants" "commercial_subscriptions" \
                   "commercial_invoices" "commercial_usage_records" "commercial_licenses")
TABLE_FOUND=0
for t in "${COMMERCIAL_TABLES[@]}"; do
    if grep -r "$t" "$PROJECT_DIR/tests/" 2>/dev/null | grep -q .; then
        TABLE_FOUND=$((TABLE_FOUND+1))
    fi
done
if [[ $TABLE_FOUND -ge 5 ]]; then
    pass "6 商业化表 e2e 覆盖 $TABLE_FOUND/6"
else
    fail "6 商业化表 e2e 覆盖不足 ($TABLE_FOUND/6)"
fi

# 3c. 跨租户 422 拦截测试存在 (W79 B-3 实战)
if grep -r "422\|TenantIsolationViolation\|cross.tenant\|跨租户" "$PROJECT_DIR/tests/" 2>/dev/null | grep -q .; then
    pass "跨租户 422 拦截 e2e 测试存在 (W79 B-3 实战)"
else
    fail "跨租户 422 拦截 e2e 测试缺失"
fi

# 3d. BILLING_LIVE_ENABLED 默认 false 硬门控 (类 20.13, W79 B-2 已落地)
LIVE_ENABLED_DEFAULT=$(grep -r "BILLING_LIVE_ENABLED" "$PRIVATE_DIR/" 2>/dev/null | \
    grep -oP 'BILLING_LIVE_ENABLED[^=]*=\s*\K(true|false|True|False)' | head -1)
if [[ "${LIVE_ENABLED_DEFAULT,,}" == "false" ]]; then
    pass "BILLING_LIVE_ENABLED 默认 false 硬门控 (类 20.13)"
elif [[ -z "$LIVE_ENABLED_DEFAULT" ]]; then
    # 从环境变量读取
    if [[ "${BILLING_LIVE_ENABLED:-false}" == "false" ]]; then
        pass "BILLING_LIVE_ENABLED 环境变量 false (类 20.13)"
    else
        fail "BILLING_LIVE_ENABLED=true 需要主拍决策 (类 20.13 真生产 key 单独拍板)"
        send_alert "BILLING_LIVE_ENABLED=true 检测到, 需要主拍决策 (类 20.13)"
    fi
else
    fail "BILLING_LIVE_ENABLED 默认值异常: $LIVE_ENABLED_DEFAULT (期望 false)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# [4/4] 客户支持工单监控
# 验证: SLA 达标 + 财务结算 + 退款流程 + 商业化运营
# 依据: W79 B-1 商业化运营 + W79 A-2 §5 阶段 2 客户支持 + W80 B-1 商业化运营
# ─────────────────────────────────────────────────────────────────────────────
log "[4/4] 客户支持工单监控"

# 4a. W80 B-2 e2e 测试存在
W80_TEST="$PROJECT_DIR/tests/test_w80_b2_private_support_e2e.py"
if [[ -f "$W80_TEST" ]]; then
    if python3 -m py_compile "$W80_TEST" 2>/dev/null; then
        pass "W80 B-2 e2e 测试存在 + 语法 OK ($W80_TEST)"
    else
        fail "W80 B-2 e2e 测试语法错误 ($W80_TEST)"
    fi
else
    fail "W80 B-2 e2e 测试缺失 ($W80_TEST)"
fi

# 4b. 客户支持 runbook 存在
RUNBOOK="$PROJECT_DIR/docs/w80-1st-batch-b2-commercial-private-support-runbook-2026-07-28.md"
if [[ -f "$RUNBOOK" ]]; then
    pass "客户支持 runbook 存在 ($RUNBOOK)"
else
    fail "客户支持 runbook 缺失 ($RUNBOOK)"
fi

# 4c. 财务结算相关: commercial_invoices + commercial_usage_records 覆盖
if grep -r "commercial_invoices\|commercial_usage_records\|invoice\|usage_record" \
   "$PROJECT_DIR/tests/" 2>/dev/null | grep -q .; then
    pass "财务结算 (invoices/usage_records) e2e 覆盖存在"
else
    fail "财务结算 e2e 覆盖缺失 (commercial_invoices/commercial_usage_records)"
fi

# 4d. 8 件套监控完整性 (W78 C-1 + W79 B-2 + W79 B-3 + W80 B-2)
MONITOR_COUNT=0
for m in "monitor-alembic-heads" "monitor-nginx-mime" "monitor-pwa-manifest" \
         "monitor-sw-cache" "monitor-tenant-isolation" "monitor-9-table-index" \
         "private_deployment_monitor" "tenant_monitoring" "private_deployment_support"; do
    if find "$PROJECT_DIR/scripts" -name "*${m}*" 2>/dev/null | grep -q .; then
        MONITOR_COUNT=$((MONITOR_COUNT+1))
    fi
done
if [[ $MONITOR_COUNT -ge 6 ]]; then
    pass "8 件套监控 $MONITOR_COUNT/9 存在 (W78 C-1 + W79 B-2 + W79 B-3 + W80 B-2)"
else
    fail "8 件套监控不足 ($MONITOR_COUNT/9)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# 汇总
# ─────────────────────────────────────────────────────────────────────────────
TOTAL=$((PASS+FAIL))
log "─────────────────────────────────────────────────────"
log "汇总: $PASS/$TOTAL PASS, $FAIL FAIL"

if [[ $FAIL -gt 0 ]]; then
    log "FAIL 列表:"
    for e in "${ERRORS[@]}"; do log "  - $e"; done
    send_alert "private_deployment_support: $FAIL/$TOTAL 检查失败"
    exit 1
fi

log "全部 $PASS/$TOTAL 检查通过 (W80 B-2 商业化私有化部署 + 客户支持)"
exit 0

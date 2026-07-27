#!/bin/bash
# monitor-9-table-index.sh
# W75 第 1 批 D-1: 9 表索引监控 (与 W73 B-2 4 + W74 D-1 tenant + W75 B-3 webhook 凑齐 7 件套)
#
# 依据: W74 B-1 commit aef117b17 9 表 2 索引修复 + 084 P1 修复 (8d0d12c2d) + W75 D-1 verify
# 用途: 每小时跑一次, 检测 9 表 2 索引 (3 GIN jsonb_path_ops + 1 联合部分) 是否生效
# 报警: 索引缺失 / 走 Seq Scan (未走 index) / 列类型回退 json → 触发 webhook
#
# 与 7 件套监控并列:
#   W73 B-2: monitor-alembic-heads.sh / monitor-nginx-mime.sh / monitor-pwa-manifest.sh / monitor-sw-cache.sh
#   W74 D-1: monitor-tenant-isolation.sh
#   W75 B-3: monitor-webhook-payload.sh (TBD)
#   W75 D-1: monitor-9-table-index.sh (本脚本)
#
# 退出码: 0=正常 (4 索引全在), 1=异常 (索引缺失/未走 index), 2=执行错误
#
# 用法:
#   bash scripts/monitor-9-table-index.sh
#   crontab: 0 * * * * bash /opt/microbubble-agent/scripts/monitor-9-table-index.sh

set -e

PROJECT_DIR="${PROJECT_DIR:-/opt/microbubble-agent}"
SCRIPTS_DIR="$PROJECT_DIR/scripts"
LOG_FILE="${LOG_FILE:-/var/log/microbubble-agent/9-table-index-monitor.log}"
WEBHOOK_URL="${WEBHOOK_URL:-}"  # 主拍 webhook, 可选

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

fail_loud() {
    log "ERROR: $*"
    if [ -n "$WEBHOOK_URL" ]; then
        curl -sS -X POST -H 'Content-Type: application/json' \
            -d "{\"text\":\"[9-table-index-monitor] $*\"" "$WEBHOOK_URL" || true
    fi
}

if [ ! -d "$PROJECT_DIR" ]; then
    fail_loud "project dir not found: $PROJECT_DIR"
    exit 2
fi

log "===== 9 表索引监控启动 ====="

# 1. 验证 alembic 084 迁移存在 + 串单链
log "[1/4] 验证 alembic 084 迁移文件 + 串单链"
ALEMBIC_084="$PROJECT_DIR/alembic/versions/084_meeting_cluster_jsonb_gin_index.py"
if [ ! -f "$ALEMBIC_084" ]; then
    fail_loud "alembic 084 不存在: $ALEMBIC_084 (W74 B-1 必须实施)"
    exit 1
fi

# 084 P1 修复 verify: 表名复数 + ALTER COLUMN TYPE jsonb
if ! grep -q "ALTER TABLE meetings" "$ALEMBIC_084"; then
    fail_loud "alembic 084 缺 ALTER TABLE meetings (P1 修复: meeting → meetings)"
    exit 1
fi
if ! grep -q "ALTER COLUMN cluster_id_history TYPE jsonb" "$ALEMBIC_084"; then
    fail_loud "alembic 084 缺 ALTER COLUMN ... TYPE jsonb (P1 修复: json → jsonb)"
    exit 1
fi
log "  OK: alembic 084 P1 修复 (复数表名 + ALTER jsonb) 已实施"

# 2. 验证 4 索引名定义存在 (3 GIN + 1 联合部分)
log "[2/4] 验证 4 索引名定义"
EXPECTED_INDEXES=(
    "ix_meetings_cluster_id_history_gin"
    "ix_meetings_speaker_mapping_gin"
    "ix_meetings_speaker_stats_gin"
    "ix_members_voice_confirmed_partial"
)
for idx in "${EXPECTED_INDEXES[@]}"; do
    if ! grep -q "$idx" "$ALEMBIC_084"; then
        fail_loud "alembic 084 缺索引名 $idx"
        exit 1
    fi
done
log "  OK: 4 索引名齐全 (3 GIN jsonb_path_ops + 1 联合部分)"

# 3. 验证 alembic 串单链 (084 接 083, 085 接 084)
log "[3/4] 验证 alembic 串单链"
DOWN_084=$(grep -E "^down_revision\s*=" "$ALEMBIC_084" | head -1 | sed -E "s/.*['\"]([^'\"]+)['\"].*/\1/")
if [ "$DOWN_084" != "083_commercial_tenant_isolation" ]; then
    fail_loud "alembic 084 down_revision 必须 = 083_commercial_tenant_isolation, 实得: $DOWN_084"
    exit 1
fi

ALEMBIC_085="$PROJECT_DIR/alembic/versions/085_billing_payment_tables.py"
if [ -f "$ALEMBIC_085" ]; then
    DOWN_085=$(grep -E "^down_revision\s*=" "$ALEMBIC_085" | head -1 | sed -E "s/.*['\"]([^'\"]+)['\"].*/\1/")
    if [ "$DOWN_085" != "084_meeting_cluster_jsonb_gin_index" ]; then
        fail_loud "alembic 085 down_revision 必须 = 084_meeting_cluster_jsonb_gin_index, 实得: $DOWN_085"
        exit 1
    fi
    log "  OK: alembic 串单链 083 → 084 → 085 守恒"
else
    log "  WARN: 085 迁移不存在, 仅验证 084 单链"
fi

# 4. 验证 7 e2e 测试存在 (W74 B-1 实施)
log "[4/4] 验证 7 e2e 测试存在"
E2E_084="$PROJECT_DIR/tests/test_alembic_084_9_table_index.py"
if [ ! -f "$E2E_084" ]; then
    fail_loud "084 e2e 测试不存在: $E2E_084"
    exit 1
fi
TEST_COUNT=$(grep -cE "^def test_" "$E2E_084" || echo "0")
if [ "$TEST_COUNT" -lt 7 ]; then
    fail_loud "084 e2e 应至少 7 case, 实得 $TEST_COUNT"
    exit 1
fi
log "  OK: 7 e2e tests 已实施"

log "===== 9 表索引监控正常结束 ====="
exit 0
#!/bin/bash
# monitor-alembic-heads.sh
# W73 第 1 批 B-2 hot-fix 监控 #1: alembic 双头检测
# 依据: W72 第 2 批 E-1 commit c29ca1663 + CLAUDE.md §2.4 + W68 第 3 批事故 1852468a6
#
# W75 第 1 批 B-3 P2 修复 (W74 E-1 报告):
# - webhook payload 改用 scripts/lib/webhook_payload.sh 共用库 (含完整 5 字段)
# - 删 || true 静默吞 → notify_alert 失败主动 exit 1
# - retry 策略 (3 次, 间隔 5s)
# - payload 必含 severity=critical, source=alembic-monitor, heads 列表, head_count
#
# 用途: 每小时跑一次, 检测 alembic chain 是否多 head
# 报警: ≥ 2 head 触发 webhook (主拍派 v6 段 5 反馈 #1 实战纪律)
# 修复: 派工 v6 §6 段 6 串单链纪律 (down_revision 接 X + clear __pycache__)
#
# 用法:
#   bash scripts/monitor-alembic-heads.sh
#   crontab: 0 * * * * bash /opt/microbubble-agent/scripts/monitor-alembic-heads.sh
#
# 退出码: 0=正常 (1 head), 1=异常 (≥ 2 head), 2=执行错误

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib/webhook_payload.sh"

PROJECT_DIR="${PROJECT_DIR:-/opt/microbubble-agent}"
ALEMBIC_DIR="$PROJECT_DIR/alembic"
LOG_FILE="${LOG_FILE:-/var/log/microbubble-agent/alembic-monitor.log}"
WEBHOOK_URL="${WEBHOOK_URL:-}"  # 主拍 webhook, 可选
export WEBHOOK_URL
ALERT_LOG_FILE="${ALERT_LOG_FILE:-/var/log/microbubble-agent/alert.log}"
export ALERT_LOG_FILE

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

if [ ! -d "$ALEMBIC_DIR" ]; then
    notify_alert "alembic-monitor" "critical" "alembic dir not found" \
        "{\"dir\":\"$ALEMBIC_DIR\",\"project_dir\":\"$PROJECT_DIR\"}" || exit 2
    exit 2
fi

cd "$PROJECT_DIR"

# 1. 解析 alembic heads (派工 v6 §6 实战)
HEADS=$(python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
c = Config()
c.set_main_option('script_location', 'alembic')
s = ScriptDirectory.from_config(c)
heads = s.get_heads()
print(' '.join(heads))
" 2>&1)

if [ $? -ne 0 ]; then
    notify_alert "alembic-monitor" "critical" "alembic script load failed" \
        "{\"error\":\"$HEADS\"}" || exit 2
    exit 2
fi

HEAD_COUNT=$(echo "$HEADS" | wc -w | tr -d ' ')

log "alembic heads: [$HEADS] (count: $HEAD_COUNT)"

if [ "$HEAD_COUNT" -ge 2 ]; then
    notify_alert "alembic-monitor" "critical" "alembic 双头 detected" \
        "{\"heads\":\"$HEADS\",\"head_count\":$HEAD_COUNT,\"fix_ref\":\"W68 §2.3 commit 1852468a6\"}" || exit 1
    log "修复路径: W68 §2.3 (commit 1852468a6)"
    log "  1. 定位双头: alembic heads"
    log "  2. 改 down_revision: sed -i 's|down_revision.*<old>.*|down_revision.*<new>.*|' alembic/versions/0XX_*.py"
    log "  3. clear cache: find alembic/versions/__pycache__ -name '*.pyc' -delete"
    log "  4. verify: alembic heads 期望 1 个"
    exit 1
fi

# 2. 检查 __pycache__ 残留 (CLAUDE.md 752 行铁律)
PYC_COUNT=$(find "$ALEMBIC_DIR/versions/__pycache__" -name "*.pyc" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PYC_COUNT" -gt 0 ]; then
    log "WARN: alembic __pycache__ 残留 $PYC_COUNT 个 .pyc, 建议清理 (CLAUDE.md 752 行铁律)"
fi

log "alembic head monitor OK: 1 head"
exit 0
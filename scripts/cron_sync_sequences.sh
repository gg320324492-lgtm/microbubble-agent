#!/bin/bash
# cron_sync_sequences.sh — 兜底 cron wrapper (凌晨跑一次)
#
# 安装: (crontab -l 2>/dev/null; echo "0 3 * * * /opt/microbubble-agent/scripts/cron_sync_sequences.sh >> /var/log/microbubble-seq-sync.log 2>&1") | crontab -
# 验证: bash /opt/microbubble-agent/scripts/cron_sync_sequences.sh
#
# 类 20.188 (2026-08-27) 兜底防线: lifespan startup + deploy-auto.sh 后置检查都修了
# 漂移场景, 但若两个都漏 (例如 lifespan 失败 + 下次 deploy 失败), 凌晨跑这个
# 保证序列第二天早上一定对齐.

set -e
PROJECT_DIR="${PROJECT_DIR:-/opt/microbubble-agent}"
DB_CONTAINER="${DB_CONTAINER:-microbubble-agent-app-revived}"

# 容器不存在 → 静默退出 (cron 任务是兜底, 不要刷错误)
if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${DB_CONTAINER}\$"; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') SKIP: ${DB_CONTAINER} not running"
    exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') Running sync_sequences.sh..."
if bash "${PROJECT_DIR}/scripts/sync_sequences.sh"; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') OK: sequence sync complete"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') ERROR: sync failed (exit $?)"
    exit 1
fi
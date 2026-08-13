#!/bin/bash
# PostgreSQL 数据库备份脚本
# 用法: bash scripts/backup_db.sh
# 建议通过 cron 定时执行: 0 2 * * * cd /path/to/microbubble-agent && bash scripts/backup_db.sh

set -e

BACKUP_DIR="./backups"
KEEP_DAYS=7
DB_CONTAINER="microbubble-agent-db-1"
DB_USER="postgres"
DB_NAME="microbubble"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/microbubble_${TIMESTAMP}.sql.gz"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

echo "[$(date)] 开始备份数据库..."

# 执行备份
docker compose exec -T db pg_dump -U "$DB_USER" "$DB_NAME" | gzip > "$BACKUP_FILE"

# 检查备份文件
FILE_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE" 2>/dev/null)
if [ "$FILE_SIZE" -gt 100 ]; then
    echo "[$(date)] 备份成功: $BACKUP_FILE ($FILE_SIZE bytes)"
else
    echo "[$(date)] 备份失败: 文件过小 ($FILE_SIZE bytes)"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# 清理过期备份
echo "[$(date)] 清理 ${KEEP_DAYS} 天前的备份..."
find "$BACKUP_DIR" -name "microbubble_*.sql.gz" -mtime +$KEEP_DAYS -delete

# 显示当前备份列表
echo "[$(date)] 当前备份文件:"
ls -lh "$BACKUP_DIR"/microbubble_*.sql.gz 2>/dev/null || echo "  无备份文件"

# 2026-08-14 类 20.155: 提醒 SECRET_KEY 是独立资产, 不在 DB 备份里
# 若 .env 中 SECRET_KEY 已轮换, 旧 refresh_token 全部失效, 用户会被强制登出
# 推荐同时把 .env 备份到 BACKUP_DIR/env_*.bak (或独立密码管理器)
if [ -f ".env" ]; then
  ENV_HASH=$(grep "^SECRET_KEY=" .env | sha256sum | cut -c1-8)
  echo "[$(date)] 当前 SECRET_KEY sha256[0:8]=$ENV_HASH (备份 DB 不含此 key)"
  echo "[$(date)] 提醒: 恢复 DB 后若 SECRET_KEY 已变, 所有用户须重新登录 (类 20.155)"
fi

echo "[$(date)] 备份完成"

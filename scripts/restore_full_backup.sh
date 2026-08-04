#!/bin/bash
# MicroBubble Full DB Restore (W2 +N 2026-08-04)
# 还原完整 DB 备份, 绕过 FK violation 用 session_replication_role = replica
#
# 用法:
#   bash scripts/restore_full_backup.sh                                          # 用最新备份
#   bash scripts/restore_full_backup.sh backups/microbubble_20260804_020001.sql.gz # 指定备份
#
# 流程:
#   1. 停 app/celery 容器 (释放 DB 连接)
#   2. DROP + CREATE DB (彻底清空)
#   3. gunzip | psql 还原 (session_replication_role=replica 绕过 FK)
#   4. RESET session_replication_role + 重启容器 + 验证

set -euo pipefail

BACKUP_FILE="${1:-}"
DB_CONTAINER="microbubble-agent-db-1"
DB_USER="postgres"
DB_NAME="microbubble"

# 选择备份
if [ -z "$BACKUP_FILE" ]; then
    BACKUP_FILE=$(ls -t backups/microbubble_*.sql.gz 2>/dev/null | head -1 || echo "")
fi

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    echo "[ERROR] No backup file found"
    echo "  Usage: bash scripts/restore_full_backup.sh [path/to/backup.sql.gz]"
    echo "  Available backups:"
    ls -lh backups/microbubble_*.sql.gz 2>/dev/null | head -5 || echo "  (none in backups/)"
    exit 1
fi

FILE_SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE" 2>/dev/null || echo 0)
echo "============================================================"
echo " MicroBubble Full DB Restore (W2 +N 2026-08-04)"
echo "============================================================"
echo ""
echo "Backup file: $BACKUP_FILE"
echo "  size: $FILE_SIZE bytes"
echo ""

# Step 1: 停 app 容器
echo "[1/5] 停止 app + celery 容器 (释放 DB 连接)..."
docker stop microbubble-agent-app-1 microbubble-agent-celery-worker-1 microbubble-agent-celery-beat-1 microbubble-agent-celery-meeting-worker-1 2>&1 | tail -2 || true
sleep 3

# Step 2: 清空 DB
echo ""
echo "[2/5] 清空 DB (DROP + CREATE)..."
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $DB_NAME WITH (FORCE)" 2>&1 | tail -2
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -c "CREATE DATABASE $DB_NAME" 2>&1 | tail -2

# Step 3: 还原 (绕过 FK)
echo ""
echo "[3/5] 还原备份 (session_replication_role=replica 绕过 FK)..."
echo "      (这步会输出 pg_dump 重放的所有 SQL, 包括 ALTER/COPY/CREATE INDEX 等)"

# 在容器内先设置 session_replication_role, 然后执行 sql
gunzip -c "$BACKUP_FILE" > /tmp/restore.sql
echo "      temp file: /tmp/restore.sql ($(stat -c%s /tmp/restore.sql) bytes)"

# 注入 SET session_replication_role = replica 在 sql 开头
echo "SET session_replication_role = replica;" | cat - /tmp/restore.sql > /tmp/restore_with_role.sql

docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=0 -f - < /tmp/restore_with_role.sql > /tmp/restore.log 2>&1
RESTORE_RC=$?

# 统计错误数 (FK violation 是预期内的)
ERROR_COUNT=$(grep -c "^ERROR:" /tmp/restore.log 2>/dev/null || echo 0)
echo ""
echo "      restore exit code: $RESTORE_RC"
echo "      ERROR lines: $ERROR_COUNT (FK violation 预期, session_replication_role 已禁用)"

if [ "$RESTORE_RC" -ne 0 ]; then
    echo "      (non-zero exit 但只要业务数据还原了就 OK, 见下方验证)"
fi

rm -f /tmp/restore.sql /tmp/restore_with_role.sql

# Step 4: 重置 session_replication_role + 重启容器
echo ""
echo "[4/5] 重置 session_replication_role + 重启容器..."
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "ALTER DATABASE $DB_NAME RESET session_replication_role;" 2>&1 | tail -2

docker start microbubble-agent-app-1 microbubble-agent-celery-worker-1 microbubble-agent-celery-beat-1 microbubble-agent-celery-meeting-worker-1 2>&1 | tail -2
sleep 15

# Step 5: 验证
echo ""
echo "[5/5] 验证业务数据完整性..."
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
SELECT
  (SELECT count(*) FROM members) AS members,
  (SELECT count(*) FROM tasks) AS tasks,
  (SELECT count(*) FROM meetings) AS meetings,
  (SELECT count(*) FROM knowledge) AS knowledge,
  (SELECT count(*) FROM projects) AS projects,
  (SELECT count(*) FROM reminders) AS reminders,
  (SELECT version_num FROM alembic_version) AS alembic_head;
"

echo ""
echo "============================================================"
echo " Restore complete. Verify via API: bash scripts/verify_backup_restore.sh $BACKUP_FILE"
echo "============================================================"
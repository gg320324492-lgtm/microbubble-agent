#!/bin/bash
# MicroBubble Backup Restore Verification
# W2 +N 2026-08-04: 验证 backup_db.sh 出的备份能真恢复完整数据
#
# 用法:
#   bash scripts/verify_backup_restore.sh                    # 验证最新备份
#   bash scripts/verify_backup_restore.sh path/to/backup.sql.gz  # 验证指定备份
#
# 流程:
#   1. 创建临时测试 DB (microbubble_restore_verify_$$)
#   2. gunzip | psql 还原备份到测试 DB
#   3. 验证 public tables ≥ 50 + members ≥ 24
#   4. DROP 测试 DB
#
# 期望: backup_db.sh 每日生成 + verify_backup_restore.sh 每日验证

set -euo pipefail

BACKUP_FILE="${1:-}"
if [ -z "$BACKUP_FILE" ]; then
    # 找最新备份
    BACKUP_FILE=$(ls -t backups/microbubble_*.sql.gz 2>/dev/null | head -1 || echo "")
fi

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    echo "[ERROR] No backup file found"
    echo "  Usage: bash scripts/verify_backup_restore.sh [path/to/backup.sql.gz]"
    echo "  Or run bash scripts/backup_db.sh first to generate a backup"
    exit 1
fi

DB_CONTAINER="microbubble-agent-db-1"
DB_USER="postgres"
TEST_DB="microbubble_restore_verify_$$"

echo "============================================================"
echo " Backup Restore Verification (W2 +N 2026-08-04)"
echo "============================================================"
echo ""
echo "[1/4] Backup file: $BACKUP_FILE"
FILE_SIZE=$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE" 2>/dev/null || echo 0)
echo "      size: $FILE_SIZE bytes"

if [ "$FILE_SIZE" -lt 1000 ]; then
    echo "[FAIL] Backup file too small (< 1000 bytes), likely empty"
    exit 1
fi

# Cleanup trap - ensure test DB is dropped even on failure
cleanup() {
    docker exec "$DB_CONTAINER" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $TEST_DB" 2>&1 | tail -1 || true
}
trap cleanup EXIT

# Step 2: Create test DB
echo ""
echo "[2/4] Creating test DB: $TEST_DB"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -c "DROP DATABASE IF EXISTS $TEST_DB" 2>&1 | tail -1
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -c "CREATE DATABASE $TEST_DB" 2>&1 | tail -1

# Step 3: Restore backup to test DB
echo ""
echo "[3/4] Restoring backup to test DB..."
if ! gunzip -c "$BACKUP_FILE" | docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB" -v ON_ERROR_STOP=1 > /tmp/restore.log 2>&1; then
    echo "[FAIL] Restore failed. Last 20 lines of psql output:"
    tail -20 /tmp/restore.log
    exit 2
fi
echo "      restore OK"

# Step 4: Verify data integrity
echo ""
echo "[4/4] Verifying data integrity..."
TABLE_COUNT=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB" -tAc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'" 2>&1 | tr -d ' \n')
USER_COUNT=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB" -tAc "SELECT count(*) FROM members" 2>&1 | tr -d ' \n')
ALEMBIC_VER=$(docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB" -tAc "SELECT version_num FROM alembic_version" 2>&1 | tr -d ' \n')

echo "      public tables: $TABLE_COUNT (expected >= 50)"
echo "      members:       $USER_COUNT (expected >= 24)"
echo "      alembic head:  $ALEMBIC_VER (expected '097_meeting_processing_persistence')"

# Final verdict
echo ""
echo "============================================================"
if [ "${TABLE_COUNT:-0}" -ge 50 ] && [ "${USER_COUNT:-0}" -ge 24 ]; then
    echo " PASS: Backup is restorable, data integrity OK"
    echo "============================================================"
    exit 0
else
    echo " FAIL: Backup restore data incomplete"
    echo "   expected: tables >= 50 AND members >= 24"
    echo "   got:      tables=$TABLE_COUNT, members=$USER_COUNT"
    echo "============================================================"
    exit 3
fi
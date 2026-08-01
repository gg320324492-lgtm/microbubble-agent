#!/usr/bin/env bash
# scripts/verify_realenv_e2e.sh — W98 P3-A 真环境 e2e 验证启停脚本.
#
# 派工 v10 §2.3 / §8 S5: 真环境可达性真查 + 启停逻辑.
# 用法:
#   bash scripts/verify_realenv_e2e.sh check     # 检查可达性
#   bash scripts/verify_realenv_e2e.sh up        # 启 docker PG+Redis
#   bash scripts/verify_realenv_e2e.sh down      # 停 docker PG+Redis
#   bash scripts/verify_realenv_e2e.sh test      # 跑 pytest tests/realenv
#   bash scripts/verify_realenv_e2e.sh migrate   # 跑 alembic upgrade head

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 默认 DATABASE_URL / REDIS_URL (本机)
DEFAULT_DB_URL="postgresql://postgres:microbubble2026@localhost:5432/microbubble"
DEFAULT_REDIS_URL="redis://localhost:6379/0"

cmd_check() {
    echo "=== 真环境可达性真查 ==="
    echo "[DB] DATABASE_URL=${DATABASE_URL:-UNSET}"
    if [ -n "$DATABASE_URL" ]; then
        python -c "
import os, sys
try:
    import psycopg2
    conn = psycopg2.connect(os.environ['DATABASE_URL'], connect_timeout=3)
    print('[DB] OK (psycopg2 connect success)')
except Exception as e:
    print(f'[DB] FAIL: {e}')
    sys.exit(0)  # 不可达不算 fail, 仅报告
" || true
    fi
    echo "[REDIS] REDIS_URL=${REDIS_URL:-UNSET}"
    if [ -n "$REDIS_URL" ]; then
        python -c "
import os, sys
try:
    import redis
    r = redis.from_url(os.environ['REDIS_URL'], socket_connect_timeout=3)
    r.ping()
    print('[REDIS] OK (redis ping success)')
except Exception as e:
    print(f'[REDIS] FAIL: {e}')
    sys.exit(0)  # 不可达不算 fail, 仅报告
" || true
    fi
    echo "[ALEMBIC] head:"
    cd "$PROJECT_ROOT" && python -m alembic heads 2>&1 | tail -3
}

cmd_up() {
    echo "=== 启动 docker PG + Redis ==="
    cd "$PROJECT_ROOT"
    docker compose up -d db redis 2>&1 || {
        echo "ERROR: docker compose 启动失败"
        exit 1
    }
    sleep 5
    echo "[OK] docker compose up 完成"
    # 尝试设默认环境变量
    export DATABASE_URL="$DEFAULT_DB_URL"
    export REDIS_URL="$DEFAULT_REDIS_URL"
    echo "请设置环境变量: export DATABASE_URL=$DEFAULT_DB_URL"
    echo "                  export REDIS_URL=$DEFAULT_REDIS_URL"
}

cmd_down() {
    echo "=== 停止 docker PG + Redis ==="
    cd "$PROJECT_ROOT"
    docker compose down 2>&1 || {
        echo "ERROR: docker compose down 失败"
        exit 1
    }
    echo "[OK] docker compose down 完成"
}

cmd_migrate() {
    echo "=== alembic upgrade head ==="
    cd "$PROJECT_ROOT"
    if [ -z "$DATABASE_URL" ]; then
        export DATABASE_URL="$DEFAULT_DB_URL"
        echo "未设 DATABASE_URL, 用默认: $DEFAULT_DB_URL"
    fi
    python -m alembic upgrade head 2>&1 | tail -10
}

cmd_test() {
    echo "=== 跑 pytest tests/realenv ==="
    cd "$PROJECT_ROOT"
    if [ -z "$DATABASE_URL" ]; then
        echo "未设 DATABASE_URL, 默认 SKIP 全套"
        unset DATABASE_URL
    fi
    if [ -z "$REDIS_URL" ]; then
        echo "未设 REDIS_URL, 默认 SKIP 全套"
        unset REDIS_URL
    fi
    python -m pytest tests/realenv -v --no-header 2>&1 | tail -30
}

# 派工 v10 §8 S5 真环境可达性真查 (默认入口)
case "${1:-check}" in
    check)
        cmd_check
        ;;
    up)
        cmd_up
        ;;
    down)
        cmd_down
        ;;
    migrate)
        cmd_migrate
        ;;
    test)
        cmd_test
        ;;
    all)
        cmd_up
        cmd_migrate
        cmd_test
        ;;
    *)
        echo "用法: $0 {check|up|down|migrate|test|all}"
        exit 1
        ;;
esac
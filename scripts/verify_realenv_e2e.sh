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
# 密码轮换过, 不再内置过时的 fallback 默认值 (L-14, 2026-10-09)。
# 本机默认 DSN 的密码从 POSTGRES_PASSWORD env 或 .env 的 DATABASE_URL 现取;
# 两者都取不到则 DEFAULT_DB_URL 置空, 由消费它的子命令 fail-loud 报错,
# 避免拿空密码/过期密码去连生产库还以为是连上了。
DEFAULT_DB_URL=""
if [ -n "${POSTGRES_PASSWORD:-}" ]; then
    DEFAULT_DB_URL="postgresql://postgres:${POSTGRES_PASSWORD}@localhost:5432/microbubble"
elif [ -f "$PROJECT_ROOT/.env" ]; then
    _db_pw="$(sed -n 's|^DATABASE_URL=.*postgres:\([^@]*\)@.*|\1|p' "$PROJECT_ROOT/.env" | head -1)"
    if [ -n "$_db_pw" ]; then
        DEFAULT_DB_URL="postgresql://postgres:${_db_pw}@localhost:5432/microbubble"
    fi
fi
DEFAULT_REDIS_URL="redis://localhost:6379/0"

# 回显用: 掩掉密码, 避免真密码进终端回滚缓冲/日志 (旧硬编码值无所谓, 现值是生产密码)
_mask_db_url() {
    echo "$1" | sed -E 's|://([^:]+):[^@]*@|://\1:***@|'
}

# 消费 DEFAULT_DB_URL 的子命令在密码取不到时必须 fail-loud
_require_default_db_url() {
    if [ -z "$DEFAULT_DB_URL" ]; then
        echo "ERROR: DATABASE_URL 未设, 且无法从 POSTGRES_PASSWORD / .env 取到 DB 密码。" >&2
        echo "密码已轮换, 不再内置默认值。设置其一: export POSTGRES_PASSWORD=<pw> 或写 .env" >&2
        exit 1
    fi
}

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
    # 尝试设默认环境变量 (仅在调用方未显式设置时; 不覆盖用户已有值)
    _require_default_db_url
    export DATABASE_URL="${DATABASE_URL:-$DEFAULT_DB_URL}"
    export REDIS_URL="${REDIS_URL:-$DEFAULT_REDIS_URL}"
    echo "请设置环境变量: export DATABASE_URL=$(_mask_db_url "$DEFAULT_DB_URL")"
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
        _require_default_db_url
        export DATABASE_URL="$DEFAULT_DB_URL"
        echo "未设 DATABASE_URL, 用默认: $(_mask_db_url "$DEFAULT_DB_URL")"
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
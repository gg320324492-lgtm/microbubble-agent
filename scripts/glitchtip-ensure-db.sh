#!/usr/bin/env bash
# W91-X-20: 幂等建 GlitchTip 专属数据库, 修 glitchtip crash loop。
#
# 背景 (W90-X-14 据实):
#   glitchtip-dev-1 在 Restarting crash loop (RestartCount=865)。
#   根因: docker-compose 的 DATABASE_URL 指向 `glitchtip` 库, 但该库从未建。
#   Django 启动即 `FATAL: database "glitchtip" does not exist` → exit 1 → restart。
#
# 为什么要脚本:
#   docs/sentry-setup.md §2 把建库写成"首次装机手动跑一次"。
#   人一旦跳过这步 (新 worktree / 新机器 / 重建 volume), 容器就无限重启。
#   本脚本幂等, 可无条件在 `docker compose up glitchtip` 之前跑。
#
# 用法:
#   bash scripts/glitchtip-ensure-db.sh                       # 默认 docker-compose.yml
#   COMPOSE_FILE=docker-compose.dev.yml bash scripts/...      # dev 栈
#   DB_CONTAINER=microbubble-agent-db-1 bash scripts/...      # 直接点名容器
set -euo pipefail

DB_NAME="${GLITCHTIP_DB_NAME:-glitchtip}"
DB_USER="${POSTGRES_USER:-postgres}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
DB_CONTAINER="${DB_CONTAINER:-}"

# psql 包一层: 优先直接 docker exec 指定容器, 否则走 compose service。
psql_exec() {
    if [ -n "$DB_CONTAINER" ]; then
        docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d postgres "$@"
    else
        docker compose -f "$COMPOSE_FILE" exec -T db psql -U "$DB_USER" -d postgres "$@"
    fi
}

echo "[glitchtip-ensure-db] target database: ${DB_NAME}"

# 幂等判定: pg_database 里已有就直接退出, 不重复建 (CREATE DATABASE 不支持 IF NOT EXISTS)。
if psql_exec -tAc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" 2>/dev/null | grep -q '^1$'; then
    echo "[glitchtip-ensure-db] OK: database '${DB_NAME}' already exists, nothing to do."
    exit 0
fi

echo "[glitchtip-ensure-db] database '${DB_NAME}' missing -> creating..."
psql_exec -c "CREATE DATABASE ${DB_NAME}"

# 建完必须复检, 不能只看 CREATE 的 returncode (类 20.30 精确断言精神)。
if psql_exec -tAc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" 2>/dev/null | grep -q '^1$'; then
    echo "[glitchtip-ensure-db] OK: database '${DB_NAME}' created."
else
    echo "[glitchtip-ensure-db] ERROR: create reported success but '${DB_NAME}' still absent." >&2
    exit 1
fi

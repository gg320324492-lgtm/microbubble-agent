#!/usr/bin/env bash
# 商业化 SaaS 平台部署脚本 (W73 第 1 批 B-1)
#
# W72 第 2 批 B-5 Dockerfile.commercial 起步 + W73 第 1 批 B-1 收口
# 用法:
#     bash commercial/saas-platform/deploy.sh [start|stop|restart|status|logs|migrate|seed]
#
# 不破坏老路径: 仅在 commercial/saas-platform/deploy.sh 新增 bash 入口
# (与现有 deploy.py 并存: deploy.py 是 Python 内核, deploy.sh 是 shell 包装)

set -euo pipefail

SAAS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SAAS_DIR}/../.." && pwd)"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
SAAS_COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.saas.yml"
SAAS_IMAGE="microbubble/commercial:latest"

ACTION="${1:-help}"

log() { echo "[$(date +%H:%M:%S)] $*"; }
err() { echo "[$(date +%H:%M:%S)] ERROR: $*" >&2; }

cmd_build() {
    log "Building commercial Docker image..."
    cd "${PROJECT_ROOT}"
    docker build -f docker/Dockerfile.commercial -t "${SAAS_IMAGE}" .
}

cmd_migrate() {
    log "Running alembic migrations (083 commercial tenant isolation)..."
    cd "${PROJECT_ROOT}"
    docker run --rm \
        -e DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@postgres:5432/microbubble}" \
        -e SKIP_DB_SETUP=1 \
        -v "${PROJECT_ROOT}/alembic:/app/alembic" \
        "${SAAS_IMAGE}" \
        alembic upgrade head
}

cmd_seed() {
    log "Seeding default plans (free / pro / enterprise)..."
    cd "${PROJECT_ROOT}"
    docker run --rm \
        -e DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://postgres:postgres@postgres:5432/microbubble}" \
        -v "${PROJECT_ROOT}/scripts:/app/scripts" \
        "${SAAS_IMAGE}" \
        python -m scripts.seed_commercial_plans
}

cmd_start() {
    cmd_build
    cmd_migrate
    cmd_seed
    if [[ -f "${SAAS_COMPOSE_FILE}" ]]; then
        log "Starting SaaS compose..."
        docker compose -f "${SAAS_COMPOSE_FILE}" up -d
    else
        log "No docker-compose.saas.yml found, starting main compose with commercial profile..."
        docker compose -f "${COMPOSE_FILE}" --profile commercial up -d
    fi
}

cmd_stop() {
    log "Stopping SaaS containers..."
    if [[ -f "${SAAS_COMPOSE_FILE}" ]]; then
        docker compose -f "${SAAS_COMPOSE_FILE}" down
    else
        docker compose -f "${COMPOSE_FILE}" --profile commercial down
    fi
}

cmd_restart() {
    cmd_stop
    cmd_start
}

cmd_status() {
    log "SaaS containers status:"
    docker ps --filter "label=com.docker.compose.project=commercial" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || true
}

cmd_logs() {
    docker compose -f "${COMPOSE_FILE}" --profile commercial logs -f commercial
}

cmd_help() {
    cat <<EOF
商业化 SaaS 平台部署脚本 (W73 B-1)
用法: $0 <action>
Actions:
    build       Build commercial Docker image
    migrate     Run alembic migrations
    seed        Seed default plans
    start       Build + migrate + seed + start
    stop        Stop SaaS containers
    restart     Stop + start
    status      Show container status
    logs        Tail logs
    help        Show this help
EOF
}

case "${ACTION}" in
    build)       cmd_build ;;
    migrate)     cmd_migrate ;;
    seed)        cmd_seed ;;
    start)       cmd_start ;;
    stop)        cmd_stop ;;
    restart)     cmd_restart ;;
    status)      cmd_status ;;
    logs)        cmd_logs ;;
    help|--help|-h) cmd_help ;;
    *)
        err "unknown action '${ACTION}'"
        cmd_help
        exit 1
        ;;
esac
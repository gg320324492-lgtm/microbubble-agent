#!/bin/bash
# 自动部署脚本 — 由 webhook 触发
# 拉取代码 → 构建前端 → 重载 Nginx

set -e

PROJECT_DIR="/opt/microbubble-agent"
LOG_FILE="/var/log/webhook-deploy.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') [DEPLOY] $1" >> "$LOG_FILE"
}

log "========== 开始部署 =========="

cd "$PROJECT_DIR"

# 拉取最新代码
log "git pull..."
git pull origin main 2>&1 | while read line; do log "  $line"; done

# 构建前端
log "npm install..."
cd "$PROJECT_DIR/web"
npm install --silent 2>&1 | tail -3 | while read line; do log "  $line"; done

log "npm run build..."
npm run build 2>&1 | tail -5 | while read line; do log "  $line"; done

# 重载 Nginx
log "nginx reload..."
nginx -s reload 2>&1 | while read line; do log "  $line"; done

log "========== 部署完成 =========="

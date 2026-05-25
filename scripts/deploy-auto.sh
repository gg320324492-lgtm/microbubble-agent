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

# 拉取最新代码（重试3次）
log "git pull..."
PULL_OK=0
for i in 1 2 3; do
    log "  第${i}次尝试..."
    if git pull origin main >> "$LOG_FILE" 2>&1; then
        PULL_OK=1
        log "  pull 成功"
        break
    fi
    sleep $((i * 2))
done

if [ $PULL_OK -eq 0 ]; then
    log "ERROR: git pull 失败，跳过本次部署"
    log "========== 部署中止 =========="
    exit 1
fi

# 检查可用磁盘空间（至少 500MB）
AVAILABLE_MB=$(df -m /opt | tail -1 | awk '{print $4}')
if [ "$AVAILABLE_MB" -lt 500 ]; then
    log "ERROR: 磁盘空间不足 (${AVAILABLE_MB}MB)，跳过构建"
    log "========== 部署中止 =========="
    exit 1
fi

# 构建前端
log "npm install..."
cd "$PROJECT_DIR/web"
npm install --silent >> "$LOG_FILE" 2>&1

log "npm run build..."
npm run build >> "$LOG_FILE" 2>&1

# 验证构建产物
if [ ! -f "$PROJECT_DIR/web/dist/index.html" ]; then
    log "ERROR: npm build 失败，dist/index.html 不存在"
    log "========== 部署中止 =========="
    exit 1
fi

# 测试 nginx 配置有效性
nginx -t >> "$LOG_FILE" 2>&1

# 重载 Nginx
log "nginx reload..."
nginx -s reload >> "$LOG_FILE" 2>&1

log "========== 部署完成 =========="

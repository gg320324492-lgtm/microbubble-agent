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

# 丢弃所有本地修改，确保干净状态
git checkout -- . >> "$LOG_FILE" 2>&1 || true
git clean -fd >> "$LOG_FILE" 2>&1 || true

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
set +e  # 构建失败不应中止脚本 — 需要走降级逻辑
npm run build >> "$LOG_FILE" 2>&1
BUILD_EXIT=$?
set -e

# 验证构建产物 — 检查 main JS 文件是否存在（不仅仅是 index.html）
MAIN_JS=""
if [ -f "$PROJECT_DIR/web/dist/index.html" ]; then
    MAIN_JS=$(grep -oP 'src="/assets/index-\w+\.js"' "$PROJECT_DIR/web/dist/index.html" | head -1 | sed 's|src="/||;s|"||')
fi

if [ "$BUILD_EXIT" -ne 0 ] || [ ! -f "$PROJECT_DIR/web/dist/$MAIN_JS" ]; then
    log "WARN: npm build 失败或产物不完整，回退到 git 已提交的 dist"
    # 恢复 git 中最后一次提交的 dist（如果 git 中有的话）
    cd "$PROJECT_DIR"
    git checkout -- web/dist/ 2>/dev/null || true
    if [ -f "$PROJECT_DIR/web/dist/index.html" ]; then
        log "已从 git 恢复旧版本 dist，跳过构建步骤继续部署"
    else
        log "ERROR: git 中也无可用 dist，部署中止"
        log "========== 部署中止 =========="
        exit 1
    fi
fi

# 测试 nginx 配置有效性
nginx -t >> "$LOG_FILE" 2>&1

# 重载 Nginx
log "nginx reload..."
nginx -s reload >> "$LOG_FILE" 2>&1

log "========== 部署完成 =========="

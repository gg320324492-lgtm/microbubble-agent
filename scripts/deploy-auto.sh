#!/bin/bash
# 自动部署脚本 — 由 webhook 触发
# 拉取代码 → 重载 Nginx（前端在本地构建，dist 由 git 提交）

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

# 拉取最新代码（重试 5 次 + 指数退避，2026-06-02 加固）
# 背景：阿里云服务器偶发无法连接 GitHub（TLS/GnuTLS 错误或超时），
# 一次重试不够稳定，加 5 次重试 + 指数退避 + GCM 加密协商回退。
log "git pull..."
PULL_OK=0
MAX_RETRY=5
for i in $(seq 1 $MAX_RETRY); do
    log "  第${i}/${MAX_RETRY}次尝试..."
    # 用 HTTP/1.1 强制 + 关闭 GCM 加密（有些 GCM 模式在阿里云上 TLS 协商失败）
    if GIT_HTTP_LOW_SPEED_LIMIT=1000 GIT_HTTP_LOW_SPEED_TIME=30 \
       git -c http.version=HTTP/1.1 -c http.sslVersion=tlsv1.2 \
           pull origin main >> "$LOG_FILE" 2>&1; then
        PULL_OK=1
        log "  pull 成功"
        break
    fi
    # 指数退避：5s, 10s, 20s, 40s（总等待 75s）
    BACKOFF=$((5 * (2 ** (i - 1))))
    log "  pull 失败，${BACKOFF}s 后重试（GitHub TLS 偶发错误）"
    sleep $BACKOFF
done

if [ $PULL_OK -eq 0 ]; then
    # 2026-06-02 修复：git pull 失败时尝试 fetch + reset --hard origin/main（绕开合并冲突）
    log "WARN: git pull 5 次都失败，尝试 fetch + reset 模式..."
    if git fetch origin main >> "$LOG_FILE" 2>&1 && \
       git reset --hard origin/main >> "$LOG_FILE" 2>&1; then
        PULL_OK=1
        log "  fetch + reset 成功"
    else
        log "ERROR: git pull/fetch 都失败，跳过本次部署"
        log "========== 部署中止 =========="
        exit 1
    fi
fi

# 检查可用磁盘空间（至少 500MB）
AVAILABLE_MB=$(df -m /opt | tail -1 | awk '{print $4}')
if [ "$AVAILABLE_MB" -lt 500 ]; then
    log "ERROR: 磁盘空间不足 (${AVAILABLE_MB}MB)，部署中止"
    log "========== 部署中止 =========="
    exit 1
fi

# 使用 git 已提交的 dist（不在服务器上构建，避免 2核2G OOM）
cd "$PROJECT_DIR"
if [ ! -f "$PROJECT_DIR/web/dist/index.html" ]; then
    log "ERROR: dist/index.html 不存在，部署中止"
    log "========== 部署中止 =========="
    exit 1
fi

# 同步 Nginx 配置（tunnel.conf → /etc/nginx/conf.d/default.conf）
# 注意：此步骤在 git pull 之后执行，配置变更下次部署生效
if [ -f "$PROJECT_DIR/nginx/conf.d/tunnel.conf" ]; then
    cp "$PROJECT_DIR/nginx/conf.d/tunnel.conf" /etc/nginx/conf.d/default.conf
    log "nginx config synced"
fi

# 测试 nginx 配置有效性
nginx -t >> "$LOG_FILE" 2>&1

# 重载 Nginx
log "nginx reload..."
nginx -s reload >> "$LOG_FILE" 2>&1

log "========== 部署完成 =========="

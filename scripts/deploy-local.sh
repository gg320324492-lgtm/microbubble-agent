#!/bin/bash

# MicroBubble Agent - 本地电脑部署脚本
# 部署全部服务 (Docker)
# SSH tunnel 启动另见 tunnel/README.md (Windows 用 start-ssh-tunnel.ps1 + Task Scheduler)
# 用法: bash scripts/deploy-local.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DOMAIN="agent.mnb-lab.cn"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo "=================================="
echo "MicroBubble Agent - 本地部署"
echo "项目目录: $PROJECT_DIR"
echo "=================================="

# ============================================
# 1. 检查 Docker
# ============================================
if ! docker compose version &> /dev/null && ! docker-compose version &> /dev/null; then
    error "未安装 Docker。请先安装 Docker Desktop: https://www.docker.com/products/docker-desktop/"
fi
info "Docker 已安装"

# ============================================
# 2. 配置环境变量
# ============================================
cd "$PROJECT_DIR"

if [ ! -f .env ]; then
    info "创建 .env 文件..."
    cp .env.example .env

    # 生成随机 SECRET_KEY
    if command -v openssl &> /dev/null; then
        SECRET_KEY=$(openssl rand -hex 32)
    else
        SECRET_KEY=$(head -c 32 /dev/urandom | base64 | tr -d '/+=' | head -c 64)
    fi

    # Windows sed 语法
    sed -i "s/change-this-a-random-string/$SECRET_KEY/" .env 2>/dev/null || \
    sed -i "" "s/change-this-a-random-string/$SECRET_KEY/" .env 2>/dev/null

    warn "请编辑 .env 文件，填入以下配置："
    echo "  CLAUDE_API_KEY=your-claude-api-key-here"
    echo "  CLAUDE_BASE_URL=https://token-plan-cn.xiaomimimo.com/anthropic"
    echo ""
    read -p "按 Enter 继续（已配置好 .env）或 Ctrl+C 退出..."
fi

# ============================================
# 3. 构建前端
# ============================================
build_frontend() {
    cd "$PROJECT_DIR/web"

    if [ ! -d "node_modules" ]; then
        info "安装前端依赖..."
        npm install
    fi

    info "构建前端..."
    npm run build
    info "前端构建完成"
}

# ============================================
# 6. 启动 Docker 服务
# ============================================
start_services() {
    cd "$PROJECT_DIR"

    # 确定 compose 命令
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    # 创建必要目录
    mkdir -p data/{postgres,redis,minio} logs models

    # 不需要 nginx 服务（nginx 在云服务器上）
    # 创建一个不含 nginx 的 compose override
    cat > docker-compose.override.yml << 'EOF'
# 本地部署：禁用 nginx 服务（nginx 在云服务器上运行）
services:
  nginx:
    profiles:
      - disabled
EOF

    info "构建 Docker 镜像（首次可能需要 10-15 分钟）..."
    $COMPOSE_CMD build

    info "启动服务..."
    $COMPOSE_CMD up -d

    info "等待服务就绪..."
    sleep 15

    info "初始化数据库..."
    $COMPOSE_CMD exec -T app python scripts/init_db.py || warn "数据库可能已初始化"

    info "运行数据库迁移..."
    $COMPOSE_CMD exec -T app alembic upgrade head || warn "迁移可能已执行"

    echo ""
    info "服务状态:"
    $COMPOSE_CMD ps
}

# ============================================
# 主流程
# ============================================
echo ""
info "步骤 1/4: 检查环境"
echo ""

info "步骤 2/4: 配置环境变量"
if [ ! -f .env ]; then
    warn "请先编辑 .env 文件，然后重新运行此脚本"
    exit 1
fi

echo ""
info "步骤 3/4: 构建前端 + 启动 Docker 服务"
build_frontend
start_services

echo ""
echo "=================================="
echo "本地 Docker 部署完成！"
echo "=================================="
echo ""
echo "下一步: 启用 SSH tunnel 让云端能访问本地服务"
echo "  Windows:  powershell tunnel/start-ssh-tunnel.ps1"
echo "  详细文档: tunnel/README.md"
echo ""
echo "访问地址: https://$DOMAIN"
echo ""

echo ""
echo "=================================="
echo "本地部署完成！"
echo "=================================="
echo ""
echo "访问地址: https://$DOMAIN"
echo ""
echo "FRP 隧道: 本地 8000 端口 -> 云服务器 8000 端口"
echo "Docker 服务: app, db, redis, minio, whisper, celery-worker, celery-beat"
echo ""
echo "常用命令:"
echo "  查看日志: docker compose logs -f app"
echo "  停止服务: docker compose down"
echo "  重启服务: docker compose restart"
echo ""

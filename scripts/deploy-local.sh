#!/bin/bash

# MicroBubble Agent - 本地电脑部署脚本
# 部署全部服务（Docker + FRP 客户端）
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
    echo "  CLAUDE_API_KEY=tp-c2dh4lwgx2519tsuoffa8npxfcqofbiyaew94pwt4bc5yjlq"
    echo "  CLAUDE_BASE_URL=https://token-plan-cn.xiaomimimo.com/anthropic"
    echo ""
    read -p "按 Enter 继续（已配置好 .env）或 Ctrl+C 退出..."
fi

# ============================================
# 3. 安装 FRP 客户端
# ============================================
install_frp() {
    if [ -f "$PROJECT_DIR/frp/frpc.exe" ] || command -v frpc &> /dev/null; then
        info "FRP 客户端已安装"
        return
    fi

    info "下载 FRP 客户端..."
    FRP_VERSION="0.61.1"

    cd "$PROJECT_DIR/frp"

    if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
        # Windows
        FRP_FILE="frp_${FRP_VERSION}_windows_amd64.zip"
        wget -q "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/${FRP_FILE}" -O frp.zip 2>/dev/null || \
        curl -sL "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/${FRP_FILE}" -o frp.zip

        if command -v unzip &> /dev/null; then
            unzip -o frp.zip
        else
            echo "请手动解压 frp.zip 到 frp/ 目录"
        fi
        cp "frp_${FRP_VERSION}_windows_amd64/frpc.exe" . 2>/dev/null || true
        rm -f frp.zip
        rm -rf "frp_${FRP_VERSION}_windows_amd64"
        info "FRP 客户端下载完成: $PROJECT_DIR/frp/frpc.exe"
    else
        # Linux/Mac
        FRP_FILE="frp_${FRP_VERSION}_linux_amd64.tar.gz"
        wget -q "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/${FRP_FILE}" -O frp.tar.gz
        tar xzf frp.tar.gz
        cp "frp_${FRP_VERSION}_linux_amd64/frpc" .
        rm -f frp.tar.gz
        rm -rf "frp_${FRP_VERSION}_linux_amd64"
        info "FRP 客户端下载完成"
    fi
}

# ============================================
# 4. 启动 FRP 客户端
# ============================================
start_frp() {
    info "启动 FRP 客户端..."

    cd "$PROJECT_DIR/frp"

    if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "cygwin"* ]] || [[ "$OSTYPE" == "win32"* ]]; then
        # Windows - 后台启动
        if [ -f frpc.exe ]; then
            start //B frpc.exe -c frpc.toml
            info "FRP 客户端已启动（后台）"
        else
            warn "frpc.exe 未找到，请手动启动: frp/frpc.exe -c frp/frpc.toml"
        fi
    else
        # Linux/Mac - 后台启动
        nohup ./frpc -c frpc.toml > frpc.log 2>&1 &
        info "FRP 客户端已启动（PID: $!）"
    fi
}

# ============================================
# 5. 构建前端
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
version: '3.8'
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
info "步骤 1/5: 检查环境"
echo ""

info "步骤 2/5: 安装 FRP 客户端"
install_frp

echo ""
info "步骤 3/5: 配置环境变量"
if [ ! -f .env ]; then
    warn "请先编辑 .env 文件，然后重新运行此脚本"
    exit 1
fi

echo ""
info "步骤 4/5: 启动 FRP 客户端"
start_frp

echo ""
info "步骤 5/5: 启动 Docker 服务"
build_frontend
start_services

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

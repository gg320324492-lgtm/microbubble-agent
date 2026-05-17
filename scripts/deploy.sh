#!/bin/bash

# MicroBubble Agent - 服务器部署脚本
# 用法: bash scripts/deploy.sh

set -e

DOMAIN="agent.mnb-lab.cn"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "=================================="
echo "MicroBubble Agent 部署脚本"
echo "域名: $DOMAIN"
echo "项目目录: $PROJECT_DIR"
echo "=================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ============================================
# 1. 安装 Docker
# ============================================
install_docker() {
    if command -v docker &> /dev/null; then
        info "Docker 已安装: $(docker --version)"
    else
        info "安装 Docker..."
        curl -fsSL https://get.docker.com | sh
        sudo systemctl enable docker
        sudo systemctl start docker
        info "Docker 安装完成"
    fi

    if docker compose version &> /dev/null; then
        info "Docker Compose 已安装: $(docker compose version)"
    elif command -v docker-compose &> /dev/null; then
        info "Docker Compose (旧版) 已安装"
    else
        info "安装 Docker Compose 插件..."
        sudo apt-get update
        sudo apt-get install -y docker-compose-plugin
        info "Docker Compose 安装完成"
    fi
}

# ============================================
# 2. 安装 Certbot (SSL 证书)
# ============================================
install_certbot() {
    if command -v certbot &> /dev/null; then
        info "Certbot 已安装"
    else
        info "安装 Certbot..."
        sudo apt-get update
        sudo apt-get install -y certbot
        info "Certbot 安装完成"
    fi
}

# ============================================
# 3. 配置环境变量
# ============================================
setup_env() {
    cd "$PROJECT_DIR"

    if [ -f .env ]; then
        warn ".env 文件已存在，跳过创建"
        warn "如需重新配置，请先删除 .env 文件"
    else
        info "创建 .env 文件..."
        cp .env.example .env

        # 生成随机 SECRET_KEY
        SECRET_KEY=$(openssl rand -hex 32)
        sed -i "s/change-this-to-a-random-string/$SECRET_KEY/" .env

        warn "请编辑 .env 文件配置以下必填项："
        echo "  - CLAUDE_API_KEY (Claude API 密钥)"
        echo "  - WECHAT_* (企业微信配置，如需要)"
        echo "  - TENCENT_MEETING_* (腾讯会议配置，如需要)"
        echo ""
        read -p "按 Enter 继续（已配置好 .env）或 Ctrl+C 退出去编辑 .env..."
    fi
}

# ============================================
# 4. 构建前端
# ============================================
build_frontend() {
    cd "$PROJECT_DIR/web"

    if [ ! -d "node_modules" ]; then
        info "安装前端依赖..."
        npm install
    fi

    info "构建前端..."
    npm run build
    info "前端构建完成: web/dist/"
}

# ============================================
# 5. 首次部署（HTTP 模式）
# ============================================
deploy_http() {
    cd "$PROJECT_DIR"

    # 创建必要目录
    mkdir -p data/{postgres,redis,minio} logs models nginx/ssl
    mkdir -p /var/www/certbot

    # 使用 HTTP 配置启动 nginx
    info "使用 HTTP 配置启动服务..."
    cp nginx/conf.d/default-http.conf nginx/conf.d/default.conf

    # 构建并启动
    docker compose build
    docker compose up -d

    # 等待服务就绪
    info "等待服务就绪..."
    sleep 15

    # 初始化数据库
    info "初始化数据库..."
    docker compose exec -T app python scripts/init_db.py || warn "数据库可能已初始化，跳过"

    info "HTTP 部署完成！"
    info "访问: http://$DOMAIN"
}

# ============================================
# 6. 申请 SSL 证书
# ============================================
setup_ssl() {
    cd "$PROJECT_DIR"

    if [ -f nginx/ssl/fullchain.pem ]; then
        info "SSL 证书已存在，跳过申请"
        return
    fi

    info "申请 SSL 证书..."

    # 停止 nginx 释放 80 端口
    docker compose stop nginx

    # 使用 standalone 模式申请证书
    sudo certbot certonly --standalone \
        -d "$DOMAIN" \
        --non-interactive \
        --agree-tos \
        --email admin@mnb-lab.cn \
        --preferred-challenges http

    # 复制证书到项目目录
    sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem nginx/ssl/
    sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem nginx/ssl/
    sudo chmod 644 nginx/ssl/*.pem

    # 切换到 HTTPS 配置
    info "切换到 HTTPS 配置..."
    cp nginx/conf.d/default.conf.https nginx/conf.d/default.conf 2>/dev/null || \
    cat > nginx/conf.d/default.conf << 'NGINX_CONF'
# HTTP -> HTTPS 重定向
server {
    listen 80;
    server_name agent.mnb-lab.cn;
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS 主配置
server {
    listen 443 ssl;
    server_name agent.mnb-lab.cn;

    ssl_certificate     /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    add_header X-Frame-Options SAMEORIGIN;
    add_header X-Content-Type-Options nosniff;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://app:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_send_timeout 5s;
        proxy_read_timeout 5s;
    }

    location /ws {
        proxy_pass http://app:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
NGINX_CONF

    # 重启 nginx
    docker compose start nginx

    info "SSL 配置完成！"
    info "访问: https://$DOMAIN"
}

# ============================================
# 7. 设置证书自动续期
# ============================================
setup_cert_renewal() {
    info "设置证书自动续期..."

    # 创建续期脚本
    cat > /tmp/renew-cert.sh << 'RENEW_SCRIPT'
#!/bin/bash
certbot renew --pre-hook "cd PROJECT_DIR && docker compose stop nginx" --post-hook "cd PROJECT_DIR && docker compose start nginx"
RENEW_SCRIPT

    sed -i "s|PROJECT_DIR|$PROJECT_DIR|g" /tmp/renew-cert.sh
    sudo mv /tmp/renew-cert.sh /usr/local/bin/renew-microbubble-cert.sh
    sudo chmod +x /usr/local/bin/renew-microbubble-cert.sh

    # 添加 cron 任务（每天凌晨 3 点检查）
    (crontab -l 2>/dev/null; echo "0 3 * * * /usr/local/bin/renew-microbubble-cert.sh >> /var/log/cert-renewal.log 2>&1") | crontab -

    info "证书自动续期已配置（每天凌晨 3 点检查）"
}

# ============================================
# 主流程
# ============================================
main() {
    echo ""
    info "步骤 1/6: 检查 Docker 环境"
    install_docker

    echo ""
    info "步骤 2/6: 检查 Certbot"
    install_certbot

    echo ""
    info "步骤 3/6: 配置环境变量"
    setup_env

    echo ""
    info "步骤 4/6: 构建前端"
    build_frontend

    echo ""
    info "步骤 5/6: 部署服务（HTTP 模式）"
    deploy_http

    echo ""
    info "步骤 6/6: 配置 SSL"
    read -p "是否现在申请 SSL 证书？(y/n): " setup_ssl_now
    if [ "$setup_ssl_now" = "y" ] || [ "$setup_ssl_now" = "Y" ]; then
        setup_ssl
        setup_cert_renewal
    else
        warn "跳过 SSL 配置，系统以 HTTP 模式运行"
        warn "稍后可运行: bash scripts/setup-ssl.sh"
    fi

    echo ""
    echo "=================================="
    echo "部署完成！"
    echo "=================================="
    echo ""
    echo "服务状态:"
    docker compose ps
    echo ""
    echo "访问地址:"
    if [ -f nginx/ssl/fullchain.pem ]; then
        echo "  - Web界面: https://$DOMAIN"
    else
        echo "  - Web界面: http://$DOMAIN"
    fi
    echo "  - API文档: http(s)://$DOMAIN/docs"
    echo ""
    echo "常用命令:"
    echo "  - 查看日志: docker compose logs -f app"
    echo "  - 停止服务: docker compose down"
    echo "  - 重启服务: docker compose restart"
    echo "  - 申请SSL:  bash scripts/setup-ssl.sh"
    echo ""
}

main "$@"

#!/bin/bash

# MicroBubble Agent - 云服务器部署脚本（轻量版）
# 只部署 Nginx + FRP 服务端，应用服务通过隧道连接本地电脑
# 用法: sudo bash scripts/deploy-cloud.sh

set -e

DOMAIN="agent.mnb-lab.cn"
PROJECT_DIR="/opt/microbubble-agent"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo "=================================="
echo "MicroBubble Agent - 云服务器部署"
echo "域名: $DOMAIN"
echo "=================================="

# ============================================
# 1. 安装 Nginx
# ============================================
if command -v nginx &> /dev/null; then
    info "Nginx 已安装"
else
    info "安装 Nginx..."
    apt-get update
    apt-get install -y nginx
    systemctl enable nginx
    info "Nginx 安装完成"
fi

# ============================================
# 2. 安装 FRP 服务端
# ============================================
install_frp() {
    if command -v frps &> /dev/null; then
        info "FRP 已安装"
        return
    fi

    info "安装 FRP..."
    FRP_VERSION="0.61.1"
    ARCH="amd64"

    cd /tmp
    wget -q "https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_${ARCH}.tar.gz" -O frp.tar.gz || \
    wget -q "https://ghproxy.com/https://github.com/fatedier/frp/releases/download/v${FRP_VERSION}/frp_${FRP_VERSION}_linux_${ARCH}.tar.gz" -O frp.tar.gz

    tar xzf frp.tar.gz
    cp "frp_${FRP_VERSION}_linux_${ARCH}/frps" /usr/local/bin/
    chmod +x /usr/local/bin/frps
    rm -rf frp.tar.gz "frp_${FRP_VERSION}_linux_${ARCH}"

    info "FRP 安装完成"
}

# ============================================
# 3. 配置 FRP 服务端
# ============================================
setup_frps() {
    info "配置 FRP 服务端..."

    mkdir -p /etc/frp
    cp "$PROJECT_DIR/frp/frps.toml" /etc/frp/frps.toml

    # 创建 systemd 服务
    cat > /etc/systemd/system/frps.service << 'EOF'
[Unit]
Description=FRP Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/frps -c /etc/frp/frps.toml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable frps
    systemctl restart frps

    info "FRP 服务端已启动（端口 7000）"
}

# ============================================
# 4. 配置 Nginx
# ============================================
setup_nginx() {
    info "配置 Nginx..."

    # 构建前端
    if [ ! -d "$PROJECT_DIR/web/dist" ]; then
        info "构建前端..."
        cd "$PROJECT_DIR/web"
        npm install
        npm run build
    fi

    # 创建 SSL 目录
    mkdir -p /etc/nginx/ssl
    mkdir -p /var/www/certbot

    # 先用 HTTP 配置启动
    cat > /etc/nginx/conf.d/default.conf << 'EOF'
server {
    listen 80;
    server_name agent.mnb-lab.cn;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    root /opt/microbubble-agent/web/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 5s;
        proxy_send_timeout 30s;
        proxy_read_timeout 30s;
    }

    location /ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
EOF

    # 删除默认站点
    rm -f /etc/nginx/sites-enabled/default

    nginx -t && systemctl reload nginx
    info "Nginx 配置完成"
}

# ============================================
# 5. 配置防火墙
# ============================================
setup_firewall() {
    info "配置防火墙..."

    if command -v ufw &> /dev/null; then
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw allow 7000/tcp
        ufw allow 7500/tcp
        info "防火墙规则已添加"
    else
        warn "未检测到 ufw，请手动开放端口: 80, 443, 7000, 7500"
    fi
}

# ============================================
# 6. 申请 SSL 证书
# ============================================
setup_ssl() {
    if [ -f /etc/nginx/ssl/fullchain.pem ]; then
        info "SSL 证书已存在"
        return
    fi

    info "申请 SSL 证书..."

    if ! command -v certbot &> /dev/null; then
        apt-get install -y certbot
    fi

    systemctl stop nginx
    certbot certonly --standalone -d "$DOMAIN" --non-interactive --agree-tos --email admin@mnb-lab.cn
    cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem /etc/nginx/ssl/
    cp /etc/letsencrypt/live/$DOMAIN/privkey.pem /etc/nginx/ssl/
    chmod 644 /etc/nginx/ssl/*.pem

    # 切换到 HTTPS 配置
    cp "$PROJECT_DIR/nginx/conf.d/tunnel.conf" /etc/nginx/conf.d/default.conf
    systemctl start nginx

    # 自动续期
    cat > /usr/local/bin/renew-cert.sh << RENEW
#!/bin/bash
certbot renew --pre-hook "systemctl stop nginx" --post-hook "systemctl start nginx"
RENEW
    chmod +x /usr/local/bin/renew-cert.sh
    (crontab -l 2>/dev/null; echo "0 3 * * * /usr/local/bin/renew-cert.sh >> /var/log/cert-renewal.log 2>&1") | crontab -

    info "SSL 配置完成"
}

# ============================================
# 主流程
# ============================================
echo ""
info "步骤 1/5: 安装 Nginx"
echo ""

info "步骤 2/5: 安装 FRP"
install_frp

echo ""
info "步骤 3/5: 配置 FRP 服务端"
setup_frps

echo ""
info "步骤 4/5: 配置 Nginx"
setup_nginx

echo ""
info "步骤 5/5: 配置防火墙"
setup_firewall

echo ""
read -p "是否申请 SSL 证书？(y/n): " ssl_choice
if [ "$ssl_choice" = "y" ] || [ "$ssl_choice" = "Y" ]; then
    setup_ssl
fi

echo ""
echo "=================================="
echo "云服务器部署完成！"
echo "=================================="
echo ""
echo "FRP 服务端状态:"
systemctl status frps --no-pager -l | head -5
echo ""
echo "Nginx 状态:"
systemctl status nginx --no-pager -l | head -5
echo ""
echo "下一步：在本地电脑上运行 deploy-local.sh"
echo "=================================="

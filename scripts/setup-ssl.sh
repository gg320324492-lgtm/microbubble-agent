#!/bin/bash

# MicroBubble Agent - SSL 证书申请脚本
# 用法: bash scripts/setup-ssl.sh

set -e

DOMAIN="agent.mnb-lab.cn"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}[INFO]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

echo "=================================="
echo "SSL 证书申请"
echo "域名: $DOMAIN"
echo "=================================="

cd "$PROJECT_DIR"

# 检查 certbot
if ! command -v certbot &> /dev/null; then
    info "安装 Certbot..."
    sudo apt-get update
    sudo apt-get install -y certbot
fi

# 创建目录
mkdir -p nginx/ssl
sudo mkdir -p /var/www/certbot

# 停止 nginx 释放 80 端口
info "停止 nginx 服务..."
docker compose stop nginx

# 申请证书
info "申请 SSL 证书..."
sudo certbot certonly --standalone \
    -d "$DOMAIN" \
    --non-interactive \
    --agree-tos \
    --email admin@mnb-lab.cn \
    --preferred-challenges http

# 复制证书
info "复制证书到项目目录..."
sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem nginx/ssl/
sudo chmod 644 nginx/ssl/*.pem

# 切换 nginx 配置
info "切换到 HTTPS 配置..."
cat > nginx/conf.d/default.conf << 'NGINX_CONF'
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
info "重启 nginx..."
docker compose start nginx

# 设置自动续期
info "设置证书自动续期..."
cat > /tmp/renew-cert.sh << 'RENEW_SCRIPT'
#!/bin/bash
certbot renew --pre-hook "cd PROJECT_DIR && docker compose stop nginx" --post-hook "cd PROJECT_DIR && docker compose start nginx"
RENEW_SCRIPT
sed -i "s|PROJECT_DIR|$PROJECT_DIR|g" /tmp/renew-cert.sh
sudo mv /tmp/renew-cert.sh /usr/local/bin/renew-microbubble-cert.sh
sudo chmod +x /usr/local/bin/renew-microbubble-cert.sh
(crontab -l 2>/dev/null; echo "0 3 * * * /usr/local/bin/renew-microbubble-cert.sh >> /var/log/cert-renewal.log 2>&1") | crontab -

echo ""
echo "=================================="
echo "SSL 配置完成！"
echo "=================================="
echo ""
echo "访问: https://$DOMAIN"
echo "证书自动续期: 每天凌晨 3 点检查"
echo ""

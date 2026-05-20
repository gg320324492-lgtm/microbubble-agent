# MicroBubble Agent 部署文档

> 适用于"小气"微纳米气泡课题组智能 Agent 系统的生产环境部署。

## 架构概览

```
用户浏览器
    │
    ▼
云服务器 (2核 2G, 公网IP)
├── Nginx (80/443) ─── SSL 证书 + 反向代理
└── FRP 服务端 (7000) ─── 隧道转发
    │
    ▼ (FRP 隧道, 端口 8000)
本地电脑 (有 GPU)
├── app (FastAPI, 8000)
├── PostgreSQL (5432)
├── Redis (6379)
├── MinIO (9000/9001)
├── Whisper GPU (8002)
├── Celery Worker
└── Celery Beat
```

- **云服务器**：只跑 Nginx + FRP 服务端，轻量无压力
- **本地电脑**：运行全部 Docker 服务，通过 FRP 隧道暴露 8000 端口
- **域名**：`agent.mnb-lab.cn`，HTTPS 访问

---

## 前置条件

### 云服务器

- 2 核 2G 内存以上（阿里云 ECS 即可）
- 公网 IP + 域名已解析到该 IP
- 开放端口：80、443、7000（FRP）
- 操作系统：Ubuntu 22.04 / Debian 12

### 本地电脑

- Windows 10/11 或 Linux
- Docker Desktop 已安装
- NVIDIA GPU + 驱动（用于 Whisper 语音识别）
- 能访问外网（需要拉取 Docker 镜像和调用 Claude API）

### 账号权限

- 企业微信管理员权限（用于创建应用、配置回调）
- GitHub 仓库访问权限

---

## 一、云服务器部署

### 1.1 安装 Nginx

```bash
sudo apt update && sudo apt install -y nginx
sudo systemctl enable nginx && sudo systemctl start nginx
```

### 1.2 安装 FRP 服务端

```bash
# 下载 FRP（以 v0.61.1 为例）
wget https://github.com/fatedier/frp/releases/download/v0.61.1/frp_0.61.1_linux_amd64.tar.gz
tar xzf frp_0.61.1_linux_amd64.tar.gz
sudo cp frp_0.61.1_linux_amd64/frps /usr/local/bin/

# 创建配置目录
sudo mkdir -p /etc/frp

# 配置文件（修改 token 为你自己的密钥）
sudo cat > /etc/frp/frps.toml << 'EOF'
bindPort = 7000
auth.token = "你的FRP密钥"

webServer.addr = "127.0.0.1"
webServer.port = 7500
webServer.user = "admin"
webServer.password = "你的FRP面板密码"
EOF

# 创建 systemd 服务
sudo cat > /etc/systemd/system/frps.service << 'EOF'
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

sudo systemctl daemon-reload
sudo systemctl enable frps && sudo systemctl start frps
```

### 1.3 SSL 证书

```bash
sudo apt install -y certbot

# 停止 Nginx 释放 80 端口
sudo systemctl stop nginx

# 申请证书
sudo certbot certonly --standalone -d agent.mnb-lab.cn

# 证书文件位置
# /etc/letsencrypt/live/agent.mnb-lab.cn/fullchain.pem
# /etc/letsencrypt/live/agent.mnb-lab.cn/privkey.pem

# 创建 SSL 目录并复制证书
sudo mkdir -p /opt/microbubble-agent/nginx/ssl
sudo cp /etc/letsencrypt/live/agent.mnb-lab.cn/fullchain.pem /opt/microbubble-agent/nginx/ssl/
sudo cp /etc/letsencrypt/live/agent.mnb-lab.cn/privkey.pem /opt/microbubble-agent/nginx/ssl/

# 设置自动续期（每天凌晨 3 点检查）
echo "0 3 * * * root certbot renew --quiet && cp /etc/letsencrypt/live/agent.mnb-lab.cn/*.pem /opt/microbubble-agent/nginx/ssl/ && nginx -s reload" | sudo tee /etc/cron.d/certbot-renew

sudo systemctl start nginx
```

### 1.4 部署前端 + Nginx 配置

```bash
# 创建项目目录
sudo mkdir -p /opt/microbubble-agent/web/dist
sudo mkdir -p /opt/microbubble-agent/nginx/conf.d

# 复制 Nginx 配置（使用 tunnel.conf 模式，代理到 FRP 隧道）
sudo cp nginx/conf.d/tunnel.conf /opt/microbubble-agent/nginx/conf.d/default.conf
sudo cp nginx/nginx.conf /opt/microbubble-agent/nginx/nginx.conf

# 部署前端（从本地构建后上传）
# 方式一：本地构建后 scp 上传
# cd web && npm run build && scp -r dist/* user@server:/opt/microbubble-agent/web/dist/

# 方式二：在服务器上构建
cd /opt/microbubble-agent
git clone https://github.com/your-repo/microbubble-agent.git temp
cd temp/web && npm install && npm run build
cp -r dist/* /opt/microbubble-agent/web/dist/
cd /opt && rm -rf temp

# 配置 Nginx
sudo ln -sf /opt/microbubble-agent/nginx/nginx.conf /etc/nginx/nginx.conf
sudo ln -sf /opt/microbubble-agent/nginx/conf.d /etc/nginx/conf.d
sudo nginx -t && sudo nginx -s reload
```

### 1.5 防火墙

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 7000/tcp
sudo ufw enable
```

---

## 二、本地电脑部署

### 2.1 安装 Docker Desktop

Windows 用户从 [Docker 官网](https://www.docker.com/products/docker-desktop/) 下载安装，确保 WSL2 后端已启用。

### 2.2 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入以下关键配置：

```env
# 数据库
POSTGRES_PASSWORD=你的数据库密码

# Claude API
CLAUDE_API_KEY=sk-xxx
CLAUDE_BASE_URL=https://your-proxy.com  # API 代理地址（可选）

# 企业微信
WECHAT_CORP_ID=wwxxxxxxxxxxxxxx
WECHAT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
WECHAT_AGENT_ID=1000002
WECHAT_CALLBACK_TOKEN=your_callback_token
WECHAT_ENCODING_AES_KEY=your_encoding_aes_key

# MinIO
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=你的MinIO密码

# 安全
SECRET_KEY=随机生成的32位字符串
```

### 2.3 一键启动

```bash
# Windows
start.bat

# 或手动
docker compose up -d
```

启动后会自动：
- 拉取并构建所有镜像
- 启动 7 个服务（app、db、redis、minio、whisper、celery-worker、celery-beat）
- 等待 db 和 redis 健康检查通过后启动 app

### 2.4 初始化数据库

```bash
# 首次部署需要初始化
docker compose exec app python scripts/init_db.py

# 或运行迁移
docker compose exec app alembic upgrade head
```

### 2.5 启动 FRP 客户端

编辑 `frp/frpc.toml`，修改服务器地址和 token：

```toml
serverAddr = "你的云服务器IP"
serverPort = 7000

[auth]
token = "你的FRP密钥（与服务端一致）"

[[proxies]]
name = "microbubble-agent"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8000
remotePort = 8000
```

启动 FRP：

```bash
cd frp
./frpc.exe -c frpc.toml
```

### 2.6 验证部署

```bash
# 检查服务状态
docker compose ps

# 检查 API 响应
curl https://agent.mnb-lab.cn/api/v1/health

# 查看日志
docker compose logs -f app
```

---

## 三、企业微信配置

### 3.1 创建应用

1. 登录 [企业微信管理后台](https://work.weixin.qq.com/)
2. 应用管理 → 自建 → 创建应用
3. 填写应用名称（如"小气助手"）、上传 Logo
4. 设置可见范围为全公司
5. 记录 **AgentId**、**Secret**

### 3.2 获取凭据

- **CorpID**：我的企业 → 企业信息
- **Secret**：应用管理 → 自建应用 → 查看 Secret
- **AgentId**：应用管理 → 自建应用 → AgentId

### 3.3 配置回调

1. 应用管理 → 自建应用 → 接收消息 → 设置 API 接收
2. 填写：
   - URL: `https://agent.mnb-lab.cn/api/v1/wechat/callback`
   - Token: 自定义一个 token（填入 `.env` 的 `WECHAT_CALLBACK_TOKEN`）
   - EncodingAESKey: 随机生成（填入 `.env` 的 `WECHAT_ENCODING_AES_KEY`）
3. 勾选事件：用户发送消息、外部联系人变更、客户群变更

### 3.4 微信插件

1. 应用管理 → 自建应用 → 微信插件 → 配置
2. 设置插件名称和 Logo
3. 成员扫码关注后可在普通微信内与机器人对话

### 3.5 成员录入

成员需要在企业微信中注册并绑定身份。系统通过以下方式自动绑定：
- 成员在微信中给机器人发送消息
- 系统通过姓名匹配成员数据库
- 自动绑定 `wechat_id`（企业微信 UserId）

---

## 四、常见问题

### FRP 隧道断连

```bash
# 检查 FRP 客户端是否在运行
tasklist | findstr frpc  # Windows
ps aux | grep frpc       # Linux

# 检查 FRP 服务端状态
sudo systemctl status frps

# 查看 FRP 日志
sudo journalctl -u frps -f
```

### SSL 证书过期

```bash
# 手动续期
sudo certbot renew
sudo cp /etc/letsencrypt/live/agent.mnb-lab.cn/*.pem /opt/microbubble-agent/nginx/ssl/
sudo nginx -s reload
```

### 容器日志查看

```bash
# 查看所有服务日志
docker compose logs -f

# 查看特定服务
docker compose logs -f app
docker compose logs -f db
docker compose logs -f celery-worker

# 查看最近 100 行
docker compose logs --tail 100 app
```

### 数据库连接失败

```bash
# 检查数据库容器状态
docker compose ps db

# 进入数据库容器
docker compose exec db psql -U postgres -d microbubble

# 检查连接
docker compose exec db pg_isready -U postgres
```

### 前端白屏

```bash
# 检查前端文件是否部署
ls /opt/microbubble-agent/web/dist/

# 检查 Nginx 配置
sudo nginx -t

# 重新构建并部署前端
cd web && npm run build
# 上传 dist/ 到服务器
```

---

## 五、运维操作

### 更新部署

```bash
# 本地电脑
git pull origin main
docker compose up -d --build

# 运行数据库迁移（如有新迁移）
docker compose exec app alembic upgrade head
```

### 数据库迁移

```bash
# 查看当前版本
docker compose exec app alembic current

# 升级到最新
docker compose exec app alembic upgrade head

# 回滚一个版本
docker compose exec app alembic downgrade -1
```

### 数据库备份

```bash
# 使用备份脚本
bash scripts/backup_db.sh

# 手动备份
docker compose exec db pg_dump -U postgres microbubble | gzip > backup_$(date +%Y%m%d).sql.gz

# 恢复备份
gunzip < backup_20260520.sql.gz | docker compose exec -T db psql -U postgres microbubble
```

### 查看服务状态

```bash
# Windows
status.bat

# 或手动
docker compose ps
docker compose stats
```

---

## 六、生产环境加固

### Docker 资源限制

在 `docker-compose.yml` 中为各服务添加 `mem_limit`：

```yaml
app:
  mem_limit: 512m

db:
  mem_limit: 512m

redis:
  mem_limit: 256m
```

### Nginx 限流

在 `nginx.conf` 的 `http` 块中添加：

```nginx
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=login:10m rate=5r/m;
```

在 `tunnel.conf` 的 `location /api` 中添加：

```nginx
limit_req zone=api burst=20 nodelay;
```

### 日志管理

生产环境日志位于容器内 `/app/logs/app.log`，通过 volume 映射到宿主机 `./logs/`。

日志格式为 JSON，便于后续接入 ELK 或 Grafana Loki。

```bash
# 查看实时日志
tail -f logs/app.log | jq .

# 按级别过滤
grep '"level": "ERROR"' logs/app.log
```

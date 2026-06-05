# 服务器迁移指南 — 5090 32GB 服务器

> 适用于将 MicroBubble Agent 从当前环境迁移到新的 5090 32GB 服务器

## 迁移概览

```
当前环境                          新环境
────────────────────────────────────────────────────────
本地 Windows + GPU               5090 32GB 服务器
├── Docker Desktop               ├── Docker Engine
├── PostgreSQL                   ├── PostgreSQL
├── Redis                        ├── Redis
├── MinIO                        ├── MinIO
├── Whisper GPU                  ├── Whisper GPU (更强)
├── Celery Worker                ├── Celery Worker
└── Celery Beat                  └── Celery Beat

云服务器 (阿里云 2核2G)           云服务器 (不变)
├── Nginx                        ├── Nginx
└── FRP 服务端                   └── FRP 服务端
```

---

## 一、迁移前准备

### 1.1 新服务器环境检查

```bash
# 检查 GPU
nvidia-smi
# 应显示 RTX 5090 32GB

# 检查 CUDA 版本
nvcc --version
# 建议 CUDA 12.x

# 检查 Docker
docker --version
docker compose version

# 检查磁盘空间
df -h
# 建议 500GB+ 可用空间

# 检查内存
free -h
# 建议 64GB+
```

### 1.2 安装基础依赖

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install -y \
  git curl wget htop tmux \
  nginx certbot python3-certbot-nginx \
  postgresql-client redis-tools

# 安装 Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 安装 NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

---

## 二、数据备份（旧服务器）

### 2.1 数据库备份

```bash
# 在旧服务器执行
cd /opt/microbubble-agent

# PostgreSQL 完整备份
docker exec microbubble-agent-db-1 pg_dump -U postgres microbubble > backup_$(date +%Y%m%d).sql

# 压缩备份
gzip backup_$(date +%Y%m%d).sql
```

### 2.2 文件备份

```bash
# MinIO 数据备份
docker exec microbubble-agent-minio-1 tar czf /tmp/minio_data.tar.gz /data
docker cp microbubble-agent-minio-1:/tmp/minio_data.tar.gz ./minio_data_$(date +%Y%m%d).tar.gz

# 上传文件备份
tar czf uploads_$(date +%Y%m%d).tar.gz uploads/
```

### 2.3 配置备份

```bash
# 环境变量备份
cp .env .env.backup.$(date +%Y%m%d)

# Docker Compose 配置备份
cp docker-compose.yml docker-compose.yml.backup.$(date +%Y%m%d)

# Nginx 配置备份（云服务器）
ssh root@云服务器IP "tar czf /tmp/nginx_conf.tar.gz /etc/nginx/conf.d/"
scp root@云服务器IP:/tmp/nginx_conf.tar.gz ./nginx_conf_$(date +%Y%m%d).tar.gz

# FRP 配置备份（云服务器）
ssh root@云服务器IP "tar czf /tmp/frp_conf.tar.gz /etc/frp/"
scp root@云服务器IP:/tmp/frp_conf.tar.gz ./frp_conf_$(date +%Y%m%d).tar.gz
```

### 2.4 模型缓存备份

```bash
# Whisper 模型
tar czf whisper_models_$(date +%Y%m%d).tar.gz ~/.cache/huggingface/

# 3D-Speaker 模型
tar czf modelscope_models_$(date +%Y%m%d).tar.gz ~/.cache/modelscope/

# silero-vad 模型
tar czf silero_vad_$(date +%Y%m%d).tar.gz ~/.cache/torch/hub/
```

---

## 三、数据传输

### 3.1 传输到新服务器

```bash
# 在旧服务器执行
# 替换 NEW_SERVER_IP 为新服务器 IP

# 传输数据库备份
scp backup_$(date +%Y%m%d).sql.gz root@NEW_SERVER_IP:/opt/microbubble-agent/

# 传输 MinIO 数据
scp minio_data_$(date +%Y%m%d).tar.gz root@NEW_SERVER_IP:/opt/microbubble-agent/

# 传输上传文件
scp uploads_$(date +%Y%m%d).tar.gz root@NEW_SERVER_IP:/opt/microbubble-agent/

# 传输配置文件
scp .env.backup.* root@NEW_SERVER_IP:/opt/microbubble-agent/
scp docker-compose.yml.backup.* root@NEW_SERVER_IP:/opt/microbubble-agent/

# 传输模型缓存
scp whisper_models_*.tar.gz root@NEW_SERVER_IP:/opt/microbubble-agent/
scp modelscope_models_*.tar.gz root@NEW_SERVER_IP:/opt/microbubble-agent/
scp silero_vad_*.tar.gz root@NEW_SERVER_IP:/opt/microbubble-agent/
```

---

## 四、新服务器部署

### 4.1 克隆代码

```bash
# 在新服务器执行
cd /opt
git clone git@github.com:gg320324492-lgtm/microbubble-agent.git
cd microbubble-agent
```

### 4.2 恢复配置

```bash
# 恢复环境变量
cp .env.backup.* .env

# 检查并修改 .env 中的配置
# 特别注意：
# - DATABASE_URL（PostgreSQL 连接）
# - REDIS_URL（Redis 连接）
# - MINIO_ENDPOINT（MinIO 地址）
# - CLAUDE_BASE_URL（API 代理地址）
# - FRP 相关配置
nano .env
```

### 4.3 恢复数据库

```bash
# 解压备份
gunzip backup_*.sql.gz

# 启动 PostgreSQL
docker compose up -d db

# 等待 PostgreSQL 启动
sleep 10

# 恢复数据库
docker exec -i microbubble-agent-db-1 psql -U postgres microbubble < backup_*.sql
```

### 4.4 恢复 MinIO 数据

```bash
# 启动 MinIO
docker compose up -d minio

# 等待 MinIO 启动
sleep 5

# 恢复数据
docker cp minio_data_*.tar.gz microbubble-agent-minio-1:/tmp/
docker exec microbubble-agent-minio-1 tar xzf /tmp/minio_data_*.tar.gz -C /
```

### 4.5 恢复上传文件

```bash
# 解压上传文件
tar xzf uploads_*.tar.gz
```

### 4.6 恢复模型缓存

```bash
# 创建缓存目录
mkdir -p ~/.cache/huggingface ~/.cache/modelscope ~/.cache/torch/hub

# 恢复 Whisper 模型
tar xzf whisper_models_*.tar.gz -C /

# 恢复 3D-Speaker 模型
tar xzf modelscope_models_*.tar.gz -C /

# 恢复 silero-vad 模型
tar xzf silero_vad_*.tar.gz -C /
```

### 4.7 启动所有服务

```bash
# 启动所有容器
docker compose up -d

# 检查服务状态
docker compose ps

# 查看日志
docker compose logs -f app
```

---

## 五、云服务器配置更新

### 5.1 更新 FRP 客户端配置

```bash
# 在新服务器创建 FRP 客户端配置
mkdir -p /etc/frp

cat > /etc/frp/frpc.toml << 'EOF'
serverAddr = "云服务器IP"
serverPort = 7000
auth.token = "你的FRP密钥"

[[proxies]]
name = "microbubble-web"
type = "tcp"
localIP = "127.0.0.1"
localPort = 8000
remotePort = 8000

[[proxies]]
name = "microbubble-minio"
type = "tcp"
localIP = "127.0.0.1"
localPort = 9000
remotePort = 9000
EOF

# 创建 systemd 服务
cat > /etc/systemd/system/frpc.service << 'EOF'
[Unit]
Description=FRP Client
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/frpc -c /etc/frp/frpc.toml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable frpc
sudo systemctl start frpc
```

### 5.2 验证 FRP 连接

```bash
# 在云服务器检查 FRP 状态
curl http://localhost:7500
# 应显示 FRP 管理面板

# 检查代理是否生效
curl http://localhost:8000/health
# 应返回 {"status": "ok"}
```

---

## 六、GPU 优化配置

### 6.1 Docker GPU 支持

```yaml
# docker-compose.yml 中为 whisper 服务添加 GPU 支持
services:
  whisper:
    build:
      context: .
      dockerfile: Dockerfile.whisper
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
```

### 6.2 Whisper 模型升级

```bash
# 5090 32GB 可以使用更大的模型
# 在 .env 中修改
WHISPER_MODEL=large-v3
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

### 6.3 本地模型部署（可选）

```bash
# 如果需要部署本地 LLM（如 Qwen-7B）
# 5090 32GB 足够运行 7B 模型

# 安装 vLLM
pip install vllm

# 启动本地模型服务
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen-7B-Chat \
  --gpu-memory-utilization 0.9 \
  --max-model-len 8192
```

---

## 七、验证清单

### 7.1 服务验证

```bash
# 检查所有容器运行状态
docker compose ps

# 检查 API 健康
curl http://localhost:8000/health

# 检查前端
curl http://localhost:8000/

# 检查 PostgreSQL 连接
docker exec microbubble-agent-db-1 psql -U postgres -c "SELECT 1;"

# 检查 Redis 连接
docker exec microbubble-agent-redis-1 redis-cli ping

# 检查 MinIO 连接
curl http://localhost:9000/minio/health/live
```

### 7.2 功能验证

- [ ] 登录系统
- [ ] 发送对话消息
- [ ] 上传文件到知识库
- [ ] 搜索知识条目
- [ ] 创建任务
- [ ] 语音识别（Whisper）
- [ ] 声纹识别（3D-Speaker）
- [ ] 企业微信消息
- [ ] 实体图谱显示
- [ ] 公式计算

### 7.3 性能验证

```bash
# GPU 使用率
nvidia-smi

# 内存使用
free -h

# 磁盘使用
df -h

# Docker 资源使用
docker stats
```

---

## 八、回滚方案

如果迁移失败，可以快速回滚到旧服务器：

```bash
# 在旧服务器执行
cd /opt/microbubble-agent

# 停止新服务器的 FRP 客户端
ssh root@NEW_SERVER_IP "systemctl stop frpc"

# 重启旧服务器的服务
docker compose down
docker compose up -d

# 验证旧服务器服务正常
curl http://localhost:8000/health
```

---

## 九、迁移后优化

### 9.1 性能优化

```bash
# PostgreSQL 优化（根据 32GB 内存调整）
# 在 docker-compose.yml 中为 db 服务添加
command: >
  postgres
  -c shared_buffers=8GB
  -c effective_cache_size=24GB
  -c maintenance_work_mem=2GB
  -c work_mem=64MB
  -c max_connections=200

# Redis 优化
# 在 docker-compose.yml 中为 redis 服务添加
command: redis-server --maxmemory 4gb --maxmemory-policy allkeys-lru
```

### 9.2 监控配置

```bash
# 安装监控工具
docker compose -f docker-compose.monitoring.yml up -d

# 包含：
# - Prometheus（指标收集）
# - Grafana（可视化面板）
# - Node Exporter（系统指标）
# - cAdvisor（容器指标）
```

### 9.3 备份策略

```bash
# 创建定时备份脚本
cat > /opt/microbubble-agent/scripts/backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# 数据库备份
docker exec microbubble-agent-db-1 pg_dump -U postgres microbubble | gzip > $BACKUP_DIR/db.sql.gz

# MinIO 备份
docker exec microbubble-agent-minio-1 tar czf /tmp/minio.tar.gz /data
docker cp microbubble-agent-minio-1:/tmp/minio.tar.gz $BACKUP_DIR/minio.tar.gz

# 保留最近 7 天备份
find /opt/backups -maxdepth 1 -mtime +7 -exec rm -rf {} \;
EOF

chmod +x /opt/microbubble-agent/scripts/backup.sh

# 添加定时任务（每天凌晨 3 点）
echo "0 3 * * * /opt/microbubble-agent/scripts/backup.sh" | crontab -
```

---

## 十、常见问题

### Q1: Docker 容器无法访问 GPU

```bash
# 检查 NVIDIA 驱动
nvidia-smi

# 检查 NVIDIA Container Toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# 测试 GPU 访问
docker run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
```

### Q2: PostgreSQL 连接失败

```bash
# 检查 PostgreSQL 是否启动
docker compose logs db

# 检查数据库是否存在
docker exec microbubble-agent-db-1 psql -U postgres -l

# 检查连接字符串
cat .env | grep DATABASE_URL
```

### Q3: MinIO 访问失败

```bash
# 检查 MinIO 是否启动
docker compose logs minio

# 检查 MinIO 数据目录
docker exec microbubble-agent-minio-1 ls -la /data

# 检查 MinIO 配置
cat .env | grep MINIO
```

### Q4: FRP 隧道不通

```bash
# 检查 FRP 客户端状态
systemctl status frpc

# 检查 FRP 日志
journalctl -u frpc -f

# 检查云服务器 FRP 服务端
ssh root@云服务器IP "systemctl status frps"
```

### Q5: Whisper 模型加载失败

```bash
# 检查 GPU 是否可用
nvidia-smi

# 检查模型缓存
ls -la ~/.cache/huggingface/

# 手动下载模型
python -c "from faster_whisper import WhisperModel; model = WhisperModel('large-v3', device='cuda')"
```

---

## 迁移检查清单

- [ ] 新服务器环境准备（Docker、NVIDIA 驱动）
- [ ] 数据库备份完成
- [ ] MinIO 数据备份完成
- [ ] 配置文件备份完成
- [ ] 模型缓存备份完成
- [ ] 数据传输到新服务器
- [ ] 数据库恢复成功
- [ ] MinIO 数据恢复成功
- [ ] 所有服务启动成功
- [ ] FRP 隧道连接正常
- [ ] 前端访问正常
- [ ] API 功能正常
- [ ] 语音识别正常
- [ ] 声纹识别正常
- [ ] 企业微信正常
- [ ] 定时任务配置完成
- [ ] 监控配置完成
- [ ] 备份策略配置完成

---

*本文档将随迁移过程持续更新*

#!/bin/bash

set -e

echo "=================================="
echo "微纳米气泡课题组Agent系统"
echo "=================================="

# 检查环境变量
if [ ! -f .env ]; then
    echo "错误：.env文件不存在"
    echo "请复制.env.example为.env并配置相应参数"
    echo ""
    echo "cp .env.example .env"
    echo "nano .env  # 编辑配置"
    exit 1
fi

# 创建必要目录
echo "创建必要目录..."
mkdir -p data/{postgres,redis,minio} logs models nginx/ssl

# 检查Docker
if ! docker compose version &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "错误：未安装 Docker Compose"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 确定 compose 命令
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    COMPOSE_CMD="docker-compose"
fi

# 构建镜像
echo "构建Docker镜像..."
$COMPOSE_CMD build

# 启动服务
echo "启动服务..."
$COMPOSE_CMD up -d

# 等待服务就绪
echo "等待服务就绪..."
sleep 15

# 初始化数据库
echo "初始化数据库..."
$COMPOSE_CMD exec -T app python scripts/init_db.py || echo "数据库可能已初始化"

echo ""
echo "=================================="
echo "启动完成！"
echo "=================================="
echo ""
echo "服务状态:"
$COMPOSE_CMD ps
echo ""
echo "访问地址："
echo "  - Web界面: http://localhost"
echo "  - API文档: http://localhost/docs"
echo ""
echo "常用命令："
echo "  - 查看日志: $COMPOSE_CMD logs -f app"
echo "  - 停止服务: $COMPOSE_CMD down"
echo "  - 重启服务: $COMPOSE_CMD restart"
echo ""

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
mkdir -p data/{postgres,redis,minio,chroma}
mkdir -p logs
mkdir -p models

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo "错误：未安装Docker"
    echo "请先安装Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "错误：未安装Docker Compose"
    exit 1
fi

# 构建镜像
echo "构建Docker镜像..."
docker-compose build

# 启动服务
echo "启动服务..."
docker-compose up -d

# 等待服务就绪
echo "等待服务就绪..."
sleep 15

# 初始化数据库
echo "初始化数据库..."
docker-compose exec app python scripts/init_db.py

echo ""
echo "=================================="
echo "启动完成！"
echo "=================================="
echo ""
echo "访问地址："
echo "  - Web界面: http://localhost"
echo "  - API文档: http://localhost:8000/docs"
echo "  - MinIO控制台: http://localhost:9001"
echo ""
echo "常用命令："
echo "  - 查看日志: docker-compose logs -f app"
echo "  - 停止服务: docker-compose down"
echo "  - 重启服务: docker-compose restart"
echo ""

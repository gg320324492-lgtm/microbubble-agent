FROM python:3.11-slim-bookworm

# 阿里云镜像源 (bookworm-security 路径已正确支持)
RUN rm -f /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list && \
    printf 'deb http://mirrors.aliyun.com/debian bookworm main contrib\n' > /etc/apt/sources.list && \
    printf 'deb http://mirrors.aliyun.com/debian bookworm-updates main contrib\n' >> /etc/apt/sources.list && \
    printf 'deb http://mirrors.aliyun.com/debian-security bookworm-security main contrib\n' >> /etc/apt/sources.list

WORKDIR /app

# Install system dependencies (with retry for transient 502)
RUN apt-get update && apt-get install -y --fix-missing \
    ffmpeg \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libavfilter-dev \
    libswscale-dev \
    libswresample-dev \
    libpq-dev \
    gcc \
    pkg-config \
    || (apt-get update && apt-get install -y --fix-missing \
        ffmpeg libavformat-dev libavcodec-dev libavdevice-dev \
        libavutil-dev libavfilter-dev libswscale-dev libswresample-dev \
        libpq-dev gcc pkg-config) \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
# PyPI 官方源（清华源/aliyun 同步 torch 2.12+ 慢，2026-06-24 ST 5.6.0 升级）
# clash 代理只对 pip install 生效，不影响 Docker 内部 registry（避免 dockerproxy.net 500）
# 清华源备选（注释保留）：-i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn
COPY requirements.txt .
ARG HTTPS_PROXY
ARG HTTP_PROXY
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefer-binary \
        --retries 10 --timeout 60 \
        -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

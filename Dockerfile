FROM python:3.11-slim-bookworm

WORKDIR /app

# 安装系统依赖（带重试）
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

# 安装Python依赖（使用官方源 + 阿里云备用）
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefer-binary -r requirements.txt \
    --extra-index-url https://mirrors.aliyun.com/pypi/simple/ \
    --trusted-host mirrors.aliyun.com

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

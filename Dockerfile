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
# 清华源 + pip 重试机制（解决大文件 IncompleteRead 断连问题）
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --prefer-binary \
        --retries 10 --timeout 60 \
        -r requirements.txt \
        -i https://pypi.tuna.tsinghua.edu.cn/simple/ \
        --trusted-host pypi.tuna.tsinghua.edu.cn

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

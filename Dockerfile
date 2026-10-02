# base image pinned on 2026-07-29 for CVE tracking (W86-C-1 Trivy)
FROM python:3.11.15-slim-bookworm

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
    && (apt-get install -y --no-install-recommends libreoffice-impress libreoffice-writer poppler-utils fonts-noto-cjk         || (apt-get update && apt-get install -y --no-install-recommends             libreoffice-impress libreoffice-writer poppler-utils fonts-noto-cjk))     && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
# PyPI 官方源（清华源/aliyun 同步 torch 2.12+ 慢，2026-06-24 ST 5.6.0 升级）
# clash 代理只对 pip install 生效，不影响 Docker 内部 registry（避免 dockerproxy.net 500）
# 清华源备选（注释保留）：-i https://pypi.tuna.tsinghua.edu.cn/simple/ --trusted-host pypi.tuna.tsinghua.edu.cn
#
# 2026-10-02 S3.9 (build-image.yml 连续 8 次 cancelled 根因修复):
#   原先两条 pip install 都带 `--no-cache-dir`, 等于**主动禁用** pip 的 HTTP/wheel 缓存。
#   GHA buildkit cache 的 TTL 是 7 天, 一旦过期, 冷构建要重下整个依赖树
#   (实测 apt 单步就 846s / 262.4 MB / 263 kB/s ≈ 16.6 分钟, pip 那步压根没轮到),
#   于是 15 分钟超时先到 → 进程被杀 → `cache-to` 永不执行 → 缓存永远写不回去
#   → 之后每次触发都是同样的冷构建 → **永久死锁**。
#   改为 cache mount 后, pip 缓存独立于 buildkit layer cache 存活, 冷构建可复用。
#
#   `exec.cachemount` 已在 GHA 导出过滤器内 (实测 Filters: type==source.local
#   type==exec.cachemount type==source.git.checkout), 故此 mount 能真正持久化。
#   纯增量改动: 不增删任何包, 不改任何系统依赖, 镜像内容语义完全不变。
#   注: cache mount 的内容不进最终镜像层, 镜像体积不受影响。
COPY requirements.txt .
ARG HTTPS_PROXY
ARG HTTP_PROXY
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --upgrade pip && \
    pip install --prefer-binary \
        --retries 10 --timeout 60 \
        -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

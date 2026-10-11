# base image bumped for L-8 image-scan CVE zeroing (2026-10-07; prior pin 2026-07-29 W86-C-1)
FROM python:3.11.17-slim-bookworm

# 2026-10-12: apt 源 mirrors.aliyun.com -> **官方 deb.debian.org**(主指挥裁定)。
#   起因: 部署 `619ae84ad` 时构建连续两次卡死在 apt 层 ——
#     `#9 Ign:5 http://mirrors.aliyun.com/debian bookworm/main amd64 Packages`
#   连续 5 次重试全部 Ign(忽略失败), 8 分钟后 exit 100。**不是代码问题**。
#
#   实测取证(同机同时段, 排除"网络整体不通"):
#     宿主直连 aliyun (不走代理)         -> 200, 1.95s   ← 宿主没问题
#     容器内 apt + aliyun 源             -> InRelease 151kB 拿到, 但 Packages 大索引超时
#     容器内 apt + 官方 deb.debian.org   -> Fetched 9388 kB in 5s (1760 kB/s)  ← 正常
#   ⇒ aliyun 对**大索引**从容器网络不通(小文件能通、大文件超时), 换官方源即可。
#   注: 宿主能通是因为走了 HTTP_PROXY/HTTPS_PROXY(clash), 而 Docker 构建的 apt
#   层**没有代理**(本文件的 ARG HTTPS_PROXY 声明在 apt 层之后, 只惠及 pip 层)。
#
#   ⚠️ 保留 aliyun 的原意是"国内网络更快", 但**可用性优先于速度** —— 源拉不到索引时
#      构建直接失败, 没有任何降级。官方源在本机实测 1760 kB/s, 足够快。
#   ⚠️ 本行改的是**构建期**源, 不影响运行时; 回滚 = 改回 aliyun 三行即可。
RUN rm -f /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list && \
    printf 'deb http://deb.debian.org/debian bookworm main contrib\n' > /etc/apt/sources.list && \
    printf 'deb http://deb.debian.org/debian bookworm-updates main contrib\n' >> /etc/apt/sources.list && \
    printf 'deb http://deb.debian.org/debian-security bookworm-security main contrib\n' >> /etc/apt/sources.list

WORKDIR /app

# Install system dependencies (with retry for transient 502)
# L-8 (2026-10-07): apt-get upgrade = 纯 OS 层安全升级 (debian-security 修复),
# 不触碰任何 pip/requirements pin; 紧跟 update、在 install 前执行。
# L-8 (2026-10-07) 补强: archives cache mount + Acquire::Retries —— 与下方 pip cache mount
# 同源理由 (S3.9): 本地/网络抖动时大包 (gcc-12/libllvm15/libreoffice) 连接中途 reset,
# 重试从零下; cache mount 让已完成 .deb 跨构建保留, 单次 RUN 内 Acquire::Retries=5 兜底。
# docker-clean 的 Post-Invoke 会把 .deb 清出 cache, 必须在同层删掉; cache mount 不进镜像层。
# lists 同挂 cache: apt-get update 的 12MB Packages 索引同样受连接中断影响, 挂载后跨构建复用
# (索引只存 mount, 不进镜像层; 故尾部原 rm -rf /var/lib/apt/lists/* 删除 —— 镜像层不含 lists 不变)。
# By-Hash off (2026-10-07 L-8): 镜像源 by-hash 路径对大索引限速 (实测 50MB plain by-hash
# 滴流 ~120kB/s, apt 60s 超时 → Ign 死循环); 关闭后走 plain→404→Packages.gz 正常路径, 传量更小。
RUN --mount=type=cache,target=/var/cache/apt/archives,sharing=locked \
        --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/80-retries && \
    echo 'Acquire::By-Hash "false";' > /etc/apt/apt.conf.d/81-byhash && \
    apt-get update && apt-get upgrade -y && apt-get install -y --fix-missing \
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
    && (apt-get install -y --no-install-recommends libreoffice-impress libreoffice-writer poppler-utils fonts-noto-cjk         || (apt-get update && apt-get install -y --no-install-recommends             libreoffice-impress libreoffice-writer poppler-utils fonts-noto-cjk))

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
#
# 2026-10-12 L-8: **删掉 `pip install --upgrade pip`** (承 679721665 对
#   Dockerfile.whisper / Dockerfile.funasr 的同型修复, 本文件当时漏改)。
#   **升级 pip 本身会引入 HIGH CVE** —— CVE 不在我们装的包里, 而在 pip
#   自带的 `pip/_vendor/` 里, 随 pip 版本走:
#       基础镜像自带 pip 24.0  → vendor setuptools 68.0.0  (trivy 不报)
#       --upgrade  pip 26.2.1  → vendor setuptools 70.3.0  (CVE-2025-47273,
#                                FixedVersion 78.1.1  ⇒ 必报)
#   同批被带进来的还有 vendor msgpack(1.0.5→1.1.2) 与 vendor urllib3
#   (1.26.17→2.7.0)。⇒ **升级构建工具 ≠ 更安全**, 这里保持基础镜像的 pip 24.0。
#   实测本镜像里**真正安装**的 setuptools 是 84.0.0(干净), 报出的 70.3.0
#   只是 pip 的 vendored 副本 —— 两者别混谈。
COPY requirements.txt .
ARG HTTPS_PROXY
ARG HTTP_PROXY
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    pip install --upgrade setuptools && \
    pip install --prefer-binary \
        --retries 10 --timeout 60 \
        -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

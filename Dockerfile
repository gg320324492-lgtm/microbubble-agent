# base image bumped for L-8 image-scan CVE zeroing (2026-10-07; prior pin 2026-07-29 W86-C-1)
# =============================================================================
# L-8 multi-stage (2026-10-13): 构建期 dev 包不再进最终镜像 (325 CVE 归零)
# =============================================================================
# 改造前是**单阶段**: 编译工具链 (gcc/pkg-config/libpq-dev) 与 7 个 libav*-dev 和
# 运行时依赖装在同一层, 于是 gcc 顺带拉进来的东西全部留在最终镜像里。实测
# microbubble-agent-app:latest 的 626 条 HIGH/CRITICAL 里, **325 条是构建期产物**:
#   linux-libc-dev 196 (由 gcc 拉入, CVE 最早到 2015) + libav*-dev 8x16 = 128 +
#   libssl-dev 1 —— 生产一条都用不上。
#
# 拆成两段:
#   builder — apt 列表与改造前**逐字一致**(只把 libreoffice 那组挪到 runtime,
#             它是纯运行时依赖, 构建期不碰), 让 pilk/crcmod 的编译行为与当前
#             生产镜像完全相同, 把风险面压到最小;
#   runtime — 同款 python:3.11.17-slim-bookworm + 只装运行时 apt 包, 并从
#             builder **整份搬运** Python 环境。
#
# ⚠️ 为什么必须"搬运"而不能在 runtime 里重新 pip install:
#   全镜像 257 个 .dist-info/WHEEL 里只有 2 个没有 Linux 预编译 wheel:
#     pilk   (requirements.txt:123 钉 pilk>=0.2.4) —— PyPI 只有 Windows wheel,
#             无 gcc 时 pip **硬失败** (能被发现);
#     crcmod (传递依赖自 oss2) —— 只有 .tar.gz, 无 gcc 时 pip **不报错**, 但会
#             退化成纯 Python 实现 (_crcfunext 缺失, WHEEL 变成 py3-none-any):
#             CRC 结果仍然正确 ⇒ **静默降级**, 构建/CI/测试全绿而产物变成慢几个
#             数量级的实现。
#   ⇒ runtime 段**绝不**再碰 pip, 编译产物原样搬过去。
#
# ⚠️ runtime 段特意保留 libstdc++6 / libgomp1: 这两个原本是 gcc 的依赖被顺带装上,
#   而 site-packages 里的 PyAV (av/*.abi3.so, RPATH=$ORIGIN/../../av.libs 但仍链接
#   系统 libstdc++.so.6 + libgcc_s.so.1) 需要它们 —— 漏装会变成运行期
#   `libstdc++.so.6: cannot open shared object file`。(pilk 的 .so 只链接 libc,
#   crcmod 的 .so 静态自足, 两者都不构成额外依赖。)
# =============================================================================
FROM python:3.11.17-slim-bookworm AS builder

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
    pkg-config
    # ⚠️ 原先与下面这行同层安装的 libreoffice-impress / libreoffice-writer /
    #   poppler-utils / fonts-noto-cjk **已挪到 runtime 段**: 它们只被运行时代码
    #   (文档转换 / PDF 文本抽取 / 中文字体) 调用, 构建期一次都用不到。
    #   ⚠️ 其余包一个不减 —— libav*-dev 在 builder 里大概率也用不到, 但**本次
    #   不动**(一次只改一件事, 出问题好定位), 它们不会进最终镜像。

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

# =============================================================================
# runtime 段 —— 最终镜像。⚠️ 见文件头: 这里**不做任何 pip install**
# =============================================================================
FROM python:3.11.17-slim-bookworm AS runtime

# 与 builder 段**逐字相同**的源改写 —— 两段是各自独立的镜像, FROM 不共享层,
# builder 段的 /etc/apt/sources.list 不会自动出现在 runtime 段。
# ⚠️ 后缀不可改成 trixie: 下面三行 printf 硬编码的是 bookworm 源地址,
#    对不上源会装出缝合怪镜像且 apt 仍返回 rc=0。
RUN rm -f /etc/apt/sources.list.d/debian.sources /etc/apt/sources.list && \
    printf 'deb http://deb.debian.org/debian bookworm main contrib\n' > /etc/apt/sources.list && \
    printf 'deb http://deb.debian.org/debian bookworm-updates main contrib\n' >> /etc/apt/sources.list && \
    printf 'deb http://deb.debian.org/debian-security bookworm-security main contrib\n' >> /etc/apt/sources.list

WORKDIR /app

# 运行时 apt 包。cache mount / retries / by-hash 三个设置与 builder 段同源同理由
# (S3.9 + L-8): 冷构建时不复用 .deb 会重下 262MB, 且镜像源 by-hash 对大索引限速。
RUN --mount=type=cache,target=/var/cache/apt/archives,sharing=locked \
        --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/80-retries && \
    echo 'Acquire::By-Hash "false";' > /etc/apt/apt.conf.d/81-byhash && \
    apt-get update && apt-get upgrade -y && apt-get install -y --fix-missing \
    ffmpeg \
    libpq5 \
    libstdc++6 \
    libgomp1 \
    && (apt-get install -y --no-install-recommends libreoffice-impress libreoffice-writer poppler-utils fonts-noto-cjk         || (apt-get update && apt-get install -y --no-install-recommends             libreoffice-impress libreoffice-writer poppler-utils fonts-noto-cjk))

# 从 builder 搬运 Python 环境 —— **精确到两处**, 理由:
#   /usr/local/bin 112 个文件 = 解释器 + 112 个 console script (uvicorn / celery /
#     alembic / accelerate / datasets-cli ...), 缺了 CMD 直接起不来;
#   site-packages = 全部包及其原生 .so (pilk / crcmod 的编译产物就在这里);
#   实测 builder 相对基础镜像**只多了这两处** —— /usr/local/include 的 190 个文件
#   (Python.h 等) 与 /usr/local/lib/pkgconfig 的 4 个 .pc 都是基础镜像自带,
#   /usr/local/share 仅 2 个文件, /usr/local/src|etc|games|man 为空。
# ⚠️⚠️ 上面那行 rm -rf 不是洁癖, 是**必需** —— `COPY` 是合并语义, 永远不删除
#   目标侧独有的文件。不清空就 COPY 会踩本次改造实测到的真坑:
#     runtime 段的基础镜像**自带** setuptools-79.0.1.dist-info 与
#     setuptools/_vendor/{jaraco.context-5.3.0, wheel-0.45.1}.dist-info
#     (基础镜像构建期就装在 site-packages 里), 而 builder 段的
#     `pip install --upgrade setuptools` 已把它们 uninstall 干净(只剩 84.0.0)。
#     两份 dist-info 并存 ⇒ `import setuptools` 报 **79.0.1**
#     (importlib.metadata 先命中旧元数据) ⇒ trivy 反而**多出 2 条** CVE
#     (CVE-2026-23949 jaraco.context / CVE-2026-24049 wheel), 而生产镜像是干净的。
#   实测残留 216 个文件(packaging-26.3 / pkg_resources / setuptools-79.0.1.* /
#   _vendor 下 6 个旧版本 dist-info / _distutils/compat/py39.py ...)。
#   ⇒ 搬运 = "清空 + 全量拷贝", **不是**"覆盖拷贝"。
#   (/usr/local/bin 一并清空是安全的: 实测 builder 的 112 个脚本 ⊇ 基础的 18 个。)
RUN rm -rf /usr/local/lib/python3.11/site-packages /usr/local/bin/*
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

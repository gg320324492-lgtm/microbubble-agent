# docker/visual-regression/Dockerfile — 视觉回归专用镜像 (阶段 2 治①)
#
# 为什么要有这个镜像:
#   实测 (2026-10-04): app 的 body 字体栈是
#     -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
#     'PingFang SC', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif
#   而 playwright.yml 的 visual job 跑在**裸 ubuntu runner** 上, 只 apt 装了
#   fonts-noto-cjk。实测 fontconfig 解析:
#     fc-match "Segoe UI"  -> WenQuanYi Zen Hei   (不是 Noto!)
#   ⇒ 装没装 fonts-noto-cjk 都一样渲染成 WenQuanYi, 因为栈里第一个"存在的"
#     名字是 Segoe UI。这正是"Windows 录 → Linux 比 0/118 全炸"的根因。
#
# 本镜像做三件事 (与基线录制环境**必须逐字节一致**):
#   1. 底座锁 mcr.microsoft.com/playwright:v1.62.0-noble
#      → Chromium 151.0.7922.34 revision1234, 与 web/package-lock.json 锁的
#        playwright-core 1.62.0 **同一个浏览器构建** (实测 executablePath 解析一致)
#   2. 装**钉版本**的 fonts-noto-cjk (1:20230817+repack1-3)
#      → 钉版本是因为字体包升级会改字形, 那等于全量基线作废
#   3. 写 fontconfig 别名规则, 把字体栈里每个名字都**钉到同一字体文件**
#      → 这样"字体是否装在系统里/别名怎么解析"与渲染结果**完全解耦**
#
# ⚠️ 改动这个文件 = 全套基线作废, 必须重录。
FROM mcr.microsoft.com/playwright:v1.62.0-noble

ARG NOTO_CJK_VERSION=1:20230817+repack1-3

USER root

# 字体包: 钉版本。字体升级会改字形 → 像全部变 → 基线作废。
RUN apt-get update -qq \
 && apt-get install -y -qq "fonts-noto-cjk=${NOTO_CJK_VERSION}" \
 && rm -rf /var/lib/apt/lists/*

# fontconfig 别名: 把 app 字体栈里出现的每个家族名都别名到 Noto Sans CJK SC。
#
# 为什么必须做这一步 (实测, 不能省):
#   只装 fonts-noto-cjk 是**无效**的 —— app 栈里第一个存在的名字是 'Segoe UI',
#   fontconfig 把它解析成 WenQuanYi Zen Hei, 于是 Noto 永远轮不到被选中。
#   实测 canvas measureText 拉丁串:
#     只装字体无规则:      380.215px  (WenQuanYi)
#     加了下面这些规则:    398.400px  (Noto Sans CJK SC)
#   ⇒ 规则确实改变了真实渲染, 不是空转。
#
# 用 mode="assign" + binding="strong" 强制覆盖, 而不是 append:
#   append 只是往栈尾追加候选, 栈首的 Segoe UI 仍会先命中。
COPY fontconfig-visual.conf /etc/fonts/local.conf

RUN fc-cache -f

# libfaketime: 冻结**浏览器进程**的时钟 (阶段 2 治②)
#
# 为什么必须用 libfaketime 而不是 page.clock / addInitScript:
#   实测 (2026-10-05) 两个事实:
#   1. page.clock.setFixedTime / addInitScript **只能在 test 或 fixture 内调用**,
#      Playwright 的 config 层**没有**全局 init-script / beforeEach 注入点。
#      要用它就必须改每一个 spec —— 而 secondary-routes.spec.mjs 已被另一个
#      agent 在改, 且"改 5 个 spec 去冻结时钟"本身也是脆弱约定。
#   2. LD_PRELOAD 会被 Chromium 子进程继承。实测页面内 new Date() 得到
#        Mon Oct 05 2026 10:00:00 GMT+0800 (China Standard Time)
#      与宿主 FAKETIME 完全一致 ⇒ 一个 spec 都不用碰就能冻结。
#
# ⚠️ libfaketime 必须**在容器启动时**通过 LD_PRELOAD + FAKETIME 传入 (见
#    docker/visual-regression/run-visual.sh), 不能写死在镜像里 —— 不同 run
#    要用同一个固定值, 而那个值属于"门禁口径", 与镜像构建解耦。
RUN apt-get update -qq \
 && apt-get install -y -qq --no-install-recommends faketime \
 && rm -rf /var/lib/apt/lists/* \
 && ls -la /usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1

# 供 CI / 本地复核用: 打印字体解析结果。字体没锁住时**一眼能看出来**。
RUN fc-match "Segoe UI" -f '%{family}|%{file}\n' \
 && fc-match "sans-serif" -f '%{family}|%{file}\n' \
 && fc-match "PingFang SC" -f '%{family}|%{file}\n'

# ⚠️ 刻意**不切回 pwuser**, 以 root 运行。
#
# 理由: 视觉回归容器要挂载一个已装好依赖的 node_modules volume。Docker named volume
# 由 root 创建, 若以 pwuser 运行, vite 的依赖预构建会撞:
#   EACCES: permission denied, mkdir '/app/web/node_modules/.vite/deps_temp_XXXX'
# (实测 2026-10-04)。而 chown named volume 在 Docker Desktop (Windows/macOS 虚拟化)
# 上会失败: `Operation not permitted` —— 跨平台不可靠。
#
# 这里跑的是**一次性测试容器**, 挂载的是 CI checkout + 本地 npm ci 产物, 不接生产
# 数据、不暴露端口到公网, root 无实际风险敞口。a11y job 未改动。
#
# 若将来要收紧, 正解是给 volume 预置正确的 uid/gid (或在 CI 里 npm ci 而非挂 volume),
# 而不是在这里切回非 root。
WORKDIR /app
#!/usr/bin/env bash
# docker/visual-regression/run-visual.sh — 视觉回归的**唯一**入口 (录基线与跑门禁共用)
#
# 为什么要有这个脚本 (实测, 2026-10-04/05):
#   像素比对有三个不确定性来源, 本脚本把其中两个在**进程层面**钉死, 使
#   "录基线" 与 "跑门禁" 必须跑在**完全相同**的确定性环境里:
#     治① 字体 → 由镜像里的 fontconfig 规则钉死 (fontconfig-visual.conf)
#              校验: fc-match "Segoe UI" 必须是 Noto Sans CJK SC
#     治② 墙钟 → 本脚本注入 LD_PRELOAD + FAKETIME + TZ
#              Chromium 子进程继承 LD_PRELOAD ⇒ 页面内 new Date() 恒定
#     治③ 数据 → 由 spec 自己 mock / 连确定性后端 (不在本脚本范围)
#
# ⚠️ 三个环境变量是**门禁口径**, 改动任何一个 = 全套基线作废:
#     VIZ_FAKETIME  固定时刻 (UTC)
#     VIZ_TZ        固定时区
#     VIZ_IMAGE     镜像 tag (含字体钉版本)
#   它们在本文件里集中定义一次, CI workflow 与本地录基线都 source 同一份。
set -euo pipefail

# ============ 门禁口径 (改动 = 基线作废) ============
export VIZ_IMAGE="${VIZ_IMAGE:-microbubble-visual-regression:pin-2026-10-05}"
export VIZ_FAKETIME="${VIZ_FAKETIME:-2026-10-05 10:00:00}"
export VIZ_TZ="${VIZ_TZ:-Asia/Shanghai}"
export VIZ_LOCALE="${VIZ_LOCALE:-zh-CN}"
# ==================================================

FAKETIME_LIB=/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1

fail_loud() { echo "::error::$1" >&2; exit 1; }

# ---------- 前置校验: 字体锁没锁住就直接失败, 别让它静默漂 ----------
assert_font_locked() {
  local resolved
  resolved="$(fc-match "Segoe UI" -f '%{family}')"
  case "$resolved" in
    "Noto Sans CJK SC") echo "✓ 字体已锁: Segoe UI -> $resolved" ;;
    *) fail_loud "字体未锁定: 'Segoe UI' 解析成 '$resolved', 期望 'Noto Sans CJK SC'。
       基线会在别的字体上重录, 等于作废。检查 fontconfig-visual.conf。" ;;
  esac
  # WenQuanYi 必须不可达 —— 它是这个镜像里唯一会抢中文的意外字体
  if fc-match "sans-serif" -f '%{file}' | grep -qi wqy; then
    fail_loud "WenQuanYi 仍可达 (rejectfont 规则未生效)。"
  fi
}

assert_clock_frozen() {
  [ -f "$FAKETIME_LIB" ] || fail_loud "libfaketime 未安装: $FAKETIME_LIB 不存在。字体/时钟未钉死。"
  export LD_PRELOAD="$FAKETIME_LIB"
  export FAKETIME="$VIZ_FAKETIME"
  export TZ="$VIZ_TZ"
  # ⚠️ DONT_FAKE_MONOTONIC=1 是**必需**的, 不是优化 (实测 2026-10-05, 三轮对照):
  #   只设 FAKETIME (冻结一切) -> `npx playwright test --list` 就**静默挂死**:
  #     零输出、零快照、进程存活, 连"列出用例"这一步都做不完 (exit 124)。
  #   设 DONT_FAKE_MONOTONIC=1 -> 墙钟冻结, 但 monotonic 时钟照常推进,
  #     `--list` 立刻 129 行 / 127 用例 (exit 0)。
  #   根因: Playwright runner 的启动与超时判定用 monotonic clock (CLOCK_MONOTONIC),
  #   一旦它也被冻住, runner 永远等不到"时间前进", 于是死等。
  #   这**不影响**我们要治的东西 —— 页面墙钟仍恒定, 实测:
  #     page.evaluate(() => new Date().toString()) 连续两次都是
  #       Mon Oct 05 2026 10:00:00 GMT+0800 (中国标准时间)
  #     即 greeting / currentDate / .tchip 时钟牌 全部取固定值。
  export DONT_FAKE_MONOTONIC=1
  # FAKETIME_NO_CACHE=1: libfaketime 默认缓存时间值。显式设上是为了不依赖
  # 不同 libfaketime 版本的默认值 (实测它单独不足以救 runner, 但也无害)。
  export FAKETIME_NO_CACHE=1
  local now
  now="$(date '+%Y-%m-%d %H:%M:%S')"
  sleep 1
  local again
  again="$(date '+%Y-%m-%d %H:%M:%S')"
  [ "$now" = "$again" ] || fail_loud "时钟未冻结: $now != $again (1s 后变了)。LD_PRELOAD/FAKETIME 没生效。"
  echo "✓ 时钟已冻结: $now $TZ (monotonic 不冻结, 否则 Playwright runner 死等)"
}

assert_font_locked
assert_clock_frozen

# ---------- 参数 ----------
# 用法:
#   run-visual.sh record   # 录基线 (--update-snapshots=all), 需人工 review 后入库
#   run-visual.sh verify   # 比对基线 (--update-snapshots=none), 门禁用这个
MODE="${1:-verify}"
case "$MODE" in
  record) SNAP_FLAG="--update-snapshots=all" ;;
  verify) SNAP_FLAG="--update-snapshots=none" ;;
  *) fail_loud "用法: run-visual.sh [record|verify]" ;;
esac

WEB_DIR="${WEB_DIR:-/app/web}"
BASE_URL="${BASE_URL:-http://127.0.0.1:3000}"

cd "$WEB_DIR"

# ⚠️ warm-up 只跑**一个**用例, 不是整套。
#    目的只是把 vite 的依赖预构建缓存热起来 —— 否则第一个 spec 会在"冷转换"
#    中间态下截图, 与后续 spec 不同源。
#    ⚠️ 2026-10-05: 原实现跑的是**整套**, 于是整个门禁跑两遍
#    (实测 118 张 x2 ≈ 32min), 直接超出 visual job 的 25min 预算。
#    a11y job 的 warm-up 同样是一整套, 但它只有 25 个用例, 不构成问题;
#    本 job 有 118 个, 必须只跑一个。
#    `-g` 过滤 + `--update-snapshots=none` ⇒ 不写任何基线。
echo "▸ warm-up vite transform cache (单用例, 不写基线)"
WARMUP_GREP="${VIZ_WARMUP_GREP:-03-chat}"
npx playwright test -c "${VIZ_CONFIG:-tests/visual/playwright.visual.config.mjs}" \
  -g "$WARMUP_GREP" --update-snapshots=none --reporter=line > /tmp/warmup.log 2>&1 || true
echo "▸ warm-up done (exit 忽略是预期的: 基线可能不存在, 与 warm-up 无关)"

# ---------- 治④ vite 依赖再优化 (2026-10-05, flaky 根因) ----------
#
# 实测证据 (本机隔离 worktree, 钉死镜像 + run-visual.sh 唯一入口):
#   冷 vite (deps 0) 跑整套 -> `optimized dependencies changed. reloading`
#   在 **测试进行中** 触发 6-7 次, 每次都强制整页 reload ⇒ 组件被卸载重挂,
#   spec 的 waitFor/断言正好落在 reload 窗口里就报"元素不存在"。
#   被打中的是 secondary-routes `07 file-detail`:
#     Error: expect(locator).toHaveText(expected) failed
#     Locator: locator('.mfd-title')  Error: element(s) not found
#   A/B 对照 (同镜像同入口, 只改 vite 优化器冷热):
#     冷 vite (全新容器 + 抹掉 .vite) -> 1 flaky (3/3 次复现)
#     热 vite                          -> 49 passed / 0 flaky
#   ⇒ 根因确证是 vite 的**懒发现**依赖预构建 + 强制 reload, 与像素无关。
#
# 为什么"单用例 warm-up"修不掉它 (S3.12 把它当成已修):
#   预构建是**懒发现**的 —— vite 只有被请求到才把该依赖纳入优化。
#   跑 1 个 chat 用例只会热 /chat 这条链; /drive、/knowledge/:id、
#   /admin/agent-traces 等各自的 element-plus / nutui 子依赖仍是冷,
#   于是 reload 事件**挪到**这些路由首次被访问时发生 —— warm-up 只是把
#   问题往后推, 没消除 (这正是 CI 里 flaky 落在 file-detail 的原因)。
#
# 修法: 在跑门禁前用**真实浏览器**把 5 个 spec 触及的**全部**路由走一遍,
#   轮询到依赖优化指纹**连续两轮一致**才放行。
#   - 走全部路由 (不是单用例) ⇒ 依赖集覆盖完整
#   - 轮询到稳定 (不是固定 sleep) ⇒ 快慢机器都正确
#   - 不稳定就 fail-loud ⇒ 环境没钉死时红在这里, 而不是伪装成 flaky 混进门禁
#
# 路由表在 web/tests/visual/route-warm.mjs (唯一来源, 与 spec 同处一地
# 便于同步维护); 本脚本只负责"跑它 + 判稳定 + 不稳定则 fail-loud"。
#
# ⚠️ 这里**不加**新的 sleep 固定值, 也不用固定次数 sleep: 全部是条件式等待。
#
# 实测成本: 预热轮 4-12s, 冷启动实测 4 轮收敛 / 已热 3 轮收敛,
#   相对 25min 预算可忽略 (门禁本身 CI 12.3m)。

# 判据: vite 依赖优化的**指纹集合** (`?v=` 版本向量)。
#   连续两轮扫完全部路由, 指纹集合逐字相同 ⇒ 这一轮没有任何重新优化
#   ⇒ 依赖集已收敛, 门禁开始跑时不会再有 reload 把组件卸载重挂。
#
# ⚠️ 判据换过三版, 每版都被实测证伪 (细节见 route-warm.mjs 顶部注释):
#   (a) vite deps 目录文件数 —— 再优化时经常不新增文件、只改写已有 chunk,
#       文件数不变但 reload 照发。实测那版门禁仍 flaky (两轮都报
#       "deps=156 已稳定", 实际仍 7 次 reload)。
#   (b) framenavigated 计数 / 同 URL 再导航计数 —— vite 的 HMR client
#       **每页加载都会重连**并把当前页再导航一次, 实测热依赖下也稳定报 31 次,
#       全是噪声, 会让门禁永远 fail-loud。
#   (c) 读 vite 容器 stdout —— CI 里 vite 跑在 workflow 另起的 visual-vite
#       容器, 本脚本与它不共 stdout, 读不到。
#   ⇒ 页面侧可见、且与"是否重新优化"严格一一对应的只有 `?v=` 指纹。
WARM_REPORT=/tmp/route-warm-fingerprint

wait_for_deps_stable() {
  local round=0 same=0 prev="" cur
  echo "▸ 预热全部路由, 直到 vite 依赖优化指纹稳定 (判据=连续两轮 ?v= 集合相同)"
  : > /tmp/route-warm.log
  while [ "$round" -lt "${VIZ_DEPS_MAX_ROUNDS:-6}" ]; do
    round=$((round + 1))
    rm -f "$WARM_REPORT"
    VIZ_WARM_REPORT="$WARM_REPORT" BASE_URL="$BASE_URL" \
      node "${VIZ_ROUTE_WARM_SCRIPT:-tests/visual/route-warm.mjs}" >> /tmp/route-warm.log 2>&1 || true
    if [ ! -s "$WARM_REPORT" ]; then
      echo "▸ 第 $round 轮: 预热脚本没产出指纹 (见 /tmp/route-warm.log), 再试一轮"
      continue
    fi
    cur="$(cat "$WARM_REPORT")"
    if [ -n "$prev" ] && [ "$cur" = "$prev" ]; then
      same=$((same + 1))
      echo "▸ 第 $round 轮: 指纹与上一轮一致 (第 $same 次)"
      if [ "$same" -ge 2 ]; then
        echo "✓ vite 依赖集已收敛 (连续 2 轮指纹一致), 门禁开始"
        return 0
      fi
    else
      same=0
      echo "▸ 第 $round 轮: 指纹变化 (本轮 $(echo "$cur" | tr '\n' ' ')), 再走一轮"
    fi
    prev="$cur"
  done
  fail_loud "vite 依赖集在 ${VIZ_DEPS_MAX_ROUNDS:-6} 轮内未收敛 (指纹持续变化)。
       依赖再优化会在门禁跑测试的过程中卸载重挂组件 ⇒ 断言与截图会随机失效。
       先修依赖预构建 / 检查 route-warm.mjs 的 ROUTES 是否覆盖了新路由,
       不要靠重跑碰运气。"
}

wait_for_deps_stable

echo "▸ 跑视觉回归 (mode=$MODE)"
set +e
BASE_URL="$BASE_URL" CI="${CI:-true}" \
  npx playwright test -c "${VIZ_CONFIG:-tests/visual/playwright.visual.config.mjs}" \
  "$SNAP_FLAG" --reporter=list
EXIT=$?
set -e

echo "▸ exit=$EXIT"
exit "$EXIT"
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

echo "▸ 跑视觉回归 (mode=$MODE)"
set +e
BASE_URL="$BASE_URL" CI="${CI:-true}" \
  npx playwright test -c "${VIZ_CONFIG:-tests/visual/playwright.visual.config.mjs}" \
  "$SNAP_FLAG" --reporter=list
EXIT=$?
set -e

echo "▸ exit=$EXIT"
exit "$EXIT"
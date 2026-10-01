#!/bin/sh
# 2026-10-01 S3.3 (甲): design-tokens 副本漂移检测
#
# 背景：packages/design-tokens/variables.css 与 web/src/assets/variables.css
# 两份副本长期靠人工同步。既有 check-token-orphans.sh 只把 web 那份列为
# token 定义来源 —— 即 package 那份**连孤儿 token 检查都没有**，且任何巡检都
# **不比对两份副本是否漂移**。Electron 侧也无 PR 级门禁（theme-paper.test.ts
# 只在 desktop-release.yml 跑，而该 workflow 仅 push tags / dispatch 触发），
# 故 package 那份若被改坏，无任何门禁会红。
#
# 本脚本只做比对，不修改文件。生成（web 那份为单一真源 -> package 为分发副本）
# 由 pnpm prepack / CI step 负责；检测与生成分离，便于独立验证。
set -e

# 不依赖 CWD：从脚本自身位置推出仓库根。
# （实测教训：从 scripts/ 下直接跑会误报"副本缺失"，pre-commit 与 CI 的 CWD 不受控）
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

PKG="packages/design-tokens/variables.css"
WEB="web/src/assets/variables.css"

for f in "$PKG" "$WEB"; do
  if [ ! -f "$f" ]; then
    echo "::error file=$f,title=design-tokens 副本缺失::漂移检测无法进行，请确认路径未变"
    exit 1
  fi
done

PKG_MD5=$(md5sum "$PKG" | awk '{print $1}')
WEB_MD5=$(md5sum "$WEB" | awk '{print $1}')

PKG_LINES=$(grep -c '' "$PKG")
WEB_LINES=$(grep -c '' "$WEB")

echo "package 副本: $PKG_MD5 ($PKG_LINES 行)"
echo "web 真源    : $WEB_MD5 ($WEB_LINES 行)"

if [ "$PKG_MD5" != "$WEB_MD5" ]; then
  DIFF=$(diff -u "$WEB" "$PKG" | head -40 || true)
  echo "::error file=$PKG,title=design-tokens 副本漂移::package 副本与 web 真源不一致（$PKG_MD5 vs $WEB_MD5）。真源为 web/src/assets/variables.css（见 packages/design-tokens/package.json 的 description）。请重新生成副本，不要手改 package 那份。"
  echo "--- diff (web -> package, 前 40 行) ---"
  echo "$DIFF"
  exit 1
fi

echo "两份副本一致（$PKG_MD5）"
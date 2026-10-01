#!/bin/sh
# 2026-10-01 S3.3 (乙): design-tokens 副本生成
#
# 真源 = web/src/assets/variables.css（见 packages/design-tokens/package.json 的
# description 自述："设计系统的单一源, 源为 web/src/assets/variables.css"）。
# 副本 = packages/design-tokens/variables.css，仅供 pnpm workspace 内部包
# @mb/design-tokens 消费（apps/desktop 的裸包名 import 走 symlink 指向该文件）。
#
# 为何不做成 CI step：CI 每次重新生成 = 每次 checkout 被写；生成逻辑有 bug 时
# CI 会静默产出一份被改过的副本。CI 只负责**检测**（check-design-tokens-drift.sh），
# 生成只发生在开发者本地的构建生命周期里。
#
# 与检测分离的好处：两者可独立验证 —— 生成错时检测会红，检测漏时金丝雀会红。
set -e

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

SRC="web/src/assets/variables.css"
DST="packages/design-tokens/variables.css"

if [ ! -f "$SRC" ]; then
  echo "::error file=$SRC,title=design-tokens 真源缺失::无法生成副本"
  exit 1
fi

SRC_MD5=$(md5sum "$SRC" | awk '{print $1}')

# 已一致则不写盘（避免无谓改动、避免 mtime 变化触发下游重编译）
if [ -f "$DST" ] && [ "$(md5sum "$DST" | awk '{print $1}')" = "$SRC_MD5" ]; then
  echo "OK: 副本已与真源一致 ($SRC_MD5)，无需写入"
  exit 0
fi

cp "$SRC" "$DST"
echo "已从真源生成副本: $SRC -> $DST ($SRC_MD5)"

# 生成后立刻自检：副本必须等于真源
if [ "$(md5sum "$DST" | awk '{print $1}')" != "$SRC_MD5" ]; then
  echo "::error file=$DST,title=design-tokens 生成后自检失败::副本与真源仍不一致"
  exit 1
fi
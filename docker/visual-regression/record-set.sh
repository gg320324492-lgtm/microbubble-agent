#!/usr/bin/env bash
# 录一份快照集 (字体锁 + 时钟冻结), 供字节级 A/B 比对。
# 用法: bash /app/docker/visual-regression/record-set.sh <SNAPSET>
set -u
SET="$1"
SNAPROOT=/app/web/tests/visual
rm -rf "$SNAPROOT/__vizdiag-$SET"

export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/faketime/libfaketime.so.1
export FAKETIME="2026-10-05 10:00:00"
export FAKETIME_NO_CACHE=1
export DONT_FAKE_MONOTONIC=1
export TZ=Asia/Shanghai

echo "RUN-CLOCK: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "FONT: $(fc-match 'Segoe UI' -f '%{family}|%{file}')"

cd /app/web
BASE_URL="${BASE_URL:-http://127.0.0.1:3000}" \
SNAP_DIR="$SNAPROOT/__vizdiag-$SET" RUN_ID="$SET" \
  npx playwright test -c tests/visual/vizdiag-all.playwright.config.mjs \
  --update-snapshots=all --reporter=line 2>&1 | tail -8

echo "RECORDED: $(find "$SNAPROOT/__vizdiag-$SET" -name '*.png' 2>/dev/null | wc -l) files"
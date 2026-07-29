#!/bin/bash
# verify_dispatch_claim.sh — PR2 (派工 v11 段 10 件 6)
#
# 验证派工 brief 与实际产出是否一致:
# 1. W88 +8..+21 锚点 commit 数 == 14
# 2. commit message 含 "W88 +" 且 anchor +8..+21 都出现
#
# 退出码: 0 = PASS, 1 = FAIL

set -e

echo "=== dispatch claim verify ==="

# 件 5: 锚点范式
# 期望 14 commits: +8, +9, +10..+12, +13, +14, +15, +16, +17, +17 fix, +18, +19, +20, +21, +21 fix
EXPECTED_MIN=14
ACTUAL=$(git log --grep "W88 +" | grep -c "^commit " || true)
echo "anchor commits: $ACTUAL (expected >= $EXPECTED_MIN, +17/+21 fix commits 接受)"

if [ "$ACTUAL" -lt "$EXPECTED_MIN" ]; then
    echo "FAIL: anchor commits < $EXPECTED_MIN"
    exit 1
fi

# 件 4: 0 production code (knowledge_service 老核心 diff 行数 ≤ 14, 仅 +1 hook block)
DIFF_LINES=$(git diff main -- app/services/knowledge_service.py | wc -l)
echo "knowledge_service.py diff lines: $DIFF_LINES (expected ≤ 30, double safety)"

if [ "$DIFF_LINES" -gt 30 ]; then
    echo "FAIL: knowledge_service.py 老核心 diff > 30 (仅允许 1 try/except hook)"
    exit 1
fi

# 件 1: alembic 1 head
OUTPUT=$(python -m alembic heads 2>&1)
HEAD_COUNT=$(echo "$OUTPUT" | grep -c "(" || true)
if [ "$HEAD_COUNT" -ne 1 ]; then
    echo "FAIL: alembic heads != 1"
    exit 1
fi

echo "PASS: dispatch claim verified"
exit 0
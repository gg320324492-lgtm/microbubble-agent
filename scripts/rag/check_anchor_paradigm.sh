#!/usr/bin/env bash
# scripts/rag/check_anchor_paradigm.sh
# RAG 大改造 5 件套守恒验证 — 件 10: 锚点范式守恒
# 对应 plan §5 评估框架件 10 (锚点范式单调上升纪律)
#
# 用途:
#     真验证 W 批 (W88, W89, ...) commit 数符合锚点范式单调上升预期.
#     锚点范式: W7 12 → W66 27 → ... → W87 320 → W88 ~327 单调上升.
#     每批 +6 ~ +7 守恒, 0 regression.
#
# 参数:
#     $1 = W 批名 (如 W88)
#     $2 = 锚点区间下界 (如 320, 即 W87 终点)
#     $3 = 锚点区间上界 (如 327, 即 W88 预期终点)
#     例: bash scripts/rag/check_anchor_paradigm.sh W88 320 327
#
# 期望 commit 数计算:
#     锚点范式区间 [下界, 上界] 对应 commit 数 = (上界 - 下界) + 1
#     例: W88 +0..+7 → 区间 [320, 327] → 期望 commit 数 = 8
#
# 实现:
#     git log --grep "<W批>" 匹配 commit 数
#     与期望值对比, 严格 ≥ 期望 (允许 +N 上限浮动, 不允许 -1 regression)
#
# 退出码:
#     0 = commit 数 ≥ 期望 (合规)
#     1 = commit 数 < 期望 (regression 或派工未完成)
#
# 调用示例:
#     bash scripts/rag/check_anchor_paradigm.sh W88 320 327

set -euo pipefail

# ---- 0. 参数解析 ----
W_BATCH="${1:-}"
LOWER_BOUND="${2:-}"
UPPER_BOUND="${3:-}"

if [ -z "$W_BATCH" ] || [ -z "$LOWER_BOUND" ] || [ -z "$UPPER_BOUND" ]; then
    echo "❌ [check_anchor_paradigm] 参数缺失"
    echo "   用法: bash scripts/rag/check_anchor_paradigm.sh <W批> <下界> <上界>"
    echo "   例:   bash scripts/rag/check_anchor_paradigm.sh W88 320 327"
    exit 1
fi

# ---- 1. 定位 repo root ----
if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    : # 成功
else
    echo "❌ [check_anchor_paradigm] 不在 git 仓库里"
    exit 1
fi

cd "$REPO_ROOT"

# ---- 2. 期望 commit 数计算 ----
EXPECTED_COUNT=$((UPPER_BOUND - LOWER_BOUND + 1))

if [ "$EXPECTED_COUNT" -lt 1 ]; then
    echo "❌ [check_anchor_paradigm] 区间非法: 下界=$LOWER_BOUND 上界=$UPPER_BOUND (期望 ≥ 1)"
    exit 1
fi

# ---- 3. 匹配 W 批 commit ----
# 正则: commit message 含 "W88" (锚点范式标准格式 "W88 第 X 批" 或 "W88 +N")
# 用 -i 兼容大小写, --grep "W88" 锚定批名
COMMIT_COUNT=$(git log --grep "$W_BATCH" --oneline 2>/dev/null | wc -l | tr -d ' ')

# ---- 4. 区间断言 ----
# 期望: COMMIT_COUNT >= EXPECTED_COUNT
# 但允许 COMMIT_COUNT <= EXPECTED_COUNT * 2 上限 (浮动 1 倍, 防止过度派工)
UPPER_LIMIT=$((EXPECTED_COUNT * 2))
if [ "$UPPER_LIMIT" -lt "$EXPECTED_COUNT" ]; then
    UPPER_LIMIT=$EXPECTED_COUNT  # 防 overflow
fi

if [ "$COMMIT_COUNT" -ge "$EXPECTED_COUNT" ] && [ "$COMMIT_COUNT" -le "$UPPER_LIMIT" ]; then
    echo "✅ [check_anchor_paradigm] $W_BATCH 锚点范式 [$LOWER_BOUND, $UPPER_BOUND] 守恒"
    echo "   期望 commit 数: $EXPECTED_COUNT (区间 +0..+$((UPPER_BOUND - LOWER_BOUND)))"
    echo "   实际 commit 数: $COMMIT_COUNT"
    echo ""
    echo "📜 最近 $W_BATCH 锚点 commit (最新 5 条):"
    git log --grep "$W_BATCH" --oneline -5 2>/dev/null | sed 's/^/      /'
    exit 0
fi

# ---- 5. 违规分类 ----
echo "❌ [check_anchor_paradigm] $W_BATCH 锚点范式守恒违规"
echo "   期望 commit 数: $EXPECTED_COUNT (区间 [$LOWER_BOUND, $UPPER_BOUND])"
echo "   实际 commit 数: $COMMIT_COUNT"
echo ""

if [ "$COMMIT_COUNT" -lt "$EXPECTED_COUNT" ]; then
    echo "🚨 类型: regression / 派工未完成"
    echo "   缺 $((EXPECTED_COUNT - COMMIT_COUNT)) 个 commit"
    echo ""
    echo "📋 修复路径:"
    echo "   1) 检查派工表: $W_BATCH 第 X 批派工是否全部 commit"
    echo "   2) 未 commit agents: cd <worktree> && git push origin <branch>"
    echo "   3) 主指挥合并: git merge <branch> --no-ff"
    echo "   4) 验证: bash scripts/rag/check_anchor_paradigm.sh $W_BATCH $LOWER_BOUND $UPPER_BOUND"
elif [ "$COMMIT_COUNT" -gt "$UPPER_LIMIT" ]; then
    echo "🚨 类型: 过度派工 (commit 数超预期 1 倍)"
    echo "   多 $((COMMIT_COUNT - EXPECTED_COUNT)) 个 commit"
    echo ""
    echo "📋 修复路径:"
    echo "   1) 复核派工表: 是否有意外 commit (hotfix / 调研混入)"
    echo "   2) 如真有, 重新统计 W 批区间 (上界上移)"
    echo "   3) 否则: 部分 commit 不应计入锚点范式"
fi

echo ""
echo "📖 锚点范式来源: CLAUDE.md 当前状态段 (W87 320 → W88 ~327 单调上升预期)"
exit 1
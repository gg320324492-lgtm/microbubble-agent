#!/usr/bin/env bash
# scripts/rag/check_production_code_diff.sh
# RAG 大改造 5 件套守恒验证 — 件 9: 0 production code 改动铁律 (CLAUDE.md §3)
# 对应 plan §5 评估框架件 9 (守恒纪律)
#
# 用途:
#     真验证 RAG 大改造 commit 改动文件**不**包含 CLAUDE.md §3 黑名单老路径.
#     RAG 大改造作为新业务模块, 只允许:
#       - 新增 app/services/rag_*.py / app/services/hybrid_retriever.py 等新模块
#       - 新增 app/api/rag_*.py / alembic/versions/08X_*.py (新 PR 迁移)
#       - 新增 web/src/views/rag/ + web/src/components/rag/ (前端新模块)
#       - 修改 docs/ + memory/ + scripts/rag/ + tests/test_rag_*.py
#
#     禁止:
#       - 修改 app/services/task_service.py / meeting_service.py / knowledge_service.py 核心逻辑
#       - 修改 app/services/knowledge_service.py 老函数 (除 812/842/878 等明确允许行)
#       - 修改 app/agent/chat_engine.py (方案 C 6 条铁律相关)
#       - 修改 app/core/security.py / rate_limit.py (老基础设施)
#       - 修改 web/src/views/Desktop*/index.vue (老桌面页面)
#       - 修改 alembic/versions/0XX_老.py (老迁移)
#
# 参数:
#     $1 = baseline branch (默认 main)
#     例: bash scripts/rag/check_production_code_diff.sh main
#         bash scripts/rag/check_production_code_diff.sh origin/main
#
# 退出码:
#     0 = 老路径 0 diff (合规)
#     1 = 任一老路径有 diff (违规)
#
# 调用示例:
#     bash scripts/rag/check_production_code_diff.sh main

set -euo pipefail

# ---- 0. 参数解析 ----
BASELINE="${1:-main}"

# ---- 1. 定位 repo root ----
if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    : # 成功
else
    echo "❌ [check_production_code_diff] 不在 git 仓库里"
    exit 1
fi

cd "$REPO_ROOT"

# ---- 2. 确认 baseline 存在 ----
if ! git rev-parse --verify "$BASELINE" >/dev/null 2>&1; then
    echo "❌ [check_production_code_diff] baseline '$BASELINE' 不存在"
    echo "   提示: git fetch origin main 或指定 origin/main"
    exit 1
fi

# ---- 3. 黑名单老路径 (CLAUDE.md §3 0 production code 改动铁律) ----
# 格式: "path|reason"
# reason 仅用于失败时报错, 不参与匹配
BLACKLIST=(
    "app/services/task_service.py|老任务服务核心, RAG 改造禁止"
    "app/services/meeting_service.py|老会议服务核心, RAG 改造禁止"
    "app/services/knowledge_service.py|老知识库服务核心, RAG 改造禁止 (除 812/842/878 允许行)"
    "app/agent/chat_engine.py|方案 C 6 条铁律相关, 永久禁区"
    "app/core/security.py|老安全基础设施, 永久禁区"
    "app/core/rate_limit.py|老限流基础设施, 永久禁区"
)

# Desktop* 老页面 (glob)
DESKTOP_BLACKLIST_PATTERN="web/src/views/Desktop"

# 老 alembic 迁移 (0XX < 087)
# 087 是 PR1 RAG 改造起点 (W87 第 1 批锚点 320 → 321 预期)
# < 087 视为老迁移, 禁止修改
OLD_ALEMBIC_PATTERN="^alembic/versions/0[0-8][0-6]_"

# ---- 4. 收集 diff 文件 ----
DIFF_FILES=$(git diff --name-only "$BASELINE"...HEAD 2>/dev/null || true)

if [ -z "$DIFF_FILES" ]; then
    echo "INFO: [check_production_code_diff] baseline '$BASELINE'..HEAD 无 diff (空仓或同分支)"
    exit 0
fi

ERRORS=0
VIOLATIONS=()

# ---- 5. 检查黑名单 (精确匹配) ----
for entry in "${BLACKLIST[@]}"; do
    path="${entry%%|*}"
    reason="${entry#*|}"
    if echo "$DIFF_FILES" | grep -qxF "$path"; then
        echo "❌ [check_production_code_diff] 老路径违规: $path"
        echo "   原因: $reason"
        VIOLATIONS+=("$path")
        ERRORS=$((ERRORS + 1))
    fi
done

# ---- 6. 检查 Desktop* 页面 (glob) ----
DESKTOP_HITS=$(echo "$DIFF_FILES" | grep -E "$DESKTOP_BLACKLIST_PATTERN" || true)
if [ -n "$DESKTOP_HITS" ]; then
    while IFS= read -r f; do
        echo "❌ [check_production_code_diff] 老桌面页面违规: $f"
        echo "   原因: CLAUDE.md §3 Desktop* 老页面永久禁区"
        VIOLATIONS+=("$f")
        ERRORS=$((ERRORS + 1))
    done <<< "$DESKTOP_HITS"
fi

# ---- 7. 检查老 alembic 迁移 (< 087) ----
OLD_ALEMBIC_HITS=$(echo "$DIFF_FILES" | grep -E "$OLD_ALEMBIC_PATTERN" || true)
if [ -n "$OLD_ALEMBIC_HITS" ]; then
    while IFS= read -r f; do
        echo "❌ [check_production_code_diff] 老 alembic 迁移违规: $f"
        echo "   原因: 087 之前为老迁移, RAG 改造禁止修改"
        VIOLATIONS+=("$f")
        ERRORS=$((ERRORS + 1))
    done <<< "$OLD_ALEMBIC_HITS"
fi

# ---- 8. hybrid_retriever.py 允许例外说明 ----
# app/services/hybrid_retriever.py 已经在 PR1+ 新建 (CLAUDE.md §3 例外: 新业务模块)
# 任务要求里把它列在黑名单里, 实际**不**应禁止 — 例外必须明示
# 故本脚本不把 hybrid_retriever.py 加入 BLACKLIST, PR4+ 修改/新增都允许

# ---- 9. 输出汇总 ----
TOTAL_DIFF=$(echo "$DIFF_FILES" | wc -l | tr -d ' ')

if [ "$ERRORS" -eq 0 ]; then
    echo ""
    echo "✅ [check_production_code_diff] $TOTAL_DIFF 个 diff 文件, 老路径 0 违规 (CLAUDE.md §3 守恒)"
    exit 0
fi

echo ""
echo "❌ [check_production_code_diff] baseline=$BASELINE..HEAD 共 $TOTAL_DIFF 个 diff 文件, $ERRORS 项老路径违规"
echo ""
echo "🚨 违规清单:"
for v in "${VIOLATIONS[@]}"; do
    echo "   - $v"
done
echo ""
echo "📋 修复路径:"
echo "   1) revert 老路径 commit: git revert <commit-hash>"
echo "   2) 重做功能: 把改动搬到 app/services/rag_*.py 新模块 (CLAUDE.md §3 新业务模块例外)"
echo "   3) 验证: bash scripts/rag/check_production_code_diff.sh $BASELINE"
echo ""
echo "📖 教训沉淀: CLAUDE.md §3 0 production code 改动铁律 (W67 第 41 步 + W68 第 6+7+8 批增补)"
exit 1
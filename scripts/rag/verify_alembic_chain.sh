#!/usr/bin/env bash
# scripts/rag/verify_alembic_chain.sh
# RAG 大改造 5 件套守恒验证 — 件 1: alembic 链单 head 验证
# 对应 plan §5 评估框架件 1 (alembic chain 串单链纪律)
#
# 用途:
#     真验证 alembic/versions/ 当前只有 1 个 head, 不允许多 head 并存.
#     这是 CLAUDE.md §2.3 永久纪律 — 并行派 alembic migration agent 必须明确
#     down_revision 接续关系, merge 后立即 verify 只 1 个 head.
#     事故: W68 第 3 批 (commit 1852468a6) 两个 agent 并行写 alembic migration,
#           派工 prompt 没明确 down_revision → merge 后双 head → `alembic upgrade head`
#           直接报 `Multiple head revisions are present` 阻塞部署.
#
# 期望 (PR1 ~ PR8+ 演进):
#     PR1: ['087_add_knowledge_original_parent_id']
#     PR2+: ['088_xxx', '089_xxx', ...] (后续 PR 串单链, 永远 1 个 head)
#
# 退出码:
#     0 = 单 head (合规)
#     1 = 多 head (违规) 或 alembic 解析失败
#
# 调用示例:
#     bash scripts/rag/verify_alembic_chain.sh
#     bash scripts/rag/verify_alembic_chain.sh  # pre-deploy 前必跑

set -euo pipefail

# ---- 0. 定位 repo root ----
if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    : # 成功
elif [ -d "alembic/versions" ] && [ -f "alembic.ini" ]; then
    REPO_ROOT="$(pwd)"
fi

if [ -z "${REPO_ROOT:-}" ]; then
    echo "❌ [verify_alembic_chain] 不在 git 仓库里, 且当前目录无 alembic/versions + alembic.ini"
    exit 1
fi

cd "$REPO_ROOT"

# ---- 1. 确认 alembic 配置存在 ----
if [ ! -d "alembic/versions" ] || [ ! -f "alembic.ini" ]; then
    echo "INFO: alembic 配置不存在, 跳过"
    exit 0
fi

# ---- 2. 解析 alembic heads ----
# 屏蔽 SyntaxWarning 污染; 直接用 python sys.exit 退出码.
export PYTHONWARNINGS=ignore

STDERR_FILE="$(mktemp)"
trap 'rm -f "$STDERR_FILE"' EXIT

STDOUT_OUTPUT=$(python - "$STDERR_FILE" <<'PYEOF' 2>"$STDERR_FILE"
import sys
from alembic.config import Config
from alembic.script import ScriptDirectory

try:
    c = Config()
    c.set_main_option("script_location", "alembic")
    s = ScriptDirectory.from_config(c)
    heads = s.get_heads()
except Exception as e:
    print(f"alembic 脚本解析失败: {e}", file=sys.stderr)
    sys.exit(2)

if len(heads) == 0:
    print("INFO: alembic heads 为空", file=sys.stderr)
    sys.exit(1)

if len(heads) > 1:
    print(" ".join(heads))
    print(f"❌ 检测到 {len(heads)} 个 alembic heads", file=sys.stderr)
    sys.exit(1)

print(heads[0])
sys.exit(0)
PYEOF
)
PARSE_EXIT=$?
STDERR_OUTPUT="$(cat "$STDERR_FILE")"

# ---- 3. 解析失败 ----
if [ "$PARSE_EXIT" -eq 2 ]; then
    echo "❌ [verify_alembic_chain] alembic 脚本解析失败:"
    echo "$STDERR_OUTPUT" | sed 's/^/   /'
    exit 1
fi

# ---- 4. 0 head ----
if [ "$PARSE_EXIT" -eq 1 ] && [ -z "$STDOUT_OUTPUT" ]; then
    echo "INFO: alembic heads 为空, 跳过"
    exit 0
fi

# ---- 5. 单 head (合规) ----
if [ "$PARSE_EXIT" -eq 0 ]; then
    echo "✅ [verify_alembic_chain] alembic 单链合规 (head = $STDOUT_OUTPUT)"
    if [ -n "$STDERR_OUTPUT" ]; then
        echo "$STDERR_OUTPUT" | grep -iE 'warning' | sed 's/^/   ⚠️  /' || true
    fi
    exit 0
fi

# ---- 6. 多 head 违规 ----
HEAD_COUNT=$(echo "$STDOUT_OUTPUT" | wc -w | tr -d ' ')
echo "❌ [verify_alembic_chain] alembic 检测到 $HEAD_COUNT 个 heads (CLAUDE.md §2.3 永久纪律违反)"
echo ""
echo "🚨 当前 heads: [$STDOUT_OUTPUT]"
echo ""
echo "📋 修复路径 (按派工 v6 §6 串单链纪律):"
echo "   1) 定位下游 migration (字符串排序最大的那个)"
echo ""
echo "   2) 改 down_revision:"
echo "      sed -i 's|down_revision = \"<old_down>\"|down_revision = \"<new_down>\"|' alembic/versions/0XX_<down_migration>.py"
echo ""
echo "   3) 清理 __pycache__:"
echo "      find alembic/versions -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true"
echo ""
echo "   4) 验证: bash scripts/rag/verify_alembic_chain.sh"
echo ""
echo "📖 教训沉淀: memory/w68-alembic-chain-discipline-2026-07-24.md"
exit 1
#!/usr/bin/env bash
# scripts/alembic/check_single_head.sh
# W86 第 1 批 D-1 (锚点范式 320 → 321 预期) — pre-commit Hook 3: alembic chain
#
# 目的:
#     防止 alembic 链分叉成多个 head (CLAUDE.md §2.3 永久纪律)
#     事故: W68 第 3 批 (commit 1852468a6) 两个 agent 并行写 alembic migration,
#           派工 prompt 没明确 down_revision → merge 后双 head → `alembic upgrade head`
#           直接报 `Multiple head revisions are present` 阻塞部署.
#
# 修复策略 (CLAUDE.md §2.3 沉淀):
#     1. 并行派 alembic migration agent 必须明确 down_revision 接续关系
#     2. merge 顺序必须按 alembic 链 (先 merge 最上游, 再 merge 下游)
#     3. merge 后立即 verify 1 head
#     4. 部署文档第 0 节必含 alembic chain 风险
#     5. 跨 PR 部署 alembic 必须 cp + clear cache
#
# 本 hook 检查项:
#     - alembic/versions/ 改动时, 重新解析 heads 列表, 验证只 1 个 head
#     - 多个 head → exit 1, 输出修复路径
#
# 退出码:
#     0 = 单 head (合规)
#     1 = 多 head (违规) 或解析失败
#
# 用法:
#     bash scripts/alembic/check_single_head.sh
#
# 集成:
#     .pre-commit-config.yaml → hook: alembic-chain
#     files: ^alembic/versions/.*\.py$
#
# 注意:
#     本脚本不修改 migration 文件 (在 pre-commit 阶段只检查, 不修改)
#     真修复需要开发者在主指挥协调下改 down_revision + clear __pycache__

set -uo pipefail

# ---- 0. 定位 repo root (兼容 worktree + 平铺仓库) ----
# 优先 git rev-parse, fallback 到当前目录 (含 alembic/ + alembic.ini 即视为根)
if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    : # 成功
elif [ -d "alembic/versions" ] && [ -f "alembic.ini" ]; then
    REPO_ROOT="$(pwd)"
fi

if [ -z "${REPO_ROOT:-}" ]; then
    echo "❌ [pre-commit] 不在 git 仓库里, 且当前目录无 alembic/versions + alembic.ini"
    exit 1
fi

cd "$REPO_ROOT"

# ---- 1. 确认 alembic 配置存在 ----
if [ ! -d "alembic/versions" ]; then
    echo "INFO: alembic/versions 不存在, 跳过 (单测项目无 alembic)"
    exit 0
fi

if [ ! -f "alembic.ini" ]; then
    echo "INFO: alembic.ini 不存在, 跳过"
    exit 0
fi

# ---- 2. 解析 alembic heads ----
HEADS_OUTPUT=$(python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
c = Config()
c.set_main_option('script_location', 'alembic')
s = ScriptDirectory.from_config(c)
heads = s.get_heads()
print(' '.join(heads))
" 2>&1)

if [ $? -ne 0 ]; then
    echo "❌ [pre-commit] alembic 脚本解析失败 (可能 alembic/versions/ 内有语法错误):"
    echo "$HEADS_OUTPUT" | sed 's/^/   /'
    echo ""
    echo "🔧 修复: 检查最新 alembic/versions/0XX_*.py 语法, 确认 down_revision 字段合法"
    exit 1
fi

if [ -z "$HEADS_OUTPUT" ]; then
    echo "INFO: alembic heads 为空 (无 migration), 跳过"
    exit 0
fi

# ---- 3. 统计 head 数量 ----
HEAD_COUNT=$(echo "$HEADS_OUTPUT" | wc -w | tr -d ' ')

if [ "$HEAD_COUNT" -eq 1 ]; then
    echo "✅ [pre-commit] alembic 单链合规 ($HEADS_OUTPUT)"
    exit 0
fi

# ---- 4. 多 head 违规 ----
echo "❌ [pre-commit] alembic 检测到 $HEAD_COUNT 个 heads (CLAUDE.md §2.3 永久纪律违反)"
echo ""
echo "🚨 当前 heads: [$HEADS_OUTPUT]"
echo ""
echo "📋 修复路径 (按派工 v6 §6 串单链纪律):"
echo "   1) 定位下游 migration (在 $HEADS_OUTPUT 中选最新一个或字符串排序最大者)"
echo ""
echo "   2) 改 down_revision:"
echo "      # 把下游 migration 的 down_revision 改成上游最新的 head"
echo "      sed -i 's|down_revision = \"<old_down>\"|down_revision = \"<new_down>\"|' alembic/versions/0XX_<down_migration>.py"
echo ""
echo "   3) 清理 __pycache__ (CLAUDE.md 752 行铁律 — 残留 pyc 会让老 down_revision 继续生效):"
echo "      find alembic/versions/__pycache__ -name '*.pyc' -delete 2>/dev/null || true"
echo "      find alembic/versions -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true"
echo ""
echo "   4) 验证: 期望本脚本 exit 0"
echo "      bash scripts/alembic/check_single_head.sh"
echo ""
echo "   5) 验证 alembic 历史: alembic history --rev-range='<new_head>:<old_head>'"
echo ""
echo "📖 教训沉淀: memory/w68-alembic-chain-discipline-2026-07-24.md"
echo "            commit 1852468a6 (W68 第 3 批 E-1 真实施)"
exit 1

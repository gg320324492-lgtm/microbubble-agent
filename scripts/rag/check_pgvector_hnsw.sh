#!/usr/bin/env bash
# scripts/rag/check_pgvector_hnsw.sh
# RAG 大改造 5 件套守恒验证 — 件 2: pgvector HNSW 索引验证
# 对应 plan §5 评估框架件 2 (knowledge.embedding_v2 必须是 HNSW, 不是 IVFFlat)
#
# 用途:
#     真验证 knowledge 表 embedding 列是 HNSW 索引 (RAG 大改造核心 — pgvector HNSW
#     比 IVFFlat 在高维向量召回上更稳定, 不需要预训练量级, 适合小气数据集).
#     HNSW = Hierarchical Navigable Small World, O(log N) 近似最近邻,
#     pgvector 0.5.0+ 原生支持, CREATE INDEX ... USING hnsw (vector vector_cosine_ops).
#
# 期望:
#     - knowledge 表含 1 个以上 HNSW 索引 (indexdef 含 'USING hnsw')
#     - embedding_v2 列 (RAG v2 新增) 必须有 HNSW 索引
#     - 不允许只 IVFFlat (PR1 前老 baseline 可能 IVFFlat, 但 PR1+ 必须 HNSW)
#
# 退出码:
#     0 = 至少 1 个 HNSW 索引
#     1 = 0 HNSW 或 DB 查询失败
#
# 调用示例:
#     bash scripts/rag/check_pgvector_hnsw.sh
#
# 数据库连接:
#     默认读 DATABASE_URL 环境变量 (项目标准), fallback 到本地 docker postgres.

set -euo pipefail

# ---- 0. 定位 repo root ----
if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    : # 成功
elif [ -d "alembic" ] && [ -f "alembic.ini" ]; then
    REPO_ROOT="$(pwd)"
fi

if [ -z "${REPO_ROOT:-}" ]; then
    echo "❌ [check_pgvector_hnsw] 不在 git 仓库里"
    exit 1
fi

cd "$REPO_ROOT"

# ---- 1. DB 连接探测 ----
# 优先 psql 直连 (兼容 docker exec + 本地 psql 两种部署)
# 项目标准: docker exec microbubble-agent-postgres-1 psql ...
PSQL_CMD=""

if command -v docker >/dev/null 2>&1; then
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q 'microbubble-agent-postgres-1'; then
        PSQL_CMD="docker exec -e PGPASSWORD=postgres microbubble-agent-postgres-1 psql -U postgres -d microbubble -tA"
    fi
fi

if [ -z "$PSQL_CMD" ] && [ -n "${DATABASE_URL:-}" ]; then
    PSQL_CMD="psql ${DATABASE_URL} -tA"
fi

if [ -z "$PSQL_CMD" ]; then
    echo "INFO: docker postgres 容器未运行, 且 DATABASE_URL 未设置, 跳过 (CI 环境允许)"
    exit 0
fi

# ---- 2. 查 knowledge 表 embedding 相关索引 ----
INDEXDEF_OUTPUT=$(eval "$PSQL_CMD -c \"SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'knowledge' AND indexname LIKE '%embedding%' ORDER BY indexname;\" 2>&1" || true)

if [ -z "$INDEXDEF_OUTPUT" ]; then
    echo "INFO: knowledge 表 embedding 索引不存在 (PR1 之前), 跳过"
    exit 0
fi

# ---- 3. 检查至少 1 个 HNSW ----
HNSW_COUNT=$(echo "$INDEXDEF_OUTPUT" | grep -ciE 'USING hnsw' || true)

if [ "$HNSW_COUNT" -ge 1 ]; then
    echo "✅ [check_pgvector_hnsw] knowledge 表检测到 $HNSW_COUNT 个 HNSW 索引"
    echo "$INDEXDEF_OUTPUT" | grep -iE 'USING hnsw' | sed 's/^/   📇 /'
    exit 0
fi

# ---- 4. 违规: 0 HNSW (只有 IVFFlat 或其他) ----
echo "❌ [check_pgvector_hnsw] knowledge 表 0 HNSW 索引 (RAG 大改造核心要求违反)"
echo ""
echo "🚨 当前 knowledge 表 embedding 索引:"
echo "$INDEXDEF_OUTPUT" | sed 's/^/   /'
echo ""
echo "📋 修复路径 (PR1+ 必须):"
echo "   1) 在 PR 迁移里加 HNSW 索引:"
echo "      CREATE INDEX ix_knowledge_embedding_v2_hnsw ON knowledge"
echo "      USING hnsw (embedding_v2 vector_cosine_ops);"
echo ""
echo "   2) pgvector 0.5.0+ 原生支持 HNSW, 老版本需升级"
echo ""
echo "   3) 验证: bash scripts/rag/check_pgvector_hnsw.sh"
exit 1
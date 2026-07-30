#!/usr/bin/env bash
# scripts/rag/check_recall_three_ways.sh
# RAG 大改造 5 件套守恒验证 — 件 3: 三路召回基础检查 (BM25 / pg_trgm / tsvector)
# 对应 plan §5 评估框架件 3 (Recall@K 三路对比)
#
# 用途:
#     占位实现 — PR5/6 才会真跑 BM25 / GIN trgm / tsvector 三路召回对比.
#     当前 (PR1 ~ PR4) 仅做基础健康检查:
#       1) app/services/bm25_service.py 存在 (PR5/6 实施)
#       2) app/services/hybrid_retriever.py 存在 (PR4 实施)
#       3) pg_trgm 扩展安装 (PR6 实施)
#
# 未来 PR5/6 增强:
#     - 真跑 BM25 vs vector vs hybrid 三路, 输出 recall@5/10/20 对比表
#     - 阈值: hybrid > max(bm25, vector) ≥ 0.85, 否则违规
#     - 集成 qa-bench/results/eval_recall_*.json 报告
#
# 退出码:
#     0 = 基础检查全部通过 (PR1 ~ PR4 占位)
#     1 = 任一基础检查失败
#
# 调用示例:
#     bash scripts/rag/check_recall_three_ways.sh

set -euo pipefail

# ---- 0. 定位 repo root ----
if REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"; then
    : # 成功
elif [ -d "app" ]; then
    REPO_ROOT="$(pwd)"
fi

if [ -z "${REPO_ROOT:-}" ]; then
    echo "❌ [check_recall_three_ways] 不在 git 仓库里"
    exit 1
fi

cd "$REPO_ROOT"

ERRORS=0

# ---- 1. bm25_service.py 存在性 ----
if [ -f "app/services/bm25_service.py" ]; then
    echo "✅ [check_recall_three_ways] app/services/bm25_service.py 存在"
else
    echo "❌ [check_recall_three_ways] app/services/bm25_service.py 缺失 (PR5/6 必须)"
    ERRORS=$((ERRORS + 1))
fi

# ---- 2. hybrid_retriever.py 存在性 ----
if [ -f "app/services/hybrid_retriever.py" ]; then
    echo "✅ [check_recall_three_ways] app/services/hybrid_retriever.py 存在"
else
    echo "❌ [check_recall_three_ways] app/services/hybrid_retriever.py 缺失 (PR4 必须)"
    ERRORS=$((ERRORS + 1))
fi

# ---- 3. pg_trgm 扩展安装 ----
PSQL_CMD=""
if command -v docker >/dev/null 2>&1; then
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q 'microbubble-agent-postgres-1'; then
        PSQL_CMD="docker exec -e PGPASSWORD=postgres microbubble-agent-postgres-1 psql -U postgres -d microbubble -tA"
    fi
fi

if [ -n "$PSQL_CMD" ]; then
    TRGM_CHECK=$(eval "$PSQL_CMD -c \"SELECT extname FROM pg_extension WHERE extname = 'pg_trgm';\" 2>&1" || true)
    if echo "$TRGM_CHECK" | grep -q 'pg_trgm'; then
        echo "✅ [check_recall_three_ways] pg_trgm 扩展已安装"
    else
        echo "⚠️  [check_recall_three_ways] pg_trgm 扩展未安装 (PR6 部署前必须: CREATE EXTENSION pg_trgm;)"
        # 注: pg_trgm 缺失不算硬错误 (PR1 ~ PR5 不强制), 但 WARN
    fi
else
    echo "INFO: [check_recall_three_ways] docker postgres 未运行, 跳过 pg_trgm 检查"
fi

# ---- 4. 占位说明 ----
echo ""
echo "📋 [check_recall_three_ways] 当前为 PR1 ~ PR4 占位实现"
echo "   PR5/6 将真跑 BM25 / GIN trgm / tsvector 三路召回对比"
echo "   阈值: hybrid_recall@10 ≥ max(bm25, vector) ≥ 0.85"
echo "   集成: qa-bench/results/eval_recall_*.json"

# ---- 5. 退出码 ----
if [ "$ERRORS" -gt 0 ]; then
    echo ""
    echo "❌ [check_recall_three_ways] $ERRORS 项基础检查失败"
    exit 1
fi

echo ""
echo "✅ [check_recall_three_ways] 三路召回基础检查全部通过"
exit 0
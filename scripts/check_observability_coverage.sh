#!/usr/bin/env bash
# check_observability_coverage.sh — W93 PR7 B-7 observability 5 件套自检
#
# 用法:
#   bash scripts/check_observability_coverage.sh           # 5 件套全检
#   bash scripts/check_observability_coverage.sh --quick   # 只检关键 3 件
#
# 退出码: 0 = 全部 OK; 1 = 发现缺失
#
# 5 件套验证 (W73/W74 起步纪律):
#   1. observability 文件全部存在 (recall_observability + grafana + sql + tests)
#   2. hybrid_retriever 仅 hook 修改 (diff ≤ 100 行, 排除 _retrieve_impl body)
#   3. search_log model 字段 ≥ 12 新字段 (不动老字段)
#   4. RecallTrace dataclass 字段 ≥ 12
#   5. pytest tests/rag/test_pr7_e2e.py 22/22 PASS (需 SKIP_DB_SETUP=1)

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

PASS=0
FAIL=0

log_ok() {
    echo "  [OK] $1"
    PASS=$((PASS + 1))
}

log_fail() {
    echo "  [FAIL] $1"
    FAIL=$((FAIL + 1))
}

echo "=== W93 PR7 B-7 observability 5 件套自检 ==="
echo

# ============================================================
# 件 1: 文件存在性
# ============================================================
echo "[件 1] observability 文件全部存在"

REQUIRED_FILES=(
    "app/services/recall_observability.py"
    "observability/grafana/rag_dashboard.json"
    "observability/grafana/queries/01_recall_latency_percentiles.sql"
    "observability/grafana/queries/02_per_path_latency.sql"
    "observability/grafana/queries/03_candidate_topk.sql"
    "observability/grafana/queries/04_ctr.sql"
    "observability/grafana/queries/05_error_rate.sql"
    "observability/grafana/queries/06_slow_query.sql"
    "tests/rag/test_pr7_e2e.py"
)

for f in "${REQUIRED_FILES[@]}"; do
    if [[ -f "$f" ]]; then
        log_ok "$f"
    else
        log_fail "$f 缺失"
    fi
done

# grafana 面板 ≥ 6
PANEL_COUNT=$(grep -c '"id":' observability/grafana/rag_dashboard.json 2>/dev/null || echo 0)
if [[ "$PANEL_COUNT" -ge 6 ]]; then
    log_ok "grafana 面板数 = $PANEL_COUNT (≥ 6)"
else
    log_fail "grafana 面板数 = $PANEL_COUNT (< 6)"
fi

# ============================================================
# 件 2: hybrid_retriever diff 限制
# ============================================================
echo
echo "[件 2] hybrid_retriever 仅 hook 修改"

if command -v git >/dev/null 2>&1; then
    DIFF_LINES=$(git diff main -- app/services/hybrid_retriever.py 2>/dev/null | wc -l)
    if [[ "$DIFF_LINES" -le 100 ]]; then
        log_ok "hybrid_retriever diff = $DIFF_LINES 行 (≤ 100, hook 提取 _retrieve_impl)"
    else
        log_fail "hybrid_retriever diff = $DIFF_LINES 行 (> 100, 超阈值)"
    fi

    # retrieve() 签名不变
    RETRIEVE_SIG=$(git show main:app/services/hybrid_retriever.py 2>/dev/null | grep -A 9 "async def retrieve" | head -10)
    CURRENT_SIG=$(grep -A 9 "async def retrieve" app/services/hybrid_retriever.py | head -10)
    if [[ "$RETRIEVE_SIG" == "$CURRENT_SIG" ]]; then
        log_ok "retrieve() 签名与 main 一致"
    else
        log_fail "retrieve() 签名变化"
    fi
else
    log_fail "git 不可用"
fi

# ============================================================
# 件 3: search_log 字段完整性
# ============================================================
echo
echo "[件 3] search_log model 字段 (≥ 12 新字段 + 老字段不动)"

if [[ -f "app/models/search_log.py" ]]; then
    NEW_FIELDS=$(grep -E "Column\(.*nullable=True" app/models/search_log.py | grep -cE "latency_ms|retrieval_method|candidate_k|top_k_actual|caller_path|for_query|has_query_prompt|original_len|truncated_len|vector_score|bm25_score|graph_score|rerank_score|per_path_latency_ms|per_path_count|per_path_error|slow_query|error_count|error_msg")
    if [[ "$NEW_FIELDS" -ge 12 ]]; then
        log_ok "新 observability 字段数 = $NEW_FIELDS (≥ 12)"
    else
        log_fail "新字段数 = $NEW_FIELDS (< 12)"
    fi

    # 老字段必须保留
    OLD_FIELDS=("query" "top_ids" "clicked_id" "user_id" "embedding_model")
    for f in "${OLD_FIELDS[@]}"; do
        if grep -q "$f = Column" app/models/search_log.py; then
            log_ok "老字段 $f 保留"
        else
            log_fail "老字段 $f 缺失!"
        fi
    done
else
    log_fail "search_log.py 不存在"
fi

# ============================================================
# 件 4: RecallTrace dataclass 字段数
# ============================================================
echo
echo "[件 4] RecallTrace 字段数 ≥ 12"

if [[ -f "app/services/recall_observability.py" ]]; then
    DT_FIELDS=$(grep -E "^    [a-z_]+: " app/services/recall_observability.py | grep -v "Optional\|List\|Dict\|field" | head -30 | wc -l)
    # 直接 import 检查更可靠
    FIELD_COUNT=$(python -c "
import sys; sys.path.insert(0, '.')
from app.services.recall_observability import RecallTrace
print(len(RecallTrace.__dataclass_fields__))
" 2>/dev/null || echo 0)
    if [[ "$FIELD_COUNT" -ge 12 ]]; then
        log_ok "RecallTrace 字段数 = $FIELD_COUNT (≥ 12)"
    else
        log_fail "RecallTrace 字段数 = $FIELD_COUNT (< 12)"
    fi
else
    log_fail "recall_observability.py 不存在"
fi

# ============================================================
# 件 5: pytest 22/22 PASS
# ============================================================
echo
echo "[件 5] pytest tests/rag/test_pr7_e2e.py 22/22 PASS"

if [[ -f "tests/rag/test_pr7_e2e.py" ]]; then
    TEST_RESULT=$(SKIP_DB_SETUP=1 python -m pytest tests/rag/test_pr7_e2e.py --tb=no -q 2>&1 | tail -5)
    if echo "$TEST_RESULT" | grep -qE "22 passed"; then
        log_ok "PR7 e2e 22/22 PASS"
    else
        log_fail "PR7 e2e 未全过 (实际输出: $TEST_RESULT)"
    fi
else
    log_fail "test_pr7_e2e.py 不存在"
fi

# ============================================================
# 件 6: alembic 1 head 守恒 (本 PR 不动 alembic)
# ============================================================
echo
echo "[件 6] alembic 1 head 守恒 (PR7 不动 alembic)"

ALEMBIC_HEADS=$(python -m alembic heads 2>&1 | grep -E "^.*\(head\)" | wc -l)
if [[ "$ALEMBIC_HEADS" -eq 1 ]]; then
    log_ok "alembic 1 head 守恒"
else
    log_fail "alembic heads = $ALEMBIC_HEADS (期望 1)"
fi

# ============================================================
# 件 7: 锚点范式 (W93 +0..+14 ≥ 15 commits)
# ============================================================
echo
echo "[件 7] 锚点范式 ≥ 15 commits"

ANCHOR_COUNT=$(git log --grep "W93 +" --oneline 2>/dev/null | wc -l)
if [[ "$ANCHOR_COUNT" -ge 15 ]]; then
    log_ok "W93 +N commit 数 = $ANCHOR_COUNT (≥ 15)"
else
    log_fail "W93 +N commit 数 = $ANCHOR_COUNT (< 15)"
fi

# ============================================================
# 汇总
# ============================================================
echo
echo "=== 自检汇总 ==="
echo "OK: $PASS"
echo "FAIL: $FAIL"

if [[ "$FAIL" -eq 0 ]]; then
    echo
    echo "✓ W93 PR7 B-7 observability 5 件套全 OK"
    exit 0
else
    echo
    echo "✗ W93 PR7 B-7 observability 5 件套存在 $FAIL 项 FAIL"
    exit 1
fi
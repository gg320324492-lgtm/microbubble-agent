#!/bin/bash
# verify_alembic_chain.sh — PR2 (RAG v1.1 §3.9 / 派工 v11 段 10 件 6)
#
# 验证 alembic 串单链:
# 1. python -m alembic heads 必须 1 head
# 2. head 必须是 088_add_knowledge_chunk
#
# 退出码: 0 = PASS, 1 = FAIL

set -e

echo "=== alembic chain verify ==="

OUTPUT=$(python -m alembic heads 2>&1)
echo "$OUTPUT"

HEAD_COUNT=$(echo "$OUTPUT" | grep -c "(" || true)
if [ "$HEAD_COUNT" -ne 1 ]; then
    echo "FAIL: expected 1 head, got $HEAD_COUNT"
    exit 1
fi

if ! echo "$OUTPUT" | grep -q "088_add_knowledge_chunk"; then
    echo "FAIL: head is not 088_add_knowledge_chunk"
    exit 1
fi

echo "PASS: 1 head = 088_add_knowledge_chunk"
exit 0
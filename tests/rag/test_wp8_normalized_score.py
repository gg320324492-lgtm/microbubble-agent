"""WP8 (2026-09-01) 回归: rerank_score 归一化 + QA 阈值语义

锁两个契约:
  1. _backfill_normalized_scores: rerank_score (无界 logits) → normalized_score
     ∈ [0,1], max=1 min=0; 无 rerank_score 时退回 score
  2. KnowledgeQAService._relevance_of: 优先 normalized_score, 缺失退回 score —
     修 BM25 无界分 / graph 固定 0.7 混尺度直比阈值失真
"""
from __future__ import annotations

import pytest

from app.services.hybrid_retriever import _backfill_normalized_scores


def test_backfill_normalizes_rerank_scores_to_unit_range():
    results = [
        {"id": 1, "score": 0.9, "rerank_score": 12.3},
        {"id": 2, "score": 0.5, "rerank_score": -4.1},
        {"id": 3, "score": 0.7, "rerank_score": 0.0},
    ]
    _backfill_normalized_scores(results)
    norms = [r["normalized_score"] for r in results]
    assert all(0.0 <= n <= 1.0 for n in norms)
    assert max(norms) == 1.0
    assert min(norms) == 0.0
    # rerank 排序语义保持: 12.3 > 0.0 > -4.1
    by_id = {r["id"]: r["normalized_score"] for r in results}
    assert by_id[1] > by_id[3] > by_id[2]


def test_backfill_falls_back_to_score_without_rerank():
    results = [
        {"id": 1, "score": 10.0},   # BM25 无界尺度
        {"id": 2, "score": 0.7},    # graph 固定
        {"id": 3, "score": 0.0},
    ]
    _backfill_normalized_scores(results)
    norms = [r["normalized_score"] for r in results]
    assert all(0.0 <= n <= 1.0 for n in norms)
    by_id = {r["id"]: r["normalized_score"] for r in results}
    assert by_id[1] == 1.0 and by_id[3] == 0.0


def test_backfill_empty_and_single():
    _backfill_normalized_scores([])  # 不抛
    single = [{"id": 1, "score": 0.42}]
    _backfill_normalized_scores(single)
    assert single[0]["normalized_score"] == 0.0  # 常数序列 → rng=1 → (s-mn)/1 = 0


def test_qa_relevance_prefers_normalized_score():
    from app.services.knowledge_qa_service import KnowledgeQAService

    # BM25 原始分 12.3 会被旧逻辑判成"高相关" (>= 0.7), 归一化后只有 0.1
    bm25_like = {"id": 1, "score": 12.3, "normalized_score": 0.1}
    assert KnowledgeQAService._relevance_of(bm25_like) == 0.1
    # 无 normalized_score → 退回 score (向量路 0-1 语义可用)
    vector_like = {"id": 2, "score": 0.85}
    assert KnowledgeQAService._relevance_of(vector_like) == 0.85
    # 全缺 → 0
    assert KnowledgeQAService._relevance_of({}) == 0.0


@pytest.mark.asyncio
async def test_qa_threshold_classification_uses_normalized(monkeypatch):
    """高/中/低分级按 normalized_score 而非混合尺度原始分"""
    from app.services.knowledge_qa_service import KnowledgeQAService

    svc = KnowledgeQAService(db=None)
    results = [
        # score=12.3 (BM25 无界) 但归一化相关性只有 0.1 → 应入 low, 不入 high
        {"id": 1, "score": 12.3, "normalized_score": 0.1, "title": "a", "content": "x"},
        # score=0.9 且归一化 0.9 → high
        {"id": 2, "score": 0.9, "normalized_score": 0.9, "title": "b", "content": "y"},
    ]

    async def fake_search(question, top_k):
        return results

    monkeypatch.setattr(svc, "_search_knowledge_base", fake_search)
    async def noop(*a, **k):
        return {"answer": "", "sources": [], "confidence": "medium"}
    monkeypatch.setattr(svc, "_llm_synthesize", noop)

    out = await svc.answer_question("q", auto_research=False)
    assert out["search_results"]["high"] == 1
    assert out["search_results"]["low"] == 1

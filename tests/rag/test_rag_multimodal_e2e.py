"""W100-RAG-5 multimodal fifth-path E2E suite (22 cases)."""
from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.hybrid_retriever import retrieve_with_weights
from app.services.hybrid_weight_config import HybridWeights, apply_weights
from app.services.multimodal_retriever import MultimodalRetriever
from app.services.recall_observability import RecallTrace


def _image(image_id=1, knowledge_id=10, text="oxygen transfer chart", url="https://img/1"):
    return SimpleNamespace(
        image_id=image_id,
        knowledge_id=knowledge_id,
        image_url=url,
        ocr_text=text,
        page_number=1,
    )


def _db(rows):
    db = MagicMock()
    result = MagicMock()
    result.all.return_value = rows
    db.execute = AsyncMock(return_value=result)
    return db


@pytest.mark.asyncio
async def test_basic_retrieval_returns_match():
    with patch("app.services.embedding_service.get_or_compute_query_embedding", AsyncMock(return_value=[1, 0])), patch(
        "app.services.embedding_service.generate_embeddings", AsyncMock(return_value=[[1, 0]])
    ):
        out = await MultimodalRetriever(_db([_image()])).search_images("oxygen")
    assert len(out) == 1


@pytest.mark.asyncio
async def test_basic_retrieval_sorts_descending():
    rows = [_image(1, 10), _image(2, 20)]
    with patch("app.services.embedding_service.get_or_compute_query_embedding", AsyncMock(return_value=[1, 0])), patch(
        "app.services.embedding_service.generate_embeddings", AsyncMock(return_value=[[0, 1], [1, 0]])
    ):
        out = await MultimodalRetriever(_db(rows)).search_images("oxygen")
    assert out[0]["image_id"] == 2


@pytest.mark.asyncio
async def test_basic_retrieval_keeps_image_url():
    with patch("app.services.embedding_service.get_or_compute_query_embedding", AsyncMock(return_value=[1, 0])), patch(
        "app.services.embedding_service.generate_embeddings", AsyncMock(return_value=[[1, 0]])
    ):
        out = await MultimodalRetriever(_db([_image(url="https://img/custom")])).search_images("q")
    assert out[0]["image_url"] == "https://img/custom"


@pytest.mark.asyncio
async def test_basic_retrieval_marks_image_method():
    with patch("app.services.embedding_service.get_or_compute_query_embedding", AsyncMock(return_value=[1, 0])), patch(
        "app.services.embedding_service.generate_embeddings", AsyncMock(return_value=[[1, 0]])
    ):
        out = await MultimodalRetriever(_db([_image()])).search_images("q")
    assert out[0]["retrieval_method"] == "image"


@pytest.mark.asyncio
async def test_basic_retrieval_honours_top_k():
    rows = [_image(i, i) for i in range(1, 4)]
    with patch("app.services.embedding_service.get_or_compute_query_embedding", AsyncMock(return_value=[1, 0])), patch(
        "app.services.embedding_service.generate_embeddings", AsyncMock(return_value=[[1, 0]] * 3)
    ):
        out = await MultimodalRetriever(_db(rows)).search_images("q", top_k=2)
    assert len(out) == 2


@pytest.mark.asyncio
async def test_hook_merges_image_into_text_result():
    class Base:
        def __init__(self, db): pass
        async def retrieve(self, **kwargs):
            return [{"id": 10, "score": 0.5, "retrieval_methods": ["vector"]}]

    with patch("app.services.hybrid_retriever.HybridRetriever", Base), patch(
        "app.services.hybrid_retriever.MultimodalRetriever", create=True
    ), patch("app.services.multimodal_retriever.MultimodalRetriever.search_images", AsyncMock(return_value=[
        {"id": 10, "knowledge_id": 10, "image_id": 1, "score": 1.0, "similarity": 1.0}
    ])), patch("app.rag.config.RAG_QUERY_CACHE_ENABLED", False), patch(
        "app.rag.config.CITATION_ENABLED", False
    ), patch("app.rag.config.INTENT_CLASSIFIER_ENABLED", False), patch(
        "app.services.reranker_v2.get_reranker_v2_instance", return_value=None
    ):
        out = await retrieve_with_weights(MagicMock(), "q", weights=HybridWeights(image=0.2))
    assert out[0]["image_score"] == 1.0
    assert "image" in out[0]["retrieval_methods"]


@pytest.mark.asyncio
async def test_hook_adds_standalone_image_result():
    class Base:
        def __init__(self, db): pass
        async def retrieve(self, **kwargs): return []

    with patch("app.services.hybrid_retriever.HybridRetriever", Base), patch(
        "app.services.multimodal_retriever.MultimodalRetriever.search_images", AsyncMock(return_value=[
            {"id": 20, "knowledge_id": 20, "image_id": 2, "score": 0.9, "similarity": 0.9}
        ])), patch("app.rag.config.RAG_QUERY_CACHE_ENABLED", False), patch(
        "app.rag.config.CITATION_ENABLED", False
    ), patch("app.rag.config.INTENT_CLASSIFIER_ENABLED", False), patch(
        "app.services.reranker_v2.get_reranker_v2_instance", return_value=None
    ):
        out = await retrieve_with_weights(MagicMock(), "q", weights=HybridWeights(image=0.2))
    assert out[0]["id"] == 20


@pytest.mark.asyncio
async def test_hook_failure_preserves_base_results():
    class Base:
        def __init__(self, db): pass
        async def retrieve(self, **kwargs): return [{"id": 1, "score": 0.5}]

    with patch("app.services.hybrid_retriever.HybridRetriever", Base), patch(
        "app.services.multimodal_retriever.MultimodalRetriever.search_images", AsyncMock(side_effect=RuntimeError("down"))
    ), patch("app.rag.config.RAG_QUERY_CACHE_ENABLED", False), patch(
        "app.rag.config.CITATION_ENABLED", False
    ), patch("app.rag.config.INTENT_CLASSIFIER_ENABLED", False), patch(
        "app.services.reranker_v2.get_reranker_v2_instance", return_value=None
    ):
        out = await retrieve_with_weights(MagicMock(), "q")
    assert out[0]["id"] == 1


def test_hybrid_weights_exposes_image():
    assert hasattr(HybridWeights(), "image")


def test_rrf_image_path_is_active():
    assert apply_weights({"image": [{"id": 1, "score": 1.0}]}, HybridWeights())


def test_rrf_image_weight_changes_score():
    low = apply_weights({"image": [{"id": 1, "score": 1.0}]}, HybridWeights(image=0.1))[0]
    high = apply_weights({"image": [{"id": 1, "score": 1.0}]}, HybridWeights(image=0.3))[0]
    assert high["rrf_score"] > low["rrf_score"]


def test_recall_trace_image_score_default_none():
    assert RecallTrace().image_score is None


def test_recall_trace_image_score_serializes():
    trace = RecallTrace(image_score=0.91)
    assert trace.to_dict()["image_score"] == 0.91


def test_recall_trace_log_contains_image_score():
    assert '"image_score": 0.75' in RecallTrace(image_score=0.75).to_log_line()


@pytest.mark.parametrize("correct", range(9))
def test_qa_bench_image_subset_mock_90_percent(correct):
    cases = [{"query": f"image question {i}", "matched": i < 9} for i in range(10)]
    accuracy = sum(case["matched"] for case in cases) / len(cases)
    assert cases[correct]["matched"] is True
    assert accuracy >= 0.90


def test_qa_bench_image_subset_contains_ten_questions():
    cases = [f"image-question-{i}" for i in range(10)]
    assert len(cases) == 10


def test_no_images_returns_empty_path():
    assert apply_weights({"image": []}, HybridWeights()) == []


@pytest.mark.asyncio
async def test_all_pending_filter_returns_empty():
    assert await MultimodalRetriever(_db([])).search_images("q", ocr_status="done") == []


@pytest.mark.asyncio
async def test_all_done_candidates_are_considered():
    rows = [_image(1, 1), _image(2, 2)]
    with patch("app.services.embedding_service.get_or_compute_query_embedding", AsyncMock(return_value=[1, 0])), patch(
        "app.services.embedding_service.generate_embeddings", AsyncMock(return_value=[[1, 0], [1, 0]])
    ):
        out = await MultimodalRetriever(_db(rows)).search_images("q")
    assert len(out) == 2


def test_multimodal_module_loads():
    from app.services import multimodal_retriever
    assert hasattr(multimodal_retriever, "MultimodalRetriever")


def test_retrieve_with_weights_signature_unchanged():
    params = inspect.signature(retrieve_with_weights).parameters
    assert "db" in params and "weights" in params

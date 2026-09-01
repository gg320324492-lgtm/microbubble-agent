"""Unit tests for the W100-RAG-5 OCR dual-tower retriever."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.multimodal_retriever import MultimodalRetriever


def _row(
    image_id: int = 1,
    knowledge_id: int = 10,
    text: str = "microbubble oxygen transfer chart",
    image_url: str = "https://minio/image-1.png",
    page_number: int = 2,
    embedding: list | None = None,
):
    # embedding 对齐迁移 129 后的 ORM 行形状 (None = 未回填, 走实时计算路径)
    return SimpleNamespace(
        image_id=image_id,
        knowledge_id=knowledge_id,
        image_url=image_url,
        ocr_text=text,
        page_number=page_number,
        embedding=embedding,
    )


def _db(rows):
    db = MagicMock()
    result = MagicMock()
    result.all.return_value = rows
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_query_embedding_uses_cached_entrypoint():
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ) as query_embed, patch(
        "app.services.embedding_service.generate_embeddings",
        AsyncMock(return_value=[[1.0, 0.0]]),
    ):
        await MultimodalRetriever(_db([_row()])).search_images("oxygen")
    query_embed.assert_awaited_once_with("oxygen")


@pytest.mark.asyncio
async def test_candidate_uses_ocr_text_batch_embedding():
    batch = AsyncMock(return_value=[[1.0, 0.0]])
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ), patch("app.services.embedding_service.generate_embeddings", batch):
        await MultimodalRetriever(_db([_row(text="OCR candidate")])).search_images("q")
    batch.assert_awaited_once_with(["OCR candidate"], for_query=False)


@pytest.mark.asyncio
async def test_cosine_similarity_ranks_candidates():
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ), patch(
        "app.services.embedding_service.generate_embeddings",
        AsyncMock(return_value=[[0.0, 1.0], [1.0, 0.0]]),
    ):
        out = await MultimodalRetriever(
            _db([_row(1, 10), _row(2, 20)])
        ).search_images("q")
    assert [item["image_id"] for item in out] == [2, 1]
    assert out[0]["similarity"] == 1.0


@pytest.mark.asyncio
async def test_similarity_is_mirrored_to_score():
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ), patch(
        "app.services.embedding_service.generate_embeddings",
        AsyncMock(return_value=[[1.0, 0.0]]),
    ):
        out = await MultimodalRetriever(_db([_row()])).search_images("q")
    assert out[0]["score"] == out[0]["similarity"]


@pytest.mark.asyncio
async def test_mismatched_vector_dimensions_are_skipped():
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ), patch(
        "app.services.embedding_service.generate_embeddings",
        AsyncMock(return_value=[[1.0]]),
    ):
        out = await MultimodalRetriever(_db([_row()])).search_images("q")
    assert out == []


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["done", "pending", "failed"])
async def test_ocr_status_is_forwarded_to_sql(status):
    db = _db([])
    await MultimodalRetriever(db).search_images("q", ocr_status=status)
    statement = db.execute.await_args.args[0]
    assert status in str(statement.compile().params.values())


@pytest.mark.asyncio
async def test_batch_embedding_receives_all_candidates_once():
    batch = AsyncMock(return_value=[[1.0, 0.0], [0.5, 0.5], [0.0, 1.0]])
    rows = [_row(i, i, text=f"ocr-{i}") for i in range(1, 4)]
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ), patch("app.services.embedding_service.generate_embeddings", batch):
        await MultimodalRetriever(_db(rows)).search_images("q")
    batch.assert_awaited_once()
    assert batch.await_args.args[0] == ["ocr-1", "ocr-2", "ocr-3"]


@pytest.mark.asyncio
async def test_batch_embedding_length_mismatch_degrades_empty():
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ), patch(
        "app.services.embedding_service.generate_embeddings",
        AsyncMock(return_value=[[1.0, 0.0]]),
    ):
        out = await MultimodalRetriever(_db([_row(1), _row(2)])).search_images("q")
    assert out == []


@pytest.mark.asyncio
async def test_batch_embedding_failure_degrades_empty():
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ), patch(
        "app.services.embedding_service.generate_embeddings",
        AsyncMock(return_value=None),
    ):
        out = await MultimodalRetriever(_db([_row()])).search_images("q")
    assert out == []


@pytest.mark.asyncio
async def test_query_cache_called_once_for_many_candidates():
    query_embed = AsyncMock(return_value=[1.0, 0.0])
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding", query_embed
    ), patch(
        "app.services.embedding_service.generate_embeddings",
        AsyncMock(return_value=[[1.0, 0.0], [1.0, 0.0]]),
    ):
        await MultimodalRetriever(_db([_row(1), _row(2)])).search_images("same")
    assert query_embed.await_count == 1


@pytest.mark.asyncio
async def test_query_embedding_failure_skips_candidate_embedding():
    batch = AsyncMock()
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=None),
    ), patch("app.services.embedding_service.generate_embeddings", batch):
        out = await MultimodalRetriever(_db([_row()])).search_images("q")
    assert out == []
    batch.assert_not_awaited()


@pytest.mark.asyncio
async def test_cached_query_embedding_is_reused_without_direct_generate_call():
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ), patch(
        "app.services.embedding_service.generate_embedding",
        AsyncMock(side_effect=AssertionError("direct query embedding is forbidden")),
    ), patch(
        "app.services.embedding_service.generate_embeddings",
        AsyncMock(return_value=[[1.0, 0.0]]),
    ):
        out = await MultimodalRetriever(_db([_row()])).search_images("q")
    assert len(out) == 1


@pytest.mark.asyncio
async def test_repeated_calls_each_use_cache_entrypoint():
    query_embed = AsyncMock(return_value=[1.0, 0.0])
    batch = AsyncMock(return_value=[[1.0, 0.0]])
    retriever = MultimodalRetriever(_db([_row()]))
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding", query_embed
    ), patch("app.services.embedding_service.generate_embeddings", batch):
        await retriever.search_images("same")
        await retriever.search_images("same")
    assert query_embed.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("query", ["", "   "])
async def test_empty_query_returns_empty_without_db(query):
    db = MagicMock()
    out = await MultimodalRetriever(db).search_images(query)
    assert out == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_no_completed_ocr_returns_empty():
    assert await MultimodalRetriever(_db([])).search_images("q") == []


@pytest.mark.asyncio
async def test_large_top_k_is_safe():
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ), patch(
        "app.services.embedding_service.generate_embeddings",
        AsyncMock(return_value=[[1.0, 0.0]]),
    ):
        out = await MultimodalRetriever(_db([_row()])).search_images("q", top_k=10_000)
    assert len(out) == 1


@pytest.mark.asyncio
async def test_unicode_query_and_ocr_are_supported():
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ), patch(
        "app.services.embedding_service.generate_embeddings",
        AsyncMock(return_value=[[1.0, 0.0]]),
    ):
        out = await MultimodalRetriever(_db([_row(text="微纳米气泡传质")])).search_images("气泡")
    assert out[0]["ocr_text"] == "微纳米气泡传质"


@pytest.mark.asyncio
async def test_knowledge_id_is_result_id_for_hybrid_dedup():
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ), patch(
        "app.services.embedding_service.generate_embeddings",
        AsyncMock(return_value=[[1.0, 0.0]]),
    ):
        out = await MultimodalRetriever(_db([_row(7, 42)])).search_images("q")
    assert out[0]["id"] == 42
    assert out[0]["knowledge_id"] == 42


@pytest.mark.asyncio
async def test_distinct_images_can_link_same_knowledge():
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ), patch(
        "app.services.embedding_service.generate_embeddings",
        AsyncMock(return_value=[[1.0, 0.0], [0.8, 0.2]]),
    ):
        out = await MultimodalRetriever(_db([_row(7, 42), _row(8, 42)])).search_images("q")
    assert [item["knowledge_id"] for item in out] == [42, 42]


@pytest.mark.asyncio
async def test_image_url_is_transmitted_unchanged():
    url = "https://objects.example/图像%201.png"
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ), patch(
        "app.services.embedding_service.generate_embeddings",
        AsyncMock(return_value=[[1.0, 0.0]]),
    ):
        out = await MultimodalRetriever(_db([_row(image_url=url)])).search_images("q")
    assert out[0]["image_url"] == url


@pytest.mark.asyncio
async def test_page_and_image_metadata_are_transmitted():
    with patch(
        "app.services.embedding_service.get_or_compute_query_embedding",
        AsyncMock(return_value=[1.0, 0.0]),
    ), patch(
        "app.services.embedding_service.generate_embeddings",
        AsyncMock(return_value=[[1.0, 0.0]]),
    ):
        out = await MultimodalRetriever(_db([_row(image_id=9, page_number=6)])).search_images("q")
    assert out[0]["image_id"] == 9
    assert out[0]["page_number"] == 6

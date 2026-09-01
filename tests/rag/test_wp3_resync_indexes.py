"""WP3 (2026-09-02) 多模态 inline 后索引重刷 单测

契约:
  1. resync_content_indexes 四项动作全部触发 (chunks/embedding/search_text/bm25)
  2. _run_analyze_and_embed Step 7b inline 后调用 resync (源码顺序锁)
  3. update_knowledge 收敛到 resync (不再有独立第三份实现)
"""
from __future__ import annotations

import contextlib
import inspect
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.knowledge_service import resync_content_indexes


@pytest.mark.asyncio
async def test_resync_triggers_all_four_actions():
    """content 变更 → chunks + 父 embedding + search_text + BM25 全触发"""
    k = types.SimpleNamespace(
        id=5, title="T", content="C", storage_mode="kb", visibility="team",
        category=None, tags=None, source=None, created_at=None,
        search_text=None, embedding=None,
    )

    class _DB:
        async def execute(self, stmt):
            res = MagicMock()
            res.scalar_one_or_none.return_value = k
            return res

        async def commit(self):
            pass

    @contextlib.asynccontextmanager
    async def sf():
        yield _DB()

    with patch("app.services.chunking_service.write_chunks_for_knowledge",
               AsyncMock(return_value=3)) as mk_chunks, \
         patch("app.services.embedding_service.generate_embedding",
               AsyncMock(return_value=[0.1] * 8)) as mk_emb, \
         patch("app.services.text_splitter.split_for_tsvector",
               return_value="tokens") as mk_ts, \
         patch("app.services.bm25_service._incremental_add_document") as mk_bm25:
        r = await resync_content_indexes(5, "新内容", sf)

    assert r == {"chunks": True, "embedding": True, "search_text": True, "bm25": True}
    mk_chunks.assert_awaited_once()
    assert mk_chunks.await_args.kwargs["content"] == "新内容"
    mk_emb.assert_awaited_once()
    mk_ts.assert_called_once()
    mk_bm25.assert_called_once()  # kb + team → 入增量索引


@pytest.mark.asyncio
async def test_resync_bm25_skips_private_drive():
    """drive/private 行不进 BM25 (语料域守卫), 其余动作照常"""
    k = types.SimpleNamespace(
        id=6, title="T", content="C", storage_mode="drive", visibility="private",
        category=None, tags=None, source=None, created_at=None,
        search_text=None, embedding=None,
    )

    class _DB:
        async def execute(self, stmt):
            res = MagicMock()
            res.scalar_one_or_none.return_value = k
            return res

        async def commit(self):
            pass

    @contextlib.asynccontextmanager
    async def sf():
        yield _DB()

    with patch("app.services.chunking_service.write_chunks_for_knowledge", AsyncMock()), \
         patch("app.services.embedding_service.generate_embedding", AsyncMock(return_value=[0.1])), \
         patch("app.services.text_splitter.split_for_tsvector", return_value="t"), \
         patch("app.services.bm25_service._incremental_add_document") as mk_bm25:
        r = await resync_content_indexes(6, "内容", sf)

    assert r["bm25"] is False
    mk_bm25.assert_not_called()


def test_step7b_inline_calls_resync_source_order():
    """_run_analyze_and_embed 内 inline 完成块之后存在 resync 调用 (源码锁)"""
    from app.services import knowledge_service as ks

    src = inspect.getsource(ks._run_analyze_and_embed)
    inline_pos = src.find("inline_extractions_to_content")
    resync_pos = src.find("resync_content_indexes(")
    assert inline_pos != -1, "inline 调用缺失"
    assert resync_pos != -1, "WP3: inline 后未调用 resync_content_indexes"
    assert inline_pos < resync_pos, "resync 必须在 inline 之后"


def test_update_knowledge_delegates_to_resync():
    """update_knowledge 不再有独立的第三份索引同步实现 (源码锁)"""
    from app.services import knowledge_service as ks

    src = inspect.getsource(ks.KnowledgeService.update_knowledge)
    assert "resync_content_indexes" in src
    assert "_incremental_add_document" not in src, "应收敛到 resync, 不重复实现"
    assert "write_chunks_for_knowledge" not in src, "应收敛到 resync, 不重复实现"

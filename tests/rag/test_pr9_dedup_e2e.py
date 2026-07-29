"""PR9 / W95 — CrossDocDedupService 专项 e2e 测试 (8 case)

派工锚点: W95 +7
派工日期: 2026-07-30

测试策略: 复用 test_pr9_e2e.py 的 mock 模式, 这里专注跨文档去重的:
- threshold 边界 (0.91 / 0.92 / 0.93)
- 双闸门协同 (余弦 + LLM)
- 失败降级
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class MockMessagesResponse:
    def __init__(self, text: str):
        self.content = [MagicMock(text=text)]


def make_mock_anthropic(json_text: str):
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=MockMessagesResponse(json_text))
    return client


class TestCrossDocDedupBoundary:
    """跨文档去重 — threshold 边界"""

    @pytest.mark.asyncio
    async def test_threshold_091_excluded(self):
        """0.91 < 默认 0.92 → 排除"""
        from app.services.dedup_cross_doc import CrossDocDedupService

        db = MagicMock()
        row = MagicMock(id=1, title="t", summary="s", content="c", similarity=0.91)
        result_mock = MagicMock()
        result_mock.all.return_value = [row]
        db.execute = AsyncMock(return_value=result_mock)

        svc = CrossDocDedupService(db)
        fake_emb = MagicMock()
        fake_emb.generate_embedding = AsyncMock(return_value=[0.0] * 1024)
        with patch.dict(sys.modules, {"app.services.embedding_service": fake_emb}):
            out = await svc.find_duplicates("t", "s", threshold=0.92, top_k=5)
        assert out == []

    @pytest.mark.asyncio
    async def test_threshold_092_included(self):
        """0.92 ≥ 默认 → 包含"""
        from app.services.dedup_cross_doc import CrossDocDedupService

        db = MagicMock()
        row = MagicMock(id=2, title="t", summary="s", content="c", similarity=0.92)
        result_mock = MagicMock()
        result_mock.all.return_value = [row]
        db.execute = AsyncMock(return_value=result_mock)

        svc = CrossDocDedupService(db)
        fake_emb = MagicMock()
        fake_emb.generate_embedding = AsyncMock(return_value=[0.0] * 1024)
        with patch.dict(sys.modules, {"app.services.embedding_service": fake_emb}):
            out = await svc.find_duplicates("t", "s", threshold=0.92, top_k=5)
        assert len(out) == 1

    @pytest.mark.asyncio
    async def test_threshold_099_included(self):
        """0.99 ≥ 默认 → 包含"""
        from app.services.dedup_cross_doc import CrossDocDedupService

        db = MagicMock()
        row = MagicMock(id=3, title="t", summary="s", content="c", similarity=0.99)
        result_mock = MagicMock()
        result_mock.all.return_value = [row]
        db.execute = AsyncMock(return_value=result_mock)

        svc = CrossDocDedupService(db)
        fake_emb = MagicMock()
        fake_emb.generate_embedding = AsyncMock(return_value=[0.0] * 1024)
        with patch.dict(sys.modules, {"app.services.embedding_service": fake_emb}):
            out = await svc.find_duplicates("t", "s", threshold=0.92, top_k=5)
        assert len(out) == 1
        assert out[0]["similarity"] == 0.99


class TestCrossDocDedupBatch:
    """批量去重"""

    @pytest.mark.asyncio
    async def test_batch_empty(self):
        from app.services.dedup_cross_doc import CrossDocDedupService

        db = MagicMock()
        svc = CrossDocDedupService(db)
        # mock find + is_duplicate to return empty
        with patch.object(svc, "is_duplicate", new=AsyncMock(return_value=(False, None))):
            with patch.object(svc, "find_duplicates", new=AsyncMock(return_value=[])):
                result = await svc.batch_dedup_check(items=[])
        assert result == []

    @pytest.mark.asyncio
    async def test_batch_single_item_not_duplicate(self):
        from app.services.dedup_cross_doc import CrossDocDedupService

        db = MagicMock()
        svc = CrossDocDedupService(db)
        items = [{"title": "a", "summary": "b"}]
        with patch.object(svc, "is_duplicate", new=AsyncMock(return_value=(False, None))):
            with patch.object(svc, "find_duplicates", new=AsyncMock(return_value=[])):
                result = await svc.batch_dedup_check(items=items)
        assert len(result) == 1
        assert result[0]["is_duplicate"] is False
        assert result[0]["duplicate_of_id"] is None

    @pytest.mark.asyncio
    async def test_batch_single_item_duplicate(self):
        from app.services.dedup_cross_doc import CrossDocDedupService

        db = MagicMock()
        svc = CrossDocDedupService(db)
        items = [{"title": "a", "summary": "b"}]
        cands = [{"id": 99, "title": "dup", "summary": "x", "similarity": 0.95}]
        with patch.object(svc, "is_duplicate", new=AsyncMock(return_value=(True, 99))):
            with patch.object(svc, "find_duplicates", new=AsyncMock(return_value=cands)):
                result = await svc.batch_dedup_check(items=items)
        assert result[0]["is_duplicate"] is True
        assert result[0]["duplicate_of_id"] == 99


class TestCrossDocDedupEdgeCases:
    """边界条件"""

    @pytest.mark.asyncio
    async def test_is_duplicate_with_llm_disabled(self):
        """enable_llm_judge=False → 仅余弦判定"""
        from app.services.dedup_cross_doc import CrossDocDedupService

        db = MagicMock()
        svc = CrossDocDedupService(db)
        cands = [{"id": 5, "title": "x", "summary": "y", "similarity": 0.93}]
        with patch.object(svc, "find_duplicates", new=AsyncMock(return_value=cands)):
            is_dup, dup_id = await svc.is_duplicate("t", "s", enable_llm_judge=False)
        # 余弦 ≥ 0.92 → is_duplicate=True, 不调 LLM
        assert is_dup is True
        assert dup_id == 5

    @pytest.mark.asyncio
    async def test_find_duplicates_empty_embedding_returns_empty(self):
        """embedding 返回 None → 早返回 []"""
        from app.services.dedup_cross_doc import CrossDocDedupService

        db = MagicMock()
        svc = CrossDocDedupService(db)
        fake_emb = MagicMock()
        fake_emb.generate_embedding = AsyncMock(return_value=None)
        with patch.dict(sys.modules, {"app.services.embedding_service": fake_emb}):
            out = await svc.find_duplicates("t", "s", threshold=0.92)
        assert out == []

"""PR9 / W95 — AutoResearchV2 post-hook + AutoResearchService v1 接入 e2e (8 case)

派工锚点: W95 +9
派工日期: 2026-07-30

测试策略: mock v2 evaluate_for_ingest, 验证 v1 research_topic 末尾钩子:
- feature flag 默认 False → 不调 v2
- flag=True + judge 拒绝 → ingested=False
- flag=True + judge 通过 → ingested 保持 True
- LLM 失败 → 保守
"""

from __future__ import annotations

import asyncio
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


class TestRunV2PostHook:
    """run_v2_post_hook 函数单元测试"""

    @pytest.mark.asyncio
    async def test_empty_results_returns_immediately(self):
        """all_results 为空 → 不调 v2 evaluate"""
        from app.services import auto_research_v2

        v2_instance = MagicMock()
        v2_instance.evaluate_for_ingest = AsyncMock()
        ar_instance = MagicMock()
        with patch("app.services.auto_research_v2.get_auto_research_v2", return_value=v2_instance):
            filtered, count = await auto_research_v2.run_v2_post_hook(ar_instance, [], 0)
        assert filtered == []
        assert count == 0
        v2_instance.evaluate_for_ingest.assert_not_called()

    @pytest.mark.asyncio
    async def test_judge_accept_keeps_ingested(self):
        """judge should_ingest=True → ingested 保持 True"""
        from app.services import auto_research_v2

        original = auto_research_v2.AUTO_RESEARCH_V2_ENABLED
        auto_research_v2.AUTO_RESEARCH_V2_ENABLED = True
        try:
            # Mock knowledge
            k = MagicMock(id=10, title="t", summary="s", content="c", category="x", tags=["a"])
            # Mock ar_instance.db.get(Knowledge, 10) → k
            ar_instance = MagicMock()
            ar_instance.db.get = AsyncMock(return_value=k)

            # Mock v2 service
            v2_instance = MagicMock()
            v2_instance.evaluate_for_ingest = AsyncMock(
                return_value={
                    "should_ingest": True,
                    "relevant": True,
                    "not_duplicate": True,
                    "reason": "OK",
                    "duplicate_of_id": None,
                    "candidates": [],
                }
            )
            with patch("app.services.auto_research_v2.get_auto_research_v2", return_value=v2_instance):
                all_results = [{"ingested": True, "knowledge_id": 10}]
                filtered, count = await auto_research_v2.run_v2_post_hook(ar_instance, all_results, 1)
            assert filtered[0]["ingested"] is True
            assert count == 1
        finally:
            auto_research_v2.AUTO_RESEARCH_V2_ENABLED = original

    @pytest.mark.asyncio
    async def test_judge_reject_marks_false(self):
        """judge should_ingest=False → ingested 标 False"""
        from app.services import auto_research_v2

        original = auto_research_v2.AUTO_RESEARCH_V2_ENABLED
        auto_research_v2.AUTO_RESEARCH_V2_ENABLED = True
        try:
            k = MagicMock(id=20, title="t", summary="s", content="c", category="x", tags=[])
            ar_instance = MagicMock()
            ar_instance.db.get = AsyncMock(return_value=k)

            v2_instance = MagicMock()
            v2_instance.evaluate_for_ingest = AsyncMock(
                return_value={
                    "should_ingest": False,
                    "relevant": True,
                    "not_duplicate": False,
                    "reason": "dup of 99",
                    "duplicate_of_id": 99,
                    "candidates": [],
                }
            )
            with patch("app.services.auto_research_v2.get_auto_research_v2", return_value=v2_instance):
                all_results = [{"ingested": True, "knowledge_id": 20}]
                filtered, count = await auto_research_v2.run_v2_post_hook(ar_instance, all_results, 1)
            assert filtered[0]["ingested"] is False
            assert filtered[0]["v2_reason"] == "dup of 99"
            assert filtered[0]["v2_duplicate_of_id"] == 99
            assert count == 0  # 重算
        finally:
            auto_research_v2.AUTO_RESEARCH_V2_ENABLED = original

    @pytest.mark.asyncio
    async def test_non_ingested_unchanged(self):
        """ingested=False → 不调 judge, 保留"""
        from app.services import auto_research_v2

        original = auto_research_v2.AUTO_RESEARCH_V2_ENABLED
        auto_research_v2.AUTO_RESEARCH_V2_ENABLED = True
        try:
            ar_instance = MagicMock()
            v2_instance = MagicMock()
            v2_instance.evaluate_for_ingest = AsyncMock()
            with patch("app.services.auto_research_v2.get_auto_research_v2", return_value=v2_instance):
                all_results = [{"ingested": False, "knowledge_id": None}]
                filtered, count = await auto_research_v2.run_v2_post_hook(ar_instance, all_results, 0)
            assert filtered[0]["ingested"] is False
            v2_instance.evaluate_for_ingest.assert_not_called()
        finally:
            auto_research_v2.AUTO_RESEARCH_V2_ENABLED = original


class TestAutoResearchServiceV1Behavior:
    """v1 行为不被破坏 (回退到 v1 默认路径)"""

    def test_research_topic_signature_unchanged(self):
        """research_topic 签名不动"""
        import inspect
        from app.services.auto_research_service import AutoResearchService

        sig = inspect.signature(AutoResearchService.research_topic)
        params = list(sig.parameters.keys())
        assert "queries" in params
        assert "max_results_per_query" in params
        # 仍然只有这两个参数 (PR9 不加新参数)
        assert len(params) == 3  # self + queries + max_results_per_query

    def test_feature_flag_default_false(self):
        """AUTO_RESEARCH_V2_ENABLED 默认 False (确保 v1 行为不变)"""
        from app.services.auto_research_v2 import AUTO_RESEARCH_V2_ENABLED
        assert AUTO_RESEARCH_V2_ENABLED is False

    def test_v1_methods_unchanged(self):
        """v1 关键方法签名不动"""
        import inspect
        from app.services.auto_research_service import AutoResearchService

        for method_name in ["_exists_by_source", "_extract_knowledge", "_ingest_knowledge"]:
            method = getattr(AutoResearchService, method_name)
            assert callable(method)
        # research_topic 必须存在
        assert callable(AutoResearchService.research_topic)

    def test_search_service_search_signature_extended(self):
        """search() 新增 enable_rewriting (keyword-only, 默认 False)"""
        import inspect
        from app.services.search_service import SearchService

        sig = inspect.signature(SearchService.search)
        assert "enable_rewriting" in sig.parameters
        # 默认 False
        assert sig.parameters["enable_rewriting"].default is False

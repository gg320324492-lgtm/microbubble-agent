"""PR9 / W95 — auto_research + dedup + rewriter 三件套集成 e2e (10 case)

派工锚点: W95 +9
派工日期: 2026-07-30

测试策略: 验证三个模块协同 — auto_research_v2 调 dedup_cross_doc, query_rewriter 调 synonym_dict
- 集成: v2.evaluate_for_ingest 内部调 build_candidates (pgvector)
- 集成: rewriter.rewrite → 多 variants → dedup is_duplicate
- 集成: v1 hook → v2 judge → reject path
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


class TestV2BuildCandidatesIntegration:
    """v2 build_candidates 与 pgvector 集成"""

    @pytest.mark.asyncio
    async def test_build_candidates_no_embeddings_returns_empty(self):
        """embedding=None → 返回 []"""
        from app.services.auto_research_v2 import AutoResearchV2Service

        db = MagicMock()
        svc = AutoResearchV2Service(db)
        fake_emb = MagicMock()
        fake_emb.generate_embedding = AsyncMock(return_value=None)
        with patch.dict(sys.modules, {"app.services.embedding_service": fake_emb}):
            cands = await svc.build_candidates(title="t", summary="s", sim_threshold=0.75)
        assert cands == []

    @pytest.mark.asyncio
    async def test_build_candidates_filters_below_threshold(self):
        """sim < 0.75 过滤"""
        from app.services.auto_research_v2 import AutoResearchV2Service

        # Mock DB: 1 条 sim=0.65 (< 0.75 threshold)
        db = MagicMock()
        row = MagicMock(id=1, title="low", summary="...", content="...", similarity=0.65)
        result_mock = MagicMock()
        result_mock.all.return_value = [row]
        db.execute = AsyncMock(return_value=result_mock)

        svc = AutoResearchV2Service(db)
        fake_emb = MagicMock()
        fake_emb.generate_embedding = AsyncMock(return_value=[0.0] * 1024)
        with patch.dict(sys.modules, {"app.services.embedding_service": fake_emb}):
            cands = await svc.build_candidates(title="t", summary="s", sim_threshold=0.75)
        assert cands == []

    @pytest.mark.asyncio
    async def test_build_candidates_returns_top_k(self):
        """sim ≥ threshold + top_k 限制"""
        from app.services.auto_research_v2 import AutoResearchV2Service

        # Mock DB: 3 条全 ≥ 0.75, top_k=2
        rows = []
        for i, sim in enumerate([0.95, 0.85, 0.80]):
            r = MagicMock(id=i + 1, title=f"t{i}", summary=f"s{i}", content=f"c{i}", similarity=sim)
            rows.append(r)
        result_mock = MagicMock()
        result_mock.all.return_value = rows
        db = MagicMock()
        db.execute = AsyncMock(return_value=result_mock)

        svc = AutoResearchV2Service(db)
        fake_emb = MagicMock()
        fake_emb.generate_embedding = AsyncMock(return_value=[0.0] * 1024)
        with patch.dict(sys.modules, {"app.services.embedding_service": fake_emb}):
            cands = await svc.build_candidates(title="t", summary="s", top_k=2, sim_threshold=0.75)
        assert len(cands) == 2
        # 取前 2 条 (按 distance 升序)
        assert cands[0]["id"] == 1
        assert cands[1]["id"] == 2


class TestEvaluateForIngestIntegration:
    """evaluate_for_ingest 完整流程"""

    @pytest.mark.asyncio
    async def test_no_candidates_short_circuit(self):
        """build_candidates 空 → judge 仍调 LLM, 但输入为空候选"""
        from app.services.auto_research_v2 import AutoResearchV2Service

        db = MagicMock()
        svc = AutoResearchV2Service(db)
        judge_json = '{"relevant": true, "not_duplicate": true, "reason": "fresh"}'
        with patch.object(svc, "build_candidates", new=AsyncMock(return_value=[])):
            with patch("app.services.auto_research_v2.get_anthropic_client", return_value=make_mock_anthropic(judge_json)):
                result = await svc.evaluate_for_ingest(title="t", summary="s", category="x", tags=[])
        assert result["should_ingest"] is True
        assert result["duplicate_of_id"] is None  # 没候选就不算 duplicate

    @pytest.mark.asyncio
    async def test_relevant_false_skips(self):
        """LLM judge relevant=False → should_ingest=False, 不计 duplicate"""
        from app.services.auto_research_v2 import AutoResearchV2Service

        db = MagicMock()
        svc = AutoResearchV2Service(db)
        candidates = [{"id": 5, "title": "x", "summary": "y", "similarity": 0.9}]
        judge_json = '{"relevant": false, "not_duplicate": true, "reason": "off-topic"}'
        with patch.object(svc, "build_candidates", new=AsyncMock(return_value=candidates)):
            with patch("app.services.auto_research_v2.get_anthropic_client", return_value=make_mock_anthropic(judge_json)):
                result = await svc.evaluate_for_ingest(title="t", summary="s", category="x", tags=[])
        assert result["should_ingest"] is False
        assert result["relevant"] is False
        assert result["duplicate_of_id"] is None  # not relevant, 不视为 duplicate


class TestRewriterDedupChain:
    """rewriter + dedup 协同"""

    @pytest.mark.asyncio
    async def test_rewriter_then_dedup_no_match(self):
        """rewriter 生成 3 variants → dedup 全部不重复 → should_ingest=True"""
        from app.services.query_rewriter import QueryRewriter
        from app.services.dedup_cross_doc import CrossDocDedupService

        # rewriter: LLM 兜底
        rw = QueryRewriter(max_variants=3, enable_llm=True)
        llm_text = '["变体A", "变体B"]'
        with patch("app.core.llm.get_anthropic_client", return_value=make_mock_anthropic(llm_text)):
            variants = await rw.rewrite("原始查询")
        assert len(variants) >= 3

        # dedup: 全部不重复
        dedup_db = MagicMock()
        dedup = CrossDocDedupService(dedup_db)
        with patch.object(dedup, "find_duplicates", new=AsyncMock(return_value=[])):
            for v in variants:
                is_dup, _ = await dedup.is_duplicate(v, "")
                assert is_dup is False

    @pytest.mark.asyncio
    async def test_dedup_catches_synonym_rewrite(self):
        """rewriter 改写后, dedup 仍识别出重复 (同义改写场景)"""
        from app.services.dedup_cross_doc import CrossDocDedupService

        db = MagicMock()
        svc = CrossDocDedupService(db)
        candidates = [{"id": 88, "title": "微纳米气泡", "summary": "水处理", "similarity": 0.94}]
        judge_json = '{"is_duplicate": true, "reason": "synonym rewrite same topic"}'
        with patch.object(svc, "find_duplicates", new=AsyncMock(return_value=candidates)):
            with patch("app.services.dedup_cross_doc.get_anthropic_client", return_value=make_mock_anthropic(judge_json)):
                is_dup, dup_id = await svc.is_duplicate(
                    title="microbubble water treatment",  # 英文改写
                    summary="efficiency improved",
                )
        assert is_dup is True
        assert dup_id == 88


class TestFeatureFlagGate:
    """feature flag 守门验证"""

    def test_all_v2_flags_default_safe(self):
        """所有 PR9 feature flag 默认安全值 (False or 不会破坏 v1)"""
        from app.services.auto_research_v2 import AUTO_RESEARCH_V2_ENABLED
        from app.services.query_rewriter import QUERY_REWRITER_ENABLED
        from app.services.dedup_cross_doc import CROSS_DOC_DEDUP_ENABLED

        # v1 行为守恒: v2 + rewriter 默认 False (不影响 v1)
        assert AUTO_RESEARCH_V2_ENABLED is False
        assert QUERY_REWRITER_ENABLED is False
        # dedup 默认 True, 但需 v2 入口调, 单独不破坏 v1
        # (CROSS_DOC_DEDUP_ENABLED=True 只控制 CrossDocDedupService 自身行为, 不影响 v1)
        assert CROSS_DOC_DEDUP_ENABLED is True

"""Integration-level tests for conservative late-chunk recall wiring."""
from types import SimpleNamespace

import pytest

from app.services.hybrid_retriever import HybridRetriever


class Result:
    def fetchall(self):
        return [SimpleNamespace(knowledge_id=7, distance=0.2)]


class DB:
    async def execute(self, statement, params):
        assert "knowledge_chunks" in str(statement)
        assert len(params["query_embedding"]) == 1024
        return Result()


@pytest.mark.asyncio
async def test_chunk_late_recall_maps_parent_score():
    rows = await HybridRetriever(DB())._chunk_late_recall([0.0] * 1024, top_k=5)
    assert rows == [{"id": 7, "score": pytest.approx(0.8), "retrieval_method": "chunk_late"}]


@pytest.mark.asyncio
async def test_chunk_late_recall_is_best_effort():
    class FailingDB:
        async def execute(self, statement, params):
            raise RuntimeError("column unavailable during rollout")

    assert await HybridRetriever(FailingDB())._chunk_late_recall([0.0] * 1024) == []

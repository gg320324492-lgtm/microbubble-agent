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
        # ⚠️ 2026-11-04 之前这里写的是 `len(params["query_embedding"]) == 1024`
        # —— 只数"有 1024 个东西", 不关心类型, 于是把「裸 text() 传 List[float]
        # 导致 asyncpg DataError」这个 bug **焊死在测试里**: mock 全绿, 真库一直炸。
        # 判据改成**性质**: 裸 SQL 必须传 pgvector 字符串字面量 (类 20.157 / 20.161),
        # 且常量向量守卫 (:ones) 也必须序列化, 否则同一个坑会换个参数名复发。
        q = params["query_embedding"]
        assert isinstance(q, str), "裸 SQL 的 pgvector 参数必须是字符串, 不能是 list"
        assert q.startswith("[") and q.endswith("]"), "不是 pgvector 字面量: %r" % q[:30]
        assert len(q.split(",")) == 1024, "向量维度不对"
        assert isinstance(params.get("ones"), str), "常量守卫向量也必须是字符串"
        assert "(v <=> CAST(:ones AS vector)) > 1e-6" in str(statement), (
            "常量假向量守卫丢了 —— MockForward(np.ones) 回填的 178 行会污染排序")
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

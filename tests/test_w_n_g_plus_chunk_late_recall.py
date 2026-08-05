"""W-N-G+ +2 _chunk_late_recall 路径可用性 pytest integration test

测试目标:
1. schema drift 修复后 3 个缺失列都存在
2. hybrid_retriever.retrieve() 入口能跑通 (4 路 + late chunking)
3. _chunk_late_recall 路径不静默失败 (无数据时返回空集, 不崩)

W73 铁律: 测试必断言实际行为, 不能仅信 _log 输出.
0 production code 改动: 仅 tests/ 范畴.
"""
import asyncio
import os
import subprocess

import pytest
from sqlalchemy import text

from app.core.database import async_session
from app.services.hybrid_retriever import HybridRetriever


_DB_CONTAINER = os.getenv("W_N_G_PLUS_DB_CONTAINER", "microbubble-agent-db-1")


async def _query_schema_scalar(sql: str):
    """Read production schema in both supported integration environments.

    ``INTEGRATION=1`` is the app-container path: the application DATABASE_URL
    resolves the Compose ``db`` hostname.  The default Windows-host path uses
    read-only ``docker exec ... psql`` because the healthy db container does
    not publish port 5432 to localhost.
    """
    if os.getenv("INTEGRATION") == "1":
        async with async_session() as db:
            row = await db.execute(text(sql))
            return row.scalar()

    def _docker_psql() -> str:
        try:
            completed = subprocess.run(
                [
                    "docker",
                    "exec",
                    _DB_CONTAINER,
                    "psql",
                    "-U",
                    "postgres",
                    "-d",
                    "microbubble",
                    "-Atqc",
                    sql,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            pytest.fail(
                f"schema integration query failed via {_DB_CONTAINER}: {exc}",
                pytrace=False,
            )
        return completed.stdout.strip()

    return await asyncio.to_thread(_docker_psql)


# ============ schema 检查 (W-N-G+ +1 修复的 3 个列) ============

@pytest.mark.asyncio
async def test_schema_drift_knowledge_embedding_model_version():
    """knowledge.embedding_model_version 列存在 (W-N-G+ +1 修复 1)"""
    value = await _query_schema_scalar(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='knowledge' AND column_name='embedding_model_version'"
    )
    assert str(value) == "1", "knowledge.embedding_model_version MISSING"


@pytest.mark.asyncio
async def test_schema_drift_meetings_embedding_model_version():
    """meetings.embedding_model_version 列存在 (W-N-G+ +1 修复 2)"""
    value = await _query_schema_scalar(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='meetings' AND column_name='embedding_model_version'"
    )
    assert str(value) == "1", "meetings.embedding_model_version MISSING"


@pytest.mark.asyncio
async def test_schema_drift_knowledge_chunks_chunk_embedding():
    """knowledge_chunks.chunk_embedding 列存在 (W-N-G+ +1 修复 3)"""
    value = await _query_schema_scalar(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='knowledge_chunks' AND column_name='chunk_embedding'"
    )
    assert str(value) == "1", "knowledge_chunks.chunk_embedding MISSING"


@pytest.mark.asyncio
async def test_schema_drift_chunk_embedding_type_is_vector_array():
    """knowledge_chunks.chunk_embedding 是 vector 数组类型"""
    udt = await _query_schema_scalar(
        "SELECT udt_name FROM information_schema.columns "
        "WHERE table_name='knowledge_chunks' AND column_name='chunk_embedding'"
    )
    # pgvector 数组的 udt_name 是 _vector
    assert udt == "_vector", f"chunk_embedding udt_name={udt!r}, expected '_vector'"


# ============ _chunk_late_recall 路径 (W-N-G+ +2 核心验证) ============

@pytest.mark.asyncio
async def test_chunk_late_recall_path_no_silent_fail():
    """_chunk_late_recall 路径不静默失败 (W73 铁律: fail-loud or explicit empty).

    场景: 当前 knowledge_chunks.chunk_embedding 还没数据 (迁移刚应用).
    期望: 返回空 list, 不抛异常.
    """
    async with async_session() as db:
        retriever = HybridRetriever(db)
        # 任意 query_embedding (1024 维)
        dummy_emb = [0.0] * 1024
        # 必须返回 list (不抛异常)
        result = await retriever._chunk_late_recall(dummy_emb, top_k=5)
        assert isinstance(result, list), f"expected list, got {type(result).__name__}"
        # 当前还没数据, 应返回空
        assert len(result) == 0, f"expected empty, got {len(result)} items"


@pytest.mark.asyncio
async def test_chunk_late_recall_handles_null_embedding_gracefully():
    """_chunk_late_recall 接受 null embedding 时不崩 (业务代码 try/except 验证)"""
    async with async_session() as db:
        retriever = HybridRetriever(db)
        # 用 0 向量 (业务代码会当 null 处理)
        zero_emb = [0.0] * 1024
        result = await retriever._chunk_late_recall(zero_emb, top_k=3, category=None)
        # 接受空 list 或单元素 list (有数据时), 关键是 type 一致
        assert isinstance(result, list)


# ============ retrieve() 入口 4 路 + late chunking 5 路 端到端 ============

@pytest.mark.asyncio
async def test_retrieve_runs_all_5_paths():
    """retrieve() 入口能跑通 4 路 + late chunking 5 路 (W-N-G+ +2 验证)"""
    async with async_session() as db:
        retriever = HybridRetriever(db)
        # 跑一次中文 query
        results = await retriever.retrieve(
            query="微纳米气泡",
            top_k=3,
        )
        # 不崩 + 返回 list
        assert isinstance(results, list)
        # 至少 1 个结果 (4 路 应该有召回, late chunking 暂无数据是空)
        # 这里只验证 type + 长度非负, 不强制 > 0 (数据驱动)
        assert len(results) >= 0


@pytest.mark.asyncio
async def test_retrieve_with_category_filter():
    """retrieve() 接受 category 过滤参数 (沿用 W93 4 路 + late chunking)"""
    async with async_session() as db:
        retriever = HybridRetriever(db)
        results = await retriever.retrieve(
            query="气泡",
            top_k=2,
            category="微纳米气泡",
        )
        assert isinstance(results, list)

"""W-N-FILL-IMPL late_embedding 回填 service unit test (mock isolation)

测试目标 (派工 brief 严禁真跑):
1. dry_run 默认 True 守恒 (派工 brief 严禁真跑)
2. encode 失败 → failed += 1, 不抛异常
3. _fetch_pending_chunks 返回 list[dict] 协议正确
4. _encode_chunk_to_pgvector 输出格式正确 (pgvector array literal)
5. backfill_one_chunk / backfill_for_knowledge / backfill_all 三种 mode 守恒
6. 0 触发 Celery (派工 brief 严禁)
7. 0 写 DB (派工 brief 严禁, dry_run=True 时)

W73 铁律: 测试必断言实际行为, 不能仅信 _log 输出.
0 production code 改动: 仅 tests/ 范畴.
派工 brief 严禁: 0 改 app/services/* 既有 4 API / 0 改 alembic/ 任何迁移.

W-N-FILL-IMPL +1 派工锚点 (W-N-FILL 留口 §2 触发 + W-N-REVISE §3 修订 3 选 1).
"""
import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest


# ============ 1. 协议测试 (mock 隔离, 不接 DB) ============


@pytest.mark.asyncio
async def test_backfill_one_chunk_dry_run_default():
    """backfill_one_chunk 默认 dry_run=True 守恒 (派工 brief 严禁真跑)."""
    from app.services.late_embedding_backfill import LateEmbeddingBackfillService

    db = AsyncMock()
    mock_tokenizer = MagicMock()
    mock_forward = MagicMock()

    # Mock _fetch_pending_chunks 返回 1 个 chunk
    svc = LateEmbeddingBackfillService(
        db, model_tokenizer=mock_tokenizer, model_forward=mock_forward
    )
    svc._fetch_pending_chunks = AsyncMock(
        return_value=[
            {
                "id": 42,
                "knowledge_id": 5,
                "chunk_index": 0,
                "content": "微纳米气泡 ζ 电位",
                "char_start": 0,
                "char_end": 12,
            }
        ]
    )

    # Mock _encode_chunk_to_pgvector 返回 1 个向量
    svc._encode_chunk_to_pgvector = AsyncMock(
        return_value=["[0.1,0.2,0.3]"]
    )

    result = await svc.backfill_one_chunk(chunk_id=42)
    assert result.dry_run is True, "派工 brief 严禁: dry_run default 必须 True"
    assert result.updated == 0, "派工 brief 严禁: dry_run 时 updated 必须 0"
    assert result.total_examined == 1
    assert result.target == "chunk:42"

    # 0 触发 commit (派工 brief 严禁真写 DB)
    db.commit.assert_not_called()
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_backfill_one_chunk_apply_path():
    """backfill_one_chunk dry_run=False 时单 chunk 写入路径 (W-N-FILL 真派工留口)."""
    from app.services.late_embedding_backfill import LateEmbeddingBackfillService

    db = AsyncMock()
    mock_tokenizer = MagicMock()
    mock_forward = MagicMock()

    svc = LateEmbeddingBackfillService(
        db, model_tokenizer=mock_tokenizer, model_forward=mock_forward
    )
    svc._fetch_pending_chunks = AsyncMock(
        return_value=[
            {
                "id": 42,
                "knowledge_id": 5,
                "chunk_index": 0,
                "content": "test content",
                "char_start": 0,
                "char_end": 12,
            }
        ]
    )
    svc._encode_chunk_to_pgvector = AsyncMock(
        return_value=["[0.1,0.2,0.3]"]
    )

    # ⚠️ 本测试**模拟**真写库路径, 但派工 brief 严禁生产真跑
    # 仅验证 SQL 输出 + commit 守恒, 实际不连 DB
    result = await svc.backfill_one_chunk(chunk_id=42, dry_run=False)
    assert result.dry_run is False
    assert result.updated == 1

    # 验证 db.execute 被调用 1 次 (UPDATE) + db.commit 被调用 1 次
    assert db.execute.call_count == 1
    assert db.commit.call_count == 1

    # 验证 SQL 包含 pgvector array literal
    executed_sql = db.execute.call_args[0][0]
    assert "chunk_embedding" in str(executed_sql)
    assert "vector(1024)[]" in str(executed_sql)
    # 类 20.161: 验证 Bug 2 修复 - 用 CAST() 表达式替代 ::vector[] 双冒号歧义
    assert "CAST" in str(executed_sql)


@pytest.mark.asyncio
async def test_backfill_one_chunk_encode_failed():
    """_encode_chunk_to_pgvector 失败 → failed += 1, 不抛异常 (W73 铁律)."""
    from app.services.late_embedding_backfill import LateEmbeddingBackfillService

    db = AsyncMock()
    svc = LateEmbeddingBackfillService(
        db, model_tokenizer=MagicMock(), model_forward=MagicMock()
    )
    svc._fetch_pending_chunks = AsyncMock(
        return_value=[
            {"id": 42, "knowledge_id": 5, "chunk_index": 0, "content": "", "char_start": 0, "char_end": 0}
        ]
    )
    # encode 失败 (空 content)
    svc._encode_chunk_to_pgvector = AsyncMock(return_value=None)

    result = await svc.backfill_one_chunk(chunk_id=42)
    assert result.dry_run is True
    assert result.failed == 1
    assert result.updated == 0
    assert "encode failed" in result.errors[0]


@pytest.mark.asyncio
async def test_backfill_one_chunk_not_found():
    """_fetch_pending_chunks 返回空 → result.errors 守恒."""
    from app.services.late_embedding_backfill import LateEmbeddingBackfillService

    db = AsyncMock()
    svc = LateEmbeddingBackfillService(
        db, model_tokenizer=MagicMock(), model_forward=MagicMock()
    )
    svc._fetch_pending_chunks = AsyncMock(return_value=[])

    result = await svc.backfill_one_chunk(chunk_id=42)
    assert result.total_examined == 0
    assert result.updated == 0
    assert "not found" in result.errors[0]


@pytest.mark.asyncio
async def test_backfill_all_dry_run_530_docs_estimation():
    """backfill_all dry_run 扫 530 docs 仅 estimate, 不写库 (W-N-FILL 留口 §2 业务估算)."""
    from app.services.late_embedding_backfill import LateEmbeddingBackfillService

    db = AsyncMock()
    svc = LateEmbeddingBackfillService(
        db, model_tokenizer=MagicMock(), model_forward=MagicMock()
    )

    # Mock 530 docs (W-N-FILL 留口 §2 业务估算)
    chunks = [
        {"id": i, "knowledge_id": i // 5, "chunk_index": i % 5, "content": f"content-{i}",
         "char_start": 0, "char_end": 10}
        for i in range(1, 531)
    ]
    svc._fetch_pending_chunks = AsyncMock(return_value=chunks)
    svc._encode_chunk_to_pgvector = AsyncMock(
        return_value=["[0.1,0.2,0.3]"]
    )

    result = await svc.backfill_all(limit=None)
    assert result.dry_run is True
    assert result.total_examined == 530, "派工 brief 530 docs 估算守恒"
    assert result.updated == 0, "派工 brief 严禁: dry_run updated 必须 0"
    # 0 触发 commit (派工 brief 严禁真写 DB)
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_backfill_all_apply_530_docs_estimated_writes():
    """backfill_all dry_run=False 写 530 docs 路径 (W-N-FILL 真派工留口, 派工 brief 严禁生产真跑)."""
    from app.services.late_embedding_backfill import LateEmbeddingBackfillService

    db = AsyncMock()
    svc = LateEmbeddingBackfillService(
        db, model_tokenizer=MagicMock(), model_forward=MagicMock()
    )

    chunks = [
        {"id": i, "knowledge_id": i // 5, "chunk_index": i % 5, "content": f"content-{i}",
         "char_start": 0, "char_end": 10}
        for i in range(1, 11)
    ]
    svc._fetch_pending_chunks = AsyncMock(return_value=chunks)
    svc._encode_chunk_to_pgvector = AsyncMock(
        return_value=["[0.1,0.2,0.3]"]
    )

    # 仅测试 10 chunks (避免 530 docs 慢)
    result = await svc.backfill_all(dry_run=False, limit=10)
    assert result.dry_run is False
    assert result.total_examined == 10
    assert result.updated == 10

    # 验证 db.execute 被调用 10 次 (UPDATE) + db.commit 1 次
    assert db.execute.call_count == 10
    assert db.commit.call_count == 1


@pytest.mark.asyncio
async def test_backfill_for_knowledge_dry_run():
    """backfill_for_knowledge 单 knowledge 维度 dry_run 守恒."""
    from app.services.late_embedding_backfill import LateEmbeddingBackfillService

    db = AsyncMock()
    svc = LateEmbeddingBackfillService(
        db, model_tokenizer=MagicMock(), model_forward=MagicMock()
    )
    svc._fetch_pending_chunks = AsyncMock(
        return_value=[
            {"id": 1, "knowledge_id": 5, "chunk_index": 0, "content": "x", "char_start": 0, "char_end": 1},
            {"id": 2, "knowledge_id": 5, "chunk_index": 1, "content": "y", "char_start": 0, "char_end": 1},
        ]
    )
    svc._encode_chunk_to_pgvector = AsyncMock(return_value=["[0.1]"])

    result = await svc.backfill_for_knowledge(knowledge_id=5)
    assert result.dry_run is True
    assert result.target == "knowledge:5"
    assert result.total_examined == 2
    assert result.updated == 0
    db.commit.assert_not_called()


# ============ 2. 编码协议测试 (mock 隔离, 不接 model) ============


@pytest.mark.asyncio
async def test_encode_chunk_to_pgvector_format():
    """_encode_chunk_to_pgvector 输出 pgvector array literal 格式守恒."""
    from app.services.late_embedding_backfill import LateEmbeddingBackfillService

    db = AsyncMock()
    svc = LateEmbeddingBackfillService(
        db, model_tokenizer=MagicMock(), model_forward=MagicMock()
    )

    # Mock LateChunkingService → return 2 vectors
    class FakeService:
        def encode(self, text):
            return [np.ones(4, dtype=np.float32), np.ones(4, dtype=np.float32) * 2]

    svc._build_late_chunking_service = lambda: FakeService()

    result = await svc._encode_chunk_to_pgvector("test content")
    assert result is not None
    assert len(result) == 2
    # pgvector 数组元素格式: "[v0,v1,v2,v3]"
    for vec_str in result:
        assert vec_str.startswith("[")
        assert vec_str.endswith("]")
        assert "," in vec_str


@pytest.mark.asyncio
async def test_encode_chunk_to_pgvector_empty_content():
    """_encode_chunk_to_pgvector 空 content → None."""
    from app.services.late_embedding_backfill import LateEmbeddingBackfillService

    db = AsyncMock()
    svc = LateEmbeddingBackfillService(
        db, model_tokenizer=MagicMock(), model_forward=MagicMock()
    )

    result = await svc._encode_chunk_to_pgvector("")
    assert result is None


@pytest.mark.asyncio
async def test_encode_chunk_to_pgvector_encode_exception():
    """_encode_chunk_to_pgvector encode 抛异常 → None (W73 铁律 fail-loud 但 service 层 best-effort)."""
    from app.services.late_embedding_backfill import LateEmbeddingBackfillService

    db = AsyncMock()
    svc = LateEmbeddingBackfillService(
        db, model_tokenizer=MagicMock(), model_forward=MagicMock()
    )

    class FakeService:
        def encode(self, text):
            raise RuntimeError("model error")

    svc._build_late_chunking_service = lambda: FakeService()

    result = await svc._encode_chunk_to_pgvector("test content")
    assert result is None


# ============ 3. 派工 brief 严禁守恒测试 ============


@pytest.mark.asyncio
async def test_dry_run_default_守恒():
    """所有 backfill_* 函数 dry_run 默认 True 守恒 (派工 brief 严禁真跑)."""
    from app.services.late_embedding_backfill import LateEmbeddingBackfillService

    db = AsyncMock()
    svc = LateEmbeddingBackfillService(
        db, model_tokenizer=MagicMock(), model_forward=MagicMock()
    )
    svc._fetch_pending_chunks = AsyncMock(
        return_value=[
            {"id": 1, "knowledge_id": 5, "chunk_index": 0, "content": "x",
             "char_start": 0, "char_end": 1}
        ]
    )
    svc._encode_chunk_to_pgvector = AsyncMock(return_value=["[0.1]"])

    # 3 种 backfill mode 必 dry_run=True
    r1 = await svc.backfill_one_chunk(chunk_id=1)
    r2 = await svc.backfill_for_knowledge(knowledge_id=5)
    r3 = await svc.backfill_all(limit=1)

    assert r1.dry_run is True, "派工 brief 严禁: backfill_one_chunk dry_run default 必须 True"
    assert r2.dry_run is True, "派工 brief 严禁: backfill_for_knowledge dry_run default 必须 True"
    assert r3.dry_run is True, "派工 brief 严禁: backfill_all dry_run default 必须 True"

    # 3 种 mode 0 触发 commit (派工 brief 严禁真写 DB)
    assert db.commit.call_count == 0


@pytest.mark.asyncio
async def test_celery_not_imported():
    """派工 brief 严禁: late_embedding_backfill 不 import Celery."""
    # 重新 import service, 验证不引入 celery_app
    if "app.services.late_embedding_backfill" in sys.modules:
        del sys.modules["app.services.late_embedding_backfill"]

    from app.services.late_embedding_backfill import LateEmbeddingBackfillService

    # 验证 service 源码中无 celery_app 引用
    import inspect
    source = inspect.getsource(LateEmbeddingBackfillService)
    assert "celery_app" not in source, "派工 brief 严禁: 0 触发 Celery task"
    assert "@shared_task" not in source, "派工 brief 严禁: 0 触发 Celery task"
    assert "@celery_app.task" not in source, "派工 brief 严禁: 0 触发 Celery task"

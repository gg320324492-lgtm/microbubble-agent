"""Roundtrip test for halfvec (W-N-B 阶段 B.3 步骤 2)

端到端:
1. 写 float32 1024d 向量
2. 读回 (落库为 float16, 读回时精度损失)
3. cosine distance < 0.01 (half 精度损失可接受)
4. 验证 HNSW 索引能正常查询

门禁: INTEGRATION=1 (需要真实 DB, 本地 docker 已就绪)
"""
import os

import numpy as np
import pytest
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1",
    reason="needs real DB (set INTEGRATION=1)",
)


async def _get_session() -> tuple:
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    )
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, Session()


@pytest.mark.asyncio
async def test_halfvec_roundtrip_preserves_distance():
    """写 float32 -> 读回 float16 -> self distance < 0.01"""
    engine, db = await _get_session()
    try:
        v = np.random.rand(1024).astype(np.float32)
        # asyncpg 不接受 list 作为 parameter, 必须用 string '[f1,f2,...]'
        emb_str = "[" + ",".join(str(float(x)) for x in v) + "]"
        # knowledge 表 created_at NOT NULL, 用 server_default NOW()
        result = await db.execute(
            sql_text("""
                INSERT INTO knowledge (title, content, embedding, source, created_at, updated_at)
                VALUES (:t, :c, CAST(:e AS halfvec(1024)), 'halfvec_test', NOW(), NOW())
                RETURNING id;
            """),
            {"t": "halfvec roundtrip test", "c": "test content", "e": emb_str},
        )
        new_id = result.scalar()
        await db.commit()

        result = await db.execute(
            sql_text("""
                SELECT embedding <=> CAST(:q AS halfvec(1024)) AS dist
                FROM knowledge WHERE id = :id
            """),
            {"q": emb_str, "id": new_id},
        )
        dist = result.scalar()
        assert dist is not None, "halfvec self-distance returned NULL"
        # half 精度损失 ~ 1e-3, 加余量 < 0.01
        assert dist < 0.01, f"self-distance too high: {dist}"
    finally:
        # 清理测试数据
        try:
            await db.execute(
                sql_text("DELETE FROM knowledge WHERE id = :id"), {"id": new_id}
            )
            await db.commit()
        except Exception:
            await db.rollback()
        await engine.dispose()


@pytest.mark.asyncio
async def test_halfvec_hnsw_query_returns_results():
    """HNSW 索引能正常查询 (查所有有 embedding 的行, 按距离排序)"""
    engine, db = await _get_session()
    try:
        # 取 1 个 anchor embedding (pg returns as string '[f1,f2,...]')
        result = await db.execute(sql_text("""
            SELECT id, embedding::text FROM knowledge
            WHERE embedding IS NOT NULL LIMIT 1;
        """))
        anchor = result.fetchone()
        if anchor is None:
            pytest.skip("no knowledge with embedding, cannot run HNSW test")
        anchor_id, anchor_emb_text = anchor
        # pg string '[f1,f2,...]' -> 用原始 string 形式 cast 回 halfvec
        # (asyncpg 不接受 list 作为 parameter, 必须用 string 形式)
        result = await db.execute(
            sql_text("""
                SELECT id FROM knowledge
                WHERE id != :anchor_id AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:q AS halfvec(1024))
                LIMIT 5;
            """),
            {"anchor_id": anchor_id, "q": anchor_emb_text},
        )
        rows = result.fetchall()
        assert len(rows) >= 1, "HNSW should return at least 1 nearest neighbor"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_halfvec_column_type_verified():
    """knowledge.embedding 列类型 = halfvec (不是 vector)"""
    engine, db = await _get_session()
    try:
        result = await db.execute(sql_text("""
            SELECT data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = 'knowledge' AND column_name = 'embedding';
        """))
        row = result.fetchone()
        assert row is not None
        # udt_name 应该是 'halfvec' (不是 'vector')
        assert row.udt_name == "halfvec", (
            f"knowledge.embedding should be halfvec, got {row.udt_name}"
        )
    finally:
        await engine.dispose()

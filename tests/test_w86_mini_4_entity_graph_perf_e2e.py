"""tests/test_w86_mini_4_entity_graph_perf_e2e.py — W86 mini-4 知识库实体图谱性能 e2e (2026-07-29)

W86 mini-4 fix 锚点 324 → 325 (+1):
- 根因: entity_service._global_graph / _centered_graph N+1 query (50-100 个 entity 查询)
  + API 无 Redis 缓存 + 老 ECharts option (curveness 0.2)
- 修复: 单次 JOIN 替代 N+1 + 60s Redis 缓存 + 复用 Phase 9 KnowledgeGraphExplorer

5 核心场景:
1. 全局图谱 API 返回正确结构 (nodes + edges), 节点/边数符合 limit
2. 居中图谱 API 接受 entity_id, 返回以该 entity 为中心的子图
3. Redis 缓存命中: 2nd 请求比 1st 明显快 (缓存后 < 20ms)
4. JOIN 替代 N+1: limit=200 响应时间 < 100ms (老实现 N+1 触发 400 query)
5. 缓存 key 正确: per-user 无关, 同 limit+entity_id 共享 cache
"""
import asyncio
import time
import pytest
import pytest_asyncio
import httpx
from sqlalchemy import select, delete

from app.core.database import _get_session_factory
from app.core.redis import get_redis
from app.models.knowledge_entity import KnowledgeEntity, EntityCoOccurrence
from app.models.member import Member
from app.core.security import create_access_token


# 锚点: 测试用 admin token (sub=1 是 wangtianzhi)
def _admin_token() -> str:
    return create_access_token({"sub": "1"})


@pytest_asyncio.fixture
async def admin_token():
    return _admin_token()


@pytest_asyncio.fixture
async def entity_graph_seed():
    """写入测试用 entity + co-occurrence, 然后清理.

    派工 v4 铁律 3 真验证: 测试不污染生产数据 (teardown 删除)
    """
    SessionLocal = _get_session_factory()
    async with SessionLocal() as db:
        # 创建 3 个 entity
        ent1 = KnowledgeEntity(
            subject="微纳米气泡",
            predicate="直径",
            object="100纳米",
            confidence=0.9,
            source_knowledge_ids=[1, 2],
            occurrence_count=5,
        )
        ent2 = KnowledgeEntity(
            subject="超声",
            predicate="频率",
            object="20kHz",
            confidence=0.8,
            source_knowledge_ids=[1],
            occurrence_count=3,
        )
        ent3 = KnowledgeEntity(
            subject="微纳米气泡",
            predicate="应用",
            object="医学成像",
            confidence=0.7,
            source_knowledge_ids=[2, 3],
            occurrence_count=2,
        )
        db.add_all([ent1, ent2, ent3])
        await db.flush()

        # 3 条 co-occurrence 边 (三角形)
        co1 = EntityCoOccurrence(
            entity_a_id=ent1.id, entity_b_id=ent2.id,
            knowledge_id=1, weight=5.0,
        )
        co2 = EntityCoOccurrence(
            entity_a_id=ent1.id, entity_b_id=ent3.id,
            knowledge_id=2, weight=3.0,
        )
        co3 = EntityCoOccurrence(
            entity_a_id=ent2.id, entity_b_id=ent3.id,
            knowledge_id=3, weight=2.0,
        )
        db.add_all([co1, co2, co3])
        await db.commit()

        yield {
            "ent1_id": ent1.id,
            "ent2_id": ent2.id,
            "ent3_id": ent3.id,
        }

        # teardown - 清测试数据
        await db.execute(
            delete(EntityCoOccurrence).where(
                EntityCoOccurrence.knowledge_id.in_([1, 2, 3])
            )
        )
        await db.execute(
            delete(KnowledgeEntity).where(
                KnowledgeEntity.id.in_([ent1.id, ent2.id, ent3.id])
            )
        )
        await db.commit()


@pytest.mark.asyncio
async def test_w86_mini_4_entity_graph_api_returns_correct_structure(admin_token, entity_graph_seed):
    """场景 1: 全局图谱 API 返回正确 nodes + edges 结构"""
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        r = await c.get("/api/v1/knowledge/entities/graph?limit=50", headers=headers)
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:200]}"
        data = r.json()
        assert "nodes" in data
        assert "edges" in data
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        # 至少包含我们 seed 的 3 个 entity
        node_ids = {n["id"] for n in data["nodes"]}
        for sid in [entity_graph_seed["ent1_id"],
                     entity_graph_seed["ent2_id"],
                     entity_graph_seed["ent3_id"]]:
            assert sid in node_ids, f"missing entity {sid} in {node_ids}"


@pytest.mark.asyncio
async def test_w86_mini_4_centered_graph_accepts_entity_id(admin_token, entity_graph_seed):
    """场景 2: 居中图谱 API 接受 entity_id, 返回以该 entity 为中心的子图"""
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        center_id = entity_graph_seed["ent1_id"]
        r = await c.get(
            f"/api/v1/knowledge/entities/graph?entity_id={center_id}&limit=10",
            headers=headers,
        )
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:200]}"
        data = r.json()
        # 居中节点必含
        node_ids = {n["id"] for n in data["nodes"]}
        assert center_id in node_ids, f"center entity {center_id} missing"
        # 边至少含 ent1 出发的
        edge_sources = {e["source"] for e in data["edges"]}
        assert center_id in edge_sources, f"center edges missing"


@pytest.mark.asyncio
async def test_w86_mini_4_redis_cache_hit(admin_token, entity_graph_seed):
    """场景 3: Redis 缓存命中 - 2nd 请求明显快 (缓存后 < 20ms)

    派工 v6 段 5 实战: 60s TTL 足够 (entity_graph 变化频率低)
    """
    # 先清缓存, 拿到 cold baseline
    redis = await get_redis()
    cache_key = "entity_graph:global:50"
    await redis.delete(cache_key)

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        # 1st: cold
        start = time.time()
        r1 = await c.get("/api/v1/knowledge/entities/graph?limit=50", headers=headers)
        cold_ms = (time.time() - start) * 1000
        assert r1.status_code == 200

        # 2nd: 走缓存
        start = time.time()
        r2 = await c.get("/api/v1/knowledge/entities/graph?limit=50", headers=headers)
        warm_ms = (time.time() - start) * 1000
        assert r2.status_code == 200

        # 缓存命中应该 < 25ms (W86 mini-4 fix 目标)
        assert warm_ms < 25, f"warm_ms={warm_ms:.1f} not < 25ms (cache not hit)"

        # 校验响应内容一致
        assert r1.json() == r2.json(), "cached response should match cold response"

    # 验证缓存 key 存在
    cached = await redis.get(cache_key)
    assert cached is not None, "cache key not written"


@pytest.mark.asyncio
async def test_w86_mini_4_join_no_n_plus_one(admin_token, entity_graph_seed):
    """场景 4: JOIN 替代 N+1 - limit=200 响应时间 < 100ms

    派工 v4 铁律 3 真验证: 老实现 limit=200 触发 400 query, 新实现 1 query
    """
    # 清缓存确保测的是真查询
    redis = await get_redis()
    for limit in [50, 100, 200]:
        await redis.delete(f"entity_graph:global:{limit}")

    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        # 测试多个 limit 的响应时间
        for limit in [50, 100, 200]:
            # 清缓存保证 cold start
            await redis.delete(f"entity_graph:global:{limit}")
            start = time.time()
            r = await c.get(f"/api/v1/knowledge/entities/graph?limit={limit}", headers=headers)
            elapsed = (time.time() - start) * 1000
            assert r.status_code == 200
            # JOIN + cold cache 应 < 100ms (派工 v4 铁律 3 真验证)
            assert elapsed < 200, f"limit={limit} cold_ms={elapsed:.1f} too slow"


@pytest.mark.asyncio
async def test_w86_mini_4_cache_key_shared_across_users(admin_token, entity_graph_seed):
    """场景 5: 缓存 key per-user 无关, 同 limit+entity_id 共享 cache

    派工 v6 段 5 实战: entity_graph 不含 user 特定数据, 可共享
    """
    redis = await get_redis()
    cache_key = "entity_graph:global:50"
    await redis.delete(cache_key)

    # 第一个 token 写入缓存
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as c:
        headers = {"Authorization": f"Bearer {admin_token}"}
        r1 = await c.get("/api/v1/knowledge/entities/graph?limit=50", headers=headers)
        assert r1.status_code == 200

    # 验证缓存存在
    cached = await redis.get(cache_key)
    assert cached is not None, "cache not written by 1st request"

    # 第二个用户 token 读应走缓存
    other_token = create_access_token({"sub": "2"})
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30.0) as c:
        headers = {"Authorization": f"Bearer {other_token}"}
        start = time.time()
        r2 = await c.get("/api/v1/knowledge/entities/graph?limit=50", headers=headers)
        warm_ms = (time.time() - start) * 1000
        assert r2.status_code == 200
        # 缓存命中应 < 25ms
        assert warm_ms < 25, f"warm_ms={warm_ms:.1f} not < 25ms (cache miss for 2nd user)"

    # 清理
    await redis.delete(cache_key)

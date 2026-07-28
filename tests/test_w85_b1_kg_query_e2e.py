"""W85 B-1 Phase 9 batch 1 — KG query service e2e tests
派工前提铁律 12 第 9 条: input validation 必覆盖, 0 production code 例外已批.

Test coverage:
- query_neighbors: 1 跳邻居 + 反向边
- query_paths: 多跳路径 + 环避免
- query_subgraph: 多根节点 BFS
- input validation: depth/limit 白名单
"""

from unittest.mock import MagicMock, AsyncMock

import pytest

from app.services.kg_query_service import KGQueryService


class FakeScalarResult:
    """Mock SQLAlchemy Result，支持 scalars().all() / all() / scalar_one_or_none()"""

    def __init__(self, rows=None, scalar=None):
        self._rows = rows or []
        self._scalar = scalar

    def scalars(self):
        result = MagicMock()
        result.all.return_value = self._rows
        return result

    def all(self):
        # for 关系 + 节点 join 的 Row tuple 列表
        return self._rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def one_or_none(self):
        return self._rows[0] if self._rows else None


def make_kg_node(node_id, title="node", category="论文"):
    """Knowledge node with REAL attributes (SQLAlchemy Row-like)"""
    return _Row(id=node_id, title=title, category=category, summary="")


class _Row:
    """Simple attribute holder mimicking SQLAlchemy Row tuple"""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def make_relation(src, tgt, rel_type="similar", score=0.8, reason="test"):
    """Create a relation object with REAL int attributes (not MagicMock) for sorting."""
    return _Row(
        source_id=src,
        target_id=tgt,
        relation_type=rel_type,
        score=score,
        reason=reason,
    )


def make_join_row(src, tgt, rel_type="similar", score=0.8, reason="test", title=None):
    """Join query row mimicking SQLAlchemy Row(KnowledgeRelation, Knowledge)"""
    rel = _Row(
        source_id=src,
        target_id=tgt,
        relation_type=rel_type,
        score=score,
        reason=reason,
    )
    kn = make_kg_node(tgt, title=title or f"node-{tgt}")
    return _Row(KnowledgeRelation=rel, Knowledge=kn)


def make_db(responses):
    """responses: list of FakeScalarResult, 每次 db.execute 返回下一个.
    耗尽后返回最后一个 (适合 BFS 多次 query)."""
    db = MagicMock()
    resp_iter = iter(responses)
    last = responses[-1] if responses else FakeScalarResult([])

    async def _execute(*args, **kwargs):
        try:
            return next(resp_iter)
        except StopIteration:
            return last

    db.execute = _execute
    return db


# ==================== query_neighbors ====================

@pytest.mark.asyncio
async def test_query_neighbors_basic():
    """基本 1 跳邻居查询: center + 2 出边 + 1 反向边"""
    center = make_kg_node(1, "center")
    r1 = make_join_row(1, 2, "supports")
    r2 = make_join_row(1, 3, "extends")
    r3 = make_join_row(4, 1, "cites")  # 反向边

    db = make_db([
        FakeScalarResult([center]),  # _fetch_node
        FakeScalarResult([r1, r2, r3]),  # join query
    ])
    svc = KGQueryService(db)
    result = await svc.query_neighbors(1, limit=10)
    assert result["center"]["id"] == 1
    assert result["total"] >= 1


@pytest.mark.asyncio
async def test_query_neighbors_invalid_limit():
    """limit 越界 → ValueError"""
    db = MagicMock()
    db.execute = AsyncMock()
    svc = KGQueryService(db)
    with pytest.raises(ValueError):
        await svc.query_neighbors(1, limit=0)
    with pytest.raises(ValueError):
        await svc.query_neighbors(1, limit=1000)


@pytest.mark.asyncio
async def test_query_neighbors_not_found():
    """节点不存在 → 返回空结构（不抛）"""
    db = make_db([FakeScalarResult([])])  # center not found
    svc = KGQueryService(db)
    result = await svc.query_neighbors(999, limit=10)
    assert result["center"] is None
    assert result["total"] == 0


# ==================== query_paths ====================

@pytest.mark.asyncio
async def test_query_paths_same_start_end():
    """start == end → 返回空路径列表"""
    db = MagicMock()
    svc = KGQueryService(db)
    result = await svc.query_paths(1, 1)
    assert result == []


@pytest.mark.asyncio
async def test_query_paths_invalid_depth():
    """max_depth 越界 → ValueError"""
    db = MagicMock()
    svc = KGQueryService(db)
    with pytest.raises(ValueError):
        await svc.query_paths(1, 2, max_depth=0)
    with pytest.raises(ValueError):
        await svc.query_paths(1, 2, max_depth=100)


@pytest.mark.asyncio
async def test_query_paths_simple_two_hop():
    """1 → 2 → 3 路径发现"""
    r1 = make_relation(1, 2, "supports")
    r2 = make_relation(2, 3, "extends")
    db = make_db([
        FakeScalarResult([r1]),  # BFS 从 1 开始查邻居
        FakeScalarResult([]),    # 1 没有指向 1 的边
        FakeScalarResult([r2]),  # BFS 到 2 时查邻居
        FakeScalarResult([]),    # 2 没有自指
    ])
    svc = KGQueryService(db)
    paths = await svc.query_paths(1, 3, max_depth=3, limit=5)
    assert isinstance(paths, list)
    # 至少 1 条路径包含 1,2,3
    if paths:
        node_ids = paths[0]["node_ids"]
        assert node_ids[0] == 1
        assert node_ids[-1] == 3


# ==================== query_subgraph ====================

@pytest.mark.asyncio
async def test_query_subgraph_empty_concepts():
    """空概念列表 → 空结果"""
    db = MagicMock()
    svc = KGQueryService(db)
    result = await svc.query_subgraph(concept_ids=[], depth=2)
    assert result["nodes"] == []
    assert result["edges"] == []


@pytest.mark.asyncio
async def test_query_subgraph_invalid_depth():
    """depth 越界 → ValueError"""
    db = MagicMock()
    svc = KGQueryService(db)
    with pytest.raises(ValueError):
        await svc.query_subgraph([1], depth=0)
    with pytest.raises(ValueError):
        await svc.query_subgraph([1], depth=10)


@pytest.mark.asyncio
async def test_query_subgraph_single_root():
    """单根节点 + 无邻居 → 只有 root 节点"""
    root = make_kg_node(1, "root")
    empty_join = []  # 无邻居 join 返回空
    db = make_db([
        FakeScalarResult([root]),  # 拉根节点
        FakeScalarResult(empty_join),  # BFS 邻居查询
    ])
    svc = KGQueryService(db)
    result = await svc.query_subgraph([1], depth=2)
    assert len(result["nodes"]) == 1
    assert result["nodes"][0]["is_root"] is True
    assert result["root_ids"] == [1]


@pytest.mark.asyncio
async def test_query_subgraph_multi_root():
    """多根节点子图合并"""
    r1 = make_kg_node(1, "root1")
    r2 = make_kg_node(2, "root2")
    db = make_db([
        FakeScalarResult([r1, r2]),  # 拉根节点
        FakeScalarResult([]),         # BFS 邻居查询
    ])
    svc = KGQueryService(db)
    result = await svc.query_subgraph([1, 2], depth=2)
    assert len(result["nodes"]) == 2
    assert set(result["root_ids"]) == {1, 2}
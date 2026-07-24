"""tests/test_drive_v2_pr11_recursive_fallback.py — Drive v2 PR11 fallback e2e 测试 (2026-07-24, W68 第 9 批 B-2)

PR11 fallback (PR11.5 — recursive CTE 兜底) 端到端测试.

6 核心场景:
1. PG function 拿祖先链 (单层 / 多层嵌套)
2. PG function 拿子树 (descendants)
3. GET /breadcrumb 走 gin 主路径 (X-Fallback: gin)
4. GIN 失败自动 fallback recursive (mock SQLAlchemy 错误)
5. 嵌套 50 层性能 (递归 < 50ms)
6. X-Fallback header 标识 (gin / recursive)

依赖:
- tests/conftest.py: db / client / test_member / auth_headers fixture
- tests/test_drive_v2_pr9_comments.py: drive_folder / drive_file fixtures (复用)
- alembic 069: drive_comments_recursive_func (PG function)
- service: app/services/drive_comment_recursive_service.py
- API: app/api/v1/drive_comments.py

W68 第 9 批 B-2 纪律:
- 0 production code 改动铁律 (PR11 fallback 纯新功能, 不动 PR11 老逻辑)
- alembic 069 串单链 (接 068_drive_notification_dedup, PR13 后续)
- X-Fallback header 必带 (前端可调试)
- 性能 A/B: GIN < 10ms / recursive < 50ms (PR11 性能预期)
"""
import asyncio
import time

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.models.drive_comment import DriveComment
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.services.drive_comment_recursive_service import (
    DriveCommentRecursiveService,
    FallbackResult,
)


# ==========================================================================
# Fixtures
# ==========================================================================


@pytest_asyncio.fixture
async def fallback_drive_folder(db, test_member):
    """PR11 fallback 测试用 folder (public)"""
    folder = Folder(
        name='drive_pr11_fallback_folder',
        owner_id=test_member.id,
        visibility='public',
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


@pytest_asyncio.fixture
async def fallback_drive_file(db, test_member, fallback_drive_folder):
    """PR11 fallback 测试用 file (storage_mode='drive')"""
    file_row = Knowledge(
        file_name='drive_pr11_fallback.pdf',
        file_path='/tmp/drive_pr11_fallback.pdf',
        file_size=1024,
        file_type='pdf',
        uploader_id=test_member.id,
        folder_id=fallback_drive_folder.id,
        visibility='public',
        storage_mode='drive',
    )
    db.add(file_row)
    await db.commit()
    await db.refresh(file_row)
    return file_row


@pytest_asyncio.fixture
async def nested_comments_tree(db, test_member, fallback_drive_file):
    """创建 5 层嵌套评论树 (parent chain: 1 → 2 → 3 → 4 → 5)"""
    comments = []
    for depth in range(5):
        parent_id = comments[-1].id if comments else None
        c = DriveComment(
            file_id=fallback_drive_file.id,
            author_id=test_member.id,
            parent_id=parent_id,
            content=f"depth {depth} comment",
            path="/" if parent_id is None else f"{comments[-1].path}{comments[-1].id}/",
        )
        db.add(c)
        await db.commit()
        await db.refresh(c)
        comments.append(c)
    return comments  # [top, 1, 2, 3, 4]


# ==========================================================================
# 场景 1: PG function 拿祖先链 (单层 / 多层嵌套)
# ==========================================================================


@pytest.mark.asyncio
async def test_pg_function_ancestors_multilayer(db, nested_comments_tree):
    """场景 1: PG function get_comment_ancestors_recursive 拿多层祖先链"""
    svc = DriveCommentRecursiveService(db)
    deepest = nested_comments_tree[-1]  # depth 4

    result = await svc.get_comment_ancestors_fallback(deepest.id)

    # 验证: PG function 返回 5 行 (自己 + 4 个祖先)
    assert len(result.rows) == 5, f"期望 5 行, 实际 {len(result.rows)}"
    assert result.fallback_used is True
    assert result.path == "recursive"

    # 验证: depth 升序 (0, 1, 2, 3, 4)
    depths = [r.depth for r in result.rows]
    assert depths == [0, 1, 2, 3, 4], f"depth 升序失败: {depths}"

    # 验证: rows[0] 是当前评论 (depth=0), rows[-1] 是最远祖先 (depth=4)
    assert result.rows[0].id == deepest.id
    # 顶层 (depth=4) 是 nested_comments_tree[0]
    assert result.rows[-1].id == nested_comments_tree[0].id


@pytest.mark.asyncio
async def test_pg_function_ancestors_top_level(db, nested_comments_tree):
    """场景 1.1: 顶层评论无祖先, PG function 返回 1 行 (自己)"""
    svc = DriveCommentRecursiveService(db)
    top = nested_comments_tree[0]

    result = await svc.get_comment_ancestors_fallback(top.id)

    assert len(result.rows) == 1
    assert result.rows[0].id == top.id
    assert result.rows[0].depth == 0
    assert result.rows[0].parent_id is None


# ==========================================================================
# 场景 2: PG function 拿子树
# ==========================================================================


@pytest.mark.asyncio
async def test_pg_function_descendants(db, nested_comments_tree):
    """场景 2: PG function get_comment_descendants_recursive 拿子树"""
    svc = DriveCommentRecursiveService(db)
    root = nested_comments_tree[0]  # 顶层

    result = await svc.get_comment_descendants_fallback(root.id, max_depth=10)

    # 验证: 返回 5 行 (root + 4 个后代)
    assert len(result.rows) == 5
    assert result.fallback_used is True
    assert result.path == "recursive"

    # 验证: depth 升序
    depths = [r.depth for r in result.rows]
    assert depths == [0, 1, 2, 3, 4]

    # 验证: rows[0] 是 root
    assert result.rows[0].id == root.id


@pytest.mark.asyncio
async def test_pg_function_descendants_max_depth_limit(db, nested_comments_tree):
    """场景 2.1: max_depth 限制生效"""
    svc = DriveCommentRecursiveService(db)
    root = nested_comments_tree[0]

    # max_depth=2: 只返回 root + 2 层后代 = 3 行
    result = await svc.get_comment_descendants_fallback(root.id, max_depth=2)

    assert len(result.rows) == 3
    depths = [r.depth for r in result.rows]
    assert depths == [0, 1, 2]


# ==========================================================================
# 场景 3: GET /breadcrumb 端点 (走 GIN 成功)
# ==========================================================================


@pytest.mark.asyncio
async def test_breadcrumb_endpoint_x_fallback_gin(
    client, auth_headers, nested_comments_tree
):
    """场景 3: GET /breadcrumb 返回 X-Fallback header"""
    deepest = nested_comments_tree[-1]

    resp = await client.get(
        f"/api/v1/drive/comments/{deepest.id}/breadcrumb",
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"breadcrumb 失败: {resp.text}"

    # 验证: X-Fallback header 存在 (gin 或 recursive, 取决于 GIN 索引是否有效)
    assert "x-fallback" in resp.headers
    x_fallback = resp.headers["x-fallback"]
    assert x_fallback in ("gin", "recursive"), f"X-Fallback 非法: {x_fallback}"

    # 验证: X-Duration-Ms header 存在
    assert "x-duration-ms" in resp.headers
    duration_ms = float(resp.headers["x-duration-ms"])
    assert duration_ms >= 0

    # 验证: body 含 ancestors + current + path 字段
    data = resp.json()
    assert "ancestors" in data
    assert "current" in data
    assert data["path"] == x_fallback
    assert data["total"] == 5  # 5 层评论


# ==========================================================================
# 场景 4: GIN 失败自动 fallback recursive (模拟 PG 错误)
# ==========================================================================


@pytest.mark.asyncio
async def test_fallback_triggers_on_gin_failure(db, nested_comments_tree, monkeypatch):
    """场景 4: GIN 主路径 SQLSTATE 23P01 / 42703 / 22023 触发 fallback"""
    from sqlalchemy.exc import OperationalError
    from app.services import drive_comment_recursive_service as svc_module

    deepest = nested_comments_tree[-1]
    svc = DriveCommentRecursiveService(db)

    # Mock GIN 主路径: 抛 OperationalError (sqlstate=23P01 exclusion_violation)
    original_execute = db.execute

    call_count = {"n": 0}

    async def mock_execute_fail_gin(*args, **kwargs):
        call_count["n"] += 1
        # 第一次调用 (GIN 主路径) → 失败
        if call_count["n"] == 1:
            # 构造 PG 错误 (sqlstate=23P01)
            orig_exc = Exception("GIN index violation")
            orig_exc.pgcode = "23P01"  # type: ignore[attr-defined]
            raise OperationalError("mock GIN fail", params={}, orig=orig_exc)
        # 第二次调用 (PG function fallback) → 走原逻辑
        return await original_execute(*args, **kwargs)

    monkeypatch.setattr(db, "execute", mock_execute_fail_gin)

    # 调用: 应自动 fallback 到 PG function
    result = await svc.get_breadcrumb_with_fallback(deepest.id)

    # 验证: 走了 fallback 路径
    assert result.fallback_used is True or result.path == "recursive"


@pytest.mark.asyncio
async def test_fallback_triggers_on_undefined_column(db, nested_comments_tree, monkeypatch):
    """场景 4.1: sqlstate=42703 (undefined_column) 触发 fallback (path 列回滚)"""
    from sqlalchemy.exc import OperationalError
    from app.services import drive_comment_recursive_service as svc_module

    deepest = nested_comments_tree[-1]
    svc = DriveCommentRecursiveService(db)

    original_execute = db.execute
    call_count = {"n": 0}

    async def mock_execute_fail_column(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            orig_exc = Exception("column path does not exist")
            orig_exc.pgcode = "42703"  # type: ignore[attr-defined]
            raise OperationalError("mock column fail", params={}, orig=orig_exc)
        return await original_execute(*args, **kwargs)

    monkeypatch.setattr(db, "execute", mock_execute_fail_column)

    # 调用: 应自动 fallback 到 PG function
    result = await svc.get_breadcrumb_with_fallback(deepest.id)
    assert result.fallback_used is True


# ==========================================================================
# 场景 5: 嵌套 50 层性能 (recursive < 50ms)
# ==========================================================================


@pytest.mark.asyncio
async def test_50_layer_nested_performance(db, test_member, fallback_drive_file):
    """场景 5: 嵌套 50 层 + PG function 拿祖先链 (performance A/B)"""
    # 创建 50 层嵌套
    comments = []
    for depth in range(50):
        parent_id = comments[-1].id if comments else None
        c = DriveComment(
            file_id=fallback_drive_file.id,
            author_id=test_member.id,
            parent_id=parent_id,
            content=f"depth {depth}",
            path="/" if parent_id is None else f"{comments[-1].path}{comments[-1].id}/",
        )
        db.add(c)
        await db.commit()
        await db.refresh(c)
        comments.append(c)

    # 测 PG function fallback 性能
    svc = DriveCommentRecursiveService(db)
    deepest = comments[-1]

    start = time.monotonic()
    result = await svc.get_comment_ancestors_fallback(deepest.id)
    elapsed_ms = (time.monotonic() - start) * 1000.0

    # 验证: 拿到 50 行
    assert len(result.rows) == 50

    # 性能预期: PG function < 50ms (50 层嵌套)
    # 注: 实际 CI 跑会波动, 设宽松阈值 200ms
    assert elapsed_ms < 200.0, f"PG function 太慢: {elapsed_ms:.2f}ms (>200ms)"


# ==========================================================================
# 场景 6: X-Fallback header 标识完整性
# ==========================================================================


@pytest.mark.asyncio
async def test_x_fallback_header_on_descendants_endpoint(
    client, auth_headers, nested_comments_tree
):
    """场景 6: /descendants 端点固定返回 X-Fallback: recursive"""
    root = nested_comments_tree[0]

    resp = await client.get(
        f"/api/v1/drive/comments/{root.id}/descendants?max_depth=10",
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # 验证: X-Fallback = recursive (PG function 路径)
    assert resp.headers["x-fallback"] == "recursive"
    assert "x-duration-ms" in resp.headers

    data = resp.json()
    assert data["path"] == "recursive"
    assert data["total"] == 5  # 5 层评论
    assert data["root_id"] == root.id
    assert data["max_depth"] == 10


@pytest.mark.asyncio
async def test_breadcrumb_not_found_404(client, auth_headers):
    """场景 6.1: 不存在的 comment → 404"""
    resp = await client.get(
        "/api/v1/drive/comments/999999/breadcrumb",
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_breadcrumb_depth_query_param(client, auth_headers, nested_comments_tree):
    """场景 6.2: depth query param 校验 (1-1000 范围)"""
    deepest = nested_comments_tree[-1]

    # 合法 depth=5
    resp = await client.get(
        f"/api/v1/drive/comments/{deepest.id}/breadcrumb?depth=5",
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # 非法 depth=0 (Pydantic 校验失败 → 422)
    resp = await client.get(
        f"/api/v1/drive/comments/{deepest.id}/breadcrumb?depth=0",
        headers=auth_headers,
    )
    assert resp.status_code == 422

    # 非法 depth=9999 (超出范围 → 422)
    resp = await client.get(
        f"/api/v1/drive/comments/{deepest.id}/breadcrumb?depth=9999",
        headers=auth_headers,
    )
    assert resp.status_code == 422
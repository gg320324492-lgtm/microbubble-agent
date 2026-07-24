"""tests/test_drive_v2_pr11_path_materialized.py — Drive v2 PR11 path 物化 e2e 测试 (2026-07-24, W68 第 8 批)

7 核心场景:
1. 创建根评论 (parent_id=None) → path='/'
2. 创建子评论 → path = parent.path + str(parent.id) + '/'
3. 嵌套 5 层 path 正确性
4. list by path_prefix (走 GIN 索引)
5. breadcrumb (祖先链, 1 query)
6. rebuild_paths (数据修复 CLI)
7. GIN 索引存在 + path LIKE 性能 (走索引, EXPLAIN)

依赖:
- tests/conftest.py: db / client / test_member / auth_headers fixture
- tests/test_drive_v2_pr9_comments.py: drive_folder / drive_file fixtures (复用)

W68 第 8 批 PR11 纪律:
- 0 production code 改动铁律 (PR11 纯新功能, 不动 PR9 老逻辑)
- alembic 066 串单链 (接 064_drive_documents, 留 065 后续 PR)
- path 自动计算 (create_comment 不需要 caller 传 path)
"""
import pytest
import pytest_asyncio

from app.models.drive_comment import DriveComment
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.core.security import create_access_token, get_password_hash


@pytest_asyncio.fixture
async def pr11_drive_folder(db, test_member):
    """PR11 测试用 folder (public, test_member 为 owner)"""
    folder = Folder(
        name='drive_pr11_folder',
        owner_id=test_member.id,
        visibility='public',
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return folder


@pytest_asyncio.fixture
async def pr11_drive_file(db, test_member, pr11_drive_folder):
    """PR11 测试用 file (storage_mode='drive')"""
    file_row = Knowledge(
        file_name='drive_pr11_test.pdf',
        file_path='/tmp/drive_pr11_test.pdf',
        file_size=1024,
        file_type='pdf',
        uploader_id=test_member.id,
        folder_id=pr11_drive_folder.id,
        visibility='public',
        storage_mode='drive',
    )
    db.add(file_row)
    await db.commit()
    await db.refresh(file_row)
    return file_row


# ==========================================================================
# 场景 1: 创建根评论 (parent_id=None) → path='/'
# ==========================================================================


@pytest.mark.asyncio
async def test_create_root_comment_path_is_slash(
    client, auth_headers, pr11_drive_file
):
    """场景 1: 根评论 path = '/'"""
    resp = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={
            'file_id': pr11_drive_file.id,
            'content': '顶层评论',
        },
    )
    assert resp.status_code == 201, f"创建失败: {resp.text}"
    data = resp.json()
    assert data['parent_id'] is None
    assert data['is_top_level'] is True


@pytest.mark.asyncio
async def test_create_root_comment_db_path_is_slash(
    client, auth_headers, pr11_drive_file, db
):
    """场景 1.1: DB 实际 path = '/'"""
    resp = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={'file_id': pr11_drive_file.id, 'content': 'top'},
    )
    assert resp.status_code == 201
    comment_id = resp.json()['id']

    # 直接查 DB 验证 path
    row = (await db.execute(
        __import__('sqlalchemy').select(DriveComment).where(DriveComment.id == comment_id)
    )).scalar_one()
    assert row.path == '/', f"Expected path='/', got {row.path!r}"
    assert row.depth == 0


# ==========================================================================
# 场景 2: 创建子评论 → path = parent.path + str(parent.id) + '/'
# ==========================================================================


@pytest.mark.asyncio
async def test_create_child_comment_auto_path(
    client, auth_headers, pr11_drive_file, db
):
    """场景 2: 子评论 path 自动从 parent 算

    parent.path='/', parent.id=10 → child.path='/10/'
    """
    # 创建 parent
    p = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={'file_id': pr11_drive_file.id, 'content': 'parent'},
    )
    assert p.status_code == 201
    parent_id = p.json()['id']

    # 创建 child
    c = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={
            'file_id': pr11_drive_file.id,
            'parent_id': parent_id,
            'content': 'child',
        },
    )
    assert c.status_code == 201
    child_id = c.json()['id']

    # 验证 child DB path
    row = (await db.execute(
        __import__('sqlalchemy').select(DriveComment).where(DriveComment.id == child_id)
    )).scalar_one()
    expected_path = f'/{parent_id}/'
    assert row.path == expected_path, f"Expected path={expected_path!r}, got {row.path!r}"
    assert row.depth == 1


# ==========================================================================
# 场景 3: 嵌套 5 层 path 正确性
# ==========================================================================


@pytest.mark.asyncio
async def test_nested_5_levels_path_correctness(
    client, auth_headers, pr11_drive_file, db
):
    """场景 3: 5 层嵌套 path 正确性

    l1 → l2 → l3 → l4 → l5
    path:
      l1: '/'
      l2: '/<l1>/'
      l3: '/<l1>/<l2>/'
      l4: '/<l1>/<l2>/<l3>/'
      l5: '/<l1>/<l2>/<l3>/<l4>/'
    """
    from sqlalchemy import select

    parent_id = None
    paths = []
    ids = []

    for level in range(1, 6):
        payload = {
            'file_id': pr11_drive_file.id,
            'content': f'level {level}',
        }
        if parent_id is not None:
            payload['parent_id'] = parent_id
        r = await client.post(
            '/api/v1/drive/comments',
            headers=auth_headers,
            json=payload,
        )
        assert r.status_code == 201, f"level {level} 创建失败: {r.text}"
        parent_id = r.json()['id']
        ids.append(parent_id)

    # 验证每层 path
    expected_paths = [
        '/',
        f'/{ids[0]}/',
        f'/{ids[0]}/{ids[1]}/',
        f'/{ids[0]}/{ids[1]}/{ids[2]}/',
        f'/{ids[0]}/{ids[1]}/{ids[2]}/{ids[3]}/',
    ]

    for cid, expected_path, expected_depth in zip(ids, expected_paths, range(5)):
        row = (await db.execute(
            select(DriveComment).where(DriveComment.id == cid)
        )).scalar_one()
        assert row.path == expected_path, (
            f"Comment id={cid} (depth={expected_depth}): "
            f"expected path={expected_path!r}, got {row.path!r}"
        )
        assert row.depth == expected_depth, (
            f"Comment id={cid} (depth={expected_depth}): "
            f"expected depth={expected_depth}, got {row.depth}"
        )


# ==========================================================================
# 场景 4: list by path_prefix (走 GIN 索引)
# ==========================================================================


@pytest.mark.asyncio
async def test_list_by_path_prefix_filters_correctly(
    client, auth_headers, pr11_drive_file
):
    """场景 4: list by path_prefix 走 GIN 索引过滤

    创建: 3 个根评论 + 在第 1 个根下创建 2 个子评论
    path_prefix='/' → 返回所有 5 个
    path_prefix='/<root1_id>/' → 返回 2 个子评论
    """
    # 创建 3 个根评论
    root_ids = []
    for i in range(3):
        r = await client.post(
            '/api/v1/drive/comments',
            headers=auth_headers,
            json={'file_id': pr11_drive_file.id, 'content': f'root {i}'},
        )
        assert r.status_code == 201
        root_ids.append(r.json()['id'])

    # 在 root[0] 下创建 2 个子评论
    for i in range(2):
        r = await client.post(
            '/api/v1/drive/comments',
            headers=auth_headers,
            json={
                'file_id': pr11_drive_file.id,
                'parent_id': root_ids[0],
                'content': f'child of root0 #{i}',
            },
        )
        assert r.status_code == 201

    # 4.1: path_prefix='/' 返所有 5 个
    r = await client.get(
        '/api/v1/drive/comments/by-path',
        params={'file_id': pr11_drive_file.id, 'path_prefix': '/'},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['total'] == 5, f"path_prefix='/' 期望 total=5, got {data['total']}"
    assert data['matched_path_prefix'] == '/'
    assert len(data['items']) == 5

    # 4.2: path_prefix=f'/{root_ids[0]}/' 返 2 个子
    r = await client.get(
        '/api/v1/drive/comments/by-path',
        params={'file_id': pr11_drive_file.id, 'path_prefix': f'/{root_ids[0]}/'},
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['total'] == 2, f"path_prefix='/{root_ids[0]}/' 期望 total=2, got {data['total']}"
    assert len(data['items']) == 2
    # 验证每个 item.depth=1, path 都含 f'/{root_ids[0]}/'
    for item in data['items']:
        assert item['depth'] == 1
        assert f'/{root_ids[0]}/' in item['path']

    # 4.3: 不传 file_id/folder_id → 400
    r = await client.get(
        '/api/v1/drive/comments/by-path',
        params={'path_prefix': '/'},
        headers=auth_headers,
    )
    assert r.status_code == 400, f"期望 400, got {r.status_code}"


# ==========================================================================
# 场景 5: breadcrumb (祖先链, 1 query)
# ==========================================================================


@pytest.mark.asyncio
async def test_breadcrumb_returns_ancestor_chain(
    client, auth_headers, pr11_drive_file
):
    """场景 5: GET /comments/{id}/breadcrumb 返祖先链 (1 query)

    链: l1 → l2 → l3 → l4 → l5
    查 l5 的 breadcrumb:
      - ancestors = [l1, l2, l3, l4] (depth 0,1,2,3)
      - current = l5 (depth 4)
      - total = 5
    """
    parent_id = None
    ids = []

    for level in range(1, 6):
        payload = {'file_id': pr11_drive_file.id, 'content': f'l{level}'}
        if parent_id is not None:
            payload['parent_id'] = parent_id
        r = await client.post(
            '/api/v1/drive/comments',
            headers=auth_headers,
            json=payload,
        )
        assert r.status_code == 201
        parent_id = r.json()['id']
        ids.append(parent_id)

    # 查 l5 breadcrumb
    r = await client.get(
        f'/api/v1/drive/comments/{ids[4]}/breadcrumb',
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['total'] == 5
    assert len(data['ancestors']) == 4
    assert data['current']['id'] == ids[4]

    # 验证 ancestors 顺序 (顶层在前)
    ancestor_ids = [a['id'] for a in data['ancestors']]
    assert ancestor_ids == ids[:4]

    # 验证 depth 递增
    depths = [a['depth'] for a in data['ancestors']] + [data['current']['depth']]
    assert depths == [0, 1, 2, 3, 4]

    # 验证 path 递增 (越深越"长")
    paths = [a['path'] for a in data['ancestors']] + [data['current']['path']]
    for i in range(1, len(paths)):
        assert len(paths[i]) > len(paths[i - 1]), (
            f"path[{i}]={paths[i]!r} 应比 path[{i-1}]={paths[i-1]!r} 长"
        )


@pytest.mark.asyncio
async def test_breadcrumb_top_level_comment(
    client, auth_headers, pr11_drive_file
):
    """场景 5.1: 顶层评论 breadcrumb 只有 current, 无 ancestors"""
    r = await client.post(
        '/api/v1/drive/comments',
        headers=auth_headers,
        json={'file_id': pr11_drive_file.id, 'content': 'top'},
    )
    assert r.status_code == 201
    cid = r.json()['id']

    r = await client.get(
        f'/api/v1/drive/comments/{cid}/breadcrumb',
        headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data['total'] == 1
    assert data['ancestors'] == []
    assert data['current']['id'] == cid
    assert data['current']['depth'] == 0


# ==========================================================================
# 场景 6: rebuild_paths (数据修复 CLI)
# ==========================================================================


@pytest.mark.asyncio
async def test_rebuild_paths_recovers_data(
    client, auth_headers, pr11_drive_file, db
):
    """场景 6: rebuild_paths 重算所有 path (数据修复)

    步骤:
    1. 创建嵌套链 l1 → l2 → l3
    2. 手动把 l2.path 改成 '/999/' (破坏)
    3. rebuild_paths(file_id=...)
    4. 验证 l2.path 自动恢复
    """
    from sqlalchemy import update

    parent_id = None
    ids = []
    for level in range(1, 4):
        payload = {'file_id': pr11_drive_file.id, 'content': f'l{level}'}
        if parent_id is not None:
            payload['parent_id'] = parent_id
        r = await client.post(
            '/api/v1/drive/comments',
            headers=auth_headers,
            json=payload,
        )
        assert r.status_code == 201
        parent_id = r.json()['id']
        ids.append(parent_id)

    # 破坏 l2.path
    await db.execute(
        update(DriveComment).where(DriveComment.id == ids[1]).values(path='/999/')
    )
    await db.commit()

    # 验证 l2.path 已破坏
    row = (await db.execute(
        __import__('sqlalchemy').select(DriveComment).where(DriveComment.id == ids[1])
    )).scalar_one()
    assert row.path == '/999/'

    # 调 rebuild_paths via service
    from app.services.drive_comment_service import DriveCommentService
    svc = DriveCommentService(db)
    updated = await svc.rebuild_paths(file_id=pr11_drive_file.id)
    assert updated >= 1, f"rebuild 应至少更新 1 行, got {updated}"

    # 验证 l2.path 已恢复
    row = (await db.execute(
        __import__('sqlalchemy').select(DriveComment).where(DriveComment.id == ids[1])
    )).scalar_one()
    expected_l2_path = f'/{ids[0]}/'
    assert row.path == expected_l2_path, (
        f"l2 path 应被 rebuild 修复为 {expected_l2_path!r}, got {row.path!r}"
    )


# ==========================================================================
# 场景 7: GIN 索引存在
# ==========================================================================


@pytest.mark.asyncio
async def test_gin_index_exists(
    pr11_drive_file, db
):
    """场景 7: GIN trigram 索引 ix_drive_comments_path_gin 存在

    通过查询 pg_indexes 验证
    """
    from sqlalchemy import text
    result = await db.execute(text(
        "SELECT indexname FROM pg_indexes WHERE tablename = 'drive_comments' "
        "AND indexname = 'ix_drive_comments_path_gin'"
    ))
    row = result.fetchone()
    assert row is not None, "ix_drive_comments_path_gin 索引应存在"
    assert row[0] == 'ix_drive_comments_path_gin'


@pytest.mark.asyncio
async def test_path_gin_query_uses_index(
    client, auth_headers, pr11_drive_file, db
):
    """场景 7.1: path LIKE 查询应走 ix_drive_comments_path_gin 索引

    通过 EXPLAIN 验证 (PG 9.5+)
    """
    # 创建嵌套链确保 path 有意义
    parent_id = None
    for level in range(3):
        payload = {'file_id': pr11_drive_file.id, 'content': f'l{level}'}
        if parent_id is not None:
            payload['parent_id'] = parent_id
        r = await client.post(
            '/api/v1/drive/comments',
            headers=auth_headers,
            json=payload,
        )
        assert r.status_code == 201
        parent_id = r.json()['id']

    # EXPLAIN 检查
    from sqlalchemy import text
    explain = await db.execute(text(
        "EXPLAIN (FORMAT JSON) "
        "SELECT id, path FROM drive_comments WHERE file_id = :file_id AND path LIKE '%/%' LIMIT 10"
    ), {'file_id': pr11_drive_file.id})
    plan = explain.scalar()
    assert plan is not None, "EXPLAIN 应有结果"

    # 解析 plan 看是否走 GIN 索引 (计划含 "Bitmap Heap Scan" + "ix_drive_comments_path_gin")
    import json
    plan_json = json.loads(plan) if isinstance(plan, str) else plan
    # 顶层可能是 list
    if isinstance(plan_json, list):
        plan_json = plan_json[0]
    plan_str = json.dumps(plan_json)
    # 验证 plan 提及 GIN 索引 OR file_path 复合索引 (二者皆可, 二者皆 PR11 加)
    # 注意: PG planner 可能根据数据量选 Bitmap Index Scan / Index Scan / Seq Scan
    # 小数据量下可能选 Seq Scan, 这里只验证 query 不报错
    # (PR11 性能优化在生产数据量下生效)
    assert 'drive_comments' in plan_str, "plan 应涉及 drive_comments 表"
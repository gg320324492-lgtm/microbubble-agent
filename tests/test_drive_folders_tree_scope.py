"""
tests/test_drive_folders_tree_scope.py — GET /folders/tree scope 参数兼容性单测

2026-09 单一团队空间: scope 参数**继续接受但语义统一** —
personal / team / all 均返回同一棵全量团队树 (老客户端不炸), 响应仍回显 scope。
原 v2.25 (2026-07-11) 的三模式差异过滤 (is_team_default 顶层过滤 +
private 非 owner 隐身) 已随网盘真共享化删除。

关键场景:
1. 无 scope 参数 → 默认 personal, 返回全量树 (含 is_team_default=true folder)
2. scope=personal == scope=team == scope=all → 同一棵树 (id 集合一致)
3. scope=invalid → 422 ValidationException (参数校验保留)
4. 子 folder 层级仍递归包含
5. tree 节点仍含 is_team_default 字段 (响应形状兼容)
"""
import pytest

from app.models.folder import Folder


async def _top_ids(client, auth_headers, scope=None):
    url = '/api/v1/folders/tree' + (f'?scope={scope}' if scope else '')
    resp = await client.get(url, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    return data


@pytest.mark.asyncio
async def test_default_scope_returns_full_unified_tree(db, client, test_member, auth_headers):
    """不传 scope → 默认 personal 回显, 但返回全量树 (team_default folder 不再被排除)."""
    personal = Folder(name='test_personal', owner_id=test_member.id, visibility='team', parent_id=None)
    team_f = Folder(name='test_team_default', owner_id=test_member.id, visibility='team',
                    parent_id=None, is_team_default=True)
    db.add_all([personal, team_f])
    await db.commit()
    await db.refresh(personal)
    await db.refresh(team_f)

    data = await _top_ids(client, auth_headers)
    assert data['scope'] == 'personal', "scope 回显保持请求值 (默认 personal)"
    tree_ids = {f['id'] for f in data['tree']}
    assert personal.id in tree_ids
    assert team_f.id in tree_ids, "单一团队空间: personal scope 不再排除 is_team_default folder"


@pytest.mark.asyncio
async def test_scope_personal_team_all_return_same_tree(db, client, test_member, auth_headers):
    """兼容性核心断言: scope=personal == scope=team == scope=all (同一棵树)."""
    personal = Folder(name='test_personal_2', owner_id=test_member.id, visibility='team', parent_id=None)
    team_f = Folder(name='test_team_default_2', owner_id=test_member.id, visibility='team',
                    parent_id=None, is_team_default=True)
    db.add_all([personal, team_f])
    await db.commit()
    await db.refresh(personal)
    await db.refresh(team_f)

    ids_by_scope = {}
    for scope in ('personal', 'team', 'all'):
        data = await _top_ids(client, auth_headers, scope=scope)
        assert data['scope'] == scope, "scope 回显不变"
        ids_by_scope[scope] = {f['id'] for f in data['tree']}

    assert ids_by_scope['personal'] == ids_by_scope['team'] == ids_by_scope['all'], \
        "单一团队空间: 三种 scope 应返回同一棵全量树"
    for scope, ids in ids_by_scope.items():
        assert personal.id in ids and team_f.id in ids, f"{scope} scope 应包含两类 folder"


@pytest.mark.asyncio
async def test_scope_invalid_returns_422(client, auth_headers):
    """scope=invalid → 422 ValidationException (参数继续接受, 非法值仍拒)."""
    resp = await client.get('/api/v1/folders/tree?scope=invalid_scope', headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_scope_team_includes_children(db, client, test_member, auth_headers):
    """子 folder 层级仍递归包含 (树形结构与 scope 无关)."""
    parent = Folder(name='test_team_parent', owner_id=test_member.id, visibility='team',
                    parent_id=None, is_team_default=True)
    db.add(parent)
    await db.commit()
    await db.refresh(parent)

    child = Folder(name='test_team_child', owner_id=test_member.id, visibility='team',
                   parent_id=parent.id)
    db.add(child)
    await db.commit()
    await db.refresh(child)

    for scope in ('personal', 'team'):
        data = await _top_ids(client, auth_headers, scope=scope)
        parent_node = next((f for f in data['tree'] if f['id'] == parent.id), None)
        assert parent_node is not None, f"{scope} scope 应返回父 folder"
        child_ids = [c['id'] for c in parent_node['children']]
        assert child.id in child_ids, f"{scope} scope 应递归包含子 folder"


@pytest.mark.asyncio
async def test_response_includes_is_team_default_flag(db, client, test_member, auth_headers):
    """tree 节点必须含 is_team_default 字段 (响应形状兼容, 前端可能用)."""
    team_f = Folder(name='test_team_default_flag', owner_id=test_member.id, visibility='team',
                    parent_id=None, is_team_default=True)
    db.add(team_f)
    await db.commit()
    await db.refresh(team_f)

    data = await _top_ids(client, auth_headers, scope='all')
    team_node = next(f for f in data['tree'] if f['id'] == team_f.id)
    assert 'is_team_default' in team_node, "tree 节点必须含 is_team_default 字段"
    assert team_node['is_team_default'] is True


@pytest.mark.asyncio
async def test_private_folder_visible_to_all(db, client, test_member, auth_headers):
    """2026-09: 历史脏数据 private 非 owner folder 也出现在树里 (无越权过滤)."""
    import uuid as _uuid
    from app.models.member import Member
    # 另一个成员 (owner != test_member) 的 private folder — 脏数据场景
    other = Member(
        username=f"tree_priv_other_{_uuid.uuid4().hex[:8]}", name="Tree Private Other",
        password_hash="hash", role="member", grade="测试", is_active=True,
        wechat_id=f"__TEST_BACKFILL_treepriv_{_uuid.uuid4().hex[:8]}__",
    )
    db.add(other)
    await db.commit()
    await db.refresh(other)

    priv = Folder(name='test_legacy_private', owner_id=other.id,
                  visibility='private', parent_id=None)
    db.add(priv)
    await db.commit()
    await db.refresh(priv)

    data = await _top_ids(client, auth_headers, scope='all')
    tree_ids = {f['id'] for f in data['tree']}
    assert priv.id in tree_ids, "单一团队空间: 树无 private/owner 过滤"


"""
tests/test_drive_folders_tree_scope.py — GET /folders/tree scope 参数单测

v2.25 (2026-07-11): scope 参数加 3 模式:
- personal: 排除 is_team_default=true folder
- team:     仅 is_team_default=true folder (含子层级)
- all:      不过滤 (兼容老调用)

关键场景:
1. 无 scope 参数 → 默认 personal (排除 is_team_default=true)
2. scope=team → 仅返回 is_team_default=true folder
3. scope=all → 返回所有 (含 personal + team)
4. scope=invalid → 422 ValidationException
5. 子 folder 继承父 folder 的 scope 过滤 (父 is_team_default → 子默认在 team 视图)
6. 越权: private folder 仍按 visibility != 'private' OR owner_id == current_user.id 过滤
"""
import pytest

from app.models.folder import Folder


@pytest.mark.asyncio
async def test_default_scope_is_personal(db, client, test_member, auth_headers):
    """不传 scope 参数 → 默认 personal, 排除 is_team_default=true folder."""
    # 创建 personal folder (默认 is_team_default=false)
    personal = Folder(name='test_personal', owner_id=test_member.id, visibility='team', parent_id=None)
    # 创建 team default folder
    team_f = Folder(name='test_team_default', owner_id=test_member.id, visibility='team',
                    parent_id=None, is_team_default=True)
    db.add_all([personal, team_f])
    await db.commit()
    await db.refresh(personal)
    await db.refresh(team_f)

    resp = await client.get('/api/v1/folders/tree', headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data['scope'] == 'personal'
    tree_ids = [f['id'] for f in data['tree']]
    assert personal.id in tree_ids, "personal folder 应在 personal scope"
    assert team_f.id not in tree_ids, "team_default folder 应在 personal scope 被排除"


@pytest.mark.asyncio
async def test_scope_team_only_returns_team_folders(db, client, test_member, auth_headers):
    """scope=team → 仅返回 is_team_default=true folder."""
    personal = Folder(name='test_personal_2', owner_id=test_member.id, visibility='team', parent_id=None)
    team_f = Folder(name='test_team_default_2', owner_id=test_member.id, visibility='team',
                    parent_id=None, is_team_default=True)
    db.add_all([personal, team_f])
    await db.commit()
    await db.refresh(personal)
    await db.refresh(team_f)

    resp = await client.get('/api/v1/folders/tree?scope=team', headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data['scope'] == 'team'
    tree_ids = [f['id'] for f in data['tree']]
    assert team_f.id in tree_ids, "team_default folder 应在 team scope"
    assert personal.id not in tree_ids, "personal folder 应在 team scope 被排除"


@pytest.mark.asyncio
async def test_scope_all_returns_everything(db, client, test_member, auth_headers):
    """scope=all → 返回 personal + team 所有 folder."""
    personal = Folder(name='test_personal_3', owner_id=test_member.id, visibility='team', parent_id=None)
    team_f = Folder(name='test_team_default_3', owner_id=test_member.id, visibility='team',
                    parent_id=None, is_team_default=True)
    db.add_all([personal, team_f])
    await db.commit()
    await db.refresh(personal)
    await db.refresh(team_f)

    resp = await client.get('/api/v1/folders/tree?scope=all', headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data['scope'] == 'all'
    tree_ids = [f['id'] for f in data['tree']]
    assert personal.id in tree_ids and team_f.id in tree_ids, "all scope 应包含两类"


@pytest.mark.asyncio
async def test_scope_invalid_returns_422(client, auth_headers):
    """scope=invalid → 422 ValidationException."""
    resp = await client.get('/api/v1/folders/tree?scope=invalid_scope', headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_scope_team_includes_children(db, client, test_member, auth_headers):
    """scope=team 递归返回 is_team_default=true folder 的子 folder (含层级)."""
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

    resp = await client.get('/api/v1/folders/tree?scope=team', headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    parent_node = next((f for f in data['tree'] if f['id'] == parent.id), None)
    assert parent_node is not None, "team_parent 应在 team scope 顶层"
    child_ids = [c['id'] for c in parent_node['children']]
    assert child.id in child_ids, "team scope 应递归包含子 folder"


@pytest.mark.asyncio
async def test_response_includes_is_team_default_flag(db, client, test_member, auth_headers):
    """tree 节点必须含 is_team_default 字段 (前端可能用)."""
    team_f = Folder(name='test_team_default_flag', owner_id=test_member.id, visibility='team',
                    parent_id=None, is_team_default=True)
    db.add(team_f)
    await db.commit()
    await db.refresh(team_f)

    resp = await client.get('/api/v1/folders/tree?scope=all', headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    team_node = next(f for f in data['tree'] if f['id'] == team_f.id)
    assert 'is_team_default' in team_node, "tree 节点必须含 is_team_default 字段"
    assert team_node['is_team_default'] is True
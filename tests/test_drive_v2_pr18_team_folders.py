"""tests/test_drive_v2_pr18_team_folders.py — Drive v2 PR18 团队共享盘 e2e 测试 (2026-07-24, W68 第 14 批 B-2)

4 核心场景:
1. 创建 team folder + 3 成员 (POST /api/v1/team-folders)
2. 加成员 → audit_log 写 write action + share action (POST /api/v1/team-folders/{id}/members)
3. 删成员 → audit_log 写 delete action (DELETE /api/v1/team-folders/{id}/members/{user_id})
4. 查审计 → 4 维度过滤 (GET /api/v1/team-folders/{id}/audit)

依赖:
- tests/conftest.py: db / client / test_member / admin_member / auth_headers fixtures
- alembic 079 已 upgrade head (本测试跳过 setup 时会 SKIP)

W68 第 14 批 B-2 纪律:
- 0 production code 改动铁律 (PR18 纯新功能模块, 不动老路径)
- alembic 079 串单链 (接 078, 留 080 后续 PR)
- 4 维审计铁律 (read/write/delete/share + restore, CLAUDE.md 2026-07-24 v78 audit_log 模式)
- flag_modified 防 PG ARRAY mutate 静默不持久 (CLAUDE.md 2026-06-28 教训)
"""
from __future__ import annotations

import pytest
import pytest_asyncio

from app.core.security import create_access_token, get_password_hash
from app.models.member import Member
from app.models.team_folder import TeamFolder, TeamFolderAuditLog


# ==========================================================================
# Fixtures: 4 个成员 (owner + 3 邀请成员)
# ==========================================================================


@pytest_asyncio.fixture
async def pr18_owner(db):
    """PR18 测试主 owner (test_member 自带 teardown, 这里直接 add 不依赖 fixture)"""
    member = Member(
        username="pr18_owner",
        name="PR18 Owner",
        password_hash=get_password_hash("test123456"),
        role="member",
        grade="研一",
        is_active=True,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@pytest_asyncio.fixture
async def pr18_member_2(db):
    """被邀请成员 2"""
    m = Member(
        username="pr18_member_2",
        name="PR18 Member 2",
        password_hash=get_password_hash("test123456"),
        role="member",
        is_active=True,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest_asyncio.fixture
async def pr18_member_3(db):
    """被邀请成员 3"""
    m = Member(
        username="pr18_member_3",
        name="PR18 Member 3",
        password_hash=get_password_hash("test123456"),
        role="member",
        is_active=True,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


@pytest_asyncio.fixture
async def pr18_member_4(db):
    """被邀请成员 4 (后续 add_member 场景用)"""
    m = Member(
        username="pr18_member_4",
        name="PR18 Member 4",
        password_hash=get_password_hash("test123456"),
        role="member",
        is_active=True,
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    return m


def _auth(member):
    """直接生成 JWT (绕开 client 中间件依赖)"""
    token = create_access_token(data={"sub": str(member.id)})
    return {"Authorization": f"Bearer {token}"}


# ==========================================================================
# 场景 1: 创建 team folder + 3 成员 (POST /api/v1/team-folders)
# 期望:
#   - 201 Created
#   - 响应含 id + name + owner_id + member_ids=[2,3,4] + visibility='team'
#   - DB 中 TeamFolderAuditLog 有 4 条: 1 write(folder) + 3 share(member)
# ==========================================================================


@pytest.mark.asyncio
async def test_create_team_folder_with_3_members_writes_4_audits(
    client, pr18_owner, pr18_member_2, pr18_member_3, pr18_member_4
):
    """场景 1: 创建 team folder 自动写 1 write + 3 share audit_logs (4 维)"""
    resp = await client.post(
        "/api/v1/team-folders",
        headers=_auth(pr18_owner),
        json={
            "name": "组会资料",
            "initial_member_ids": [pr18_member_2.id, pr18_member_3.id, pr18_member_4.id],
            "visibility": "team",
        },
    )
    assert resp.status_code == 201, f"创建 team folder 应 201, 实际 {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["name"] == "组会资料"
    assert body["owner_id"] == pr18_owner.id
    assert set(body["member_ids"]) == {pr18_member_2.id, pr18_member_3.id, pr18_member_4.id}
    assert body["visibility"] == "team"
    assert body["deleted_at"] is None

    # 验证 audit_log: 1 write (folder) + 3 share (member) = 4 条
    # 复用 db fixture 的 session (client 走 dependency_overrides get_db)
    from app.core.database import get_db

    audit_resp = await client.get(
        f"/api/v1/team-folders/{body['id']}/audit",
        headers=_auth(pr18_owner),
        params={"page_size": 50},
    )
    assert audit_resp.status_code == 200
    audit_body = audit_resp.json()
    assert audit_body["total"] == 4, f"期望 4 条 audit, 实际 {audit_body['total']}"

    actions_by_target = {(a["action"], a["target_type"]) for a in audit_body["items"]}
    assert ("write", "folder") in actions_by_target
    share_count = sum(1 for a in audit_body["items"] if a["action"] == "share" and a["target_type"] == "member")
    assert share_count == 3, f"期望 3 条 share audit, 实际 {share_count}"


# ==========================================================================
# 场景 2: 加成员 → audit_log 写 write action + share action
# 期望:
#   - POST 200 OK
#   - member_ids 新增 target_user_id
#   - audit_log 新增 write + share 两条 (新成员 add)
# ==========================================================================


@pytest.mark.asyncio
async def test_add_member_writes_write_and_share_audit(
    client, pr18_owner, pr18_member_2, pr18_member_3
):
    """场景 2: add_member 自动写 write + share 2 条 audit (4 维)"""
    # 先创建只邀请 member_2 的 team folder
    create_resp = await client.post(
        "/api/v1/team-folders",
        headers=_auth(pr18_owner),
        json={
            "name": "项目组",
            "initial_member_ids": [pr18_member_2.id],
            "visibility": "team",
        },
    )
    assert create_resp.status_code == 201
    team_folder_id = create_resp.json()["id"]

    # add member_3
    add_resp = await client.post(
        f"/api/v1/team-folders/{team_folder_id}/members",
        headers=_auth(pr18_owner),
        json={"target_user_id": pr18_member_3.id, "permission": "read"},
    )
    assert add_resp.status_code == 200, f"add member 应 200, 实际 {add_resp.status_code}: {add_resp.text}"
    body = add_resp.json()
    assert pr18_member_3.id in body["member_ids"], f"member_ids 应含 {pr18_member_3.id}"
    assert pr18_member_2.id in body["member_ids"], f"member_ids 应仍含原 member_2"

    # 验证 audit: 之前 2 (1 write folder + 1 share member_2) + 现在 2 (1 write member_3 + 1 share member_3) = 4
    audit_resp = await client.get(
        f"/api/v1/team-folders/{team_folder_id}/audit",
        headers=_auth(pr18_owner),
        params={"page_size": 50},
    )
    assert audit_resp.status_code == 200
    audit_body = audit_resp.json()
    assert audit_body["total"] == 4, f"期望 4 条 audit (write+share 两次), 实际 {audit_body['total']}"

    # 验证最近 2 条是 write + share 写给 member_3
    recent_two = audit_body["items"][:2]  # 按 created_at DESC 倒序
    actions = [(a["action"], a["target_type"], a["target_id"]) for a in recent_two]
    assert ("share", "member", f"member:{pr18_member_3.id}") in actions
    assert ("write", "member", f"member:{pr18_member_3.id}") in actions


# ==========================================================================
# 场景 3: 删成员 → audit_log 写 delete action
# 期望:
#   - DELETE 200 OK
#   - member_ids 中不再含 target_user_id
#   - audit_log 新增 1 条 delete action
# ==========================================================================


@pytest.mark.asyncio
async def test_remove_member_writes_delete_audit(
    client, pr18_owner, pr18_member_2, pr18_member_3
):
    """场景 3: remove_member 自动写 delete action (仅 1 条, 不写 share 反向)"""
    # 先创建邀请 member_2 + member_3
    create_resp = await client.post(
        "/api/v1/team-folders",
        headers=_auth(pr18_owner),
        json={
            "name": "删除测试",
            "initial_member_ids": [pr18_member_2.id, pr18_member_3.id],
            "visibility": "team",
        },
    )
    assert create_resp.status_code == 201
    team_folder_id = create_resp.json()["id"]

    # 移除 member_2
    del_resp = await client.delete(
        f"/api/v1/team-folders/{team_folder_id}/members/{pr18_member_2.id}",
        headers=_auth(pr18_owner),
    )
    assert del_resp.status_code == 200, f"remove member 应 200, 实际 {del_resp.status_code}: {del_resp.text}"
    body = del_resp.json()
    assert body["ok"] is True
    assert body["removed_user_id"] == pr18_member_2.id

    # 验证 audit: 之前 3 (write folder + share m2 + share m3) + 现在 1 (delete m2) = 4 条
    audit_resp = await client.get(
        f"/api/v1/team-folders/{team_folder_id}/audit",
        headers=_auth(pr18_owner),
        params={"page_size": 50},
    )
    assert audit_resp.status_code == 200
    audit_body = audit_resp.json()
    assert audit_body["total"] == 4

    # 最新一条应该是 delete + member:member_2
    latest = audit_body["items"][0]
    assert latest["action"] == "delete"
    assert latest["target_type"] == "member"
    assert latest["target_id"] == f"member:{pr18_member_2.id}"
    assert latest["extra"]["operation"] == "remove_member"


# ==========================================================================
# 场景 4: 查审计 → 4 维度过滤
# 过滤维度:
#   1. actor_id (who)  — 按操作者过滤
#   2. action (what)   — 按动作类型过滤
#   3. target_type (on_what) — 按对象类型过滤
#   4. created_at (when) — 通过分页 + since/until 间接表达
# 期望:
#   - actor_id=owner_id 过滤 → 只看到 owner 操作
#   - action=share 过滤 → 只看到 share 行
#   - target_type=member 过滤 → 只看到 member 相关行
#   - 分页 (page=1, page_size=2) → 只看前 2 条
# ==========================================================================


@pytest.mark.asyncio
async def test_list_audit_supports_4_dimension_filtering(
    client, pr18_owner, pr18_member_2, pr18_member_3, pr18_member_4
):
    """场景 4: list_audit 支持 4 维过滤 (actor + action + target_type + 分页)"""
    # 创建 + 邀请 2 个, 再加 1 个 — 共: 1 write folder + 2 share member + (write member + share member) ×1 = 5
    create_resp = await client.post(
        "/api/v1/team-folders",
        headers=_auth(pr18_owner),
        json={
            "name": "过滤测试",
            "initial_member_ids": [pr18_member_2.id, pr18_member_3.id],
        },
    )
    team_folder_id = create_resp.json()["id"]
    await client.post(
        f"/api/v1/team-folders/{team_folder_id}/members",
        headers=_auth(pr18_owner),
        json={"target_user_id": pr18_member_4.id},
    )

    # 总 5 条 audit
    full_resp = await client.get(
        f"/api/v1/team-folders/{team_folder_id}/audit",
        headers=_auth(pr18_owner),
        params={"page_size": 50},
    )
    assert full_resp.json()["total"] == 5

    # 维 1: actor_id=owner → 5 条 (全是 owner 操作)
    actor_resp = await client.get(
        f"/api/v1/team-folders/{team_folder_id}/audit",
        headers=_auth(pr18_owner),
        params={"actor_id": pr18_owner.id, "page_size": 50},
    )
    assert actor_resp.status_code == 200
    assert actor_resp.json()["total"] == 5
    assert all(a["actor_id"] == pr18_owner.id for a in actor_resp.json()["items"])

    # 维 2: action=share → 3 条 (2 initial + 1 add 的 share)
    share_resp = await client.get(
        f"/api/v1/team-folders/{team_folder_id}/audit",
        headers=_auth(pr18_owner),
        params={"action": "share", "page_size": 50},
    )
    assert share_resp.status_code == 200
    assert share_resp.json()["total"] == 3
    assert all(a["action"] == "share" for a in share_resp.json()["items"])

    # 维 3: target_type=member → 4 条 (3 share member + 1 write member member_4)
    member_resp = await client.get(
        f"/api/v1/team-folders/{team_folder_id}/audit",
        headers=_auth(pr18_owner),
        params={"target_type": "member", "page_size": 50},
    )
    assert member_resp.status_code == 200
    assert member_resp.json()["total"] == 4
    assert all(a["target_type"] == "member" for a in member_resp.json()["items"])

    # 维 4 (分页): page=1 + page_size=2 → 总 5 条但 items 长度 = 2
    page_resp = await client.get(
        f"/api/v1/team-folders/{team_folder_id}/audit",
        headers=_auth(pr18_owner),
        params={"page": 1, "page_size": 2},
    )
    assert page_resp.status_code == 200
    page_body = page_resp.json()
    assert page_body["total"] == 5  # total 反映全部, 不分页
    assert len(page_body["items"]) == 2  # 但 items 限制 2 条

    # 组合过滤: action=write + target_type=folder → 仅 1 条 (创建时)
    combo_resp = await client.get(
        f"/api/v1/team-folders/{team_folder_id}/audit",
        headers=_auth(pr18_owner),
        params={"action": "write", "target_type": "folder", "page_size": 50},
    )
    assert combo_resp.status_code == 200
    combo_body = combo_resp.json()
    assert combo_body["total"] == 1
    assert combo_body["items"][0]["target_id"] == str(team_folder_id)
    assert combo_body["items"][0]["extra"]["operation"] == "create"

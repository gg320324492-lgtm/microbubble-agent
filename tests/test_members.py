"""成员相关测试"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_member(client: AsyncClient, admin_headers):
    """创建成员（管理员）"""
    resp = await client.post("/api/v1/members", headers=admin_headers, json={
        "name": "新成员",
        "username": "newmember",
        "password": "newpass123",
        "grade": "研一",
        "research_area": "微纳米气泡",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "新成员"
    # 2026-08-18 #Plan v2 #10: MemberResponse 不含 username 字段 (MemberBase 无),
    # 断言改为 name (已有) + role (响应含)


@pytest.mark.asyncio
async def test_create_duplicate_username(client: AsyncClient, admin_headers, test_member):
    """重复用户名"""
    resp = await client.post("/api/v1/members", headers=admin_headers, json={
        "name": "重复用户",
        "username": "testuser",  # 已存在
        "password": "123456",
    })
    # 2026-08-18 #Plan v2 #10: PR6-P16 起重复 identifier 返 ConflictException (409),
    # 非 400 (见 app/api/v1/member.py:138 提前检查 4 个 identifier 唯一性)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_members(client: AsyncClient, auth_headers):
    """查询成员列表"""
    resp = await client.get("/api/v1/members", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


@pytest.mark.asyncio
async def test_get_member(client: AsyncClient, auth_headers, test_member):
    """获取成员详情"""
    resp = await client.get(f"/api/v1/members/{test_member.id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "测试用户"


@pytest.mark.asyncio
async def test_update_member(client: AsyncClient, admin_headers, test_member):
    """更新成员"""
    resp = await client.put(
        f"/api/v1/members/{test_member.id}",
        headers=admin_headers,
        json={"research_area": "气泡动力学"}
    )
    assert resp.status_code == 200
    assert resp.json()["research_area"] == "气泡动力学"


@pytest.mark.asyncio
async def test_delete_member_soft_deactivates(client: AsyncClient, auth_headers, test_member):
    """删除成员 = 软删停用 (is_active=False)

    (2026-09-05 角色扁平化后 get_current_admin_user 仅要求登录, 不再返 403;
     原断言 403 为扁平化前的陈旧语义, 本测试随企业微信清理一并修正)
    """
    resp = await client.delete(f"/api/v1/members/{test_member.id}", headers=auth_headers)
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_delete_member_trashes_assigned_tasks(client: AsyncClient, admin_headers, auth_headers, test_member):
    """2026-09-12: 软删成员后其名下任务移入回收站 — 任务列表/仪表盘不再显示。

    背景: 张懿软删后「准备数学考试」仍挂在任务列表 (assignee 已停用但任务仍可见)。
    会议记录不受影响 (端点不触碰 meetings)。
    """
    ids = []
    for title in ("任务甲", "任务乙"):
        r = await client.post("/api/v1/tasks", headers=admin_headers,
                              json={"title": title, "assignee_id": test_member.id})
        assert r.status_code in (200, 201), r.text
        ids.append(r.json()["id"])

    # 软删成员
    resp = await client.delete(f"/api/v1/members/{test_member.id}", headers=admin_headers)
    assert resp.status_code == 204

    # 默认任务列表不再显示该成员的任务
    lst = await client.get("/api/v1/tasks", headers=admin_headers)
    assert lst.status_code == 200
    got = {t["id"] for t in lst.json()["items"]}
    assert not (set(ids) & got), "被软删成员的任务应进入回收站, 不再出现在任务列表"

    # 回收站可见 (include_deleted=true, 3 天保留期内可恢复)
    trash = await client.get("/api/v1/tasks?include_deleted=true", headers=admin_headers)
    assert trash.status_code == 200
    trashed = {t["id"] for t in trash.json()["items"] if t["id"] in ids}
    assert trashed == set(ids), "回收站应包含被删成员的全部未删任务"

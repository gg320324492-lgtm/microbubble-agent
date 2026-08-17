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
        # 2026-08-18 #Plan v2 #9: MemberCreate.wechat_id required (PR6-P17, DB NOT NULL)
        "wechat_id": "newmember_wechat",
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
        # 2026-08-18 #Plan v2 #9: MemberCreate.wechat_id required (PR6-P17)
        "wechat_id": "dup_wechat",
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
async def test_delete_member_requires_admin(client: AsyncClient, auth_headers, test_member):
    """删除成员需要管理员权限"""
    resp = await client.delete(f"/api/v1/members/{test_member.id}", headers=auth_headers)
    assert resp.status_code == 403

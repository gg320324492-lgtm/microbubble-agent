"""认证相关测试"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_member):
    """登录成功"""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "test123456"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["name"] == "测试用户"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_member):
    """密码错误"""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "wrongpassword"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """用户不存在"""
    resp = await client.post("/api/v1/auth/login", json={
        "username": "nobody",
        "password": "123456"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user(client: AsyncClient, auth_headers, test_member):
    """获取当前用户信息"""
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["name"] == "测试用户"


@pytest.mark.asyncio
async def test_unauthorized_access(client: AsyncClient):
    """未认证访问"""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 403  # HTTPBearer raises 403


@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient, test_member):
    """刷新令牌"""
    login_resp = await client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "test123456"
    })
    refresh_token = login_resp.json()["refresh_token"]

    resp = await client.post("/api/v1/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_change_password(client: AsyncClient, auth_headers, test_member):
    """修改密码"""
    resp = await client.post("/api/v1/auth/change-password", headers=auth_headers, json={
        "old_password": "test123456",
        "new_password": "newpass123"
    })
    assert resp.status_code == 200

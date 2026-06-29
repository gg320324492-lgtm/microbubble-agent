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
    # v31.2.6: 清残留 ZSET (切到 Redis 后跨 pytest run 残留), 防跨测试污染
    from app.core.redis import get_redis
    await (await get_redis()).delete("rl:login:testclient")

    resp = await client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "wrongpassword"
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limit_returns_retry_after(client: AsyncClient, test_member):
    """v31.2.6: 5 次错误密码后第 6 次返回 429 + Retry-After 头.

    ASGI 测试 client.host 是 "testclient", Redis key = "rl:login:testclient".
    """
    from app.core.redis import get_redis
    r = await get_redis()
    await r.delete("rl:login:testclient")  # 清残留

    # 前 5 次: 全 401 (每次记录 +1, ZSET 累计 1..5)
    for _ in range(5):
        resp = await client.post("/api/v1/auth/login", json={
            "username": "testuser",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    # 第 6 次: 触发 429 + Retry-After: 300
    resp = await client.post("/api/v1/auth/login", json={
        "username": "testuser",
        "password": "wrongpassword",
    })
    assert resp.status_code == 429, f"Expected 429, got {resp.status_code}"
    assert resp.headers.get("Retry-After") == "300", \
        f"Expected Retry-After: 300, got {resp.headers.get('Retry-After')!r}"

    # 清理 (让后续测试不受影响)
    await r.delete("rl:login:testclient")


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

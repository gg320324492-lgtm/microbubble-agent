"""用户自助重置密码 (恢复码) 测试 — 2026-09-02

覆盖:
- recovery_code_service 单元: 生成格式 / 归一化 / hash-verify 往返
- API e2e: 登录 → 生成恢复码 → 自助重置 → 旧密码失效/新密码可登录 → 恢复码单次有效
- 防枚举: 用户名不存在与码错误同一文案
- 限流: 6 次错误尝试 → 429 + Retry-After: 900
- Pydantic: 新密码 <6 位 → 422
"""
import pytest
from httpx import AsyncClient

from app.services import recovery_code_service as rcs


# ==================== 单元 ====================

def test_generate_format():
    code = rcs.generate_recovery_code()
    parts = code.split("-")
    assert len(parts) == 3
    assert all(len(p) == 4 for p in parts)
    assert all(ch in rcs._CODE_ALPHABET for ch in code.replace("-", ""))


def test_normalize_and_verify_roundtrip():
    code = rcs.generate_recovery_code()
    stored = rcs.hash_recovery_code(code)
    # 大小写 / 横线 / 空格不敏感
    assert rcs.verify_recovery_code(code.upper(), stored)
    assert rcs.verify_recovery_code(code.replace("-", " "), stored)
    assert rcs.verify_recovery_code(code, stored)
    assert not rcs.verify_recovery_code("aaaa-bbbb-cccc", stored)
    assert not rcs.verify_recovery_code(code, None)
    # 明文永不等于哈希
    assert code not in stored


# ==================== API e2e ====================

async def _login_token(client: AsyncClient) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "test123456"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_generate_and_self_reset_full_flow(client: AsyncClient, test_member):
    """生成 → 重置 → 旧密码失效 / 新密码可登录 / 码单次有效"""
    token = await _login_token(client)
    auth = {"Authorization": f"Bearer {token}"}

    # 生成恢复码
    resp = await client.post("/api/v1/auth/recovery-code", headers=auth)
    assert resp.status_code == 200
    code = resp.json()["code"]
    assert code.count("-") == 2

    # 状态查询: 已生成
    resp = await client.get("/api/v1/auth/recovery-code/status", headers=auth)
    assert resp.status_code == 200
    assert resp.json()["has_code"] is True

    # 用旧密码 + 恢复码自助重置
    resp = await client.post(
        "/api/v1/auth/reset-password-self",
        json={
            "username": "testuser",
            "recovery_code": code.lower(),
            "new_password": "newpass456",
        },
    )
    assert resp.status_code == 200, resp.text

    # 旧密码登录 → 401
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "test123456"},
    )
    assert resp.status_code == 401

    # 新密码登录 → 200
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "newpass456"},
    )
    assert resp.status_code == 200

    # 同一恢复码第二次使用 → 401 (单次有效)
    resp = await client.post(
        "/api/v1/auth/reset-password-self",
        json={
            "username": "testuser",
            "recovery_code": code,
            "new_password": "another789",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_reset_anti_enumeration(client: AsyncClient, test_member):
    """用户名不存在 / 码错误 → 同一 401 文案 (防枚举)"""
    r1 = await client.post(
        "/api/v1/auth/reset-password-self",
        json={
            "username": "no_such_user_xyz",
            "recovery_code": "abcd-efgh-jkmn",
            "new_password": "whatever1",
        },
    )
    r2 = await client.post(
        "/api/v1/auth/reset-password-self",
        json={
            "username": "testuser",
            "recovery_code": "zzzz-zzzz-zzzz",
            "new_password": "whatever1",
        },
    )
    assert r1.status_code == r2.status_code == 401
    assert "用户名或恢复码错误" in str(r1.json())
    assert "用户名或恢复码错误" in str(r2.json())


@pytest.mark.asyncio
async def test_reset_rate_limit_429(client: AsyncClient):
    """6 次错误尝试 → 429 + Retry-After: 900 (pwreset_limiter 5/15min)"""
    from app.core.redis import get_redis

    xff = "203.0.113.77"  # RFC 5737 TEST-NET-3
    username = "ratelimit_probe_user"
    key = f"rl:pwreset:{xff}:{username}"
    r = await get_redis()
    await r.delete(key)  # 清跨 run 残留

    headers = {"X-Forwarded-For": xff}
    try:
        for _ in range(5):
            resp = await client.post(
                "/api/v1/auth/reset-password-self",
                json={
                    "username": username,
                    "recovery_code": "aaaa-bbbb-cccc",
                    "new_password": "whatever1",
                },
                headers=headers,
            )
            assert resp.status_code == 401

        resp = await client.post(
            "/api/v1/auth/reset-password-self",
            json={
                "username": username,
                "recovery_code": "aaaa-bbbb-cccc",
                "new_password": "whatever1",
            },
            headers=headers,
        )
        assert resp.status_code == 429, f"Expected 429, got {resp.status_code}"
        assert resp.headers.get("Retry-After") == "900"
    finally:
        await r.delete(key)


@pytest.mark.asyncio
async def test_reset_short_password_422(client: AsyncClient):
    """新密码 <6 位 → Pydantic 校验 422 (服务端兜底, 不止前端)"""
    resp = await client.post(
        "/api/v1/auth/reset-password-self",
        json={
            "username": "testuser",
            "recovery_code": "abcd-efgh-jkmn",
            "new_password": "abc",
        },
    )
    assert resp.status_code == 422

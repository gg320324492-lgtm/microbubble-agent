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
    # 用 X-Forwarded-For 隔离测试 IP, 避免污染其他测试
    from app.core.redis import get_redis
    test_xff = "203.0.113.1"
    await (await get_redis()).delete(f"rl:login:{test_xff}")

    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "wrongpassword"},
        headers={"X-Forwarded-For": test_xff},
    )
    assert resp.status_code == 401
    # 清理
    await (await get_redis()).delete(f"rl:login:{test_xff}")


@pytest.mark.asyncio
async def test_login_rate_limit_returns_retry_after(client: AsyncClient):
    """v31.2.6: 5 次错误密码后第 6 次返回 429 + Retry-After 头.

    用 X-Forwarded-For 固定 IP → Redis key 变 rl:login:203.0.113.66 (确定性),
    不依赖 request.client.host 在不同 pytest-asyncio 版本下的行为差异.

    不依赖 test_member fixture (避免 conftest.py 中测试隔离 pre-existing bug,
    即 fixture 不清理导致多次创建同名 Member). 错误密码永远 401, 与 user 是否存在无关.
    """
    from app.core.redis import get_redis
    test_xff = "203.0.113.66"  # RFC 5737 TEST-NET-3 (文档保留, 不会被真实用户用)
    rkey = f"rl:login:{test_xff}"
    r = await get_redis()
    await r.delete(rkey)  # 清残留 (跨测试 / 跨 run 都不会污染)

    headers = {"X-Forwarded-For": test_xff}
    # 前 5 次: 全 401 (每次记录 +1, ZSET 累计 1..5)
    for _ in range(5):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"username": "testuser", "password": "wrongpassword"},
            headers=headers,
        )
        assert resp.status_code == 401

    # 第 6 次: 触发 429 + Retry-After: 300
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "testuser", "password": "wrongpassword"},
        headers=headers,
    )
    assert resp.status_code == 429, f"Expected 429, got {resp.status_code}"
    assert resp.headers.get("Retry-After") == "300", \
        f"Expected Retry-After: 300, got {resp.headers.get('Retry-After')!r}"

    # 清理 (让后续测试不受影响)
    await r.delete(rkey)


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
    # FastAPI 0.125+ HTTPBearer(auto_error=True) 默认 raise HTTPException(401)
    # v0.0.1 修复 (2026-06-30): 老代码断言 403 (旧版 FastAPI < 0.46 行为),
    # 实测 curl localhost:8000/api/v1/auth/me 无 token 返 401 + WWW-Authenticate: Bearer.
    assert resp.status_code == 401  # HTTPBearer raises 401 with WWW-Authenticate: Bearer header


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


@pytest.mark.asyncio
async def test_update_profile_research_area(client: AsyncClient, auth_headers, test_member):
    """2026-09-12: PUT /auth/profile 必须持久化 research_area (研究方向下拉选项目)。

    根因回归: ProfileUpdateRequest 原本没有 research_area 字段, 前端存了也白存。
    """
    resp = await client.put("/api/v1/auth/profile", headers=auth_headers,
                            json={"research_area": "黑臭水体无药剂低能耗治理"})
    assert resp.status_code == 200
    assert resp.json()["research_area"] == "黑臭水体无药剂低能耗治理"
    # 持久化: 再拉一次 /auth/me 仍是新值
    me = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert me.json()["research_area"] == "黑臭水体无药剂低能耗治理"


@pytest.mark.asyncio
async def test_update_profile_research_area_clear(client: AsyncClient, auth_headers, test_member):
    """research_area 支持清空: 传空字符串 → 服务端清空字段"""
    resp = await client.put("/api/v1/auth/profile", headers=auth_headers,
                            json={"research_area": "水处理"})
    assert resp.status_code == 200
    resp = await client.put("/api/v1/auth/profile", headers=auth_headers,
                            json={"research_area": ""})
    assert resp.status_code == 200
    assert resp.json()["research_area"] == ""


# ==========================================================================
# L-14 P4 (2026-10-09): jose 加密层直测 —— 补 alg confusion / 篡改 / 过期
#
# 为什么是**增强**而非修复: 本文件原有 8 个用例全在 HTTP 层 (登录/刷新/鉴权/限流),
# jose 的 encode/decode 只被**间接**覆盖 (经 /auth/login 返回的 token)。
# 2026-10-09 python-jose 3.3.0 → 3.4.0 升级动过认证核心, 却没有任何一条测试
# 直接钉住"伪造/篡改的 token 会被拒绝"这个安全属性 —— 升级若悄悄放宽了校验,
# 现有 8 条 HTTP 用例**照样全绿**。本节把该属性显式钉死。
#
# 本项目是 HS256 **对称**签名 (security.py: ALGORITHM = "HS256", 单一 SECRET_KEY),
# 所以教科书里那条 RS256→HS256 的算法混淆不适用; 真正该防的是:
#   ① alg:none 无签名伪造   ② 载荷篡改(改 sub 提权)   ③ 换密钥重签
#   ④ 过期令牌             ⑤ access/refresh 类型混用
# ==========================================================================
import base64
import json
from datetime import timedelta

from fastapi import HTTPException
from jose import jwt

from app.core.security import (
    SECRET_KEY,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.base import utcnow


def _b64url(raw: bytes) -> str:
    """JWT 用的 base64url 无填充编码"""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unsigned_none_alg_token(payload: dict) -> str:
    """手工拼一个 alg=none 的**无签名** token (经典 JWT 绕过手法)"""
    header = _b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    body = _b64url(json.dumps(payload).encode())
    return f"{header}.{body}."  # 第三段(签名)为空


# ---------- 正常往返 (基线: 证明测试本身没把好路径写坏) ----------

def test_access_token_roundtrip():
    """合法 access token 能解出 sub / type=access"""
    token = create_access_token({"sub": "42"})
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_refresh_token_roundtrip():
    """合法 refresh token 解出 type=refresh"""
    token = create_refresh_token({"sub": "42"})
    assert decode_token(token)["type"] == "refresh"


# ---------- ① alg:none 无签名伪造 ----------

def test_alg_none_forged_token_rejected():
    """alg=none 且签名为空 → 必须 401。

    没有这条, 攻击者随便拼一个 header 就能拿到任意 sub 的合法身份。
    """
    forged = _unsigned_none_alg_token({
        "sub": "1",
        "type": "access",
        "exp": int((utcnow() + timedelta(hours=1)).timestamp()),
    })
    with pytest.raises(HTTPException) as exc:
        decode_token(forged)
    assert exc.value.status_code == 401


# ---------- ② 载荷篡改 (改 sub 提权, 签名保持原样) ----------

def test_tampered_payload_rejected():
    """改动载荷但沿用原签名 → 必须 401。

    这是最贴近真实的攻击: 拿到自己的合法 token, 把 sub 改成别人的 id。
    """
    token = create_access_token({"sub": "42"})
    header, _payload_b64, signature = token.split(".")

    tampered_payload = {
        "sub": "1",              # 试图冒充别的用户
        "type": "access",
        "exp": int((utcnow() + timedelta(hours=1)).timestamp()),
    }
    tampered = ".".join([header, _b64url(json.dumps(tampered_payload).encode()), signature])

    with pytest.raises(HTTPException) as exc:
        decode_token(tampered)
    assert exc.value.status_code == 401


# ---------- ③ 攻击者用自己的密钥重签 ----------

def test_token_signed_with_attacker_key_rejected():
    """用攻击者密钥签的 token (payload 完全合法) → 必须 401。

    载荷看着再"正"也没用: 签名对不上就一律拒。
    """
    forged = jwt.encode(
        {
            "sub": "1",
            "type": "access",
            "exp": int((utcnow() + timedelta(hours=1)).timestamp()),
        },
        "attacker-controlled-secret",
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        decode_token(forged)
    assert exc.value.status_code == 401


def test_garbage_token_rejected():
    """完全不是 JWT 的字符串 → 401 (不得抛未捕获异常)"""
    with pytest.raises(HTTPException) as exc:
        decode_token("not-a-jwt-at-all")
    assert exc.value.status_code == 401


# ---------- ④ 过期 ----------

def test_expired_token_rejected():
    """已过期 access token → 401"""
    expired = create_access_token({"sub": "42"}, expires_delta=timedelta(seconds=-60))
    with pytest.raises(HTTPException) as exc:
        decode_token(expired)
    assert exc.value.status_code == 401


# ---------- ⑤ access / refresh 类型混用 ----------

def test_decode_token_does_not_enforce_type_by_itself():
    """**如实记录当前行为**: decode_token() 只验签不验 type。

    refresh token 在这一层能解开 —— 因为 type 门禁刻意放在 get_current_user
    (security.py: `payload.get("type") != "access"`) 而不是解码层。
    本用例把该分层钉住: 免得日后有人以为"解码层已经拦了"而撤掉 get_current_user 的检查。
    """
    assert decode_token(create_refresh_token({"sub": "42"}))["type"] == "refresh"


@pytest.mark.asyncio
async def test_refresh_token_rejected_as_bearer(client: AsyncClient, test_member):
    """**真正的安全属性**: refresh token 当 access token 用 → 401 无效的令牌类型。

    两者同为 HS256 + 同一 SECRET_KEY, 只差 type claim, 所以这层检查一旦失守,
    长期有效(REFRESH_TOKEN_EXPIRE_DAYS)的 refresh token 就等价于长期 access token。
    """
    refresh = create_refresh_token({"sub": str(test_member.id)})
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh}"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_forged_none_alg_token_rejected_at_http_layer(client: AsyncClient, test_member):
    """alg=none 伪造令牌打到真实端点 → 401 (端到端确认不是只有单测在拦)"""
    forged = _unsigned_none_alg_token({
        "sub": str(test_member.id),
        "type": "access",
        "exp": int((utcnow() + timedelta(hours=1)).timestamp()),
    })
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_without_sub_rejected(client: AsyncClient, test_member):
    """缺 sub 的合法签名 token → 401 (签名有效也不放行)"""
    token = create_access_token({"type": "access"})  # 不给 sub
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 401

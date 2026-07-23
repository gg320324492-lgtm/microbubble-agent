"""tests/test_drive_v2_pr9_rate_limit.py — Drive v2 PR9 评论 7 端点 rate-limit tier 验证 (2026-07-24)

锚点范式第 56 守恒 — W68 第 4 批 (Drive 评论 rate-limit 接入)

7 端点 × tier 矩阵 (期望):
  POST   /api/v1/drive/comments                     → drive_upload (50/min)
  GET    /api/v1/drive/comments                     → drive_list  (300/min)
  GET    /api/v1/drive/comments/{id}                → drive_list  (300/min)
  PATCH  /api/v1/drive/comments/{id}                → drive_upload (50/min)
  DELETE /api/v1/drive/comments/{id}                → drive_upload (50/min)
  POST   /api/v1/drive/comments/{id}/resolve        → drive_upload (50/min)
  POST   /api/v1/drive/comments/{id}/unresolve      → drive_upload (50/min)

rate_limit.py:285 path match `path.startswith("/api/v1/drive/")` 自动覆盖,
drive_comments router prefix="/drive/comments" + main.py mounted at /api/v1
= 全路径 /api/v1/drive/comments/* → 7 端点全命中 drive_upload / drive_list.

无 PostgreSQL / Redis 依赖 (SKIP_DB_SETUP=1 兼容):
- 复用 test_rate_limit_integration.py 的 InMemoryZSetRedis mock
- 复用 rate_limit_middleware 直接挂载到 tiny FastAPI app
- 不依赖 DB / Drive 模型 / service 层 (只验证 tier 判定 + 响应头 + 429 行为)
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core import rate_limit as rate_limit_module
from app.core.rate_limit import (
    AsyncRedisRateLimiter,
    _get_rate_limit_type,
    _rate_limiters,
    rate_limit_middleware,
)
from app.core.security import create_access_token


# ────────────────────── Redis ZSET mock (复用 test_rate_limit_integration.py) ─────────

@dataclass
class _ZSet:
    members: dict[str, float]


class InMemoryZSetRedis:
    """与 test_rate_limit_integration.py 同一份契约, 满足 limiter 的 ZSET 调用."""

    def __init__(self) -> None:
        self.zsets: dict[str, _ZSet] = defaultdict(lambda: _ZSet({}))
        self.expirations: dict[str, int] = {}

    async def zremrangebyscore(self, key: str, minimum: float, maximum: float) -> int:
        members = self.zsets[key].members
        expired = [m for m, s in members.items() if minimum <= s <= maximum]
        for m in expired:
            del members[m]
        return len(expired)

    async def zcard(self, key: str) -> int:
        return len(self.zsets[key].members)

    async def zadd(self, key: str, mapping: dict[str, float]) -> int:
        before = len(self.zsets[key].members)
        self.zsets[key].members.update(mapping)
        return len(self.zsets[key].members) - before

    async def expire(self, key: str, ttl: int) -> bool:
        self.expirations[key] = ttl
        return True


@pytest.fixture
def redis(monkeypatch: pytest.MonkeyPatch) -> InMemoryZSetRedis:
    fake = InMemoryZSetRedis()

    async def get_fake_redis() -> InMemoryZSetRedis:
        return fake

    monkeypatch.setattr("app.core.redis.get_redis", get_fake_redis)
    return fake


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> dict[str, float]:
    current = {"now": 1_700_000_000.0}
    monkeypatch.setattr(rate_limit_module.time, "time", lambda: current["now"])
    return current


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    """挂载 production rate_limit_middleware + 7 个 drive_comments 路由 (与 API 形态一致)."""
    test_app = FastAPI()
    test_app.middleware("http")(rate_limit_middleware)

    # 与 app/api/v1/drive_comments.py 完全对齐: 7 端点 + 完全相同的 path/method
    # (前缀挂载由 main.py:89 (prefix="/api/v1") + drive_comments.py:34 (prefix="/drive/comments") 拼成)
    @test_app.post("/api/v1/drive/comments")
    async def create_comment(request: Request):
        return {
            "tier": _get_rate_limit_type(request),
            "endpoint": "POST /drive/comments",
        }

    @test_app.get("/api/v1/drive/comments")
    async def list_comments(request: Request):
        return {
            "tier": _get_rate_limit_type(request),
            "endpoint": "GET /drive/comments",
        }

    @test_app.get("/api/v1/drive/comments/{comment_id}")
    async def get_comment(request: Request, comment_id: int):
        return {
            "tier": _get_rate_limit_type(request),
            "endpoint": f"GET /drive/comments/{comment_id}",
        }

    @test_app.patch("/api/v1/drive/comments/{comment_id}")
    async def update_comment(request: Request, comment_id: int):
        return {
            "tier": _get_rate_limit_type(request),
            "endpoint": f"PATCH /drive/comments/{comment_id}",
        }

    @test_app.delete("/api/v1/drive/comments/{comment_id}")
    async def delete_comment(request: Request, comment_id: int):
        return {
            "tier": _get_rate_limit_type(request),
            "endpoint": f"DELETE /drive/comments/{comment_id}",
        }

    @test_app.post("/api/v1/drive/comments/{comment_id}/resolve")
    async def resolve_comment(request: Request, comment_id: int):
        return {
            "tier": _get_rate_limit_type(request),
            "endpoint": f"POST /drive/comments/{comment_id}/resolve",
        }

    @test_app.post("/api/v1/drive/comments/{comment_id}/unresolve")
    async def unresolve_comment(request: Request, comment_id: int):
        return {
            "tier": _get_rate_limit_type(request),
            "endpoint": f"POST /drive/comments/{comment_id}/unresolve",
        }

    async def no_audit(**_kwargs) -> None:
        return None

    monkeypatch.setattr("app.core.audit_middleware._audit_request", no_audit)
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _token(user_id: int) -> str:
    return create_access_token({"sub": str(user_id)})


# ────────────────────── 7 端点 × tier 矩阵 (drive_upload / drive_list) ────────────────


@pytest.mark.parametrize(
    ("method", "path", "expected_tier", "expected_endpoint"),
    [
        ("POST",   "/api/v1/drive/comments",                    "drive_upload", "POST /drive/comments"),
        ("GET",    "/api/v1/drive/comments",                    "drive_list",  "GET /drive/comments"),
        ("GET",    "/api/v1/drive/comments/42",                 "drive_list",  "GET /drive/comments/42"),
        ("PATCH",  "/api/v1/drive/comments/42",                 "drive_upload", "PATCH /drive/comments/42"),
        ("DELETE", "/api/v1/drive/comments/42",                 "drive_upload", "DELETE /drive/comments/42"),
        ("POST",   "/api/v1/drive/comments/42/resolve",         "drive_upload", "POST /drive/comments/42/resolve"),
        ("POST",   "/api/v1/drive/comments/42/unresolve",       "drive_upload", "POST /drive/comments/42/unresolve"),
    ],
)
def test_drive_comments_endpoint_maps_to_expected_tier(
    client, redis, clock, method, path, expected_tier, expected_endpoint
):
    """7 端点全部命中 rate_limit.py:285 path match → drive_upload / drive_list tier."""
    headers = {"X-Forwarded-For": "203.0.113.200"}
    response = client.request(method, path, headers=headers)

    assert response.status_code == 200, f"{method} {path} → {response.text}"
    body = response.json()
    assert body["tier"] == expected_tier, (
        f"{method} {path} 应 tier={expected_tier}, 实际 tier={body['tier']}"
    )
    assert body["endpoint"] == expected_endpoint

    # 响应头 X-RateLimit-Policy 必须与 tier 一致 (前端 tier-aware UX)
    assert response.headers["x-ratelimit-policy"] == expected_tier
    assert response.headers["x-ratelimit-limit"] == str(
        _rate_limiters[expected_tier].max_attempts
    )
    assert response.headers["x-ratelimit-remaining"] == str(
        _rate_limiters[expected_tier].max_attempts - 1
    )


# ────────────────────── 写操作超 30 次 (write tier 默认) / 50 次 (drive_upload 默认) ──


def test_drive_upload_tier_triggers_429_after_exceeding_50_per_minute(
    client, redis, clock
):
    """drive_upload tier 默认 50/min, 第 51 次写应 429 + Retry-After=60.

    注意: mock ZSET 用 dict 模拟, 同一 timestamp 多次 record 会覆盖 (真实 Redis ZSET
    按 score=now, value=str(now) 也只产生 1 个 entry). 必须每请求 +1ms 让每条 record
    落在独立 score, 模拟生产 50 个独立 timestamp.
    """
    headers = {
        "X-Forwarded-For": "203.0.113.210",
        "Authorization": f"Bearer {_token(99)}",
    }

    # 50 次 POST 全部 200 (达到 drive_upload 配额). clock 必须每请求 +1ms 让 ZSET
    # dict 模拟产生 50 个独立 member (real Redis ZSET 同样按 str(now) 去重, 实战必须
    # 每秒请求不能多于 1 才能完整跑通, 否则 50/min 配额永远用不尽).
    for i in range(50):
        clock["now"] += 0.001
        r = client.post(
            "/api/v1/drive/comments", headers=headers, json={"file_id": 1, "content": "x"}
        )
        assert r.status_code == 200, f"第 {i + 1} 次 POST 失败: {r.status_code} {r.text}"
        assert r.headers["x-ratelimit-policy"] == "drive_upload"
        assert r.headers["x-ratelimit-limit"] == "50"

    # 第 51 次 → 429
    clock["now"] += 0.001
    blocked = client.post(
        "/api/v1/drive/comments", headers=headers, json={"file_id": 1, "content": "x"}
    )
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "60"
    assert blocked.json() == {
        "error": {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "请求过于频繁，请 60 秒后重试",
        }
    }

    # Redis ZSET 应只有 50 条 (第 51 次被 check 阶段拦下, 未 record)
    zset_key = "rl:drive_upload:203.0.113.210:user:99"
    assert len(redis.zsets[zset_key].members) == 50


def test_drive_list_tier_allows_300_reads_without_429(client, redis, clock):
    """drive_list tier 默认 300/min, 30 次读全 200 (远未达限)."""
    headers = {"X-Forwarded-For": "203.0.113.220"}

    # 30 次 GET list (drive_list 配额 300, 远未达限). clock 必须每请求 +1ms 让
    # mock ZSET dict 模拟产生独立 member (否则 str(now) 去重 → 1 个 entry).
    for i in range(30):
        clock["now"] += 0.001
        r = client.get("/api/v1/drive/comments", headers=headers)
        assert r.status_code == 200, f"第 {i + 1} 次 GET 失败: {r.status_code} {r.text}"
        assert r.headers["x-ratelimit-policy"] == "drive_list"
        assert r.headers["x-ratelimit-limit"] == "300"
        assert int(r.headers["x-ratelimit-remaining"]) == 300 - (i + 1)


def test_drive_upload_and_drive_list_use_independent_quotas(
    client, redis, clock
):
    """同一 IP 写 50 用尽后, GET 不受影响 (drive_upload / drive_list 独立配额)."""
    headers = {"X-Forwarded-For": "203.0.113.230"}

    # 把 drive_upload 配额临时调到 2 加速测试
    original = _rate_limiters["drive_upload"]
    _rate_limiters["drive_upload"] = AsyncRedisRateLimiter(
        max_attempts=2, window_seconds=60
    )
    try:
        # 2 次 POST 用尽 drive_upload 配额
        assert client.post(
            "/api/v1/drive/comments", headers=headers, json={"file_id": 1, "content": "x"}
        ).status_code == 200
        clock["now"] += 0.001
        assert client.post(
            "/api/v1/drive/comments", headers=headers, json={"file_id": 1, "content": "x"}
        ).status_code == 200
        clock["now"] += 0.001
        # 第 3 次 → 429
        assert client.post(
            "/api/v1/drive/comments", headers=headers, json={"file_id": 1, "content": "x"}
        ).status_code == 429

        # 但 GET (drive_list 独立配额) 不受影响
        for _ in range(5):
            r = client.get("/api/v1/drive/comments", headers=headers)
            assert r.status_code == 200, "drive_list 不应被 drive_upload 配额影响"
            assert r.headers["x-ratelimit-policy"] == "drive_list"
    finally:
        _rate_limiters["drive_upload"] = original


def test_authenticated_user_uses_user_dimension_key_for_drive_tiers(
    client, redis, clock
):
    """登录用户用 {ip}:user:{uid} 而非 {ip}:anon, 多用户互不干扰."""
    headers_a = {
        "X-Forwarded-For": "203.0.113.240",
        "Authorization": f"Bearer {_token(101)}",
    }
    headers_b = {
        "X-Forwarded-For": "203.0.113.240",  # 同一 IP
        "Authorization": f"Bearer {_token(102)}",  # 不同用户
    }

    # 用尽 user_101 的 drive_upload 配额
    original = _rate_limiters["drive_upload"]
    _rate_limiters["drive_upload"] = AsyncRedisRateLimiter(
        max_attempts=2, window_seconds=60
    )
    try:
        assert client.post(
            "/api/v1/drive/comments", headers=headers_a, json={"file_id": 1, "content": "x"}
        ).status_code == 200
        clock["now"] += 0.001
        assert client.post(
            "/api/v1/drive/comments", headers=headers_a, json={"file_id": 1, "content": "x"}
        ).status_code == 200
        clock["now"] += 0.001
        assert client.post(
            "/api/v1/drive/comments", headers=headers_a, json={"file_id": 1, "content": "x"}
        ).status_code == 429

        # user_102 独立配额 (同一 IP, 不同 uid)
        assert client.post(
            "/api/v1/drive/comments", headers=headers_b, json={"file_id": 1, "content": "x"}
        ).status_code == 200
        clock["now"] += 0.001
        assert client.post(
            "/api/v1/drive/comments", headers=headers_b, json={"file_id": 1, "content": "x"}
        ).status_code == 200
    finally:
        _rate_limiters["drive_upload"] = original

    # Redis key 验证 (per-user 独立)
    assert "rl:drive_upload:203.0.113.240:user:101" in redis.zsets
    assert "rl:drive_upload:203.0.113.240:user:102" in redis.zsets


def test_all_drive_write_endpoints_share_drive_upload_quota(
    client, redis, clock
):
    """5 个写端点 (POST/PATCH/DELETE/POST resolve/POST unresolve) 共享 drive_upload 配额."""
    headers = {"X-Forwarded-For": "203.0.113.250"}

    # 把 drive_upload 配额临时调到 5 加速测试
    original = _rate_limiters["drive_upload"]
    _rate_limiters["drive_upload"] = AsyncRedisRateLimiter(
        max_attempts=5, window_seconds=60
    )
    try:
        # 5 个写操作覆盖全部 5 写端点
        responses = [
            ("POST",   "/api/v1/drive/comments",                {"file_id": 1, "content": "x"}),
            ("PATCH",  "/api/v1/drive/comments/1",             {"content": "y"}),
            ("DELETE", "/api/v1/drive/comments/1",             None),
            ("POST",   "/api/v1/drive/comments/1/resolve",     None),
            ("POST",   "/api/v1/drive/comments/1/unresolve",   None),
        ]
        for method, path, json_body in responses:
            r = client.request(
                method, path, headers=headers, json=json_body
            )
            assert r.status_code == 200, f"{method} {path} → {r.status_code} {r.text}"
            assert r.headers["x-ratelimit-policy"] == "drive_upload"
            clock["now"] += 0.001

        # 第 6 次写 → 429 (配额共享)
        blocked = client.post(
            "/api/v1/drive/comments", headers=headers, json={"file_id": 1, "content": "x"}
        )
        assert blocked.status_code == 429
        assert blocked.headers["retry-after"] == "60"
    finally:
        _rate_limiters["drive_upload"] = original


def test_drive_comments_default_tier_limits_match_production_config():
    """drive_upload=50/min, drive_list=300/min 是生产配置, 不能漂移."""
    # 这些数值与 app/core/rate_limit.py:185-186 一致
    assert _rate_limiters["drive_upload"].max_attempts == 50
    assert _rate_limiters["drive_upload"].window_seconds == 60
    assert _rate_limiters["drive_list"].max_attempts == 300
    assert _rate_limiters["drive_list"].window_seconds == 60
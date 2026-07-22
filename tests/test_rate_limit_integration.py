"""API rate-limit middleware integration specs without PostgreSQL or real Redis.

The suite mounts the production ``rate_limit_middleware`` on a tiny FastAPI app,
so requests exercise path-tier selection, JWT user-key extraction, Redis ZSET
sliding-window behavior, the 429 envelope, and response headers end to end.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import pytest
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.testclient import TestClient

from app.core import rate_limit as rate_limit_module
from app.core.rate_limit import (
    AsyncRedisRateLimiter,
    _get_client_key,
    _get_rate_limit_type,
    _rate_limiters,
    get_client_ip,
    login_limiter,
    rate_limit_middleware,
)
from app.core.security import create_access_token


@dataclass
class _ZSet:
    members: dict[str, float]


class InMemoryZSetRedis:
    """Small async Redis substitute implementing the limiter's ZSET contract."""

    def __init__(self) -> None:
        self.zsets: dict[str, _ZSet] = defaultdict(lambda: _ZSet({}))
        self.expirations: dict[str, int] = {}

    async def zremrangebyscore(self, key: str, minimum: float, maximum: float) -> int:
        members = self.zsets[key].members
        expired = [member for member, score in members.items() if minimum <= score <= maximum]
        for member in expired:
            del members[member]
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
    test_app = FastAPI()
    test_app.middleware("http")(rate_limit_middleware)

    @test_app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def endpoint(request: Request, path: str):
        return {
            "path": f"/{path}",
            "user_id": getattr(request.state, "user_id", None),
            "client_key": _get_client_key(request),
            "tier": _get_rate_limit_type(request),
        }

    # Auditing is best effort in production but would otherwise attempt PostgreSQL.
    async def no_audit(**_kwargs) -> None:
        return None

    monkeypatch.setattr("app.core.audit_middleware._audit_request", no_audit)
    return test_app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def login_client() -> TestClient:
    """Minimal HTTP endpoint preserving production login limiter ordering."""
    test_app = FastAPI()

    @test_app.post("/api/v1/auth/login")
    async def failed_login(request: Request):
        client_ip = get_client_ip(request)
        key = f"login:{client_ip}"
        await login_limiter.check(key)
        await login_limiter.record(key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad credentials")

    with TestClient(test_app) as test_client:
        yield test_client


def _limit(tier: str, max_attempts: int, window_seconds: int = 60):
    """Temporarily replace one production tier, then restore it exactly."""

    class _LimiterContext:
        def __enter__(self):
            self.original = _rate_limiters[tier]
            _rate_limiters[tier] = AsyncRedisRateLimiter(max_attempts, window_seconds)
            return _rate_limiters[tier]

        def __exit__(self, *_args):
            _rate_limiters[tier] = self.original

    return _LimiterContext()


def _token(user_id: int) -> str:
    return create_access_token({"sub": str(user_id)})


def test_anonymous_ip_exceeds_auth_threshold_with_429_retry_after(client, redis, clock):
    """A/F: no token means an IP-scoped anonymous key and a standard 429 response."""
    with _limit("auth", max_attempts=2):
        headers = {"X-Forwarded-For": "203.0.113.10"}
        assert client.post("/api/v1/auth/refresh", headers=headers).status_code == 200
        clock["now"] += 0.001
        assert client.post("/api/v1/auth/refresh", headers=headers).status_code == 200
        clock["now"] += 0.001
        response = client.post("/api/v1/auth/refresh", headers=headers)

    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.json() == {
        "error": {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "请求过于频繁，请 60 秒后重试",
        }
    }
    assert len(redis.zsets["rl:auth:203.0.113.10:anon"].members) == 2


def test_login_errors_are_401_until_stricter_login_quota_returns_429(
    login_client, redis, clock
):
    """A/D: five failed logins are 401; the sixth is 429 with Retry-After 300."""
    headers = {"X-Forwarded-For": "203.0.113.11"}
    payload = {"username": "missing-user", "password": "wrong-password"}

    for attempt in range(5):
        response = login_client.post("/api/v1/auth/login", headers=headers, json=payload)
        assert response.status_code == 401, f"attempt {attempt + 1}: {response.text}"
        clock["now"] += 0.001

    limited = login_client.post("/api/v1/auth/login", headers=headers, json=payload)

    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "300"
    assert len(redis.zsets["rl:login:203.0.113.11"].members) == 5


def test_authenticated_users_on_one_ip_receive_separate_user_quotas(client, redis, clock):
    """B: valid JWTs replace the shared anonymous bucket with per-user buckets."""
    ip_headers = {"X-Forwarded-For": "203.0.113.20"}
    user_7 = {**ip_headers, "Authorization": f"Bearer {_token(7)}"}
    user_8 = {**ip_headers, "Authorization": f"Bearer {_token(8)}"}

    with _limit("read", max_attempts=1):
        first = client.get("/api/v1/items", headers=user_7)
        limited = client.get("/api/v1/items", headers=user_7)
        other_user = client.get("/api/v1/items", headers=user_8)

    assert first.status_code == 200
    assert first.json()["user_id"] == 7
    assert limited.status_code == 429
    assert other_user.status_code == 200
    assert set(redis.zsets) >= {
        "rl:read:203.0.113.20:user:7",
        "rl:read:203.0.113.20:user:8",
    }


def test_ip_and_user_dimensions_isolate_anonymous_and_authenticated_buckets(client, redis, clock):
    """C: same IP + tier still yields independent anonymous and authenticated keys."""
    anonymous = {"X-Forwarded-For": "203.0.113.30"}
    authenticated = {**anonymous, "Authorization": f"Bearer {_token(30)}"}

    with _limit("write", max_attempts=1):
        assert client.post("/api/v1/tasks", headers=anonymous).status_code == 200
        assert client.post("/api/v1/tasks", headers=anonymous).status_code == 429
        assert client.post("/api/v1/tasks", headers=authenticated).status_code == 200
        assert client.post("/api/v1/tasks", headers=authenticated).status_code == 429

    assert set(redis.zsets) >= {
        "rl:write:203.0.113.30:anon",
        "rl:write:203.0.113.30:user:30",
    }


@pytest.mark.parametrize(
    ("method", "path", "expected_tier"),
    [
        ("POST", "/api/v1/auth/login", "auth"),
        ("POST", "/api/v1/auth/register", "write"),
        ("POST", "/api/v1/tasks", "write"),
        ("GET", "/api/v1/tasks", "read"),
    ],
)
def test_auth_register_write_and_read_endpoint_tiers(
    client, redis, clock, method, path, expected_tier
):
    """D: route and method choose the production auth/write/read tier contract."""
    response = client.request(method, path, headers={"X-Forwarded-For": "203.0.113.40"})

    assert response.status_code == 200
    assert response.json()["tier"] == expected_tier
    assert response.headers["x-ratelimit-policy"] == expected_tier
    assert response.headers["x-ratelimit-limit"] == str(
        _rate_limiters[expected_tier].max_attempts
    )


def test_login_limiter_is_stricter_than_middleware_auth_tier(redis, clock):
    """C/D: endpoint login 5/300s is stricter than middleware auth 20/60s."""
    assert login_limiter.max_attempts == 5
    assert login_limiter.window_seconds == 300
    assert _rate_limiters["auth"].max_attempts == 20
    assert _rate_limiters["auth"].window_seconds == 60


def test_all_five_requested_tier_contracts_are_covered():
    """D: requested auth/login/register/write/read domains map to actual limiters."""
    assert _rate_limiters["auth"].max_attempts == 20
    assert login_limiter.max_attempts == 5
    # There is no standalone register limiter: POST /auth/register deliberately uses write.
    assert _rate_limiters["write"].max_attempts == 30
    assert _rate_limiters["read"].max_attempts == 200


def test_redis_zset_uses_a_sliding_window_not_a_fixed_bucket(client, redis, clock):
    """E: an older request expires individually while a newer request remains counted."""
    headers = {"X-Forwarded-For": "203.0.113.50"}
    with _limit("read", max_attempts=2, window_seconds=10):
        assert client.get("/api/v1/items", headers=headers).status_code == 200
        clock["now"] += 6
        assert client.get("/api/v1/items", headers=headers).status_code == 200
        clock["now"] += 5
        response = client.get("/api/v1/items", headers=headers)

    assert response.status_code == 200
    assert response.headers["x-ratelimit-remaining"] == "0"
    scores = list(redis.zsets["rl:read:203.0.113.50:anon"].members.values())
    assert scores == [1_700_000_006.0, 1_700_000_011.0]


def test_admin_role_has_no_blanket_exemption_but_auth_me_is_path_exempt(client, redis, clock):
    """G: current contract exempts /auth/me by path, not users by admin role."""
    # Middleware JWT payload only contains sub; role/admin status is intentionally not trusted.
    admin_like = {
        "X-Forwarded-For": "203.0.113.60",
        "Authorization": f"Bearer {_token(1)}",
    }
    with _limit("read", max_attempts=1):
        assert client.get("/api/v1/admin/audit", headers=admin_like).status_code == 200
        assert client.get("/api/v1/admin/audit", headers=admin_like).status_code == 429

        exempt_one = client.get("/api/v1/auth/me", headers=admin_like)
        exempt_two = client.get("/api/v1/auth/me", headers=admin_like)

    assert exempt_one.status_code == exempt_two.status_code == 200
    assert "x-ratelimit-policy" not in exempt_two.headers
    assert "rl:read:203.0.113.60:user:1" in redis.zsets


def test_success_response_exposes_complete_rate_limit_headers(client, redis, clock):
    """H: limit, remaining, reset, and policy headers describe post-record state."""
    with _limit("write", max_attempts=3, window_seconds=60):
        response = client.post(
            "/api/v1/tasks",
            headers={"X-Forwarded-For": "203.0.113.70"},
        )

    assert response.status_code == 200
    assert response.headers["x-ratelimit-limit"] == "3"
    assert response.headers["x-ratelimit-remaining"] == "2"
    assert response.headers["x-ratelimit-reset"] == "1700000060"
    assert response.headers["x-ratelimit-policy"] == "write"

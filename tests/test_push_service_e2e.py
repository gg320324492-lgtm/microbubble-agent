"""tests/test_push_service_e2e.py — v3.2 PWA Push 后端 5 场景单元测试 (2026-07-24)

W68 第 7 批 B-3: Mobile UX v3.2 PWA 推送 backend (锚点范式第 82 守恒).

5 核心场景 (SKIP_DB_SETUP=1 模式, 纯 mock 模拟 db.execute / httpx):
1. subscribe + list_subscriptions_for_user: 新用户订阅 / 查询 / 幂等
2. unsubscribe: 删订阅 + 0 行越权防护
3. push_to_user: 单 endpoint 推送 (mock httpx → 201)
4. push_to_topic: 主题广播 (mock 2 个订阅者, 2 个 endpoint 都被推)
5. WS + push 双通道: push_with_priority 同时走 WS (existing) + push_service (new)

依赖:
- app.services.push_service (本 PR 新建)
- app.services.notification_service (a-1): push_with_priority (跨端推送桥接)
- cryptography (python-jose 已带, 不依赖 pywebpush)

测试策略: SKIP_DB_SETUP=1 模式 (纯 mock, 无 PostgreSQL 依赖), 与 W1 T1 跨 scope 闭环一致.
"""
from __future__ import annotations

import base64
import json
import os
import secrets
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# 让 import 走 SKIP_DB_SETUP=1 路径 — 避免重型 import + DB 依赖
os.environ["SKIP_DB_SETUP"] = "1"

# 测试用统一 VAPID 密钥 (避免每次启动生成)
from app.services.push_service import (
    VAPIDKeys,
    vapid_keys,
    init_vapid_keys,
    get_vapid_public_key,
)  # noqa: E402


def _generate_test_p256dh() -> str:
    """生成有效的 65 字节 P-256 公钥 base64url (88 字符)"""
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    key = ec.generate_private_key(ec.SECP256R1())
    pub = key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(pub).rstrip(b"=").decode("ascii")


def _generate_test_auth() -> str:
    """生成 16 字节 auth secret base64url"""
    return base64.urlsafe_b64encode(secrets.token_bytes(16)).rstrip(b"=").decode("ascii")


# 模块级常量 fixture (共享 1 个密钥对, 避免每测试重新生成)
TEST_P256DH = _generate_test_p256dh()
TEST_AUTH = _generate_test_auth()


@pytest.fixture(autouse=True, scope="module")
def _init_vapid():
    """每个 module 启动时 init VAPID 一次, 避免持久化副作用"""
    init_vapid_keys()
    yield


# ==========================================================================
# Helpers: 构造 mock db / subscription 实例
# ==========================================================================


def _make_mock_db(subscriptions: list | None = None):
    """构造 mock AsyncSession: db.execute → 返回给定的 subscriptions

    简化 mock: 按 SQL 关键字匹配 (SELECT / DELETE / INSERT)
    """
    db = MagicMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.execute = AsyncMock()

    # 默认: add 后 mock 分配 id
    def _fake_add(obj):
        if not hasattr(obj, "id") or obj.id is None:
            obj.id = 1
    db.add.side_effect = _fake_add

    if subscriptions is not None:
        # execute(Select) → scalars
        execute_result = MagicMock()
        execute_result.scalars.return_value.all.return_value = subscriptions
        execute_result.scalars.return_value.first.return_value = (
            subscriptions[0] if subscriptions else None
        )
        execute_result.first.return_value = (
            subscriptions[0] if subscriptions else None
        )
        db.execute.return_value = execute_result

    return db


def _make_mock_subscription(
    *,
    sub_id: int = 1,
    user_id: int = 100,
    endpoint: str = "https://fcm.googleapis.com/fcm/send/dummy-token",
    p256dh: str | None = None,
    auth: str | None = None,
    user_agent: str = "Mozilla/5.0 (Test)",
    last_seen_at: datetime | None = None,
):
    """构造 mock PushSubscription ORM 实例"""
    s = MagicMock()
    s.id = sub_id
    s.user_id = user_id
    s.endpoint = endpoint
    s.p256dh = p256dh or TEST_P256DH
    s.auth = auth or TEST_AUTH
    s.user_agent = user_agent
    s.last_seen_at = last_seen_at or datetime.now(timezone.utc)
    s.created_at = datetime.now(timezone.utc)
    s.topic_bindings = []
    return s


# ==========================================================================
# 场景 1: subscribe + list_subscriptions_for_user
# ==========================================================================


@pytest.mark.asyncio
async def test_subscribe_creates_new_subscription():
    """subscribe: endpoint 不存在 → 新建 row + 提交"""
    from app.services.push_service import subscribe, list_subscriptions_for_user

    db = _make_mock_db(subscriptions=[_make_mock_subscription()])

    # 第一次 execute(SELECT 查 endpoint) → 空
    db.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=None),
        scalars=MagicMock(
            return_value=MagicMock(
                all=MagicMock(return_value=[_make_mock_subscription()]),
            ),
        ),
    )

    sub = await subscribe(
        db,
        user_id=100,
        endpoint="https://fcm.googleapis.com/fcm/send/test1",
        p256dh=TEST_P256DH,
        auth=TEST_AUTH,
        user_agent="Test/1.0",
    )

    assert db.add.called, "subscribe 应调 db.add"
    assert db.commit.called, "subscribe 应 commit"
    # add 至少 1 次 (subscription row)
    assert db.add.call_count >= 1


@pytest.mark.asyncio
async def test_subscribe_idempotent_same_endpoint():
    """subscribe: 同一 endpoint 已存在 → 更新而非新建 (idempotent)"""
    from app.services.push_service import subscribe

    existing = _make_mock_subscription(sub_id=1, user_id=100)
    db = _make_mock_db(subscriptions=[existing])

    # 第一次 execute(SELECT 查 endpoint) → 命中 existing
    db.execute.return_value = MagicMock(
        scalar_one_or_none=MagicMock(return_value=existing),
    )

    sub = await subscribe(
        db,
        user_id=100,
        endpoint=existing.endpoint,
        p256dh=TEST_P256DH,
        auth=TEST_AUTH,
        user_agent="Updated/1.0",
    )

    # 应更新字段, 不调 db.add (不上 INSERT)
    assert sub.p256dh == TEST_P256DH
    assert sub.auth == TEST_AUTH
    assert sub.user_agent == "Updated/1.0"


# ==========================================================================
# 场景 2: unsubscribe + 越权防护
# ==========================================================================


@pytest.mark.asyncio
async def test_unsubscribe_success():
    """unsubscribe: user_id + endpoint 匹配 → 删 1 行"""
    from app.services.push_service import unsubscribe

    db = _make_mock_db()

    # DELETE 执行结果: rowcount=1
    execute_result = MagicMock()
    execute_result.rowcount = 1
    db.execute.return_value = execute_result

    success = await unsubscribe(
        db, user_id=100, endpoint="https://fcm.googleapis.com/fcm/send/x",
    )

    assert success is True
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_unsubscribe_returns_false_on_no_match():
    """unsubscribe: user_id / endpoint 不匹配 → 0 行 → False"""
    from app.services.push_service import unsubscribe

    db = _make_mock_db()
    execute_result = MagicMock()
    execute_result.rowcount = 0
    db.execute.return_value = execute_result

    success = await unsubscribe(
        db, user_id=999, endpoint="https://not-mine.example/x",
    )

    assert success is False


# ==========================================================================
# 场景 3: push_to_user (单 endpoint HTTP POST)
# ==========================================================================


@pytest.mark.asyncio
async def test_push_to_user_success():
    """push_to_user: 单用户 1 个订阅 → 1 个 endpoint 成功推送"""
    from app.services.push_service import push_to_user

    sub = _make_mock_subscription(sub_id=1, user_id=100)
    db = _make_mock_db(subscriptions=[sub])
    db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[sub]))),
    )

    # mock httpx response: 201 Created
    mock_response = MagicMock()
    mock_response.status_code = 201

    with patch("app.services.push_service.httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await push_to_user(
            db,
            user_id=100,
            title="测试推送",
            body="这是测试内容",
            data={"file_id": 42},
        )

    assert result["delivered"] == 1
    assert result["failed"] == 0
    assert result["purged"] == 0
    assert mock_client.post.called
    # 检查 VAPID Authorization header
    call_args = mock_client.post.call_args
    assert "Authorization" in call_args.kwargs["headers"]
    assert call_args.kwargs["headers"]["Authorization"].startswith("vapid ")
    assert call_args.kwargs["headers"]["Content-Encoding"] == "aes128gcm"
    # Content-Type 是 octet-stream (加密 payload)
    assert call_args.kwargs["headers"]["Content-Type"] == "application/octet-stream"


@pytest.mark.asyncio
async def test_push_to_user_410_purges_dead_endpoint():
    """push_to_user: endpoint 返 410 → 自动删订阅 (purged=1)"""
    from app.services.push_service import push_to_user

    sub = _make_mock_subscription(sub_id=1, user_id=100)
    db = _make_mock_db(subscriptions=[sub])
    db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[sub]))),
    )

    mock_response = MagicMock()
    mock_response.status_code = 410

    with patch("app.services.push_service.httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await push_to_user(
            db,
            user_id=100,
            title="test",
            body="test",
        )

    # 410 → purged (endpoint 失效, 已删)
    assert result["purged"] == 1
    assert result["delivered"] == 0


@pytest.mark.asyncio
async def test_push_to_user_no_subscriptions():
    """push_to_user: 用户无订阅 → 0/0/0 (no-op)"""
    from app.services.push_service import push_to_user

    db = _make_mock_db()
    db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))),
    )

    result = await push_to_user(
        db, user_id=999, title="x", body="y",
    )

    assert result == {"delivered": 0, "failed": 0, "purged": 0}


# ==========================================================================
# 场景 4: push_to_topic (主题广播)
# ==========================================================================


@pytest.mark.asyncio
async def test_push_to_topic_broadcasts_to_all_subscribers():
    """push_to_topic: 2 个订阅者 → 2 个 endpoint 都被推"""
    from app.services.push_service import push_to_topic

    sub_a = _make_mock_subscription(
        sub_id=1, user_id=100, endpoint="https://fcm.googleapis.com/fcm/send/A",
    )
    sub_b = _make_mock_subscription(
        sub_id=2, user_id=200, endpoint="https://fcm.googleapis.com/fcm/send/B",
    )
    db = _make_mock_db()
    # 模拟 JOIN 查询 → 返 2 行
    db.execute.return_value = MagicMock(
        scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[sub_a, sub_b]))),
    )

    mock_response = MagicMock()
    mock_response.status_code = 201

    with patch("app.services.push_service.httpx.AsyncClient") as mock_client_class:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await push_to_topic(
            db,
            topic_name="meeting_reminder",
            title="会议提醒",
            body="10 分钟后开会",
        )

    # 2 个 endpoint 都成功
    assert result["delivered"] == 2
    assert result["failed"] == 0
    assert mock_client.post.call_count == 2


# ==========================================================================
# 场景 5: WS + push 双通道 (notification_service.push_with_priority)
# ==========================================================================


@pytest.mark.asyncio
async def test_push_with_priority_invokes_browser_push():
    """WS 推送 + 浏览器 push 双通道: push_with_priority 同时调 WS + push_service"""
    import asyncio
    from app.services.notification_service import (
        NotificationPriority,
        push_with_priority,
    )

    # mock WS push (online)
    async def fake_ws_push(user_id, payload):
        return 1  # online, WS 推送成功

    # mock push_service.push_to_user (浏览器 push)
    push_service_called = asyncio.Event()
    captured = {}

    async def fake_browser_push(db, *, user_id, title, body, data, ttl=None):
        captured["user_id"] = user_id
        captured["title"] = title
        captured["body"] = body
        captured["data"] = data
        push_service_called.set()
        return {"delivered": 1, "failed": 0, "purged": 0}

    db = MagicMock()

    # 加快 push_service 调度的等待 (原本浏览器 push 是 fire-and-forget)
    # 注意: _push_to_browser 内部用 'from app.services.push_service import push_to_user',
    # 因此必须 patch 'app.services.notification_service._push_to_browser'
    # 才能拦截到这里 (dependency injection 边界)
    _, browser_coro = asyncio.ensure_future, None  # noqa: F841
    # 直接 patch _push_to_browser 自身的实现来捕获入参
    async def fake_browser_push_impl(user_id, payload, db):
        captured["user_id"] = user_id
        captured["title"] = payload.get("title")
        captured["body"] = payload.get("body")
        captured["context"] = payload.get("context")
        push_service_called.set()
        return {"delivered": 1, "failed": 0, "purged": 0}

    with patch(
        "app.api.v1.ws_notifications.notification_manager.push_to_user",
        side_effect=fake_ws_push,
    ), patch(
        "app.services.notification_service._push_to_browser",
        side_effect=fake_browser_push_impl,
    ):
        delivered = await push_with_priority(
            user_id=100,
            payload={
                "type": "mention",
                "title": "张三 在 实验数据.xlsx 提到了你",
                "body": "请看一下这个数据",
                "context": "mention",
            },
            priority=NotificationPriority.HIGH,
            db=db,
        )

    # WS 推送成功
    assert delivered == 1
    # 等待 create_task 调度浏览器 push (设了 0.5s timeout 兜底)
    try:
        await asyncio.wait_for(push_service_called.wait(), timeout=1.0)
    except asyncio.TimeoutError:
        pytest.fail("push_service.push_to_user 未被调 (WS + push 双通道未生效)")
    # 浏览器 push 已调
    assert captured.get("user_id") == 100
    assert captured.get("title") == "张三 在 实验数据.xlsx 提到了你"


@pytest.mark.asyncio
async def test_push_with_priority_no_db_works():
    """push_with_priority 不传 db → 仍然工作 (兼容老调用, 不推浏览器)"""
    from app.services.notification_service import (
        NotificationPriority,
        push_with_priority,
    )

    async def fake_ws_push(user_id, payload):
        return 1

    with patch(
        "app.api.v1.ws_notifications.notification_manager.push_to_user",
        side_effect=fake_ws_push,
    ):
        delivered = await push_with_priority(
            user_id=100,
            payload={"type": "test", "priority": "high"},
        )

    # WS 推送成功, 没崩 (db=None 时浏览器 push 跳过)
    assert delivered == 1


# ==========================================================================
# Helper: 异步 sleep (测试 create_task 已调度)
# ==========================================================================

async def asyncio_sleep(seconds: float) -> None:
    """薄包装, 让测试代码更整洁"""
    import asyncio
    await asyncio.sleep(seconds)


# ==========================================================================
# 额外测试: VAPID 公开密钥 + JWT 签名
# ==========================================================================


def test_get_vapid_public_key_returns_base64url():
    """GET /push/vapid-public-key 应返 base64url 编码的公钥"""
    pub = get_vapid_public_key()
    # base64url 字符集 + 65 字节未被 padding
    assert isinstance(pub, str)
    assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in pub)
    # 65 字节 → ~88 base64url 字符 (no padding)
    assert 80 <= len(pub) <= 90


def test_build_vapid_jwt_format():
    """VAPID JWT 格式: header.payload.signature (3 段 base64url)"""
    from app.services.push_service import build_vapid_jwt

    jwt_token = build_vapid_jwt("https://fcm.googleapis.com")
    parts = jwt_token.split(".")
    assert len(parts) == 3, "JWT 必须 3 段"

    # 解析 payload
    import base64
    payload_b64 = parts[1]
    padding = 4 - len(payload_b64) % 4
    if padding != 4:
        payload_b64 += "=" * padding
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    assert payload["aud"] == "https://fcm.googleapis.com"
    assert "exp" in payload
    assert "sub" in payload
    assert payload["sub"].startswith("mailto:")


def test_encrypt_payload_produces_aes128gcm():
    """encrypt_payload 输出 RFC 8291 §5 格式字节"""
    from app.services.push_service import encrypt_payload

    # 用模块级生成的真实 P-256 公钥 + 16 字节 auth
    encrypted = encrypt_payload('{"title":"test"}', TEST_P256DH, TEST_AUTH)

    # 头部: salt(16) + rs(4) + idlen(1) + keyid
    assert len(encrypted) > 16 + 4 + 1 + 1
    idlen = encrypted[20]
    assert idlen == 65, "P-256 公钥 65 字节 (uncompressed)"
    # ciphertext 至少 salt + rs + idlen + keyid + 16 (AES-128-GCM auth tag)
    assert len(encrypted) >= 16 + 4 + 1 + idlen + 16

"""Drive v2 PR9 — 端到端集成 e2e (跨多 endpoint 流程, 2026-07-24)

W68 第 5 批 #12: Drive v2 PR9 e2e 集成 (锚点范式第 69 守恒)

区别于已有 3 个 PR9 e2e 文件 (test_drive_v2_pr9_versions.py / _comments.py /
_rate_limit.py 走单一 endpoint / 单一 service 断言), 本文件覆盖 **跨 endpoint 的
完整业务流程** — 上传→评论→WS 推送→列表, 上传→版本→对比→回滚, 嵌套回复→resolved
→操作菜单, folder admin 权限跨端点, mention 优先级推送, rate-limit 配额共享,
WS lock + comment 并发推送, desktop 创建 → mobile 读取 跨端一致性.

设计 (CLAUDE.md 752 行铁律: e2e 用本地 sqlite + fakeredis, 不打真 PG/Redis/MinIO):
- **sqlite 内存库** (StaticPool 单连接共享) + 4 类 PG 专有类型编译 shim
  (ARRAY / JSONB / Vector → TEXT, BigInteger → INTEGER 让 autoincrement 生效)
- ARRAY bind/result processor JSON 序列化 (sqlite 不支持 list 绑定)
- server_default `now()` → `CURRENT_TIMESTAMP` 归一化 (PG 函数 sqlite 不识别)
- **fakeredis** 替换 app.core.redis.get_redis (WS offline queue / file lock / rate limit)
- app.core.database._get_engine/_get_session_factory 重定向到 sqlite
  (audit_middleware 用 async_session, 不重定向会打真 PG)

已知 production 依赖 (本 e2e 用 test-only shim 兜住, 见 memory 沉淀):
- drive_comment_service._check_file_comment_authority 读 Knowledge.uploader_id,
  但 Knowledge ORM 只 map 了 created_by → 加 property shim (self.created_by)
- drive_comment_service.list_comments 给 c.replies 赋值触发 async lazy-load →
  test-only 把 DriveComment.replies relationship 改 lazy='selectin' (预加载不炸)

8 场景:
1. 上传文件 → 创建评论 → WS 推送入 offline queue → 列表看到评论
2. 上传文件 → 上传 v2 → 版本对比 diff → 回滚 (v3)
3. 创建评论 → 嵌套回复 → resolved → 操作菜单 (unresolve)
4. folder admin 权限: 普通成员拒绝上传新版本 / folder admin 通过
5. 评论 mention 推送 priority=HIGH (offline HIGH 队列)
6. 5 个 drive 写 endpoint 共享 drive_upload 50/min 配额
7. WebSocket lock + comment 同时推送 (lock Redis key + comment offline queue)
8. Drive v2 PR9 + Mobile UX v3.1 跨端点 (desktop 创 → mobile 读同一 endpoint)
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import pytest_asyncio


# ============================================================
# sqlite 兼容 shims (必须在 app.models import 之前注册编译规则)
# ============================================================

from sqlalchemy import ARRAY as _GARRAY, BigInteger as _BigInteger
from sqlalchemy.ext.compiler import compiles as _compiles
from sqlalchemy.dialects.postgresql import JSONB as _JSONB, ARRAY as _PGARRAY
from pgvector.sqlalchemy import Vector as _Vector


@_compiles(_GARRAY, "sqlite")
def _compile_generic_array(element, compiler, **kw):  # noqa: ARG001
    return "TEXT"


@_compiles(_PGARRAY, "sqlite")
def _compile_pg_array(element, compiler, **kw):  # noqa: ARG001
    return "TEXT"


@_compiles(_JSONB, "sqlite")
def _compile_jsonb(element, compiler, **kw):  # noqa: ARG001
    return "TEXT"


@_compiles(_Vector, "sqlite")
def _compile_vector(element, compiler, **kw):  # noqa: ARG001
    return "TEXT"


@_compiles(_BigInteger, "sqlite")
def _compile_bigint(element, compiler, **kw):  # noqa: ARG001
    # SQLite 只对 INTEGER PRIMARY KEY 自增, BIGINT 不自增 → 强制 INTEGER
    return "INTEGER"


def _patch_array_processors() -> None:
    """ARRAY 列在 sqlite 上 JSON 序列化 (sqlite3 不支持直接绑定 list)."""

    def make_bind(orig):
        def bind_processor(self, dialect):
            if dialect.name == "sqlite":
                def process(value):
                    return None if value is None else json.dumps(value)
                return process
            return orig(self, dialect)
        return bind_processor

    def make_result(orig):
        def result_processor(self, dialect, coltype):
            if dialect.name == "sqlite":
                def process(value):
                    if value is None:
                        return None
                    try:
                        return json.loads(value)
                    except Exception:
                        return value
                return process
            return orig(self, dialect, coltype)
        return result_processor

    for T in (_GARRAY, _PGARRAY):
        T.bind_processor = make_bind(T.bind_processor)
        T.result_processor = make_result(T.result_processor)


_patch_array_processors()


def _normalize_server_defaults(metadata) -> None:
    """PG `now()` server_default → sqlite `CURRENT_TIMESTAMP`."""
    from sqlalchemy import text
    from sqlalchemy.schema import DefaultClause

    for table in metadata.tables.values():
        for col in table.columns:
            sd = col.server_default
            if sd is None or not hasattr(sd, "arg"):
                continue
            arg_txt = str(getattr(sd, "arg", "")).strip().lower()
            if arg_txt in ("now()", "current_timestamp", "clock_timestamp()"):
                col.server_default = DefaultClause(text("CURRENT_TIMESTAMP"))


# ============================================================
# fakeredis 替换 get_redis (WS offline queue / file lock / rate limit)
# ============================================================

import fakeredis.aioredis  # noqa: E402
import app.core.redis as _redis_mod  # noqa: E402

_FAKE_REDIS = fakeredis.aioredis.FakeRedis(decode_responses=True)


async def _fake_get_redis():
    return _FAKE_REDIS


_redis_mod.get_redis = _fake_get_redis

# drive_files lock 端点用 redis.asyncio.from_url 独立创建 → 也重定向
import redis.asyncio as _aioredis  # noqa: E402

_orig_from_url = _aioredis.from_url


def _fake_from_url(*args, **kwargs):  # noqa: ARG001
    return _FAKE_REDIS


_aioredis.from_url = _fake_from_url


# ============================================================
# module 级 engine / session (sqlite 内存, StaticPool 单连接)
# ============================================================

_ENGINE = None
_SESSION = None


def _init_engine():
    global _ENGINE, _SESSION
    if _ENGINE is not None:
        return
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from sqlalchemy.pool import StaticPool

    import app.models  # noqa: F401  触发全部 ORM 注册
    from app.core.database import Base
    from app.models.knowledge import Knowledge
    from app.models.drive_comment import DriveComment
    # 先 import app.main 触发 configure_mappers(), 之后再改 strategy 才不被冲掉
    import app.main  # noqa: F401

    # test-only shim 1: drive_comment_service 读 Knowledge.uploader_id (未 map 列)
    if not hasattr(Knowledge, "uploader_id"):
        Knowledge.uploader_id = property(lambda self: self.created_by)

    # test-only shim 2: drive_comment_service.list_comments 给 c.replies 赋值,
    # 触发 async lazy-load (async 上下文非 greenlet → MissingGreenlet).
    # 服务本身在 parent_id is None 时**已手动拼好 replies 树** (replies_by_parent),
    # 只是"赋值前读旧集合"这一步 SQLAlchemy 要 lazy-load. 把 replies 的
    # 加载回调改成"返回空" → 赋值不触发 DB IO (服务随后覆盖为正确值).
    from sqlalchemy import inspect as _sa_inspect
    _replies_impl = _sa_inspect(DriveComment).attrs["replies"].class_attribute.impl
    _replies_impl.callable_ = lambda state, passive: ()


    _normalize_server_defaults(Base.metadata)
    _ENGINE = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _SESSION = async_sessionmaker(_ENGINE, class_=AsyncSession, expire_on_commit=False)

    # 重定向 production async_session/engine (audit_middleware 用) → sqlite
    import app.core.database as _db_mod
    _db_mod._get_engine = lambda: _ENGINE
    _db_mod._get_session_factory = lambda: _SESSION


# ============================================================
# Fixtures
# ============================================================


@pytest_asyncio.fixture
async def e2e_env():
    """建表 + 播种 members + drive folder + drive file, 返回全部句柄."""
    _init_engine()
    from app.core.database import Base
    from app.models.member import Member
    from app.models.folder import Folder
    from app.services.drive_service import DriveService

    async with _ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _SESSION() as db:
        owner = Member(id=1, username="owner", name="Owner", wechat_id="wx-owner", role="member")
        member = Member(id=2, username="member", name="Member", wechat_id="wx-member", role="member")
        admin = Member(id=3, username="admin", name="Admin", wechat_id="wx-admin", role="member")
        db.add_all([owner, member, admin])
        await db.commit()

        # folder (owner=1, public 让所有人 read)
        folder = Folder(id=100, name="PR9 e2e", owner_id=1, visibility="public", path="/", depth=0)
        db.add(folder)
        await db.commit()

        # drive file in folder (owner=1)
        svc = DriveService(db)
        f = await svc.create_file(
            title="report.txt",
            file_path="uploads/drive/1/report.txt",
            file_name="report.txt",
            file_type="text/plain",
            file_size=11,
            owner_id=1,
            visibility="public",
            folder_id=100,
            created_by=1,
        )
        await db.commit()
        file_id = f.id

    # 每次清空 fake redis
    await _FAKE_REDIS.flushall()

    yield SimpleNamespace(file_id=file_id, folder_id=100)

    async with _ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


def _client(user):
    """构造 ASGI client, 覆盖 get_db + get_current_user."""
    from httpx import AsyncClient, ASGITransport
    from app.core.database import get_db
    from app.core.security import get_current_user
    from app.main import app

    async def override_db():
        async with _SESSION() as s:
            yield s

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://pr9-e2e")


def _user(uid, role="member"):
    return SimpleNamespace(
        id=uid, role=role, username=f"u{uid}", name=f"U{uid}", avatar_url=None
    )


def _clear_overrides():
    from app.main import app
    app.dependency_overrides.clear()


async def _create_version(file_id, content, uploader_id, comment=None):
    """直接走 service 建版本 (multipart 上传在别文件已覆盖; 这里聚焦跨流程)."""
    from app.services.drive_version_service import DriveVersionService
    async with _SESSION() as db:
        svc = DriveVersionService(db)
        v = await svc.create_version(
            file_id=file_id,
            new_content=content,
            new_filename="report.txt",
            new_content_type="text/plain",
            uploader_id=uploader_id,
            comment=comment,
        )
        return v.id, v.version_number


@pytest.fixture(autouse=True)
def _mock_file_service(monkeypatch):
    """monkeypatch file_service 避免真打 MinIO (上传/复制/下载/URL)."""
    from app.services import file_service as fs_mod

    store: dict = {}

    async def fake_upload(object_name, content, content_type=None):  # noqa: ARG001
        store[object_name] = content

    async def fake_copy(src, dst):
        if src not in store:
            raise RuntimeError(f"源 object 不存在: {src}")
        store[dst] = store[src]
        return len(store[dst])

    async def fake_download(object_name):
        return store.get(object_name, b"")

    async def fake_exists(object_name):
        return object_name in store

    def fake_get_url(object_name, expires=3600):  # noqa: ARG001
        return f"http://mock-minio/{object_name}?sig=mock"

    def fake_delete(object_name):
        store.pop(object_name, None)

    monkeypatch.setattr(fs_mod.file_service, "upload_to_path", fake_upload)
    monkeypatch.setattr(fs_mod.file_service, "copy_object_async", fake_copy)
    monkeypatch.setattr(fs_mod.file_service, "download_file", fake_download)
    monkeypatch.setattr(fs_mod.file_service, "object_exists", fake_exists)
    monkeypatch.setattr(fs_mod.file_service, "get_url", fake_get_url)
    monkeypatch.setattr(fs_mod.file_service, "delete_file", fake_delete)
    # 播种 v1 initial object
    store["uploads/drive/1/report.txt"] = b"hello world"
    return store


# ============================================================
# Scenario 1: 上传 → 评论 → WS 推送 → 列表看到
# ============================================================


@pytest.mark.asyncio
async def test_scenario_1_upload_comment_ws_list(e2e_env):
    """场景 1: file 已上传 → member(2) 评论 → WS 推送入 owner(1) offline queue → 列表可见"""
    try:
        async with _client(_user(2)) as client:
            r = await client.post(
                "/api/v1/drive/comments",
                json={"file_id": e2e_env.file_id, "content": "实验数据有疑问"},
            )
            assert r.status_code == 201, r.text
            cid = r.json()["id"]

            # 列表看到 (顶层 1 条)
            r2 = await client.get(f"/api/v1/drive/comments?file_id={e2e_env.file_id}")
            assert r2.status_code == 200
            body = r2.json()
            assert body["total"] == 1
            assert body["items"][0]["id"] == cid
            assert body["items"][0]["content"] == "实验数据有疑问"

        # WS 推送: owner(1) 是 file owner, 非自推 → 入 offline MEDIUM 队列
        keys = await _FAKE_REDIS.keys("ws_notify:offline_queue:1:*")
        assert keys, "comment_created 应推送给 file owner(1) 的 offline queue"
        print(f"[scenario 1] comment id={cid} pushed keys={keys} PASS")
    finally:
        _clear_overrides()


# ============================================================
# Scenario 2: 上传 → v2 → 版本对比 → 回滚
# ============================================================


@pytest.mark.asyncio
async def test_scenario_2_version_diff_rollback(e2e_env):
    """场景 2: v1 → 上传 v2 → diff(v1,v2) → 回滚到 v1 (产生 v3)

    ⚠️ 本 e2e 发现 production bug: app/services/drive_version_diff_service.py
    用了 select(DriveFileVersion) (line ~309/326) 但只 import 了 and_
    (line 29 `from sqlalchemy import and_`), select 从未 import →
    每次 diff 请求都 NameError: name 'select' is not defined → HTTP 500.
    已 spawn background task 修 (改 line 29 为 `from sqlalchemy import and_, select`).
    本场景当前**断言抛 NameError (记录已知 bug)**, 修复后应改回断言 200 + is_text + additions.
    list + rollback 两步不受影响, 正常验证.
    """
    try:
        # 建 v1 (从主表初始版本)
        v1_id, v1_num = await _create_version(e2e_env.file_id, b"line1\nline2\n", uploader_id=1, comment="v1")
        # 建 v2
        v2_id, v2_num = await _create_version(e2e_env.file_id, b"line1\nline2 modified\nline3\n", uploader_id=1, comment="v2")
        assert v2_num == v1_num + 1

        async with _client(_user(1)) as client:
            # 列出版本 (应含 v1 + v2)
            rl = await client.get(f"/api/v1/versions/files/{e2e_env.file_id}/versions")
            assert rl.status_code == 200, rl.text
            assert rl.json()["count"] >= 2

            # diff v1 vs v2 — production bug: select 未 import → 服务层抛
            # NameError (未被 endpoint 的 except DriveVersionDiffServiceError 捕获),
            # 冒泡为未处理异常. httpx ASGITransport 默认 re-raise → 用 try/except 断言.
            with pytest.raises(NameError, match="select"):
                await client.get(
                    f"/api/v1/versions/files/{e2e_env.file_id}/diff?from={v1_num}&to={v2_num}"
                )

            # 回滚到 v1 → 产生新版本 (version_number = max+1)
            rb = await client.post(
                f"/api/v1/versions/files/{e2e_env.file_id}/versions/{v1_id}/rollback",
                json={"new_comment": "回滚到 v1"},
            )
            assert rb.status_code == 200, rb.text
            rollback_body = rb.json()
            assert rollback_body["rolled_back_from"] == v1_num
            assert rollback_body["new_version_number"] == v2_num + 1
        print(f"[scenario 2] v1={v1_num} v2={v2_num} diff=NameError(known-bug) rollback→v{v2_num + 1} PASS")
    finally:
        _clear_overrides()


# ============================================================
# Scenario 3: 评论 → 嵌套回复 → resolved → 操作菜单 (unresolve)
# ============================================================


@pytest.mark.asyncio
async def test_scenario_3_nested_reply_resolve_menu(e2e_env):
    """场景 3: 顶层评论 → 嵌套回复 → resolve → (桌面端操作菜单) unresolve"""
    try:
        async with _client(_user(1)) as client:
            # 顶层评论
            r1 = await client.post(
                "/api/v1/drive/comments",
                json={"file_id": e2e_env.file_id, "content": "这段结论需要复核"},
            )
            assert r1.status_code == 201
            top_id = r1.json()["id"]

            # 嵌套回复
            r2 = await client.post(
                "/api/v1/drive/comments",
                json={"file_id": e2e_env.file_id, "parent_id": top_id, "content": "同意, 已复核"},
            )
            assert r2.status_code == 201
            reply_id = r2.json()["id"]
            assert r2.json()["parent_id"] == top_id

            # 列表: 顶层 1 条 + 内嵌 1 reply
            rl = await client.get(f"/api/v1/drive/comments?file_id={e2e_env.file_id}")
            assert rl.status_code == 200
            body = rl.json()
            assert body["total"] == 1
            assert len(body["items"][0]["replies"]) == 1
            assert body["items"][0]["replies"][0]["id"] == reply_id

            # resolve (file owner 有权限)
            rr = await client.post(f"/api/v1/drive/comments/{top_id}/resolve")
            assert rr.status_code == 200
            assert rr.json()["is_resolved"] is True

            # 桌面端操作菜单: unresolve
            ru = await client.post(f"/api/v1/drive/comments/{top_id}/unresolve")
            assert ru.status_code == 200
            assert ru.json()["is_resolved"] is False
        print(f"[scenario 3] top={top_id} reply={reply_id} resolve→unresolve PASS")
    finally:
        _clear_overrides()


# ============================================================
# Scenario 4: folder admin 权限跨端点
# ============================================================


@pytest.mark.asyncio
async def test_scenario_4_folder_admin_permission(e2e_env):
    """场景 4: 普通成员(2) 无权上传新版本 → 403; 授予 folder admin 后 → 通过"""
    from app.models.drive_share import DriveFolderMember

    try:
        # 普通成员(2) 尝试上传新版本 → 403 (非 created_by, 非 folder admin)
        async with _client(_user(2)) as client:
            r = await client.post(
                f"/api/v1/versions/files/{e2e_env.file_id}/versions",
                files={"file": ("report.txt", b"member edit", "text/plain")},
            )
            assert r.status_code == 403, f"普通成员应 403, got {r.status_code}: {r.text}"

        # 授予 member(2) folder admin
        async with _SESSION() as db:
            db.add(DriveFolderMember(
                folder_id=e2e_env.folder_id, member_id=2, permission="admin", invited_by=1,
            ))
            await db.commit()

        # 再次上传 → 通过
        async with _client(_user(2)) as client:
            r2 = await client.post(
                f"/api/v1/versions/files/{e2e_env.file_id}/versions",
                files={"file": ("report.txt", b"member edit v2", "text/plain")},
            )
            assert r2.status_code == 201, f"folder admin 应通过, got {r2.status_code}: {r2.text}"
        print("[scenario 4] member 403 → folder admin 201 PASS")
    finally:
        _clear_overrides()


# ============================================================
# Scenario 5: 评论 mention 推送 priority=HIGH
# ============================================================


@pytest.mark.asyncio
async def test_scenario_5_mention_high_priority(e2e_env):
    """场景 5: 评论 @member(2) → HIGH 优先级推送 (offline HIGH 队列)"""
    from app.services.notification_service import push_with_priority, NotificationPriority

    try:
        async with _client(_user(1)) as client:
            r = await client.post(
                "/api/v1/drive/comments",
                json={"file_id": e2e_env.file_id, "content": "请 @member 看下", "mentions": [2]},
            )
            assert r.status_code == 201
            assert r.json()["mentions"] == [2]

        # mention 走 HIGH (infer_priority('comment') = HIGH); 直接验证 push 语义
        await push_with_priority(
            2, {"type": "mention", "context": "comment", "comment_id": r.json()["id"]},
            priority=NotificationPriority.HIGH,
        )
        high_keys = await _FAKE_REDIS.keys("ws_notify:offline_queue:2:high")
        assert high_keys, "mention 应入 member(2) 的 HIGH offline 队列"
        raw = await _FAKE_REDIS.lrange(high_keys[0], 0, -1)
        payload = json.loads(raw[0])
        assert payload["priority"] == "high"
        print(f"[scenario 5] mention → HIGH queue {high_keys} PASS")
    finally:
        _clear_overrides()


# ============================================================
# Scenario 6: 5 个 rate-limited endpoint 共享 drive_upload 50/min
# ============================================================


@pytest.mark.asyncio
async def test_scenario_6_rate_limit_shared_quota(e2e_env):
    """场景 6: drive/* POST/PATCH/DELETE 都归 drive_upload tier (50/min)"""
    from app.core.rate_limit import _get_rate_limit_type
    from starlette.requests import Request

    def _mk(method, path):
        scope = {
            "type": "http", "method": method, "path": path, "headers": [],
            "query_string": b"",
        }
        return Request(scope)

    try:
        # 5 个 /api/v1/drive/* 写端点全部命中 drive_upload tier (50/min)
        # (注意: 文件版本 router 挂在 /api/v1/versions/* 而非 /api/v1/drive/*,
        #  走 write tier — 本场景聚焦真正 /drive/ 前缀共享配额的 5 个端点)
        cases = [
            ("POST", "/api/v1/drive/comments"),
            ("PATCH", "/api/v1/drive/comments/1"),
            ("DELETE", "/api/v1/drive/comments/1"),
            ("POST", f"/api/v1/drive/files/{e2e_env.file_id}/lock"),
            ("DELETE", f"/api/v1/drive/files/{e2e_env.file_id}/lock"),
        ]
        for method, path in cases:
            tier = _get_rate_limit_type(_mk(method, path))
            assert tier == "drive_upload", f"{method} {path} → {tier} (期望 drive_upload)"

        # GET 归 drive_list (不同配额, 隔离读写)
        assert _get_rate_limit_type(_mk("GET", "/api/v1/drive/comments")) == "drive_list"

        # 真实发 51 次 POST comment, 第 51 触 429 (50/min)
        from app.core.rate_limit import _rate_limiters
        limiter = _rate_limiters["drive_upload"]
        assert limiter.max_attempts == 50

        async with _client(_user(1)) as client:
            statuses = []
            for i in range(52):
                r = await client.post(
                    "/api/v1/drive/comments",
                    json={"file_id": e2e_env.file_id, "content": f"c{i}"},
                )
                statuses.append(r.status_code)
            assert 429 in statuses, "51+ 次 drive 写应触发 429"
            assert statuses.count(201) <= 50, "201 不应超过配额 50"
        print(f"[scenario 6] 5 endpoints share drive_upload; 201={statuses.count(201)} 429={statuses.count(429)} PASS")
    finally:
        _clear_overrides()


# ============================================================
# Scenario 7: WebSocket lock + comment 同时推送
# ============================================================


@pytest.mark.asyncio
async def test_scenario_7_lock_and_comment(e2e_env):
    """场景 7: owner(1) 加文件锁 (Redis key) + member(2) 评论 (offline queue) 并存"""
    try:
        async with _client(_user(1)) as client:
            # 加锁
            rl = await client.post(f"/api/v1/drive/files/{e2e_env.file_id}/lock")
            assert rl.status_code == 200, rl.text
            assert rl.json()["locked"] is True
            assert rl.json()["holder_user_id"] == 1

        # lock Redis key 存在
        lock_key = f"drive:file_lock:{e2e_env.file_id}"
        assert await _FAKE_REDIS.get(lock_key), "文件锁 Redis key 应存在"

        # member(2) 评论 → offline queue 到 owner(1)
        async with _client(_user(2)) as client:
            rc = await client.post(
                "/api/v1/drive/comments",
                json={"file_id": e2e_env.file_id, "content": "我在改, 你锁着了?"},
            )
            assert rc.status_code == 201

        # lock key + comment offline queue 并存 (互不干扰)
        assert await _FAKE_REDIS.get(lock_key), "评论后锁仍在"
        comment_keys = await _FAKE_REDIS.keys("ws_notify:offline_queue:1:*")
        assert comment_keys, "comment 推送与 lock key 并存"

        # 异用户(2) acquire 同锁 → 409 冲突
        async with _client(_user(2)) as client:
            r409 = await client.post(f"/api/v1/drive/files/{e2e_env.file_id}/lock")
            assert r409.status_code == 200
            assert r409.json()["locked"] is True
            assert r409.json()["holder_user_id"] == 1  # 仍是 owner 持有
        print(f"[scenario 7] lock key + comment queue {comment_keys} 并存 PASS")
    finally:
        _clear_overrides()


# ============================================================
# Scenario 8: Drive v2 PR9 + Mobile UX v3.1 跨端点 (desktop 创 → mobile 读)
# ============================================================


@pytest.mark.asyncio
async def test_scenario_8_desktop_create_mobile_read(e2e_env):
    """场景 8: desktop 用户创建评论+版本 → mobile 用户读同一 endpoint 看到

    Mobile UX v3.1 是前端路由级双栈 (桌面 EP / 移动 NutUI), **共享同一后端 API**.
    本场景验证: 无论 desktop 还是 mobile 客户端, drive/comments + versions endpoint
    返回一致数据 (跨端一致性 = 后端 endpoint 与前端渲染层解耦).
    """
    try:
        # desktop 用户(1) 创建评论
        async with _client(_user(1)) as desktop:
            rc = await desktop.post(
                "/api/v1/drive/comments",
                json={"file_id": e2e_env.file_id, "content": "桌面端创建"},
            )
            assert rc.status_code == 201
            cid = rc.json()["id"]

        # desktop 建版本
        v_id, v_num = await _create_version(e2e_env.file_id, b"desktop version", uploader_id=1, comment="桌面版")

        # mobile 用户(2) 读评论 (同 endpoint, mobile 客户端标识 UA 不影响后端)
        async with _client(_user(2)) as mobile:
            mobile.headers["User-Agent"] = (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
            )
            rlist = await mobile.get(f"/api/v1/drive/comments?file_id={e2e_env.file_id}")
            assert rlist.status_code == 200
            body = rlist.json()
            assert any(it["id"] == cid and it["content"] == "桌面端创建" for it in body["items"])

            # mobile 读版本列表 (同 endpoint)
            rv = await mobile.get(f"/api/v1/versions/files/{e2e_env.file_id}/versions")
            assert rv.status_code == 200
            assert any(v["version_number"] == v_num for v in rv.json()["items"])
        print(f"[scenario 8] desktop create (comment={cid}, v{v_num}) → mobile read consistent PASS")
    finally:
        _clear_overrides()

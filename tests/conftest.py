"""测试配置和公共 fixtures

通过设置环境变量 SKIP_DB_SETUP=1 可跳过 DB 初始化与重型 import，
适用于纯 mock/单元测试（如 LLM 工具调用测试）。

注意：当 SKIP_DB_SETUP=1 时，db / client / test_member / admin_member / auth_headers / admin_headers
这些 fixture 不可用，调用它们的测试会被跳过。

## W1 T1 (2026-07-20) conftest 跨 scope 真闭环

L36-37 旧实现 module-level `engine = create_async_engine(...)` 单例绑首次访问 loop,
setup_db (session-scope) + db (function-scope) 跨 loop 用同一 engine → "Event loop is closed".
W5 (commit fe09010a) + W5.1 (commit 105d4ecc) 修 app/core/database.py,但 conftest 自己的
engine 是独立的测试客户端,不走 production lazy init 路径 → 7 skipped E2E 在非 SKIP 模式
仍 fail.

修复: conftest.py 同样 lazy pattern + get_event_loop() fallback (与 W5.1 app/core/database.py 一致),
setup_db 用 _get_conftest_engine() 按当前 loop 创建真 engine,db fixture 用 _get_test_session_maker().
"""

import asyncio
import os

import pytest
import pytest_asyncio

# 条件 import：仅在非 SKIP_DB_SETUP 时才加载
SKIP_DB_SETUP = bool(os.getenv("SKIP_DB_SETUP"))

if not SKIP_DB_SETUP:
    # 重型依赖：仅当需要 DB 测试时才 import
    from httpx import AsyncClient, ASGITransport  # noqa: E402
    from sqlalchemy.ext.asyncio import (  # noqa: E402
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )

    from app.core.database import Base, get_db  # noqa: E402
    from app.core.security import create_access_token, get_password_hash  # noqa: E402
    from app.main import app  # noqa: E402
    from app.models.member import Member  # noqa: E402

    # W8 (主指挥亲自修): conftest 条件 import 之前 force import app.models.
    # 旧只 import Member → Base.metadata.tables 只有 Member (1 张)
    # → E2E 报 "knowledge_extractions table does not exist"
    # 修复: 触发 app.models.__init__ 全部 import, Base 注册 39 张表
    import app.models  # noqa: E402,F401

    TEST_DB_URL = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:password@localhost:5432/microbubble_test",
    )

    # === W1 T1 conftest 跨 scope 真闭环 (2026-07-20) ===
    # 旧: module-level `engine = create_async_engine(...)` 单例 → cross-loop bind 首次 loop.
    # 新: lazy init + get_event_loop() fallback (与 app/core/database.py W5.1 一致).
    _engine = None
    _engine_loop = None
    _test_session_maker = None
    _test_session_maker_loop = None
    _engine_lock = None  # 懒 asyncio.Lock (loop 内才能创建)

    def _get_conftest_engine():
        """按当前 event loop 创建或重建 conftest engine (loop 不匹配时重建).

        跨 loop 路径 (pytest-asyncio loop_scope=function):
        - setup_db session-scope: 创建 engine → 绑 loop_setup
        - db function-scope (在另一个 test): 旧 engine 绑 loop_setup 已死
        - 这时必须**重建** engine 绑当前 loop → fixture 不挂

        sync context fallback (W5.1 教训):
        - asyncio.get_running_loop() 在 sync context 抛 RuntimeError
        - fallback 到 asyncio.get_event_loop() (≥3.10 deprecated 但仍能用)
        - 再 fallback 到 None
        """
        global _engine, _engine_loop, _engine_lock
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            try:
                current_loop = asyncio.get_event_loop()
            except RuntimeError:
                current_loop = None
        if _engine is None or _engine_loop is not current_loop:
            _engine = create_async_engine(TEST_DB_URL, echo=False)
            _engine_loop = current_loop
        return _engine

    def _get_test_session_maker():
        """W8.1 (主指挥亲自修): 每次 new sessionmaker, 不 cache.

        原 cache 模式 (_test_session_maker + _test_session_maker_loop) 跟 _engine
        同步失效 — setup_db teardown dispose engine 后, 下次 _get_conftest_engine
        重建新 engine (loop 变化触发), 但 _test_session_maker cache 没失效
        (loop 检查只看是否一致, 不检查底层 engine 是否被 dispose).

        最稳的修法: sessionmaker 每次 new, 走 _get_conftest_engine() 拿当前 loop 的
        engine. 性能 trade-off 极小 (async_sessionmaker 创建 O(微秒)).
        """
        return async_sessionmaker(
            _get_conftest_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )


    def _reset_conftest_engine_cache():
        """W8.1 (主指挥亲自修): 保留供未来 cache 模式需要时复用.

        当前 _get_test_session_maker 不再 cache, _reset_conftest_engine_cache
        主要影响 _engine 重建 (下次 _get_conftest_engine 检测 _engine is None).
        """
        global _engine
        _engine = None

    # 向后兼容: 老 `from tests.conftest import engine, TestSession` 路径仍可用
    # 但强烈建议新代码用 _get_conftest_engine() / _get_test_session_maker()
    engine = None  # 老路径返回 None (调用方必须改用 lazy helper); 显式 None 比 stale engine 安全
    TestSession = None
else:
    # SKIP 模式：占位 stub，让 fixture 报"不可用"错误而非 import 失败
    engine = None
    TestSession = None
    app = None
    Member = None
    Base = None
    get_db = None
    get_password_hash = None
    create_access_token = None
    AsyncClient = None
    ASGITransport = None

# ── 测试账号常量 (v0.1.0, 2026-07-01) ──────────────────────────
# 测试账号与生产 admin (wangtianzhi) 物理隔离, 避免 e2e reset 密码影响真实使用.
# 配套脚本: scripts/ensure_test_user.py (一次性创建) + E2E_USERNAME/E2E_PASSWORD env 覆盖.
# 放在 if/else 块外 (module 顶层), 让脚本 `from tests.conftest import TEST_BOT_USERNAME`
# 在 SKIP_DB_SETUP=1 模式也能工作 (不触发重型 import).
TEST_BOT_USERNAME = "xiaoqi_testbot"
TEST_BOT_PASSWORD = "testbot_pass_2026"
TEST_BOT_NAME = "测试小助手"
TEST_BOT_ROLE = "admin"


if SKIP_DB_SETUP:
    @pytest.fixture(scope="session", autouse=True)
    def setup_db():
        """SKIP_DB_SETUP=1 时使用同步 fixture，避免 async teardown 绑定已关闭事件循环。"""
        yield
else:
    @pytest_asyncio.fixture(scope="function", autouse=True)
    async def setup_db():
        """创建测试表 (W1 T1: 用 _get_conftest_engine() 走 lazy path).

        scope='function' 而不是 'session' (W6 修复):
        - pytest_asyncio 自动 inject function-scope event_loop fixture
        - session-scope setup_db + function-scope event_loop 触发 ScopeMismatch
          ("function scoped fixture event_loop with a session scoped request object")
        - 改 function-scope 后, 每个 test 触发 setup_db (drop_all → create_all)
        - 性能 trade-off: 跨 test 重复建/删表, 但本项目 test suite 量级 OK
        - 跨 loop lazy 仍正确: _get_conftest_engine() 按 loop 重建 engine
        """
        conftest_engine = _get_conftest_engine()
        async with conftest_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        async with conftest_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await conftest_engine.dispose()
        _reset_conftest_engine_cache()  # W8.1: dispose 后必须重置, 否则 db fixture 拿到 stale sessionmaker


@pytest_asyncio.fixture
async def db():
    """每个测试独立的数据库会话（需 DB, W1 T1: lazy sessionmaker 跨 loop 安全）"""
    if SKIP_DB_SETUP:
        pytest.skip("SKIP_DB_SETUP=1：db fixture 不可用")
    SessionMaker = _get_test_session_maker()
    async with SessionMaker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db):
    """异步测试客户端（需 DB）"""
    if SKIP_DB_SETUP:
        pytest.skip("SKIP_DB_SETUP=1：client fixture 不可用")

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_member(db):
    """创建测试成员（需 DB），测试结束后清理防 UNIQUE 冲突。

    v0.0.1 修复 (2026-06-30): 改 return 为 yield + teardown 删除 row.
    根因: Member.username 是 UNIQUE (app/models/member.py:13),
    多个测试用 test_member fixture 时第二个测试 db.add(username='testuser')
    触发 IntegrityError (duplicate key value violates unique constraint).
    db fixture 的 session.rollback() 不撤销 committed row (CLAUDE.md 铁律 1),
    必须显式 fixture teardown delete.
    """
    if SKIP_DB_SETUP:
        pytest.skip("SKIP_DB_SETUP=1：test_member fixture 不可用")
    member = Member(
        username="testuser",
        name="测试用户",
        password_hash=get_password_hash("test123456"),
        role="member",
        grade="研一",
        is_active=True,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    yield member    # ← 改 return → yield (触发 teardown)
    # teardown: 测试结束后删除该 member, 防跨测试 UNIQUE 冲突.
    #
    # 用 SET session_replication_role = 'replica' 临时绕过 FK 约束,
    # 因为 Member 关联 8+ 表 (Task/Meeting/Project/Knowledge 等),
    # 这些表的 FK 没有 ON DELETE CASCADE (生产 schema 设计合理,
    # 但测试 fixture 需要强制清理). replica role = 跳过触发器/FK 检查,
    # 是 PostgreSQL 标准 bulk cleanup 技巧, 只在测试 teardown 用.
    #
    # try/except 防止清理失败掩盖原测试错误.
    try:
        from sqlalchemy import text
        await db.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as sql_delete
        await db.execute(sql_delete(Member).where(Member.id == member.id))
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass


@pytest_asyncio.fixture
async def admin_member(db):
    """创建管理员成员（需 DB），测试结束后清理防 UNIQUE 冲突。

    v0.0.1 修复 (2026-06-30): 改 return 为 yield + teardown, 与 test_member 同 pattern.

    v0.1.0 修改 (2026-07-01): username/password/name 切到测试账号 xiaoqi_testbot.
    原 username="admin"/password="admin123" 与 app/api/v1/knowledge.py:1416 admin 白名单
    (`{"admin", "wangtianzhi"}`) 撞车, 易被 admin bypass 路径误命中. 改用 TEST_BOT_* 常量 —
    生产 admin (wangtianzhi) 不再被 fixture 隐式关联.
    """
    if SKIP_DB_SETUP:
        pytest.skip("SKIP_DB_SETUP=1：admin_member fixture 不可用")
    member = Member(
        username=TEST_BOT_USERNAME,
        name=TEST_BOT_NAME,
        password_hash=get_password_hash(TEST_BOT_PASSWORD),
        role="admin",  # 保留 hardcoded, 不引用 TEST_BOT_ROLE — fixture 与 conftest 常量最小耦合
        is_active=True,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    yield member    # ← 改 return → yield (触发 teardown)
    try:
        from sqlalchemy import text
        await db.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as sql_delete
        await db.execute(sql_delete(Member).where(Member.id == member.id))
        await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass


@pytest_asyncio.fixture
def auth_headers(test_member):
    """普通用户的认证 headers（需 DB）"""
    if SKIP_DB_SETUP:
        pytest.skip("SKIP_DB_SETUP=1：auth_headers fixture 不可用")
    token = create_access_token(data={"sub": str(test_member.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def admin_headers(admin_member):
    """管理员的认证 headers（需 DB）"""
    if SKIP_DB_SETUP:
        pytest.skip("SKIP_DB_SETUP=1：admin_headers fixture 不可用")
    token = create_access_token(data={"sub": str(admin_member.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def mock_embedding():
    """固定 192 维向量（不需 DB）"""
    import numpy as np
    return np.random.randn(192).astype(np.float32).tolist()


# === W62 T1 (2026-07-22) baseline 9 files 锚点 ===
# 与 docs/2026-07-22-baseline-13-stats.md 表格同步.
# 9 文件合跑 SKIP_DB_SETUP=1 模式产出 71 PASS + 7 SKIP (W62 第 24 次守恒).
# Agent 3 audit (commit pending) 验证全部存在 + pytest --collect-only = 78.
#
# 用法 (main repo audit 时):
#   SKIP_DB_SETUP=1 pytest $(printf ' %s' "${BASELINE_9_FILES[@]}") -v
#   # 等价: SKIP_DB_SETUP=1 pytest tests/test_meeting_transcript_buffer.py \
#   #       tests/test_orphan_meeting_cleanup_audio_chunks.py ... (9 个)
#
# 不要修改本列表除非同步更新 docs/2026-07-22-baseline-13-stats.md 表格.
# 已删文件 (Self-RAG / 5th-wave / 4th-wave / Phase 1 / 活动动态+模板) 不应在
# 本列表, 详见 tests/test_baseline_audit.py STALE_BASELINE_PATTERNS.
BASELINE_9_FILES = [
    "tests/test_meeting_transcript_buffer.py",                # 2 cases
    "tests/test_orphan_meeting_cleanup_audio_chunks.py",      # 9 cases
    "tests/test_meeting_recording_user_agent.py",             # 10 cases
    "tests/test_meeting_recording_audio_chunk_auth.py",       # 8 cases
    "tests/test_meeting_recording_cancel.py",                 # 8 cases
    "tests/test_chat_history_tasks.py",                       # 7 cases
    "tests/test_chat_share_cleanup.py",                       # 8 cases
    "tests/test_kb_dedup_admin_cli.py",                       # 19 cases
    "tests/scripts/test_kb_dedup_admin_cli_e2e.py",           # 7 cases (7 SKIP)
]


def get_baseline_9_files():
    """返回 9 baseline 文件的 pytest 命令行参数 (含 tests/scripts/ 子目录).

    用途: 给 audit / verify / CI 脚本动态生成 pytest 命令.
    Returns:
        list[str]: 9 文件绝对路径或相对路径 (相对于 conftest.py 父目录)
    """
    return list(BASELINE_9_FILES)


@pytest.fixture
def baseline_9_files():
    """pytest fixture: 提供 9 baseline 文件列表给测试使用.

    测试用法:
        def test_x(baseline_9_files):
            assert len(baseline_9_files) == 9
    """
    return list(BASELINE_9_FILES)

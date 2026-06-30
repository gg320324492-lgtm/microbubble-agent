"""测试配置和公共 fixtures

通过设置环境变量 SKIP_DB_SETUP=1 可跳过 DB 初始化与重型 import，
适用于纯 mock/单元测试（如 LLM 工具调用测试）。

注意：当 SKIP_DB_SETUP=1 时，db / client / test_member / admin_member / auth_headers / admin_headers
这些 fixture 不可用，调用它们的测试会被跳过。
"""

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

    TEST_DB_URL = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:password@localhost:5432/microbubble_test",
    )
    engine = create_async_engine(TEST_DB_URL, echo=False)
    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
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


if SKIP_DB_SETUP:
    @pytest.fixture(scope="session", autouse=True)
    def setup_db():
        """SKIP_DB_SETUP=1 时使用同步 fixture，避免 async teardown 绑定已关闭事件循环。"""
        yield
else:
    @pytest_asyncio.fixture(scope="session", autouse=True)
    async def setup_db():
        """创建测试表。"""
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest_asyncio.fixture
async def db():
    """每个测试独立的数据库会话（需 DB）"""
    if SKIP_DB_SETUP:
        pytest.skip("SKIP_DB_SETUP=1：db fixture 不可用")
    async with TestSession() as session:
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
    """
    if SKIP_DB_SETUP:
        pytest.skip("SKIP_DB_SETUP=1：admin_member fixture 不可用")
    member = Member(
        username="admin",
        name="管理员",
        password_hash=get_password_hash("admin123"),
        role="admin",
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

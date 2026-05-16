"""测试配置和公共 fixtures"""

import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.core.database import Base, get_db
from app.core.security import get_password_hash, create_access_token
from app.models.member import Member
from app.main import app

# 使用内存数据库测试（需要 aiosqlite）
# 由于项目使用 PostgreSQL 特有类型（ARRAY, Vector），测试需要真实 PostgreSQL
# 这里使用环境变量指定测试数据库

import os
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:password@localhost:5432/microbubble_test"
)

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """创建测试表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db():
    """每个测试独立的数据库会话"""
    async with TestSession() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db):
    """异步测试客户端"""

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_member(db):
    """创建测试成员"""
    member = Member(
        username="testuser",
        name="测试用户",
        password_hash=get_password_hash("test123456"),
        role="member",
        grade="研一",
        is_active=True
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@pytest_asyncio.fixture
async def admin_member(db):
    """创建管理员成员"""
    member = Member(
        username="admin",
        name="管理员",
        password_hash=get_password_hash("admin123"),
        role="admin",
        is_active=True
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    return member


@pytest_asyncio.fixture
def auth_headers(test_member):
    """普通用户的认证 headers"""
    token = create_access_token(data={"sub": str(test_member.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
def admin_headers(admin_member):
    """管理员的认证 headers"""
    token = create_access_token(data={"sub": str(admin_member.id)})
    return {"Authorization": f"Bearer {token}"}

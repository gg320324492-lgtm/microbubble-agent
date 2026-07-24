"""tests/test_drive_pr9_comment_delete.py — Drive v2 PR9 续 评论软删 e2e 测试 (2026-07-24, W68 第 12 批 C-2)

6 场景:
1. author 删自己评论 → 204, 软删成功
2. 文件 owner 删评论 → 204 (非 author 但 owner)
3. 平台 admin 删评论 → 204 (非 author 非 owner 但 admin)
4. 普通成员删别人评论 → 403
5. 不存在评论 ID 删 → 404
6. 已软删评论再次删 → 404 (幂等)

设计说明 (W68 第 12 批 C-2):
- 自包含 fixtures (drive_file / author / second / admin), 不依赖 conftest.test_member
  原因: conftest.test_member 在 alembic 057 (wechat_id NOT NULL) 之后未更新,
  所有用 test_member 的旧测试也 fail (pre-existing infra bug, 与本 PR 无关).
- 用 pytest_asyncio fixture 而非依赖共享 db fixture, 自己管理 transaction
- 完整 teardown: SET session_replication_role = 'replica' + DELETE

依赖:
- 模型: app/models/drive_comment.py: DriveComment
- service: app/services/drive_comment_service.py
- API: app/api/v1/drive_comments.py
- alembic: 070_drive_comments_soft_delete.py (deleted_at + deleted_by)
"""
import asyncio
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.security import create_access_token, get_password_hash
from app.main import app as fastapi_app
from app.models.drive_comment import DriveComment
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.models.member import Member

import app.models  # noqa: F401, E402  # 触发所有 model 注册

# === 测试 DB 配置 ===
import os
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:microbubble2026@db:5432/microbubble_test",
)


# ==========================================================================
# 自包含 fixtures (不依赖 conftest.py 中已坏掉的 test_member)
# ==========================================================================


@pytest_asyncio.fixture
async def test_engine():
    """测试用 async engine"""
    engine = create_async_engine(TEST_DATABASE_URL)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db(test_engine):
    """测试 session (独立于 conftest.py 的 db, 不共享 SKIP_DB_SETUP)"""
    Session = async_sessionmaker(test_engine, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest_asyncio.fixture
async def author_member(db):
    """author 角色成员 (W68 第 12 批 C-2 自包含)"""
    member = Member(
        username=f"pr9del_author_{uuid.uuid4().hex[:8]}",
        name="C-2 author 用户",
        password_hash=get_password_hash("test123456"),
        role="member",
        grade="研一",
        wechat_id=f"wx_pr9del_author_{uuid.uuid4().hex[:8]}",  # alembic 057 NOT NULL
        is_active=True,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    yield member
    # teardown
    try:
        from sqlalchemy import text
        await db.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as sql_delete
        await db.execute(sql_delete(Member).where(Member.id == member.id))
        await db.commit()
    except Exception:
        pass


@pytest_asyncio.fixture
def author_headers(author_member):
    """author 认证 headers"""
    token = create_access_token(data={"sub": str(author_member.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def second_member(db):
    """第二个测试成员 (普通成员, 试图删别人的评论)"""
    member = Member(
        username=f"pr9del_second_{uuid.uuid4().hex[:8]}",
        name="第二个用户",
        password_hash=get_password_hash("test123456"),
        role="member",
        grade="研二",
        wechat_id=f"wx_pr9del_second_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    yield member
    try:
        from sqlalchemy import text
        await db.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as sql_delete
        await db.execute(sql_delete(Member).where(Member.id == member.id))
        await db.commit()
    except Exception:
        pass


@pytest_asyncio.fixture
def second_headers(second_member):
    return {"Authorization": f"Bearer {create_access_token(data={'sub': str(second_member.id)})}"}


@pytest_asyncio.fixture
async def admin_member(db):
    """平台 admin 成员"""
    member = Member(
        username=f"pr9del_admin_{uuid.uuid4().hex[:8]}",
        name="平台管理员",
        password_hash=get_password_hash("test123456"),
        role="admin",
        grade="教授",
        wechat_id=f"wx_pr9del_admin_{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(member)
    await db.commit()
    await db.refresh(member)
    yield member
    try:
        from sqlalchemy import text
        await db.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as sql_delete
        await db.execute(sql_delete(Member).where(Member.id == member.id))
        await db.commit()
    except Exception:
        pass


@pytest_asyncio.fixture
def admin_headers(admin_member):
    return {"Authorization": f"Bearer {create_access_token(data={'sub': str(admin_member.id)})}"}


@pytest_asyncio.fixture
async def drive_folder(db, author_member):
    """drive folder (public 让其他用户能访问)"""
    folder = Folder(
        name=f"drive_pr9del_folder_{uuid.uuid4().hex[:8]}",
        owner_id=author_member.id,
        visibility="public",
    )
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    yield folder
    try:
        from sqlalchemy import text
        await db.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as sql_delete
        await db.execute(sql_delete(Folder).where(Folder.id == folder.id))
        await db.commit()
    except Exception:
        pass


@pytest_asyncio.fixture
async def drive_file(db, author_member, drive_folder):
    """drive file (storage_mode='drive', created_by=author_member)"""
    file_row = Knowledge(
        title=f"drive_pr9del_{uuid.uuid4().hex[:8]}",
        content="drive_pr9del 测试文件内容",
        file_name=f"drive_pr9del_{uuid.uuid4().hex[:8]}.pdf",
        file_path=f"/tmp/drive_pr9del_{uuid.uuid4().hex[:8]}.pdf",
        file_size=1024,
        file_type="pdf",
        created_by=author_member.id,
        folder_id=drive_folder.id,
        visibility="public",
        storage_mode="drive",
    )
    db.add(file_row)
    await db.commit()
    await db.refresh(file_row)
    yield file_row
    try:
        from sqlalchemy import text
        await db.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as sql_delete
        await db.execute(sql_delete(Knowledge).where(Knowledge.id == file_row.id))
        await db.commit()
    except Exception:
        pass


@pytest_asyncio.fixture
async def client(db):
    """异步测试客户端 (ASGI transport)"""
    async def override_get_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    fastapi_app.dependency_overrides.clear()


# ==========================================================================
# 场景 1: author 删自己评论 → 204
# ==========================================================================


@pytest.mark.asyncio
async def test_author_can_delete_own_comment(
    client, author_headers, drive_file
):
    """场景 1: author 本人删自己的评论 → 204"""
    # author 创建评论
    r1 = await client.post(
        "/api/v1/drive/comments",
        headers=author_headers,
        json={"file_id": drive_file.id, "content": "author 自己的评论"},
    )
    assert r1.status_code == 201, f"创建评论失败: {r1.text}"
    cid = r1.json()["id"]

    # author 删除
    r2 = await client.delete(
        f"/api/v1/drive/comments/{cid}",
        headers=author_headers,
    )
    assert r2.status_code == 204, (
        f"author 应能删自己的评论, 实际 {r2.status_code}: {r2.text}"
    )


# ==========================================================================
# 场景 2: 文件 owner 删别人评论 → 204
# ==========================================================================


@pytest.mark.asyncio
async def test_file_owner_can_delete_others_comment(
    client, author_headers, second_headers, drive_file
):
    """场景 2: 文件 owner (author_member) 删 second_member 的评论 → 204"""
    # second_member 创建评论 (public folder 允许)
    r1 = await client.post(
        "/api/v1/drive/comments",
        headers=second_headers,
        json={"file_id": drive_file.id, "content": "second_member 的评论"},
    )
    assert r1.status_code == 201, f"second 创建评论失败: {r1.text}"
    cid = r1.json()["id"]

    # file owner (author_member) 删
    r2 = await client.delete(
        f"/api/v1/drive/comments/{cid}",
        headers=author_headers,
    )
    assert r2.status_code == 204, (
        f"file owner 应能删评论, 实际 {r2.status_code}: {r2.text}"
    )


# ==========================================================================
# 场景 3: 平台 admin 删评论 → 204
# ==========================================================================


@pytest.mark.asyncio
async def test_platform_admin_can_delete_others_comment(
    client, author_headers, admin_headers, drive_file
):
    """场景 3: 平台 admin 删评论 (既非 author 也非 file owner) → 204"""
    # author_member 创建评论
    r1 = await client.post(
        "/api/v1/drive/comments",
        headers=author_headers,
        json={"file_id": drive_file.id, "content": "test_member 的评论"},
    )
    assert r1.status_code == 201
    cid = r1.json()["id"]

    # admin 删除
    r2 = await client.delete(
        f"/api/v1/drive/comments/{cid}",
        headers=admin_headers,
    )
    assert r2.status_code == 204, (
        f"平台 admin 应能删, 实际 {r2.status_code}: {r2.text}"
    )


# ==========================================================================
# 场景 4: 普通成员删别人评论 → 403
# ==========================================================================


@pytest.mark.asyncio
async def test_regular_member_cannot_delete_others_comment(
    client, author_headers, second_headers, drive_file
):
    """场景 4: second_member (普通成员) 删 author_member 的评论 → 403

    关键: second_member 不是 author, 不是 file owner (file.created_by != second),
    不是平台 admin (role=member) → 应被拒
    """
    # author_member 创建评论
    r1 = await client.post(
        "/api/v1/drive/comments",
        headers=author_headers,
        json={"file_id": drive_file.id, "content": "author 评论 (second 不能删)"},
    )
    assert r1.status_code == 201
    cid = r1.json()["id"]

    # second_member 试图删 → 应 403
    r2 = await client.delete(
        f"/api/v1/drive/comments/{cid}",
        headers=second_headers,
    )
    assert r2.status_code == 403, (
        f"普通成员删应被拒, 实际 {r2.status_code}: {r2.text}"
    )


# ==========================================================================
# 场景 5: 不存在评论 ID 删 → 404
# ==========================================================================


@pytest.mark.asyncio
async def test_delete_nonexistent_comment_returns_404(
    client, author_headers, drive_file
):
    """场景 5: 删不存在的评论 ID → 404"""
    r = await client.delete(
        "/api/v1/drive/comments/99999999",
        headers=author_headers,
    )
    assert r.status_code == 404, f"删不存在评论应 404, 实际 {r.status_code}: {r.text}"


# ==========================================================================
# 场景 6: 已软删评论再次删 → 404 (幂等)
# ==========================================================================


@pytest.mark.asyncio
async def test_re_delete_soft_deleted_comment_returns_404(
    client, author_headers, drive_file
):
    """场景 6: 已软删评论再次删 → 404 (幂等)"""
    # author 创建 + 删除
    r1 = await client.post(
        "/api/v1/drive/comments",
        headers=author_headers,
        json={"file_id": drive_file.id, "content": "将被删两次"},
    )
    assert r1.status_code == 201
    cid = r1.json()["id"]

    r2 = await client.delete(
        f"/api/v1/drive/comments/{cid}",
        headers=author_headers,
    )
    assert r2.status_code == 204

    # 再次删 → 应 404 (幂等: 已软删视为不存在)
    r3 = await client.delete(
        f"/api/v1/drive/comments/{cid}",
        headers=author_headers,
    )
    assert r3.status_code == 404, (
        f"重复删应 404, 实际 {r3.status_code}: {r3.text}"
    )
"""PR2.9 drive_tools.py pytest (2026-07-01)

测试 Agent 工具的隐私边界:
- list_drive_files: private 仅 owner 可见, team/public 全员可见
- search_my_files: 仅搜 created_by=current_user 的文件
"""
import asyncio
import pytest
import pytest_asyncio
import uuid as _uuid_lib
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from app.config import settings
from app.models.member import Member
from app.models.knowledge import Knowledge
from app.models.folder import Folder
from app.agent.tool_registry import ToolContext
from app.agent.tools.drive_tools import list_drive_files, search_my_files


# === ToolContext 兼容 (复用 conftest 模式) ===
@pytest_asyncio.fixture
async def db_session():
    url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session, factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def alice_bob(db_session):
    session, factory = db_session
    u = _uuid_lib.uuid4().hex[:8]
    u_alice = f"alice_drt_{u}"
    u_bob = f"bob_drt_{u}"

    alice = Member(
        username=u_alice, name="Alice Drive Tool Test",
        password_hash="hash", role="member", grade="测试", is_active=True,
        # 2026-07-21 W2 P0 修类 2: PR6-P17 wechat_id NOT NULL schema drift
        wechat_id=f"__TEST_BACKFILL_{u}_alice__",
    )
    bob = Member(
        username=u_bob, name="Bob Drive Tool Test",
        password_hash="hash", role="member", grade="测试", is_active=True,
        wechat_id=f"__TEST_BACKFILL_{u}_bob__",
    )
    session.add_all([alice, bob])
    await session.commit()
    await session.refresh(alice)
    await session.refresh(bob)

    yield {"alice": alice, "bob": bob, "factory": factory, "u": u}

    try:
        await session.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as _del
        await session.execute(_del(Knowledge).where(Knowledge.created_by.in_([alice.id, bob.id])))
        await session.execute(_del(Member).where(Member.id.in_([alice.id, bob.id])))
        await session.execute(text("RESET session_replication_role"))
        await session.commit()
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass


def _make_ctx(db, user_id):
    """构造 ToolContext (字段名: db / user_id, 看 tool_registry.py 实际签名)"""
    return ToolContext(db=db, user_id=user_id)


# === 实际测试 ===

@pytest.mark.asyncio
async def test_list_drive_files_private_only_owner_sees(alice_bob):
    """private 文件仅 owner 可见"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    bob = alice_bob["bob"]
    u = alice_bob["u"]
    async with factory() as session:
        # alice 创建 1 private + 1 team
        for vis in ("private", "team"):
            k = Knowledge(
                title=f"alice_drive_{vis}_{u}",
                content="[drive test]",
                file_path=f"drive/test_{vis}.txt",
                file_name=f"test_{vis}.txt",
                file_type=".txt",
                storage_mode="drive",
                visibility=vis,
                created_by=alice.id,
                source_type="drive",
            )
            session.add(k)
        await session.commit()

    # alice 查 -> 看到 2 (private + team)
    async with factory() as session:
        ctx = _make_ctx(session, alice.id)
        from app.agent.tools.drive_tools import ListDriveFilesInput
        result = await list_drive_files(
            ListDriveFilesInput(page=1, page_size=20), ctx
        )
        titles = [x["title"] for x in result["items"] if u in x["title"]]
        assert len(titles) == 2
        assert any("private" in t for t in titles)
        assert any("team" in t for t in titles)

    # bob 查 -> 看到 1 (只有 team, private 隐身)
    async with factory() as session:
        ctx = _make_ctx(session, bob.id)
        from app.agent.tools.drive_tools import ListDriveFilesInput
        result = await list_drive_files(
            ListDriveFilesInput(page=1, page_size=20), ctx
        )
        titles = [x["title"] for x in result["items"] if u in x["title"]]
        assert len(titles) == 1
        assert "team" in titles[0]
        assert "private" not in titles[0]


@pytest.mark.asyncio
async def test_list_drive_files_excludes_kb(alice_bob):
    """list_drive_files 只返 storage_mode=drive, 不含 kb"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    u = alice_bob["u"]
    async with factory() as session:
        # alice 创建 1 drive + 1 kb
        k_drive = Knowledge(
            title=f"alice_drive_{u}", content="[drive test]",
            file_path="drive/a.txt", file_name="a.txt",
            file_type=".txt", storage_mode="drive", visibility="team",
            created_by=alice.id, source_type="drive",
        )
        k_kb = Knowledge(
            title=f"alice_kb_{u}", content="[kb test]",
            storage_mode="kb", visibility="team",
            created_by=alice.id, source_type="conversation",
        )
        session.add_all([k_drive, k_kb])
        await session.commit()

    async with factory() as session:
        ctx = _make_ctx(session, alice.id)
        from app.agent.tools.drive_tools import ListDriveFilesInput
        result = await list_drive_files(
            ListDriveFilesInput(page=1, page_size=20), ctx
        )
        titles = [x["title"] for x in result["items"] if u in x["title"]]
        assert len(titles) == 1
        assert "drive" in titles[0]
        assert "kb" not in titles[0]


@pytest.mark.asyncio
async def test_search_my_files_only_current_user(alice_bob):
    """search_my_files 仅搜 created_by=current_user"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    bob = alice_bob["bob"]
    u = alice_bob["u"]
    async with factory() as session:
        # alice + bob 各建一个含 ozone 的 drive file
        for owner in (alice, bob):
            k = Knowledge(
                title=f"ozone_paper_{u}", content="[drive test]",
                file_path=f"drive/{owner.username}_o3.txt",
                file_name=f"{owner.username}_o3.txt", file_type=".txt",
                storage_mode="drive", visibility="team",
                created_by=owner.id, source_type="drive",
            )
            session.add(k)
        await session.commit()

    # alice 搜 -> 看到自己那个 (file_name 含 "alice_"), 看不到 bob 的
    async with factory() as session:
        ctx = _make_ctx(session, alice.id)
        from app.agent.tools.drive_tools import SearchMyFilesInput
        result = await search_my_files(
            SearchMyFilesInput(query="ozone"), ctx
        )
        items = [x for x in result["items"] if u in x["title"]]
        assert len(items) == 1
        # alice 创建的 file_name 含 "alice_drv_"
        assert "alice_drt_" in items[0]["file_name"]
        assert "bob_drt_" not in items[0]["file_name"]

    # bob 搜 -> 看到自己那个
    async with factory() as session:
        ctx = _make_ctx(session, bob.id)
        from app.agent.tools.drive_tools import SearchMyFilesInput
        result = await search_my_files(
            SearchMyFilesInput(query="ozone"), ctx
        )
        items = [x for x in result["items"] if u in x["title"]]
        assert len(items) == 1
        assert "bob_drt_" in items[0]["file_name"]


@pytest.mark.asyncio
async def test_search_my_files_match_filename(alice_bob):
    """搜 file_name 而非 title 也能匹配"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    u = alice_bob["u"]
    async with factory() as session:
        k = Knowledge(
            title=f"unrelated_{u}", content="[drive test]",
            file_path="drive/secret_ozone_report.pdf",
            file_name="secret_ozone_report.pdf",  # 含 ozone
            file_type=".pdf",
            storage_mode="drive", visibility="team",
            created_by=alice.id, source_type="drive",
        )
        session.add(k)
        await session.commit()

    async with factory() as session:
        ctx = _make_ctx(session, alice.id)
        from app.agent.tools.drive_tools import SearchMyFilesInput
        result = await search_my_files(
            SearchMyFilesInput(query="ozone"), ctx
        )
        titles = [x["title"] for x in result["items"] if u in x["title"]]
        assert len(titles) == 1
        assert result["items"][0]["file_name"] == "secret_ozone_report.pdf"

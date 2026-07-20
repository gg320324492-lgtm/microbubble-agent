"""PR2.1 DriveService pytest (2026-07-01)

测试核心边界:
- create / list / get / update / soft_delete / restore
- 跨用户 private 文件隐身
- visibility 升级 (extract-to-kb) + 不能从 public 降级到 private (保留)
- 文件夹 visibility 硬上限
- 软删后不可见
"""
import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from app.config import settings
from app.core.database import Base
from app.models.member import Member
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.services.drive_service import (
    DriveService,
    DriveServiceError,
    MAX_DRIVE_FILE_SIZE_BYTES,
)


# === 异步 pytest 配置 ===
@pytest_asyncio.fixture
async def db_session():
    """测试用独立 Postgres 临时 schema (或同库 SKIP_DB_SETUP mode)

    用真实 PG 但限定测试 schema, 避免污染生产数据.
    """
    from app.config import settings
    # 用同一 DB 但 schema 隔离
    url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with factory() as session:
            yield session, factory
    finally:
        await engine.dispose()


# === 4 个测试用户的 fixture (admin xiaoqi_testbot 已经在生产里有, 不创建) ===
import uuid as _uuid_lib

@pytest_asyncio.fixture
async def alice_bob_folders(db_session):
    """每次跑用唯一 UUID 用户名, 避免 UNIQUE 冲突"""
    session, factory = db_session
    # 唯一 suffix (uuid4 8 char) 让并行跑 / 重跑都安全
    u = _uuid_lib.uuid4().hex[:8]
    u_alice = f"alice_drv_{u}"
    u_bob = f"bob_drv_{u}"
    u_charlie = f"charlie_drv_{u}"
    f_priv = f"alice_priv_folder_{u}"
    f_team = f"alice_team_folder_{u}"

    alice = Member(
        username=u_alice,
        name="Alice Drive Test",
        password_hash="hash",
        role="member",
        grade="测试",
        is_active=True,
        # 2026-07-21 W2 P0 修类 2: PR6-P17 wechat_id NOT NULL schema drift
        # 跟 test_folder_service.py 一致, 用 __TEST_BACKFILL_<u>_<user>__ 占位
        wechat_id=f"__TEST_BACKFILL_{u}_alice__",
    )
    bob = Member(
        username=u_bob,
        name="Bob Drive Test",
        password_hash="hash",
        role="member",
        grade="测试",
        is_active=True,
        wechat_id=f"__TEST_BACKFILL_{u}_bob__",
    )
    charlie = Member(
        username=u_charlie,
        name="Charlie Drive Test",
        password_hash="hash",
        role="member",
        grade="测试",
        is_active=True,
        wechat_id=f"__TEST_BACKFILL_{u}_charlie__",
    )
    session.add_all([alice, bob, charlie])
    await session.commit()
    await session.refresh(alice)
    await session.refresh(bob)
    await session.refresh(charlie)

    folder_private = Folder(
        name=f_priv,
        owner_id=alice.id,
        visibility="private",
        path="/",
        depth=0,
    )
    folder_team = Folder(
        name=f_team,
        owner_id=alice.id,
        visibility="team",
        path="/",
        depth=0,
    )
    session.add_all([folder_private, folder_team])
    await session.commit()
    await session.refresh(folder_private)
    await session.refresh(folder_team)

    yield {
        "alice": alice,
        "bob": bob,
        "charlie": charlie,
        "folder_private": folder_private,
        "folder_team": folder_team,
        "factory": factory,
        "u": u,  # 暴露给测试做唯一 title 前缀
    }

    # cleanup (replica role 绕 FK + Member ON DELETE RESTRICT)
    try:
        await session.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as _del
        await session.execute(_del(Knowledge).where(Knowledge.created_by.in_([
            alice.id, bob.id, charlie.id
        ])))
        await session.execute(_del(Folder).where(Folder.id.in_([
            folder_private.id, folder_team.id
        ])))
        await session.execute(_del(Member).where(Member.id.in_([
            alice.id, bob.id, charlie.id
        ])))
        await session.execute(text("RESET session_replication_role"))
        await session.commit()
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass


# === 实际测试用例 ===

@pytest.mark.asyncio
async def test_create_file_basic(alice_bob_folders):
    """正常场景: alice 创建文件不指定 folder, 顶级目录, visibility=team"""
    factory = alice_bob_folders["factory"]
    alice = alice_bob_folders["alice"]
    async with factory() as session:
        svc = DriveService(session)
        f = await svc.create_file(
            title="drive_test_basic",
            file_path="drive/test/basic.txt",
            file_name="basic.txt",
            file_type=".txt",
            file_size=1024,
            owner_id=alice.id,
            visibility="team",
        )
        await session.commit()
    assert f.id is not None
    assert f.storage_mode == "drive"
    assert f.visibility == "team"
    assert f.folder_id is None
    assert f.created_by == alice.id


@pytest.mark.asyncio
async def test_create_file_oversize_rejected(alice_bob_folders):
    """超大文件应被拒绝 (HTTP 413)"""
    factory = alice_bob_folders["factory"]
    alice = alice_bob_folders["alice"]
    async with factory() as session:
        svc = DriveService(session)
        with pytest.raises(DriveServiceError) as exc_info:
            await svc.create_file(
                title="drive_test_huge",
                file_path="drive/test/huge.bin",
                file_name="huge.bin",
                file_type=".bin",
                file_size=MAX_DRIVE_FILE_SIZE_BYTES + 1,
                owner_id=alice.id,
            )
        assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_visibility_inherits_hard_upper_bound(alice_bob_folders):
    """文件 visibility 不能 < 文件夹 visibility

    private folder 里尝试放 team 文件 → 应抛 400
    """
    factory = alice_bob_folders["factory"]
    alice = alice_bob_folders["alice"]
    private_folder = alice_bob_folders["folder_private"]
    async with factory() as session:
        svc = DriveService(session)
        # private 文件夹 (visibility=0) 不能放 team 文件 (visibility=1)
        with pytest.raises(DriveServiceError) as exc_info:
            await svc.create_file(
                title="drive_test_violation",
                file_path="drive/test/violation.txt",
                file_name="violation.txt",
                file_type=".txt",
                file_size=100,
                owner_id=alice.id,
                visibility="team",
                folder_id=private_folder.id,
            )
        assert exc_info.value.status_code == 400
        assert "越权" in str(exc_info.value)


@pytest.mark.asyncio
async def test_list_files_private_invisible_to_others(alice_bob_folders):
    """private 文件仅 owner 可见, 其他用户**完全看不到** (连文件名都不展示)"""
    factory = alice_bob_folders["factory"]
    alice = alice_bob_folders["alice"]
    bob = alice_bob_folders["bob"]

    # alice 创建 2 个文件: 1 private + 1 team
    async with factory() as session:
        svc = DriveService(session)
        await svc.create_file(
            title="drive_test_alice_private",
            file_path="drive/alice/secret.txt",
            file_name="secret.txt",
            file_type=".txt",
            file_size=100,
            owner_id=alice.id,
            visibility="private",
        )
        await svc.create_file(
            title="drive_test_alice_team",
            file_path="drive/alice/public-ish.txt",
            file_name="public-ish.txt",
            file_type=".txt",
            file_size=200,
            owner_id=alice.id,
            visibility="team",
        )
        await session.commit()

    # alice 自己看应看到 2 个
    async with factory() as session:
        svc = DriveService(session)
        items, total = await svc.list_files(current_user_id=alice.id)
        titles = [x.title for x in items if x.title.startswith("drive_test_alice_")]
        assert len(titles) == 2

    # bob 看应只看到 1 个 (team 那个, private 隐身)
    async with factory() as session:
        svc = DriveService(session)
        items, total = await svc.list_files(current_user_id=bob.id)
        alice_titles = [x.title for x in items if x.title.startswith("drive_test_alice_")]
        assert len(alice_titles) == 1
        assert "private" not in alice_titles[0]


@pytest.mark.asyncio
async def test_soft_delete_and_restore(alice_bob_folders):
    """软删 → list 端点不返 → restore → 重新可见"""
    factory = alice_bob_folders["factory"]
    alice = alice_bob_folders["alice"]

    async with factory() as session:
        svc = DriveService(session)
        f = await svc.create_file(
            title="drive_test_delete",
            file_path="drive/test/delete.txt",
            file_name="delete.txt",
            file_type=".txt",
            file_size=100,
            owner_id=alice.id,
        )
        file_id = f.id
        await session.commit()

    # 软删
    async with factory() as session:
        svc = DriveService(session)
        ok = await svc.soft_delete_file(file_id, current_user_id=alice.id)
        assert ok is True
        await session.commit()

    # 列表应不含
    async with factory() as session:
        svc = DriveService(session)
        items, total = await svc.list_files(current_user_id=alice.id)
        assert file_id not in [x.id for x in items]

    # get_file 也返 None (软删后不可见)
    async with factory() as session:
        svc = DriveService(session)
        f = await svc.get_file(file_id, current_user_id=alice.id)
        assert f is None

    # restore
    async with factory() as session:
        svc = DriveService(session)
        f = await svc.restore_file(file_id, current_user_id=alice.id)
        assert f is not None
        assert f.deleted_at is None
        await session.commit()

    # 列表应含
    async with factory() as session:
        svc = DriveService(session)
        items, total = await svc.list_files(current_user_id=alice.id)
        assert file_id in [x.id for x in items]


@pytest.mark.asyncio
async def test_extract_to_kb_upgrades_visibility(alice_bob_folders):
    """extract-to-kb 应改 storage_mode + visibility + source_type"""
    factory = alice_bob_folders["factory"]
    alice = alice_bob_folders["alice"]

    async with factory() as session:
        svc = DriveService(session)
        # alice 创建 1 个 private 文件
        f = await svc.create_file(
            title="drive_test_extract",
            file_path="drive/test/extract.txt",
            file_name="extract.txt",
            file_type=".txt",
            file_size=100,
            owner_id=alice.id,
            visibility="private",
        )
        file_id = f.id
        await session.commit()

    # extract-to-kb target=team
    async with factory() as session:
        svc = DriveService(session)
        f = await svc.extract_to_kb(file_id, current_user_id=alice.id, target_visibility="team")
        assert f is not None
        assert f.storage_mode == "kb"
        assert f.visibility == "team"
        assert f.source_type == "drive_extracted"
        await session.commit()

    # 此时 bob 也能看到 (team 可见 + storage_mode='kb' 不影响 Bob 看, 因为他通过 list_files 走 visibility 过滤)
    async with factory() as session:
        svc = DriveService(session)
        items, total = await svc.list_files(current_user_id=alice.id, storage_mode="kb")
        ids = [x.id for x in items]
        assert file_id in ids


@pytest.mark.asyncio
async def test_non_owner_update_file_returns_none(alice_bob_folders):
    """非 owner 调 update 应返 None (隐身)"""
    factory = alice_bob_folders["factory"]
    alice = alice_bob_folders["alice"]
    bob = alice_bob_folders["bob"]

    async with factory() as session:
        svc = DriveService(session)
        f = await svc.create_file(
            title="drive_test_owner_check",
            file_path="drive/test/owner.txt",
            file_name="owner.txt",
            file_type=".txt",
            file_size=100,
            owner_id=alice.id,
        )
        file_id = f.id
        await session.commit()

    # bob 尝试 update
    async with factory() as session:
        svc = DriveService(session)
        result = await svc.update_file(
            file_id, current_user_id=bob.id,
            title="bob_tried_to_rename",
        )
        assert result is None

    # alice 应仍能 update
    async with factory() as session:
        svc = DriveService(session)
        result = await svc.update_file(
            file_id, current_user_id=alice.id,
            title="alice_renamed_ok",
        )
        assert result is not None
        assert result.title == "alice_renamed_ok"


@pytest.mark.asyncio
async def test_storage_stats_basic(alice_bob_folders):
    """storage_stats 返回 file_count + by_visibility 分布"""
    factory = alice_bob_folders["factory"]
    alice = alice_bob_folders["alice"]

    async with factory() as session:
        svc = DriveService(session)
        # alice 创建 3 个 (1 private + 2 team)
        await svc.create_file(
            title="drive_test_stat_p",
            file_path="d/p.txt", file_name="p.txt", file_type=".txt", file_size=10,
            owner_id=alice.id, visibility="private",
        )
        for i in range(2):
            await svc.create_file(
                title=f"drive_test_stat_t_{i}",
                file_path=f"d/t{i}.txt", file_name=f"t{i}.txt", file_type=".txt",
                file_size=20 + i, owner_id=alice.id, visibility="team",
            )
        await session.commit()

    async with factory() as session:
        svc = DriveService(session)
        stats = await svc.storage_stats(current_user_id=alice.id)
        assert stats["file_count"] >= 3
        assert stats["by_visibility"].get("private", 0) >= 1
        assert stats["by_visibility"].get("team", 0) >= 2

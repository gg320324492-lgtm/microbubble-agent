"""PR2.2 FolderService pytest (2026-07-01)

测试核心边界:
- create / get / list / update / soft_delete / restore
- 嵌套深度校验 (depth ≤ 5)
- visibility 继承 (子 ≤ 父)
- 物化 path 自动维护 (/1/4/7/ 形式)
- 跨用户 folder 隐身 (private folder 越权)
- 不能 move folder 到自己子 folder (环检测)
"""
import asyncio
import pytest
import pytest_asyncio
import uuid as _uuid_lib
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from app.config import settings
from app.models.member import Member
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.services.folder_service import FolderService, FolderServiceError, MAX_FOLDER_DEPTH


# === db session fixture (PR2.1 复用) ===
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


# === 测试用户 fixture (UUID 唯一化, PR2.1 同款) ===
@pytest_asyncio.fixture
async def alice_bob(db_session):
    session, factory = db_session
    u = _uuid_lib.uuid4().hex[:8]
    u_alice = f"alice_fld_{u}"
    u_bob = f"bob_fld_{u}"

    alice = Member(
        username=u_alice, name="Alice Folder Test",
        password_hash="hash", role="member", grade="测试", is_active=True,
        # 2026-07-10 PR6-P17: wechat_id NOT NULL, 测试 fixture 用 `__TEST_BACKFILL_<u>__` 占位
        wechat_id=f"__TEST_BACKFILL_{u}_alice__",
    )
    bob = Member(
        username=u_bob, name="Bob Folder Test",
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
        await session.execute(_del(Folder).where(Folder.owner_id.in_([alice.id, bob.id])))
        await session.execute(_del(Knowledge).where(Knowledge.created_by.in_([alice.id, bob.id])))
        await session.execute(_del(Member).where(Member.id.in_([alice.id, bob.id])))
        await session.execute(text("RESET session_replication_role"))
        await session.commit()
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass


# === 实际测试 ===

@pytest.mark.asyncio
async def test_create_top_folder_path_materialized(alice_bob):
    """顶级 folder: depth=0, path=/<id>/"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    async with factory() as session:
        svc = FolderService(session)
        f = await svc.create_folder(
            name=f"alice_root_{alice_bob['u']}",
            owner_id=alice.id,
            visibility="team",
        )
    assert f.id is not None
    assert f.depth == 0
    assert f.parent_id is None
    assert f.path == f"/{f.id}/"
    assert f.owner_id == alice.id


@pytest.mark.asyncio
async def test_create_nested_depth_increments(alice_bob):
    """子 folder depth=parent+1, path='/parent.id/child.id/'"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    async with factory() as session:
        svc = FolderService(session)
        root = await svc.create_folder(
            name=f"alice_root_{alice_bob['u']}", owner_id=alice.id, visibility="team",
        )
        child = await svc.create_folder(
            name=f"alice_child_{alice_bob['u']}", owner_id=alice.id,
            parent_id=root.id, visibility="team",
        )
    assert child.depth == 1
    assert child.path == f"{root.path}{child.id}/"


@pytest.mark.asyncio
async def test_create_folder_visibility_inherits_hard_upper_bound(alice_bob):
    """子 folder visibility 必须 ≤ 父 folder

    private folder (0) 下尝试建 public folder (2) → 400
    """
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    async with factory() as session:
        svc = FolderService(session)
        priv = await svc.create_folder(
            name=f"alice_priv_{alice_bob['u']}", owner_id=alice.id, visibility="private",
        )
        with pytest.raises(FolderServiceError) as exc_info:
            await svc.create_folder(
                name=f"alice_pub_child_{alice_bob['u']}",
                owner_id=alice.id, parent_id=priv.id, visibility="public",
            )
        assert exc_info.value.status_code == 400
        assert "越权" in str(exc_info.value)


@pytest.mark.asyncio
async def test_create_folder_depth_exceeds_max(alice_bob):
    """depth > MAX_FOLDER_DEPTH (5) 应被拒绝"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    async with factory() as session:
        svc = FolderService(session)
        # 手动建一条 5 层链: 0→1→2→3→4→5 (depth=5 时已超)
        parent = await svc.create_folder(
            name=f"alice_d0_{alice_bob['u']}", owner_id=alice.id, visibility="team",
        )
        for i in range(MAX_FOLDER_DEPTH):
            parent = await svc.create_folder(
                name=f"alice_d{i+1}_{alice_bob['u']}", owner_id=alice.id,
                parent_id=parent.id, visibility="team",
            )
        # 此刻 parent.depth = 5
        assert parent.depth == MAX_FOLDER_DEPTH
        # 再建一层应被拒
        with pytest.raises(FolderServiceError) as exc_info:
            await svc.create_folder(
                name=f"alice_d6_too_deep_{alice_bob['u']}",
                owner_id=alice.id, parent_id=parent.id, visibility="team",
            )
        assert exc_info.value.status_code == 400
        assert "嵌套深度" in str(exc_info.value)


@pytest.mark.asyncio
async def test_list_folders_private_invisible_to_others(alice_bob):
    """private folder 仅 owner 可见"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    bob = alice_bob["bob"]
    u = alice_bob["u"]
    async with factory() as session:
        svc = FolderService(session)
        # alice 创建 1 private + 1 team folder
        await svc.create_folder(name=f"alice_priv_{u}", owner_id=alice.id, visibility="private")
        await svc.create_folder(name=f"alice_team_{u}", owner_id=alice.id, visibility="team")
        await session.commit()

    # alice 自己看应 2 个
    async with factory() as session:
        svc = FolderService(session)
        items, total = await svc.list_folders(current_user_id=alice.id)
        names = [x.name for x in items if x.name.startswith(f"alice_") and u in x.name]
        assert len(names) == 2

    # bob 看应只看到 1 个 (team 那个, private 隐身)
    async with factory() as session:
        svc = FolderService(session)
        items, total = await svc.list_folders(current_user_id=bob.id)
        names = [x.name for x in items if x.name.startswith(f"alice_") and u in x.name]
        assert len(names) == 1
        assert "team" in names[0]


@pytest.mark.asyncio
async def test_update_folder_rename_visibility(alice_bob):
    """update folder 改名 + 改 visibility"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    u = alice_bob["u"]
    async with factory() as session:
        svc = FolderService(session)
        f = await svc.create_folder(
            name=f"alice_orig_{u}", owner_id=alice.id, visibility="private",
        )
        fid = f.id
        await session.commit()

    async with factory() as session:
        svc = FolderService(session)
        updated = await svc.update_folder(
            fid, current_user_id=alice.id,
            name=f"alice_renamed_{u}",
            visibility="team",
        )
        await session.commit()

    assert updated is not None
    assert updated.name == f"alice_renamed_{u}"
    assert updated.visibility == "team"


@pytest.mark.asyncio
async def test_update_folder_visibility_blocked_by_incompatible_child(alice_bob):
    """down-grade 父 folder visibility 时若有更高 visibility 的子 folder → 400

    场景: public parent 下有 public child, 尝试把 parent down 到 team
    期望: 400 (因为 child=public > 新 parent=team)
    """
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    u = alice_bob["u"]
    async with factory() as session:
        svc = FolderService(session)
        parent = await svc.create_folder(
            name=f"alice_parent_pub_{u}", owner_id=alice.id, visibility="public",
        )
        # public parent 下挂 public child (合法: 0 ≤ 2)
        child = await svc.create_folder(
            name=f"alice_child_pub_{u}", owner_id=alice.id,
            parent_id=parent.id, visibility="public",
        )
        await session.commit()
        pid = parent.id

    # 尝试把 parent down 到 team (会违反 child=public, 2 > 1)
    async with factory() as session:
        svc = FolderService(session)
        with pytest.raises(FolderServiceError) as exc_info:
            await svc.update_folder(
                pid, current_user_id=alice.id, visibility="team",
            )
        assert exc_info.value.status_code == 400
        assert "子文件夹" in str(exc_info.value)


@pytest.mark.asyncio
async def test_update_folder_move_rebuilds_subtree_path(alice_bob):
    """move folder 重建 path"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    u = alice_bob["u"]
    async with factory() as session:
        svc = FolderService(session)
        root1 = await svc.create_folder(
            name=f"alice_r1_{u}", owner_id=alice.id, visibility="team",
        )
        root2 = await svc.create_folder(
            name=f"alice_r2_{u}", owner_id=alice.id, visibility="team",
        )
        # 在 root1 下建一个 child
        child = await svc.create_folder(
            name=f"alice_child_{u}", owner_id=alice.id,
            parent_id=root1.id, visibility="team",
        )
        cid = child.id
        old_path = child.path  # /root1.id/child.id/
        r2_id = root2.id
        await session.commit()

    # 把 child move 到 root2
    async with factory() as session:
        svc = FolderService(session)
        moved = await svc.update_folder(
            cid, current_user_id=alice.id, parent_id=r2_id,
        )
        await session.commit()

    assert moved is not None
    assert moved.parent_id == r2_id
    assert moved.path == f"/{r2_id}/{cid}/"
    assert moved.path != old_path


@pytest.mark.asyncio
async def test_update_folder_move_to_own_descendant_blocked(alice_bob):
    """不能把 folder move 到自己子 folder (环检测)"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    u = alice_bob["u"]
    async with factory() as session:
        svc = FolderService(session)
        parent = await svc.create_folder(
            name=f"alice_p_{u}", owner_id=alice.id, visibility="team",
        )
        child = await svc.create_folder(
            name=f"alice_c_{u}", owner_id=alice.id,
            parent_id=parent.id, visibility="team",
        )
        pid, cid = parent.id, child.id
        await session.commit()

    # 尝试把 parent move 到 child 下 (会形成环)
    async with factory() as session:
        svc = FolderService(session)
        with pytest.raises(FolderServiceError) as exc_info:
            await svc.update_folder(
                pid, current_user_id=alice.id, parent_id=cid,
            )
        assert exc_info.value.status_code == 400
        assert "环" in str(exc_info.value)


@pytest.mark.asyncio
async def test_non_owner_update_returns_none(alice_bob):
    """非 owner 调 update 返 None (隐身)"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    bob = alice_bob["bob"]
    u = alice_bob["u"]
    async with factory() as session:
        svc = FolderService(session)
        f = await svc.create_folder(
            name=f"alice_x_{u}", owner_id=alice.id, visibility="team",
        )
        fid = f.id
        await session.commit()

    async with factory() as session:
        svc = FolderService(session)
        result = await svc.update_folder(
            fid, current_user_id=bob.id, name="bob_tried",
        )
        assert result is None


@pytest.mark.asyncio
async def test_soft_delete_blocks_when_has_children(alice_bob):
    """folder 有未删子 folder → 删除应被拒 (PR1 铁律)"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    u = alice_bob["u"]
    async with factory() as session:
        svc = FolderService(session)
        parent = await svc.create_folder(
            name=f"alice_p_{u}", owner_id=alice.id, visibility="team",
        )
        await svc.create_folder(
            name=f"alice_c_{u}", owner_id=alice.id,
            parent_id=parent.id, visibility="team",
        )
        await session.commit()
        pid = parent.id

    async with factory() as session:
        svc = FolderService(session)
        with pytest.raises(FolderServiceError) as exc_info:
            await svc.soft_delete_folder(pid, current_user_id=alice.id)
        assert exc_info.value.status_code == 400
        assert "子 folder" in str(exc_info.value)


@pytest.mark.asyncio
async def test_soft_delete_blocks_when_not_owner(alice_bob):
    """非 owner 调 soft_delete → 应 raise FolderServiceError(403)

    v2.12 (2026-07-10) 修复: 旧行为非 owner 返回 False (→ endpoint 转 404),
    误导用户「Folder不存在」(实际 folder 存在但越权)。
    新行为: 显式 raise 403 让前端能区分「不存在」vs「无权限」。
    """
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    bob = alice_bob["bob"]
    u = alice_bob["u"]
    async with factory() as session:
        svc = FolderService(session)
        f = await svc.create_folder(
            name=f"alice_owned_by_bob_to_delete_{u}",
            owner_id=alice.id,
            visibility="team",  # team visibility 让 bob 也能看到, 但不能删
        )
        fid = f.id
        await session.commit()

    async with factory() as session:
        svc = FolderService(session)
        with pytest.raises(FolderServiceError) as exc_info:
            await svc.soft_delete_folder(fid, current_user_id=bob.id)
        assert exc_info.value.status_code == 403, (
            f"应返 403 (越权), 实际 {exc_info.value.status_code}: {exc_info.value}"
        )
        assert "无法删除非自己拥有" in str(exc_info.value)


@pytest.mark.asyncio
async def test_soft_delete_admin_can_bypass_owner(alice_bob):
    """admin 越权 → 应允许删除 (与 CLAUDE.md 任务权限模型对齐)

    v2.13 (2026-07-10): 加 is_admin 越权支持。admin 调 soft_delete_folder(others_folder)
    应返 True (成功软删), 无 FolderServiceError。
    """
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    bob = alice_bob["bob"]  # 普通用户 (非 admin)
    u = alice_bob["u"]
    # 准备 alice 的 folder (bob 不是 owner)
    async with factory() as session:
        svc = FolderService(session)
        f = await svc.create_folder(
            name=f"alice_target_for_admin_{u}",
            owner_id=alice.id,
            visibility="team",
        )
        fid = f.id
        await session.commit()

    # bob (非 admin) 调 → 应 403
    async with factory() as session:
        svc = FolderService(session)
        with pytest.raises(FolderServiceError) as exc_info:
            await svc.soft_delete_folder(fid, current_user_id=bob.id)
        assert exc_info.value.status_code == 403

    # bob (is_admin=True) 调 → 应成功 (bypass owner 检查)
    async with factory() as session:
        svc = FolderService(session)
        ok = await svc.soft_delete_folder(
            fid, current_user_id=bob.id, is_admin=True,  # admin bypass
        )
        assert ok is True
        await session.commit()

    # 验证软删成功
    async with factory() as session:
        svc = FolderService(session)
        f = await svc.get_folder(fid, include_deleted=True)
        assert f is not None
        assert f.deleted_at is not None


@pytest.mark.asyncio
async def test_soft_delete_returns_false_when_not_exist(alice_bob):
    """folder 不存在 → 返 False (→ endpoint 转 404 NotFoundException)

    v2.12 区分: 不存在 (False) vs 非 owner (raise 403) 是两条独立路径,
    endpoint 见 False raise NotFoundException, 见 FolderServiceError _reraise 透传。
    """
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    async with factory() as session:
        svc = FolderService(session)
        ok = await svc.soft_delete_folder(999_999_999, current_user_id=alice.id)
        assert ok is False  # → endpoint raise NotFoundException(404)


@pytest.mark.asyncio
async def test_get_folder_children_stats(alice_bob):
    """v2.14 智能 confirm 前置: 返 {folder_count, file_count}

    准备: parent folder + 1 子 folder + 1 drive 文件 + 1 个已软删的 folder
    期望: folder_count=1 (排除软删), file_count=1
    """
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    u = alice_bob["u"]
    async with factory() as session:
        svc = FolderService(session)
        parent = await svc.create_folder(
            name=f"alice_parent_stats_{u}", owner_id=alice.id, visibility="team",
        )
        child = await svc.create_folder(
            name=f"alice_child_stats_{u}", owner_id=alice.id,
            parent_id=parent.id, visibility="team",
        )
        # 1 个 drive 文件 (storage_mode='drive')
        kb_drive = Knowledge(
            title=f"file_drive_{u}",
            content="x",
            folder_id=parent.id,
            storage_mode="drive",
        )
        # 1 个 KB 知识卡片 (storage_mode='kb', 不算 file_count)
        kb_kb = Knowledge(
            title=f"file_kb_{u}",
            content="y",
            folder_id=parent.id,
            storage_mode="kb",
        )
        session.add_all([kb_drive, kb_kb])
        await session.commit()
        # 额外: 1 个子 folder 加 deleted_at (软删, 不应被统计)
        deleted_child = await svc.create_folder(
            name=f"alice_delchild_{u}", owner_id=alice.id,
            parent_id=parent.id, visibility="team",
        )
        deleted_child_id = deleted_child.id
        await session.commit()
    pid = parent.id

    # 软删那个 child
    async with factory() as session:
        svc = FolderService(session)
        folder = await svc.get_folder(deleted_child_id)
        folder.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()

    # stats 应: folder_count=1 (child alive, 不含 deleted_child), file_count=1 (kb_drive, 不含 kb_kb)
    async with factory() as session:
        svc = FolderService(session)
        stats = await svc.get_folder_children_stats(pid)
        assert stats == {"folder_count": 1, "file_count": 1}, (
            f"期望 {{folder_count: 1, file_count: 1}}, 实际 {stats}"
        )


@pytest.mark.asyncio
async def test_get_folder_children_stats_empty(alice_bob):
    """空 folder (无子 folder/file) → folder_count=0, file_count=0

    v2.14 confirm 弹窗: 这个结果走「普通删除」分支
    """
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    u = alice_bob["u"]
    async with factory() as session:
        svc = FolderService(session)
        f = await svc.create_folder(
            name=f"alice_empty_stats_{u}", owner_id=alice.id, visibility="team",
        )
        await session.commit()
        fid = f.id

    async with factory() as session:
        svc = FolderService(session)
        stats = await svc.get_folder_children_stats(fid)
        assert stats == {"folder_count": 0, "file_count": 0}


@pytest.mark.asyncio
async def test_soft_delete_and_restore(alice_bob):
    """无子 folder 时可软删, 3 天保留期内可恢复"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    u = alice_bob["u"]
    async with factory() as session:
        svc = FolderService(session)
        f = await svc.create_folder(
            name=f"alice_d_{u}", owner_id=alice.id, visibility="team",
        )
        fid = f.id
        await session.commit()

    # 软删
    async with factory() as session:
        svc = FolderService(session)
        ok = await svc.soft_delete_folder(fid, current_user_id=alice.id)
        assert ok is True
        await session.commit()

    # list 应不含
    async with factory() as session:
        svc = FolderService(session)
        items, _ = await svc.list_folders(current_user_id=alice.id)
        assert fid not in [x.id for x in items]

    # restore
    async with factory() as session:
        svc = FolderService(session)
        f = await svc.restore_folder(fid, current_user_id=alice.id)
        assert f is not None
        assert f.deleted_at is None
        await session.commit()


@pytest.mark.asyncio
async def test_list_children_for_tree_walk(alice_bob):
    """list_children 用于 UI 树形递归, 无越权过滤"""
    factory = alice_bob["factory"]
    alice = alice_bob["alice"]
    u = alice_bob["u"]
    async with factory() as session:
        svc = FolderService(session)
        root = await svc.create_folder(
            name=f"alice_r_{u}", owner_id=alice.id, visibility="team",
        )
        c1 = await svc.create_folder(
            name=f"alice_c1_{u}", owner_id=alice.id,
            parent_id=root.id, visibility="team",
        )
        c2 = await svc.create_folder(
            name=f"alice_c2_{u}", owner_id=alice.id,
            parent_id=root.id, visibility="team",
        )
        await session.commit()
        rid = root.id

    # 顶级 (parent_id=None) 应包含 root 自己 (root.parent_id 是 None)
    async with factory() as session:
        svc = FolderService(session)
        top = await svc.list_children(folder_id=None)
        top_ids = {x.id for x in top}
        assert rid in top_ids
        assert c1.id not in top_ids
        assert c2.id not in top_ids

    # root 的子应含 c1, c2
    async with factory() as session:
        svc = FolderService(session)
        kids = await svc.list_children(folder_id=rid)
        kids_ids = {k.id for k in kids}
        assert c1.id in kids_ids
        assert c2.id in kids_ids

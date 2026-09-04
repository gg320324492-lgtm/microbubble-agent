"""2026-09 单一团队空间 (网盘真共享化) 服务层回归测试

核心场景 (成员 A/B 双账号):
1. 成员 B 在成员 A 的 folder 下建子 folder → 成功 (owner 门禁退役)
2. 成员 B 改成员 A 的 folder 名 (rename) → 成功
3. 成员 B 上传文件到成员 A 的 folder → 成功 (is_team_shared 恒 True)
4. 成员 B 把成员 A 的文件移动 (update_file folder_id) → 成功
5. 成员 B 软删 + 永久删成员 A 的文件 → 成功
6. create_folder visibility='private' 收口点强制改写 'team'
7. 顶级 folder is_team_default=True / 子 folder False
8. list_folders 无 private 隐身 (A/B 看到同一批)
9. create_version / restore_version 的 cur.owner_id BUG 修复回归
   (Knowledge 模型无 owner_id 列 — 旧代码 AttributeError/TypeError)

注: /tree scope 兼容 (personal==team==all 同树) 见
tests/test_drive_folders_tree_scope.py (已改写为统一树断言)。

DB: 走 settings.DATABASE_URL (容器内为 db:5432 真库), 与 test_folder_service.py 同款
fixture 模式 (UUID 唯一化 + replica role 清理)。
"""
import pytest
import pytest_asyncio
import uuid as _uuid_lib
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import select, text

from app.config import settings
from app.models.member import Member
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.services.folder_service import FolderService
from app.services.drive_service import DriveService


def _mk_member(username: str, name: str) -> Member:
    return Member(
        username=username,
        name=name,
        password_hash="hash",
        role="member",
        grade="测试",
        is_active=True,
        # wechat_id NOT NULL (类 20.183): placeholder 避开 UNIQUE 冲突
        wechat_id=f"__TEST_BACKFILL_{username}__",
    )


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
async def anna_beno(db_session):
    """成员 A (anna) + 成员 B (beno) — 跨成员操作双向验证用"""
    session, factory = db_session
    u = _uuid_lib.uuid4().hex[:8]
    anna = _mk_member(f"anna_stw_{u}", f"Anna STW {u}")
    beno = _mk_member(f"beno_stw_{u}", f"Beno STW {u}")
    session.add_all([anna, beno])
    await session.commit()
    await session.refresh(anna)
    await session.refresh(beno)

    yield {"anna": anna, "beno": beno, "factory": factory, "u": u}

    try:
        await session.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as _del
        from app.models.knowledge import KnowledgeVersion
        ids = [anna.id, beno.id]
        krows = (await session.execute(
            select(Knowledge).where(Knowledge.created_by.in_(ids))
        )).scalars().all()
        kids = [k.id for k in krows]
        if kids:
            await session.execute(_del(KnowledgeVersion).where(KnowledgeVersion.file_id.in_(kids)))
        await session.execute(_del(Knowledge).where(Knowledge.created_by.in_(ids)))
        await session.execute(_del(Folder).where(Folder.owner_id.in_(ids)))
        await session.execute(_del(Member).where(Member.id.in_(ids)))
        await session.execute(text("RESET session_replication_role"))
        await session.commit()
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass


# === 1. 跨成员 folder 操作 ===

@pytest.mark.asyncio
async def test_beno_creates_subfolder_under_anna_folder(anna_beno):
    """成员 B 在成员 A 的 folder 下建子 folder → 成功, owner 溯源记 B"""
    factory = anna_beno["factory"]
    anna = anna_beno["anna"]
    beno = anna_beno["beno"]
    u = anna_beno["u"]
    async with factory() as session:
        svc = FolderService(session)
        parent = await svc.create_folder(name=f"anna_p_{u}", owner_id=anna.id, visibility="team")
        pid = parent.id
        await session.commit()

    async with factory() as session:
        svc = FolderService(session)
        child = await svc.create_folder(
            name=f"beno_sub_{u}", owner_id=beno.id, parent_id=pid, visibility="team",
        )
        assert child.owner_id == beno.id, "子 folder 溯源 = 实际创建人 B"
        assert child.parent_id == pid
        assert child.path.startswith(f"/{pid}/"), f"物化 path 应挂在 A 的父夹下, 实际 {child.path}"
        await session.commit()


@pytest.mark.asyncio
async def test_beno_renames_anna_folder(anna_beno):
    """成员 B 改成员 A 的 folder 名 → 成功"""
    factory = anna_beno["factory"]
    anna = anna_beno["anna"]
    beno = anna_beno["beno"]
    u = anna_beno["u"]
    async with factory() as session:
        svc = FolderService(session)
        f = await svc.create_folder(name=f"anna_rename_{u}", owner_id=anna.id, visibility="team")
        fid = f.id
        await session.commit()

    async with factory() as session:
        svc = FolderService(session)
        updated = await svc.update_folder(fid, current_user_id=beno.id, name=f"beno_renamed_{u}")
        assert updated is not None, "跨成员 rename 应成功"
        assert updated.name == f"beno_renamed_{u}"
        assert updated.owner_id == anna.id, "rename 不改溯源"
        await session.commit()


@pytest.mark.asyncio
async def test_beno_moves_anna_folder_into_beno_folder(anna_beno):
    """成员 B 把成员 A 的 folder 移动到成员 B 的 folder 下 → 成功"""
    factory = anna_beno["factory"]
    anna = anna_beno["anna"]
    beno = anna_beno["beno"]
    u = anna_beno["u"]
    async with factory() as session:
        svc = FolderService(session)
        a_f = await svc.create_folder(name=f"anna_mv_{u}", owner_id=anna.id, visibility="team")
        b_f = await svc.create_folder(name=f"beno_dst_{u}", owner_id=beno.id, visibility="team")
        aid, bid = a_f.id, b_f.id
        await session.commit()

    async with factory() as session:
        svc = FolderService(session)
        moved = await svc.update_folder(aid, current_user_id=beno.id, parent_id=bid)
        assert moved is not None, "跨成员 move 应成功 (new_parent owner 403 已删)"
        assert moved.parent_id == bid
        await session.commit()


# === 2. 跨成员文件操作 ===

@pytest.mark.asyncio
async def test_beno_upload_move_delete_anna_file(anna_beno):
    """成员 B 上传到 A 的 folder + 移动 A 的文件到 B 的 folder + 软删 + 永久删 A 的文件"""
    factory = anna_beno["factory"]
    anna = anna_beno["anna"]
    beno = anna_beno["beno"]
    u = anna_beno["u"]
    async with factory() as session:
        fsvc = FolderService(session)
        anna_folder = await fsvc.create_folder(
            name=f"anna_filehome_{u}", owner_id=anna.id, visibility="team",
        )
        beno_folder = await fsvc.create_folder(
            name=f"beno_filehome_{u}", owner_id=beno.id, visibility="team",
        )
        afid, bfid = anna_folder.id, beno_folder.id
        await session.commit()

    # B 在 A 的 folder 上传 (create_file 不再校验 folder owner)
    async with factory() as session:
        dsvc = DriveService(session)
        b_file = await dsvc.create_file(
            title=f"beno_upload_{u}",
            file_path=f"drive/stw/{u}/b.txt",
            file_name="b.txt", file_type=".txt", file_size=10,
            owner_id=beno.id, created_by=beno.id,
            folder_id=afid, visibility="team",
        )
        # A 的文件
        a_file = await dsvc.create_file(
            title=f"anna_file_{u}",
            file_path=f"drive/stw/{u}/a.txt",
            file_name="a.txt", file_type=".txt", file_size=10,
            owner_id=anna.id, created_by=anna.id,
            folder_id=afid, visibility="team",
        )
        bid, aid = b_file.id, a_file.id
        assert b_file.is_team_shared is True, "drive 上传服务端恒 is_team_shared=True"
        await session.commit()

    # B 把 A 的文件移动到自己的 folder
    async with factory() as session:
        dsvc = DriveService(session)
        moved = await dsvc.update_file(
            aid, current_user_id=beno.id, folder_id=bfid,
        )
        assert moved is not None, "跨成员移动文件应成功"
        assert moved.folder_id == bfid
        await session.commit()

    # B 软删 A 的文件
    async with factory() as session:
        dsvc = DriveService(session)
        ok = await dsvc.soft_delete_file(aid, current_user_id=beno.id)
        assert ok is True, "跨成员软删应成功"
        await session.commit()

    # B 永久删 A 的文件
    async with factory() as session:
        dsvc = DriveService(session)
        gone = await dsvc.permanent_delete(aid, current_user_id=beno.id)
        assert gone is True, "跨成员永久删应成功"
        assert await session.get(Knowledge, aid) is None
        await session.commit()


@pytest.mark.asyncio
async def test_beno_batch_ops_cover_anna_files(anna_beno):
    """B 的 batch_soft_delete / batch_restore 覆盖 A 的文件 (owner skip 已删)"""
    factory = anna_beno["factory"]
    anna = anna_beno["anna"]
    beno = anna_beno["beno"]
    u = anna_beno["u"]
    async with factory() as session:
        dsvc = DriveService(session)
        ids = []
        for i in range(2):
            f = await dsvc.create_file(
                title=f"anna_batch_{i}_{u}",
                file_path=f"drive/stw/{u}/batch{i}.txt",
                file_name=f"batch{i}.txt", file_type=".txt", file_size=10,
                owner_id=anna.id, created_by=anna.id, visibility="team",
            )
            ids.append(f.id)
        await session.commit()

    async with factory() as session:
        dsvc = DriveService(session)
        deleted, skipped = await dsvc.batch_soft_delete(ids, current_user_id=beno.id)
        assert deleted == 2 and skipped == [], f"B 批量软删 A 的 2 个文件应全成功: {deleted}/{skipped}"
        restored, skipped2 = await dsvc.batch_restore(ids, current_user_id=beno.id)
        assert restored == 2 and skipped2 == [], "B 批量恢复 A 的文件应全成功"
        await session.commit()


# === 3. 收口点语义 ===

@pytest.mark.asyncio
async def test_create_folder_private_coerced_to_team(anna_beno):
    """create_folder visibility='private' → 强制改写 'team' (私有概念无报错退役)"""
    factory = anna_beno["factory"]
    anna = anna_beno["anna"]
    u = anna_beno["u"]
    async with factory() as session:
        svc = FolderService(session)
        f = await svc.create_folder(
            name=f"anna_priv_{u}", owner_id=anna.id, visibility="private",
        )
        assert f.visibility == "team", "private 收口改写"
        await session.commit()


@pytest.mark.asyncio
async def test_top_level_folder_is_team_default(anna_beno):
    """新建顶级 folder is_team_default=True; 子 folder False"""
    factory = anna_beno["factory"]
    anna = anna_beno["anna"]
    u = anna_beno["u"]
    async with factory() as session:
        svc = FolderService(session)
        top = await svc.create_folder(name=f"anna_top_{u}", owner_id=anna.id)
        assert top.is_team_default is True, "顶级 folder 自动 is_team_default=True"
        child = await svc.create_folder(
            name=f"anna_top_child_{u}", owner_id=anna.id, parent_id=top.id,
        )
        assert child.is_team_default is False, "子 folder 不继承 team_default"
        await session.commit()


@pytest.mark.asyncio
async def test_create_file_forces_team_shared_and_rejects_private(anna_beno):
    """create_file: visibility private→team 强制改写 + is_team_shared 恒 True"""
    factory = anna_beno["factory"]
    anna = anna_beno["anna"]
    u = anna_beno["u"]
    async with factory() as session:
        dsvc = DriveService(session)
        f = await dsvc.create_file(
            title=f"anna_priv_file_{u}",
            file_path=f"drive/stw/{u}/priv.txt",
            file_name="priv.txt", file_type=".txt", file_size=10,
            owner_id=anna.id, visibility="private", is_team_shared=False,
        )
        assert f.visibility == "team", "create_file 收口改写 private→team"
        assert f.is_team_shared is True, "is_team_shared 服务端恒 True (入参 False 被忽略)"
        await session.commit()


# === 4. 版本 bug 修复 (cur.owner_id → created_by) ===

@pytest.mark.asyncio
async def test_create_version_no_owner_id_attribute_error(anna_beno):
    """create_version 回归: Knowledge 无 owner_id 列, 旧代码 cur.owner_id +
    Knowledge(owner_id=...) 直接 AttributeError/TypeError; 修复后正常建版。"""
    factory = anna_beno["factory"]
    anna = anna_beno["anna"]
    beno = anna_beno["beno"]
    u = anna_beno["u"]
    async with factory() as session:
        dsvc = DriveService(session)
        f = await dsvc.create_file(
            title=f"anna_ver_{u}",
            file_path=f"drive/stw/{u}/v1.txt",
            file_name="v1.txt", file_type=".txt", file_size=10,
            owner_id=anna.id, visibility="team", file_hash="a" * 32,
        )
        fid = f.id
        await session.commit()

    # B 给 A 的文件建新版本 (owner 门禁已删, uploader=beno)
    async with factory() as session:
        dsvc = DriveService(session)
        new_k = await dsvc.create_version(
            file_id=fid,
            new_hash="b" * 32,
            new_size=20,
            new_object_name=f"drive/stw/{u}/v2.txt",
            new_filename="v2.txt",
            change_note="beno uploads v2",
            uploader_id=beno.id,
        )
        assert new_k.version_number == 2
        assert new_k.created_by == beno.id
        assert new_k.is_latest is True
        await session.commit()


@pytest.mark.asyncio
async def test_restore_version_uses_created_by_prefix(anna_beno, monkeypatch):
    """restore_version 回归: 旧 L2026 f\"uploads/drive/{cur.owner_id}/\" AttributeError,
    修复后用 cur.created_by 拼 MinIO 前缀。file_service copy/exists 用 mock。"""
    import app.services.drive_service as ds_mod
    from unittest.mock import AsyncMock

    factory = anna_beno["factory"]
    anna = anna_beno["anna"]
    u = anna_beno["u"]
    async with factory() as session:
        dsvc = DriveService(session)
        f = await dsvc.create_file(
            title=f"anna_rver_{u}",
            file_path=f"drive/stw/{u}/r1.txt",
            file_name="r1.txt", file_type=".txt", file_size=10,
            owner_id=anna.id, visibility="team", file_hash="c" * 32,
        )
        fid = f.id
        # create_file 的初始版本写 drive_file_versions; restore_version 走
        # knowledge_versions 明细, 手动补一条 v1
        from app.models.knowledge import KnowledgeVersion
        kv = KnowledgeVersion(file_id=fid, version_number=1,
                              file_hash="c" * 32, file_size=10, uploaded_by=anna.id)
        session.add(kv)
        await session.commit()
        await session.refresh(kv)
        kv_id = kv.id

    monkeypatch.setattr(ds_mod.file_service, "object_exists", AsyncMock(return_value=True))
    monkeypatch.setattr(ds_mod.file_service, "copy_object_async", AsyncMock(return_value=10))

    async with factory() as session:
        dsvc = DriveService(session)
        new_k = await dsvc.restore_version(
            file_id=fid, version_id=kv_id, uploader_id=anna.id,
        )
        assert new_k.version_number == 2
        assert new_k.file_path.startswith(f"uploads/drive/{anna.id}/"), (
            f"restore 新 object 前缀应为 created_by 的 namespace, 实际 {new_k.file_path}"
        )
        await session.commit()

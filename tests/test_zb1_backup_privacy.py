"""ZB-1 备份隐私隔离 — 保留区判定 + create_file/create_instant_upload 豁免 + private 写路径闸

覆盖 (工单 ZB-1):
1. 保留区根名归一边界五类: backups / BackupS / ' backups ' / backups2 / 非保留区
2. 嵌套子目录: backups/<user>/ 子目录内 create_file → private (走链判定)
3. create_file 保留区强制 private (客户端传 team 也强制); 区外 private 仍退役改写 team (零回归)
4. create_instant_upload 保留区同款 (秒传路径不漏网)
5. private 写路径闸: 非 owner 对 private 行 = 隐身 (update/soft_delete/restore/extract/
   share_link/toggle_star/update_visibility/create_version/permanent_delete/batch 系列);
   owner 一切正常; 区外普通 team 文件对非 owner 行为与今天逐字一致 (零回归)
6. chunked complete 复用 create_file (代码走查 + 同收口点单测覆盖)

DB: conftest 测试库 (与 test_single_team_workspace.py 同款 fixture 模式)。
"""
import uuid as _uuid_lib

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.services.drive_service import (
    DriveService,
    is_backup_reserved_root_name,
)
from app.services.file_service import file_service
from app.services.folder_service import FolderService
from tests.conftest import get_test_database_url


def _mk_member(username: str, name: str) -> Member:
    return Member(
        username=username,
        name=name,
        password_hash="hash",
        role="member",
        grade="测试",
        is_active=True,
    )


@pytest_asyncio.fixture
async def db_session():
    url = get_test_database_url()
    engine = create_async_engine(url, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session, factory
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def zb_users(db_session):
    session, _ = db_session
    u = _uuid_lib.uuid4().hex[:8]
    a = _mk_member(f"zb1_a_{u}", f"ZB1 A {u}")
    b = _mk_member(f"zb1_b_{u}", f"ZB1 B {u}")
    session.add_all([a, b])
    await session.commit()
    await session.refresh(a)
    await session.refresh(b)
    yield {"a": a, "b": b, "u": u}
    # 清理: replica role 绕 FK, 按 user 链删 (与 single_team_workspace 同款)
    try:
        await session.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as _del
        for uid in (a.id, b.id):
            await session.execute(_del(Knowledge).where(Knowledge.created_by == uid))
        await session.execute(
            _del(Folder).where(Folder.owner_id.in_([a.id, b.id]))
        )
        await session.execute(_del(Member).where(Member.id.in_([a.id, b.id])))
        await session.commit()
    except Exception:
        await session.rollback()


async def _mk_reserved_tree(session, owner_id: int) -> tuple[Folder, Folder]:
    """A 的保留区: 顶级 backups/ + 子目录 backups/<u>/"""
    fsvc = FolderService(session)
    root = await fsvc.create_folder(name="backups", owner_id=owner_id)
    sub = await fsvc.create_folder(name=f"u-{owner_id}", owner_id=owner_id, parent_id=root.id)
    return root, sub


async def _mk_plain_folder(session, owner_id: int, name: str) -> Folder:
    return await FolderService(session).create_folder(name=name, owner_id=owner_id)


async def _mk_file(session, *, folder_id, owner_id, name, visibility="team", file_hash=None) -> Knowledge:
    svc = DriveService(session)
    return await svc.create_file(
        title=name,
        file_path=f"drive/{owner_id}/{uuid4hex()}.bin",
        file_name=name,
        file_type="bin",
        file_size=1024,
        owner_id=owner_id,
        folder_id=folder_id,
        visibility=visibility,
        file_hash=file_hash,
    )


def uuid4hex() -> str:
    return _uuid_lib.uuid4().hex


# ==========================================================================
# 1. 保留区根名归一边界 (纯函数, 工单指定五类)
# ==========================================================================

class TestReservedRootName:
    def test_backups_exact(self):
        assert is_backup_reserved_root_name("backups") is True

    def test_case_insensitive(self):
        assert is_backup_reserved_root_name("BackupS") is True
        assert is_backup_reserved_root_name("BACKUPS") is True

    def test_whitespace_normalized(self):
        assert is_backup_reserved_root_name("  backups ") is True

    def test_prefix_not_matched(self):
        assert is_backup_reserved_root_name("backups2") is False
        assert is_backup_reserved_root_name("backups_old") is False

    def test_non_reserved_and_empty(self):
        assert is_backup_reserved_root_name("docs") is False
        assert is_backup_reserved_root_name("") is False
        assert is_backup_reserved_root_name(None) is False


# ==========================================================================
# 2/3. create_file 保留区豁免 (含嵌套子目录) + 区外零回归
# ==========================================================================

class TestCreateFileReservedExemption:
    @pytest.mark.asyncio
    async def test_reserved_nested_subdir_forces_private(self, zb_users, db_session):
        """backups/<u>/ 子目录内 create_file → private (客户端传 team 也强制)"""
        session, _ = db_session
        root, sub = await _mk_reserved_tree(session, zb_users["a"].id)
        f = await _mk_file(session, folder_id=sub.id, owner_id=zb_users["a"].id,
                          name="probe.mnbbak", visibility="team")
        assert f.visibility == "private"  # 服务端强制, 不信任客户端

    @pytest.mark.asyncio
    async def test_reserved_root_key_json_forced_private(self, zb_users, db_session):
        """保留区根直下 (key.json 形态) 同样强制 private"""
        session, _ = db_session
        root, _sub = await _mk_reserved_tree(session, zb_users["a"].id)
        f = await _mk_file(session, folder_id=root.id, owner_id=zb_users["a"].id,
                           name="x.mnbbak.key.json", visibility="team")
        assert f.visibility == "private"

    @pytest.mark.asyncio
    async def test_outside_private_still_rewritten_team(self, zb_users, db_session):
        """区外: private 退役改写 team 的历史行为逐字不变 (零回归)"""
        session, _ = db_session
        docs = await _mk_plain_folder(session, zb_users["a"].id, f"docs-{uuid4hex()[:6]}")
        f = await _mk_file(session, folder_id=docs.id, owner_id=zb_users["a"].id,
                           name="paper.pdf", visibility="private")
        assert f.visibility == "team"

    @pytest.mark.asyncio
    async def test_outside_team_unchanged(self, zb_users, db_session):
        """区外: team 上传行为不变 (仍 team、全组可见)"""
        session, _ = db_session
        docs = await _mk_plain_folder(session, zb_users["a"].id, f"docs-{uuid4hex()[:6]}")
        f = await _mk_file(session, folder_id=docs.id, owner_id=zb_users["a"].id,
                           name="data.csv", visibility="team")
        assert f.visibility == "team"

    @pytest.mark.asyncio
    async def test_chunked_complete_reuses_create_file(self, zb_users, db_session):
        """chunked complete 复用 create_file (同一收口点, 保留区豁免自动覆盖)——
        这里直接以 create_file 为被测对象 (complete_chunked_upload L2681 调用点走查确认)"""
        session, _ = db_session
        root, sub = await _mk_reserved_tree(session, zb_users["a"].id)
        svc = DriveService(session)
        f = await svc.create_file(
            title="chunked.mnbbak",
            file_path=f"drive/{zb_users['a'].id}/{uuid4hex()}.bin",
            file_name="chunked.mnbbak",
            file_type="bin",
            file_size=2048,
            owner_id=zb_users["a"].id,
            folder_id=sub.id,
            visibility="team",
            storage_mode="drive",
            is_team_shared=True,
        )
        assert f.visibility == "private"


# ==========================================================================
# 4. create_instant_upload 保留区豁免 (秒传路径)
# ==========================================================================

class TestInstantUploadReserved:
    @pytest.mark.asyncio
    async def test_instant_upload_in_reserved_forces_private(self, zb_users, db_session, monkeypatch):
        session, _ = db_session
        a = zb_users["a"]
        root, sub = await _mk_reserved_tree(session, a.id)
        h = "ab" * 32
        src = await _mk_file(session, folder_id=sub.id, owner_id=a.id,
                             name="origin.mnbbak", visibility="team", file_hash=h)
        # 秒传: 同 hash 再传进保留区另一子目录 — mock MinIO copy (零对象存储依赖)
        async def _fake_copy(_src_path, _dst_object):
            return src.file_size
        monkeypatch.setattr(file_service, "copy_object_async", _fake_copy)

        svc = DriveService(session)
        result = await svc.create_instant_upload(
            file_hash=h,
            file_size=src.file_size,
            file_name="origin.mnbbak",
            owner_id=a.id,
            created_by=a.id,
            folder_id=root.id,
            visibility="team",
        )
        new_k = result[0] if isinstance(result, tuple) else result
        assert new_k is not None
        assert new_k.visibility == "private"  # 秒传行不漏网


# ==========================================================================
# 5. private 写路径闸 + 区外零回归 (A/B 双账号)
# ==========================================================================

class TestPrivateWriteGates:
    @pytest_asyncio.fixture
    async def backup_fixture(self, zb_users, db_session):
        session, _ = db_session
        a, b = zb_users["a"], zb_users["b"]
        _root, sub = await _mk_reserved_tree(session, a.id)
        f = await _mk_file(session, folder_id=sub.id, owner_id=a.id,
                           name="secret.mnbbak", visibility="team", file_hash="cd" * 32)
        docs = await _mk_plain_folder(session, a.id, f"docs-{uuid4hex()[:6]}")
        plain = await _mk_file(session, folder_id=docs.id, owner_id=a.id,
                               name="shared.csv", visibility="team")
        return {"a": a, "b": b, "file": f, "plain": plain, "docs": docs}

    async def _assert_hidden_to_b(self, session, file_id, b_id):
        svc = DriveService(session)
        assert await svc.get_file(file_id, b_id) is None

    @pytest.mark.asyncio
    async def test_list_hides_private_from_b(self, backup_fixture, db_session):
        session, _ = db_session
        svc = DriveService(session)
        items, _total = await svc.list_files(current_user_id=backup_fixture["b"].id, include_subfolders=True)
        ids = {i.id for i in items}
        assert backup_fixture["file"].id not in ids
        assert backup_fixture["plain"].id in ids  # 区外普通文件对 B 仍可见 (零回归)

    @pytest.mark.asyncio
    async def test_get_file_hidden_to_b_owner_ok(self, backup_fixture, db_session):
        session, _ = db_session
        svc = DriveService(session)
        assert await svc.get_file(backup_fixture["file"].id, backup_fixture["b"].id) is None
        assert await svc.get_file(backup_fixture["file"].id, backup_fixture["a"].id) is not None

    @pytest.mark.asyncio
    async def test_update_file_hidden_to_b(self, backup_fixture, db_session):
        session, _ = db_session
        svc = DriveService(session)
        fid = backup_fixture["file"].id
        assert await svc.update_file(fid, backup_fixture["b"].id, title="hacked") is None
        assert await svc.update_file(fid, backup_fixture["a"].id, title="renamed") is not None

    @pytest.mark.asyncio
    async def test_soft_delete_and_restore_hidden_to_b(self, backup_fixture, db_session):
        session, _ = db_session
        svc = DriveService(session)
        fid = backup_fixture["file"].id
        assert await svc.soft_delete_file(fid, backup_fixture["b"].id) is False
        assert await svc.restore_file(fid, backup_fixture["b"].id) is None
        # 文件未被 B 删掉 (owner 视角仍活跃)
        assert await svc.get_file(fid, backup_fixture["a"].id) is not None

    @pytest.mark.asyncio
    async def test_extract_and_share_link_hidden_to_b(self, backup_fixture, db_session):
        session, _ = db_session
        svc = DriveService(session)
        fid = backup_fixture["file"].id
        assert await svc.extract_to_kb(fid, backup_fixture["b"].id) is None
        assert await svc.create_share_link(fid, backup_fixture["b"].id) is None
        # FIN-1 A1: 备份形态 owner 也禁止分享 (分享即公开会让密钥信封对外可达)
        from app.services.drive_service import DriveServiceError

        with pytest.raises(DriveServiceError):
            await svc.create_share_link(fid, backup_fixture["a"].id)
        await session.refresh(backup_fixture["file"])
        assert backup_fixture["file"].visibility == "private"  # 未被翻转

    @pytest.mark.asyncio
    async def test_visibility_and_star_hidden_to_b(self, backup_fixture, db_session):
        session, _ = db_session
        svc = DriveService(session)
        fid = backup_fixture["file"].id
        assert await svc.update_visibility(fid, backup_fixture["b"].id, "public") is None
        assert await svc.toggle_star_file(fid, backup_fixture["b"].id) is None

    @pytest.mark.asyncio
    async def test_create_version_hidden_to_b(self, backup_fixture, db_session):
        session, _ = db_session
        svc = DriveService(session)
        from app.services.drive_service import DriveServiceError
        with pytest.raises(DriveServiceError) as ei:
            await svc.create_version(
                file_id=backup_fixture["file"].id,
                new_hash="ef" * 32,
                new_size=1,
                new_object_name=f"drive/x/{uuid4hex()}",
                new_filename="injected.bin",
                change_note=None,
                uploader_id=backup_fixture["b"].id,
            )
        assert ei.value.status_code == 404

    @pytest.mark.asyncio
    async def test_permanent_delete_hidden_to_b(self, backup_fixture, db_session):
        session, _ = db_session
        svc = DriveService(session)
        fid = backup_fixture["file"].id
        await svc.soft_delete_file(fid, backup_fixture["a"].id)  # owner 自己进回收站
        assert await svc.permanent_delete(fid, backup_fixture["b"].id) is False  # B 不可硬删
        # 回收站视角: B 的回收站看不到, A 的回收站还在
        b_trash, _ = await svc.list_trash(current_user_id=backup_fixture["b"].id)
        a_trash, _ = await svc.list_trash(current_user_id=backup_fixture["a"].id)
        assert fid not in {t.id for t in b_trash}
        assert fid in {t.id for t in a_trash}

    @pytest.mark.asyncio
    async def test_batch_ops_skip_private_for_b(self, backup_fixture, db_session):
        session, _ = db_session
        svc = DriveService(session)
        fid = backup_fixture["file"].id
        pid = backup_fixture["plain"].id
        # 批量软删: private 跳过, 区外普通文件照删 (B 对 A 的 team 文件有扁平化权限 = 今天行为)
        deleted, skipped = await svc.batch_soft_delete([fid, pid], backup_fixture["b"].id)
        assert deleted == 1 and skipped == [fid]
        await svc.batch_restore([pid], backup_fixture["b"].id)

    @pytest.mark.asyncio
    async def test_batch_update_visibility_skips_private_for_b(self, backup_fixture, db_session):
        session, _ = db_session
        svc = DriveService(session)
        fid = backup_fixture["file"].id
        pid = backup_fixture["plain"].id
        # 目标 team (folder=team 允许 team): private 被 ZB-1 闸跳过, 普通 team 文件照常
        updated, skipped = await svc.batch_update_visibility(
            [fid, pid], "team", backup_fixture["b"].id)
        assert updated == 1 and skipped == [fid]
        await session.refresh(backup_fixture["file"])
        assert backup_fixture["file"].visibility == "private"  # 未被翻公开

    @pytest.mark.asyncio
    async def test_hash_lookup_hidden_to_b(self, backup_fixture, db_session):
        session, _ = db_session
        svc = DriveService(session)
        h = "cd" * 32
        assert await svc.hash_lookup(file_hash=h, current_user_id=backup_fixture["a"].id) is not None
        assert await svc.hash_lookup(file_hash=h, current_user_id=backup_fixture["b"].id) is None

    @pytest.mark.asyncio
    async def test_backup_visible_in_owner_list(self, backup_fixture, db_session):
        session, _ = db_session
        svc = DriveService(session)
        items, _total = await svc.list_files(current_user_id=backup_fixture["a"].id, include_subfolders=True)
        ids = {i.id for i in items}
        assert backup_fixture["file"].id in ids  # A 自己可见可管 (恢复路径不受影响)

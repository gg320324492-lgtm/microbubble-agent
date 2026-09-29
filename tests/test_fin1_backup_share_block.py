"""FIN-1 A1/A2 —— 备份形态禁公开分享 + 异步任务引擎 URL 守卫

A1: 备份形态 (.mnbbak / .key.json) 的 public 通道全部拦截 (owner 也在内):
    create_share_link / update_visibility / update_file(visibility) / batch_update_visibility
    「分享即公开」(2026-09-05) 对非备份文件逐字不变 (不许误伤)。
A2: 异步任务引擎 URL 可注入 + 回归守卫 (测试注入的 URL 必须不是生产库)。
"""
import uuid as _uuid_lib

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.services.drive_service import DriveService, DriveServiceError
from tests.conftest import TEST_DB_URL, get_test_database_url


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
async def fin1_user(db_session):
    session, _ = db_session
    u = _uuid_lib.uuid4().hex[:8]
    m = _mk_member(f"fin1_{u}", f"FIN1 {u}")
    session.add(m)
    await session.commit()
    await session.refresh(m)
    # 保留区子树 (backups/<u>/) —— 备份形态文件的真实归宿
    fsvc = DriveService  # noqa: F841 (语义标注)
    from app.services.folder_service import FolderService

    root = await FolderService(session).create_folder(name="backups", owner_id=m.id)
    sub = await FolderService(session).create_folder(
        name=f"u-{m.id}", owner_id=m.id, parent_id=root.id
    )
    yield {"m": m, "sub": sub.id}
    try:
        await session.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as _del
        await session.execute(_del(Knowledge).where(Knowledge.created_by == m.id))
        await session.execute(
            _del(Folder).where(Folder.owner_id == m.id)
        )
        await session.execute(_del(Member).where(Member.id == m.id))
        await session.commit()
    except Exception:
        await session.rollback()


async def _mk_file(session, owner_id: int, file_name: str, visibility: str = "team", folder_id: int | None = None) -> Knowledge:
    svc = DriveService(session)
    return await svc.create_file(
        title=file_name[:200],
        file_path=f"drive/{owner_id}/{_uuid_lib.uuid4().hex}_{file_name}",
        file_name=file_name,
        file_type="bin",
        file_size=1024,
        owner_id=owner_id,
        folder_id=folder_id,
        visibility=visibility,
    )


# ==========================================================================
# A1 · 备份形态禁公开分享 (owner 也在内) + 普通文件照旧 (不许误伤 09-05 决策)
# ==========================================================================

class TestBackupShareBlock:
    @pytest_asyncio.fixture
    async def backup_fixture(self, fin1_user, db_session):
        """保留区内 private 备份容器 + key.json + 区外普通 team 文件"""
        session, _ = db_session
        key = await _mk_file(session, fin1_user["m"].id, "probe.mnbbak.key.json",
                             folder_id=fin1_user["sub"])
        container = await _mk_file(session, fin1_user["m"].id, "probe.mnbbak",
                                   folder_id=fin1_user["sub"])
        plain = await _mk_file(session, fin1_user["m"].id, "paper.pdf", visibility="team")
        return {"user": fin1_user["m"], "key": key, "container": container, "plain": plain,
                "sub": fin1_user["sub"]}

    @pytest.mark.asyncio
    async def test_backup_share_link_rejected_even_by_owner(self, backup_fixture, db_session):
        session, _ = db_session
        key = backup_fixture["key"]
        assert key.visibility == "private"  # 保留区强制 private (ZB-1)
        svc = DriveService(session)
        with pytest.raises(DriveServiceError) as ei:
            await svc.create_share_link(key.id, current_user_id=backup_fixture["user"].id)
        assert ei.value.status_code == 400
        assert "备份" in ei.value.message
        # 文件未被翻转 public
        await session.refresh(key)
        assert key.visibility == "private"

    @pytest.mark.asyncio
    async def test_plain_team_file_share_still_works(self, backup_fixture, db_session):
        """09-05「分享即公开」对普通文件零变化"""
        session, _ = db_session
        plain = backup_fixture["plain"]
        svc = DriveService(session)
        f = await svc.create_share_link(plain.id, current_user_id=backup_fixture["user"].id)
        assert f is not None
        assert f.share_token
        assert f.visibility == "public"  # 分享即公开 (既有产品决策)

    @pytest.mark.asyncio
    async def test_backup_update_visibility_to_public_rejected(self, backup_fixture, db_session):
        session, _ = db_session
        key = backup_fixture["key"]
        svc = DriveService(session)
        with pytest.raises(DriveServiceError) as ei:
            await svc.update_visibility(key.id, backup_fixture["user"].id, "public")
        assert ei.value.status_code == 400
        await session.refresh(key)
        assert key.visibility == "private"

    @pytest.mark.asyncio
    async def test_backup_update_visibility_to_team_allowed(self, backup_fixture, db_session):
        """team 双向不受限 (保留可逆空间; 仅 public 拦截)"""
        session, _ = db_session
        key = backup_fixture["key"]
        svc = DriveService(session)
        f = await svc.update_visibility(key.id, backup_fixture["user"].id, "team")
        assert f is not None and f.visibility == "team"

    @pytest.mark.asyncio
    async def test_update_file_public_on_backup_rejected(self, backup_fixture, db_session):
        session, _ = db_session
        key = backup_fixture["key"]
        svc = DriveService(session)
        # update_file 对非法 visibility 的既有风格是抛 DriveServiceError (API 转 400 可见)
        with pytest.raises(DriveServiceError):
            await svc.update_file(key.id, backup_fixture["user"].id, visibility="public")
        await session.refresh(key)
        assert key.visibility == "private"

    @pytest.mark.asyncio
    async def test_batch_visibility_public_skips_backup(self, backup_fixture, db_session):
        session, _ = db_session
        key = backup_fixture["key"]
        svc = DriveService(session)
        updated, skipped = await svc.batch_update_visibility(
            [key.id], "public", backup_fixture["user"].id
        )
        assert updated == 0 and skipped == [key.id]
        await session.refresh(key)
        assert key.visibility == "private"


# ==========================================================================
# A2 · 异步任务引擎 URL 守卫
# ==========================================================================

class TestTaskEngineUrlGuard:
    def test_guard_injected_test_url_is_not_production(self, monkeypatch):
        """★ A2 回归守卫: 任务解析出的引擎 URL 在测试注入下必须不是生产库"""
        import app.services.drive_ingest_tasks as dit

        monkeypatch.setattr(dit, "_database_url_override", get_test_database_url())
        resolved = dit._resolve_engine_url()
        assert resolved != settings.DATABASE_URL
        assert resolved != settings.DATABASE_URL.replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        assert "microbubble_test" in resolved

    def test_guard_default_is_settings_url_documented(self):
        """默认 (无注入) = settings.DATABASE_URL —— 生产行为契约, 显式固化"""
        import app.services.drive_ingest_tasks as dit

        assert dit._database_url_override is None
        assert dit._resolve_engine_url() == settings.DATABASE_URL.replace(
            "postgresql://", "postgresql+asyncpg://"
        )

    def test_guard_conftest_test_url_differs_from_production(self):
        """conftest 层守卫: 测试库 URL 与生产库 URL 必须不同 (防回退)"""
        assert TEST_DB_URL != settings.DATABASE_URL
        assert get_test_database_url() != settings.DATABASE_URL

    def test_guard_index_service_override_attr(self, monkeypatch):
        """index 任务同款注入点存在且可覆盖"""
        import app.services.drive_index_service as dis

        monkeypatch.setattr(dis, "_index_db_url_override", get_test_database_url())
        assert dis._index_db_url_override != settings.DATABASE_URL
        assert "microbubble_test" in dis._index_db_url_override

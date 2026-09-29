"""ZB-2 备份形态跳过抽取 + 孪生行 private 继承

覆盖 (工单 ZB-2 Part B):
1. is_backup_artifact_name 判定矩阵 (.mnbbak / .key.json / 大小写 / 近似名 / 非)
2. auto_ingest_drive_file_task 入口跳过: 备份形态不建 kb 孪生行 (早于建行, 返回 skipped)
3. _create_kb_row 去翻转: private 源行 → 孪生行继承 private (不再翻 team);
   team 源行 → team (不变)

DB: conftest 测试库; Celery 任务以 apply() 内联执行 (容器测试库环境变量注入)。
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
from app.services.drive_ingest_tasks import (
    auto_ingest_drive_file_task,
    is_backup_artifact_name,
)
from app.services.drive_to_kb_service import DriveToKBService
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
async def zb2_user(db_session):
    session, _ = db_session
    u = _uuid_lib.uuid4().hex[:8]
    m = _mk_member(f"zb2_{u}", f"ZB2 {u}")
    session.add(m)
    await session.commit()
    await session.refresh(m)
    yield m
    try:
        await session.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as _del
        await session.execute(_del(Knowledge).where(Knowledge.created_by == m.id))
        await session.execute(_del(Member).where(Member.id == m.id))
        await session.commit()
    except Exception:
        await session.rollback()


async def _mk_drive_row(session, owner_id: int, file_name: str, visibility: str = "team") -> Knowledge:
    k = Knowledge(
        title=file_name[:200],
        content=f"[drive upload] {file_name}",
        file_path=f"drive/{owner_id}/{_uuid_lib.uuid4().hex}_{file_name}",
        file_name=file_name,
        file_type="bin",
        file_size=1024,
        source_type="drive",
        created_by=owner_id,
        storage_mode="drive",
        visibility=visibility,
        folder_id=None,
    )
    session.add(k)
    await session.commit()
    await session.refresh(k)
    return k


# ==========================================================================
# 1. 判定矩阵
# ==========================================================================

class TestBackupArtifactName:
    def test_container_and_key_shapes(self):
        assert is_backup_artifact_name("workbench-20260929-192707.mnbbak") is True
        assert is_backup_artifact_name("workbench-20260929-192707.mnbbak.key.json") is True

    def test_case_insensitive_and_whitespace(self):
        assert is_backup_artifact_name("X.MNBBak") is True
        assert is_backup_artifact_name("  x.Key.JSON  ") is True

    def test_near_miss_not_matched(self):
        assert is_backup_artifact_name("x.mnbbak2") is False
        assert is_backup_artifact_name("x.mnbbak.bak") is False
        assert is_backup_artifact_name("key.json") is False  # 需 .key.json 后缀
        assert is_backup_artifact_name("notes.txt") is False

    def test_empty_and_none(self):
        assert is_backup_artifact_name("") is False
        assert is_backup_artifact_name(None) is False


# ==========================================================================
# 2. ingest 任务入口跳过 (早于建孪生行)
# ==========================================================================

class TestIngestTaskSkip:
    @pytest.mark.asyncio
    async def test_backup_shape_skipped_no_kb_twin(self, zb2_user, db_session):
        session, _ = db_session
        k = await _mk_drive_row(session, zb2_user.id, "probe.mnbbak.key.json")

        # 线程内执行: 任务体 asyncio.run 与 pytest-asyncio 的活动循环互斥
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(1) as ex:
            res = ex.submit(
                lambda: auto_ingest_drive_file_task.apply(args=[k.id]).get()
            ).result(timeout=120)
        assert res["skipped"] == "backup-artifact"
        assert res["knowledge_id"] is None

        # 库里没有为它建 kb 孪生行
        cnt = (
            await session.execute(
                text(
                    "SELECT COUNT(*) FROM knowledge "
                    "WHERE source_type = 'drive_extracted' AND file_name = 'probe.mnbbak.key.json'"
                )
            )
        ).scalar()
        assert cnt == 0

    @pytest.mark.asyncio
    async def test_backup_container_shape_skipped(self, zb2_user, db_session):
        session, _ = db_session
        k = await _mk_drive_row(session, zb2_user.id, "probe.mnbbak")
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(1) as ex:
            res = ex.submit(
                lambda: auto_ingest_drive_file_task.apply(args=[k.id]).get()
            ).result(timeout=120)
        assert res["skipped"] == "backup-artifact"


# ==========================================================================
# 3. 孪生行 private 继承 (去 private→team 翻转)
# ==========================================================================

class TestKbRowInheritsVisibility:
    @pytest.mark.asyncio
    async def test_private_source_twin_stays_private(self, zb2_user, db_session):
        session, _ = db_session
        row = await _mk_drive_row(session, zb2_user.id, "private-doc.pdf", visibility="private")
        twin = await DriveToKBService(session)._create_kb_row(row, "正文摘要", "document")
        assert twin.visibility == "private"  # ZB-2: 不再翻 team
        assert twin.storage_mode == "kb"
        assert twin.source_type == "drive_extracted"

    @pytest.mark.asyncio
    async def test_team_source_twin_stays_team(self, zb2_user, db_session):
        session, _ = db_session
        row = await _mk_drive_row(session, zb2_user.id, "shared-doc.pdf", visibility="team")
        twin = await DriveToKBService(session)._create_kb_row(row, "正文摘要", "document")
        assert twin.visibility == "team"  # 区外行为不变

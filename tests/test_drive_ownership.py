"""2026-09 单一团队空间 — app/services/drive_ownership.py 归属转移助手测试

覆盖:
1. reassign_member_rows 各表 rowcount (seed 最小行集: folders/knowledge/
   knowledge_versions/drive_file_versions/file_requests/agent_traces/chat_sessions)
2. 转移后行的归属列真变成 anchor
3. ValueError 守卫: member==anchor / member 不存在 / anchor 不存在
4. member_cleanup.list_member_referencing_rows 只读普查 + blocking_refs 过滤

DB: 走 settings.DATABASE_URL (容器内 db:5432 真库), 与 test_folder_service.py 同款
fixture (UUID 唯一化 + replica role 清理)。
"""
import secrets
import pytest
import pytest_asyncio
import uuid as _uuid_lib
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.member import Member
from app.models.folder import Folder
from app.models.knowledge import Knowledge, KnowledgeVersion, FileRequest
from app.models.drive_file_version import DriveFileVersion
from app.models.agent_trace import AgentTrace
from app.models.chat_history import ChatSession
from app.services.drive_ownership import reassign_member_rows
from app.services.member_cleanup import list_member_referencing_rows, blocking_refs


def _mk_member(username: str) -> Member:
    return Member(
        username=username, name=f"Own {username}",
        password_hash="hash", role="member", grade="测试", is_active=True,
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
async def ghost_anchor(db_session):
    """ghost = 被删成员; anchor = 工作区锚点. seed 每表 ≥1 行归属 ghost。"""
    session, factory = db_session
    u = _uuid_lib.uuid4().hex[:8]
    ghost = _mk_member(f"ghost_own_{u}")
    anchor = _mk_member(f"anchor_own_{u}")
    session.add_all([ghost, anchor])
    await session.commit()
    await session.refresh(ghost)
    await session.refresh(anchor)

    folder = Folder(name=f"ghost_f_{u}", owner_id=ghost.id, visibility="team",
                    path="/", depth=0)
    file = Knowledge(title=f"ghost_file_{u}", content="c", file_path="drive/x.txt",
                     file_name="x.txt", file_type=".txt", file_size=1,
                     created_by=ghost.id, storage_mode="drive", visibility="team")
    session.add_all([folder, file])
    await session.commit()
    await session.refresh(folder)
    await session.refresh(file)

    kv = KnowledgeVersion(file_id=file.id, version_number=1,
                          file_hash="f" * 32, file_size=1, uploaded_by=ghost.id)
    dfv = DriveFileVersion(file_id=file.id, version_number=1,
                          minio_object_key="drive/x.txt", size=1, uploader_id=ghost.id)
    freq = FileRequest(token=secrets.token_hex(16)[:32], title=f"req_{u}",
                       created_by=ghost.id)
    trace = AgentTrace(user_id=ghost.id, session_id=f"own_{u}", message="m")
    chat = ChatSession(id=f"own_chat_{u}", user_id=ghost.id, title="t")
    session.add_all([kv, dfv, freq, trace, chat])
    await session.commit()

    yield {"ghost": ghost, "anchor": anchor, "factory": factory, "u": u,
           "ids": {"folder": folder.id, "file": file.id}}

    try:
        await session.execute(text("SET session_replication_role = 'replica'"))
        from sqlalchemy import delete as _del
        await session.execute(_del(AgentTrace).where(
            AgentTrace.user_id.in_([ghost.id, anchor.id])))
        await session.execute(_del(ChatSession).where(
            ChatSession.id == f"own_chat_{u}"))
        await session.execute(_del(FileRequest).where(
            FileRequest.created_by.in_([ghost.id, anchor.id])))
        await session.execute(_del(DriveFileVersion).where(
            DriveFileVersion.file_id == file.id))
        await session.execute(_del(KnowledgeVersion).where(
            KnowledgeVersion.file_id == file.id))
        await session.execute(_del(Knowledge).where(
            Knowledge.id == file.id))
        await session.execute(_del(Folder).where(
            Folder.owner_id.in_([ghost.id, anchor.id])))
        await session.execute(_del(Member).where(
            Member.id.in_([ghost.id, anchor.id])))
        await session.execute(text("RESET session_replication_role"))
        await session.commit()
    except Exception:
        try:
            await session.rollback()
        except Exception:
            pass


@pytest.mark.asyncio
async def test_reassign_member_rows_counts_and_effect(ghost_anchor):
    """7 张表 rowcount ≥1 且转移后归属列 = anchor.id"""
    factory = ghost_anchor["factory"]
    ghost = ghost_anchor["ghost"]
    anchor = ghost_anchor["anchor"]
    async with factory() as session:
        counts = await reassign_member_rows(
            session, member_id=ghost.id, anchor_id=anchor.id,
        )
        assert counts["folders.owner_id"] >= 1, counts
        assert counts["knowledge.created_by"] >= 1, counts
        assert counts["knowledge_versions.uploaded_by"] >= 1, counts
        assert counts["drive_file_versions.uploader_id"] >= 1, counts
        assert counts["file_requests.created_by"] >= 1, counts
        assert counts["agent_traces.user_id"] >= 1, counts
        assert counts["chat_sessions.user_id"] >= 1, counts

        # 归属真转移
        f = await session.get(Folder, ghost_anchor["ids"]["folder"])
        assert f.owner_id == anchor.id
        k = await session.get(Knowledge, ghost_anchor["ids"]["file"])
        assert k.created_by == anchor.id
        # ghost 名下 0 行残留
        remain = (await session.execute(
            select(Folder).where(Folder.owner_id == ghost.id)
        )).scalars().all()
        assert not remain


@pytest.mark.asyncio
async def test_reassign_guard_same_member_anchor(ghost_anchor):
    factory = ghost_anchor["factory"]
    ghost = ghost_anchor["ghost"]
    async with factory() as session:
        with pytest.raises(ValueError):
            await reassign_member_rows(
                session, member_id=ghost.id, anchor_id=ghost.id,
            )


@pytest.mark.asyncio
async def test_reassign_guard_nonexistent_member(ghost_anchor):
    factory = ghost_anchor["factory"]
    anchor = ghost_anchor["anchor"]
    async with factory() as session:
        with pytest.raises(ValueError):
            await reassign_member_rows(
                session, member_id=999_999_999, anchor_id=anchor.id,
            )


@pytest.mark.asyncio
async def test_reassign_guard_nonexistent_anchor(ghost_anchor):
    factory = ghost_anchor["factory"]
    ghost = ghost_anchor["ghost"]
    async with factory() as session:
        with pytest.raises(ValueError):
            await reassign_member_rows(
                session, member_id=ghost.id, anchor_id=999_999_999,
            )


@pytest.mark.asyncio
async def test_census_and_blocking_refs(ghost_anchor):
    """普查: ghost 名下各表行数正确, blocking_refs 含 RESTRICT 的 folders"""
    factory = ghost_anchor["factory"]
    ghost = ghost_anchor["ghost"]
    async with factory() as session:
        census = await list_member_referencing_rows(session, ghost.id)
        assert census["folders.owner_id"] >= 1
        assert census["knowledge.created_by"] >= 1
        assert census["agent_traces.user_id"] >= 1
        blockers = blocking_refs(census)
        assert "folders.owner_id" in blockers, "folders RESTRICT 必须算阻塞"
        assert "knowledge.created_by" in blockers, "knowledge NO ACTION 必须算阻塞"
        # CASCADE 表 (chat_sessions) 不阻塞, 不应出现在 blockers
        assert "chat_sessions.user_id" not in blockers
        assert "activity_events.actor_id" not in blockers  # SET NULL 不阻塞

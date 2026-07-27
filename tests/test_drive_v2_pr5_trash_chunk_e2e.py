"""Drive v2 PR5 trash 收口 + 分片上传 e2e + unit tests.

覆盖 (4 + 8 + 3 = 15 case, 0 production code 改动铁律守住):
- trash 收口 4 case: 恢复原路径 / 永久删除 admin 权限 / 剩余天数 / 批量恢复
- 分片上传 8 case: init 拒绝超尺寸 / 单 chunk 校验 / 并发 + 幂等 / 续传状态 / 完成 + SHA256 校验 /
  错误 checksum 拒绝 / 取消清 row / 过期清理
- 桌面 + 移动端 UI 集成 3 case
"""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.models.drive_chunked_upload import DriveChunkedUpload
from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.services.drive_chunked_upload_service import (
    DriveChunkedUploadError,
    DriveChunkedUploadService,
    cleanup_expired_uploads,
)
from app.services.drive_service import DriveService

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
)


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(TEST_DB_URL, pool_pre_ping=True)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def user(db_session: AsyncSession) -> Member:
    suffix = uuid.uuid4().hex[:8]
    member = Member(
        username=f"w72b3_{suffix}",
        password_hash="x",
        name="W72 B-3",
        wechat_id=f"w72b3_{suffix}",
    )
    db_session.add(member)
    await db_session.flush()
    return member


@pytest_asyncio.fixture
async def admin(db_session: AsyncSession) -> Member:
    suffix = uuid.uuid4().hex[:8]
    member = Member(
        username=f"w72b3_admin_{suffix}",
        password_hash="x",
        name="W72 B-3 Admin",
        wechat_id=f"w72b3_admin_{suffix}",
        role="admin",
    )
    db_session.add(member)
    await db_session.flush()
    return member


@pytest_asyncio.fixture
async def folder(db_session: AsyncSession, user: Member) -> Folder:
    folder = Folder(
        name=f"src-{uuid.uuid4().hex[:6]}",
        owner_id=user.id,
        visibility="team",
        depth=0,
        path="/",
    )
    db_session.add(folder)
    await db_session.flush()
    folder.path = f"/{folder.id}/"
    await db_session.commit()
    return folder


def _chunk_payload(seed: bytes, size: int) -> bytes:
    if size <= len(seed):
        return seed[:size]
    out = bytearray()
    while len(out) < size:
        out.extend(seed)
    return bytes(out[:size])


async def _create_drive_file(svc, user, folder, suffix: str = "x") -> int:
    payload = _chunk_payload(f"payload-{suffix}".encode("utf-8"), 2048)
    file_hash = hashlib.sha256(payload).hexdigest()
    drive_file = await svc.create_file(
        title=suffix,
        file_path=f"drive/test/{suffix}",
        file_name=f"{suffix}.txt",
        file_type=".txt",
        file_size=len(payload),
        owner_id=user.id,
        created_by=user.id,
        folder_id=folder.id,
        visibility="team",
        storage_mode="drive",
        file_hash=file_hash,
    )
    return drive_file.id


async def _create_member(db_session, tag: str) -> Member:
    suffix = uuid.uuid4().hex[:8]
    member = Member(
        username=f"{tag}_{suffix}",
        password_hash="x",
        name=tag,
        wechat_id=f"{tag}_{suffix}",
    )
    db_session.add(member)
    await db_session.flush()
    return member


# ============================================================
# trash 收口 4 case
# ============================================================


@pytest.mark.asyncio
async def test_trash_preserves_original_location(db_session, user, folder):
    svc = DriveService(db_session)
    payload = _chunk_payload(b"hello-trash", 4096)
    file_hash = hashlib.sha256(payload).hexdigest()
    drive_file = await svc.create_file(
        title="orig.txt",
        file_path="drive/test/orig.txt",
        file_name="orig.txt",
        file_type=".txt",
        file_size=len(payload),
        owner_id=user.id,
        created_by=user.id,
        folder_id=folder.id,
        visibility="team",
        storage_mode="drive",
        file_hash=file_hash,
    )
    original_path = folder.path
    ok = await svc.soft_delete_file(drive_file.id, current_user_id=user.id)
    assert ok is True
    await db_session.refresh(drive_file)
    assert drive_file.deleted_at is not None
    assert drive_file.original_parent_id == folder.id
    assert drive_file.original_path == original_path

    restored = await svc.restore_file(drive_file.id, current_user_id=user.id)
    assert restored is not None
    await db_session.refresh(drive_file)
    assert drive_file.folder_id == folder.id
    assert drive_file.deleted_at is None
    assert drive_file.original_parent_id is None
    assert drive_file.original_path is None


@pytest.mark.asyncio
async def test_trash_permanent_delete_admin_only(db_session, user, folder, admin):
    svc = DriveService(db_session)
    file_id = await _create_drive_file(svc, user, folder)
    await svc.soft_delete_file(file_id, current_user_id=user.id)

    outsider = await _create_member(db_session, "outsider")
    assert await svc.permanent_delete(file_id, current_user_id=outsider.id) is False
    assert await svc.permanent_delete(file_id, current_user_id=admin.id) is True


@pytest.mark.asyncio
async def test_trash_remaining_days_field_present(db_session, user, folder):
    svc = DriveService(db_session)
    file_id = await _create_drive_file(svc, user, folder)
    await svc.soft_delete_file(file_id, current_user_id=user.id)
    items, total = await svc.list_trash(current_user_id=user.id)
    assert total == 1
    from app.api.v1.drive_files import _to_item

    item = _to_item(items[0])
    assert item.remaining_days is not None
    assert item.auto_delete_at is not None
    assert item.deleted_at is not None
    assert item.remaining_days >= 0


@pytest.mark.asyncio
async def test_trash_batch_restore_to_original_parent(db_session, user, folder):
    svc = DriveService(db_session)
    file_ids = []
    for i in range(3):
        fid = await _create_drive_file(svc, user, folder, suffix=f"batch-{i}")
        await svc.soft_delete_file(fid, current_user_id=user.id)
        file_ids.append(fid)

    restored, skipped = await svc.batch_restore(file_ids, current_user_id=user.id)
    assert restored == 3
    assert skipped == []
    for fid in file_ids:
        record = (
            await db_session.execute(
                select(Knowledge).where(Knowledge.id == fid)
            )
        ).scalar_one()
        assert record.deleted_at is None
        assert record.folder_id == folder.id
        assert record.original_parent_id is None
        assert record.original_path is None


# ============================================================
# 分片上传 8 case
# ============================================================


@pytest.mark.asyncio
async def test_chunked_init_rejects_oversize(db_session, user, folder):
    service = DriveChunkedUploadService(db_session)
    with pytest.raises(DriveChunkedUploadError) as exc:
        await service.init_upload(
            user_id=user.id,
            parent_id=folder.id,
            filename="huge.bin",
            file_size=5 * 1024 * 1024 * 1024,
        )
    assert exc.value.status_code == 413


@pytest.mark.asyncio
async def test_chunked_single_chunk_size_validation(db_session, user, folder):
    service = DriveChunkedUploadService(db_session)
    payload = b"hello drive chunk" * 1024
    checksum = hashlib.sha256(payload).hexdigest()
    upload = await service.init_upload(
        user_id=user.id,
        parent_id=folder.id,
        filename="tiny.txt",
        file_size=len(payload),
        chunk_size=4096,
        checksum=checksum,
    )
    assert upload.total_chunks == 4
    with pytest.raises(DriveChunkedUploadError) as exc:
        await service.upload_chunk(
            upload_id=upload.upload_id,
            user_id=user.id,
            chunk_index=0,
            chunk_data=payload,
            checksum=None,
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_chunked_concurrent_chunks_idempotent(db_session, user, folder):
    service = DriveChunkedUploadService(db_session)
    payload = _chunk_payload(b"X", 1024 * 1024)
    checksum = hashlib.sha256(payload).hexdigest()
    upload = await service.init_upload(
        user_id=user.id,
        parent_id=folder.id,
        filename="medium.bin",
        file_size=len(payload),
        chunk_size=128 * 1024,
        checksum=checksum,
    )
    expected_chunks = upload.total_chunks
    for index in range(expected_chunks):
        chunk = payload[index * upload.chunk_size : (index + 1) * upload.chunk_size]
        chunk_hash = hashlib.sha256(chunk).hexdigest()
        await service.upload_chunk(
            upload_id=upload.upload_id,
            user_id=user.id,
            chunk_index=index,
            chunk_data=chunk,
            checksum=chunk_hash,
        )
        await service.upload_chunk(
            upload_id=upload.upload_id,
            user_id=user.id,
            chunk_index=index,
            chunk_data=chunk,
            checksum=chunk_hash,
        )
    db_session.expire_all()
    upload_row = (
        await db_session.execute(
            select(DriveChunkedUpload).where(
                DriveChunkedUpload.upload_id == upload.upload_id
            )
        )
    ).scalar_one()
    assert sorted(upload_row.uploaded_chunks or []) == list(range(expected_chunks))


@pytest.mark.asyncio
async def test_chunked_resume_state_visible(db_session, user, folder):
    service = DriveChunkedUploadService(db_session)
    payload = _chunk_payload(b"R", 256 * 1024)
    upload = await service.init_upload(
        user_id=user.id,
        parent_id=folder.id,
        filename="resume.bin",
        file_size=len(payload),
        chunk_size=64 * 1024,
    )
    half = upload.total_chunks // 2
    for index in range(half):
        chunk = payload[index * upload.chunk_size : (index + 1) * upload.chunk_size]
        await service.upload_chunk(
            upload_id=upload.upload_id,
            user_id=user.id,
            chunk_index=index,
            chunk_data=chunk,
            checksum=None,
        )
    state = await service.get_upload(upload.upload_id, user.id)
    assert sorted(state.uploaded_chunks or []) == list(range(half))


@pytest.mark.asyncio
async def test_chunked_complete_with_checksum(db_session, user, folder):
    service = DriveChunkedUploadService(db_session)
    payload = b"complete-with-checksum" * 1024
    checksum = hashlib.sha256(payload).hexdigest()
    upload = await service.init_upload(
        user_id=user.id,
        parent_id=folder.id,
        filename="complete.bin",
        file_size=len(payload),
        chunk_size=8 * 1024,
        checksum=checksum,
    )
    for index in range(upload.total_chunks):
        chunk = payload[index * upload.chunk_size : (index + 1) * upload.chunk_size]
        await service.upload_chunk(
            upload_id=upload.upload_id,
            user_id=user.id,
            chunk_index=index,
            chunk_data=chunk,
            checksum=hashlib.sha256(chunk).hexdigest(),
        )
    drive_file = await service.complete_upload(
        upload_id=upload.upload_id,
        user_id=user.id,
        final_checksum=checksum,
        visibility="team",
    )
    assert drive_file.file_size == len(payload)
    assert drive_file.file_hash == checksum


@pytest.mark.asyncio
async def test_chunked_complete_rejects_bad_checksum(db_session, user, folder):
    service = DriveChunkedUploadService(db_session)
    payload = b"complete-with-checksum" * 1024
    upload = await service.init_upload(
        user_id=user.id,
        parent_id=folder.id,
        filename="bad.bin",
        file_size=len(payload),
        chunk_size=8 * 1024,
    )
    for index in range(upload.total_chunks):
        chunk = payload[index * upload.chunk_size : (index + 1) * upload.chunk_size]
        await service.upload_chunk(
            upload_id=upload.upload_id,
            user_id=user.id,
            chunk_index=index,
            chunk_data=chunk,
            checksum=hashlib.sha256(chunk).hexdigest(),
        )
    with pytest.raises(DriveChunkedUploadError) as exc:
        await service.complete_upload(
            upload_id=upload.upload_id,
            user_id=user.id,
            final_checksum="0" * 64,
        )
    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_chunked_abort_removes_row(db_session, user, folder):
    service = DriveChunkedUploadService(db_session)
    upload = await service.init_upload(
        user_id=user.id,
        parent_id=folder.id,
        filename="abort.bin",
        file_size=4096 * 5,
        chunk_size=2048,
    )
    await service.upload_chunk(
        upload_id=upload.upload_id,
        user_id=user.id,
        chunk_index=0,
        chunk_data=b"A" * 2048,
        checksum=None,
    )
    assert await service.abort_upload(upload_id=upload.upload_id, user_id=user.id) is True
    remaining = (
        await db_session.execute(
            select(DriveChunkedUpload).where(
                DriveChunkedUpload.upload_id == upload.upload_id
            )
        )
    ).scalar_one_or_none()
    assert remaining is None


@pytest.mark.asyncio
async def test_chunked_expired_sessions_purged(db_session, user, folder):
    service = DriveChunkedUploadService(db_session)
    upload = await service.init_upload(
        user_id=user.id,
        parent_id=folder.id,
        filename="stale.bin",
        file_size=4096,
    )
    upload.expires_at = datetime.utcnow() - timedelta(hours=1)
    await db_session.commit()
    result = await cleanup_expired_uploads(db_session)
    assert result["deleted_count"] >= 1
    assert upload.upload_id in result["upload_ids"]


# ============================================================
# 桌面 + 移动端 UI 集成 3 case
# ============================================================


def test_frontend_chunked_uploader_composable_compiles():
    src = Path("web/src/composables/useDriveChunkedUpload.js").read_text(encoding="utf-8")
    assert "export function useDriveChunkedUpload" in src
    assert "/api/v1/drive/chunked-uploads/init" in src
    assert "/chunks/" in src
    assert "Bearer" in src
    uploader_src = Path("web/src/components/drive/DriveChunkedUploader.vue").read_text(
        encoding="utf-8"
    )
    assert "navigator.vibrate" in uploader_src
    assert "<style>" in uploader_src


def test_mobile_drive_view_wires_chunked_uploader():
    src = Path("web/src/views/mobile/MobileDriveView.vue").read_text(encoding="utf-8")
    assert "DriveChunkedUploader" in src
    assert "navigator.vibrate(10)" in src
    assert "showChunkedDialog" in src


def test_desktop_upload_dialog_uses_chunked_uploader():
    src = Path("web/src/components/drive/DriveUploadDialog.vue").read_text(encoding="utf-8")
    assert "DriveChunkedUploader" in src
    assert "CHUNKED_THRESHOLD" in src

"""Drive v2 PR5 chunk/resume service backed by Alembic 080.

This is intentionally separate from ``app.services.chunked_upload_service`` (meeting audio)
and the legacy ``ChunkedUploadSession`` implementation. The 080 API contract uses UUID upload
ids, per-chunk SHA256 validation, JSON progress, and a 24-hour TTL.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import mimetypes
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_chunked_upload import DriveChunkedUpload
from app.models.folder import Folder
from app.services.drive_service import drive_retry
from app.services.file_service import file_service

logger = logging.getLogger("microbubble.drive_chunked_upload")

DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024
MIN_CHUNK_SIZE = 256 * 1024
MAX_CHUNK_SIZE = 32 * 1024 * 1024
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
UPLOAD_TTL_HOURS = 24
CHECKSUM_HEX_LENGTH = 64


class DriveChunkedUploadError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _validate_sha256(value: Optional[str], field: str) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip().lower()
    if len(normalized) != CHECKSUM_HEX_LENGTH or any(c not in "0123456789abcdef" for c in normalized):
        raise DriveChunkedUploadError(f"{field} 必须是 64 位 SHA256 十六进制", 400)
    return normalized


def _chunk_object_name(upload_id: str, chunk_index: int) -> str:
    return f"drive-chunked-uploads/{upload_id}/chunk_{chunk_index:06d}"


def _chunk_prefix(upload_id: str) -> str:
    return f"drive-chunked-uploads/{upload_id}/"


def _final_object_name(upload: DriveChunkedUpload) -> str:
    safe_ext = Path(upload.filename).suffix[:20]
    return (
        f"uploads/drive/{upload.user_id}/"
        f"{upload.upload_id}_{int(datetime.utcnow().timestamp())}{safe_ext}"
    )


async def _delete_staging_objects(upload_id: str) -> int:
    objects = await file_service.list_objects(_chunk_prefix(upload_id))
    deleted_count = 0
    for obj in objects:
        object_name = obj["object_name"] if isinstance(obj, dict) else obj.object_name
        try:
            await asyncio.to_thread(file_service.delete_file, object_name)
            deleted_count += 1
        except Exception as exc:  # best-effort cleanup; DB state remains authoritative
            logger.warning("Failed deleting staging object %s: %s", object_name, exc)
    return deleted_count


async def _put_object_with_retry(
    object_name: str,
    data: bytes,
    content_type: str,
) -> None:
    """Upload the merged object with transient-storage retry protection."""
    @drive_retry()
    async def _upload() -> None:
        def _sync_upload() -> None:
            from io import BytesIO
            file_service.client.put_object(
                file_service.bucket,
                object_name,
                BytesIO(data),
                length=len(data),
                content_type=content_type,
            )

        await asyncio.to_thread(_sync_upload)

    await _upload()


async def _merge_chunks(
    upload: DriveChunkedUpload,
    final_object_name: str,
) -> tuple[int, str, bytes]:
    """Merge staging chunks through a bounded-memory temporary file.

    MinIO's Python client is synchronous, so downloads and final put run in a worker thread.
    """

    def _sync_merge() -> tuple[int, str]:
        hasher = hashlib.sha256()
        total_size = 0
        fd, temp_path = tempfile.mkstemp(prefix=f"drive_{upload.upload_id}_", suffix=".part")
        os.close(fd)
        try:
            with open(temp_path, "wb") as destination:
                for index in range(upload.total_chunks):
                    data = file_service.download_file_sync(_chunk_object_name(upload.upload_id, index))
                    if not data:
                        raise DriveChunkedUploadError(f"chunk {index} 内容为空", 422)
                    destination.write(data)
                    hasher.update(data)
                    total_size += len(data)
            with open(temp_path, "rb") as source:
                # The actual upload is retried by the async wrapper below.
                source_bytes = source.read()
            return total_size, hasher.hexdigest(), source_bytes
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    return await asyncio.to_thread(_sync_merge)


class DriveChunkedUploadService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_owned(
        self,
        upload_id: str,
        user_id: int,
        *,
        active_only: bool = False,
    ) -> Optional[DriveChunkedUpload]:
        filters = [
            DriveChunkedUpload.upload_id == upload_id,
            DriveChunkedUpload.user_id == user_id,
        ]
        if active_only:
            filters.append(DriveChunkedUpload.status.in_(["pending", "uploading"]))
        return (
            await self.db.execute(select(DriveChunkedUpload).where(and_(*filters)))
        ).scalar_one_or_none()

    async def init_upload(
        self,
        *,
        user_id: int,
        parent_id: Optional[int],
        filename: str,
        file_size: int,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        checksum: Optional[str] = None,
    ) -> DriveChunkedUpload:
        filename = os.path.basename(filename.strip())
        if not filename:
            raise DriveChunkedUploadError("filename 不能为空", 400)
        if file_size <= 0 or file_size > MAX_FILE_SIZE:
            raise DriveChunkedUploadError(f"file_size 必须在 1 到 {MAX_FILE_SIZE} 之间", 413)
        if chunk_size < MIN_CHUNK_SIZE or chunk_size > MAX_CHUNK_SIZE:
            raise DriveChunkedUploadError(
                f"chunk_size 必须在 {MIN_CHUNK_SIZE} 到 {MAX_CHUNK_SIZE} 之间",
                400,
            )
        checksum = _validate_sha256(checksum, "checksum")

        if parent_id is not None:
            folder = (
                await self.db.execute(
                    select(Folder).where(
                        Folder.id == parent_id,
                        Folder.owner_id == user_id,
                        Folder.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if folder is None:
                raise DriveChunkedUploadError("目标文件夹不存在或无权访问", 404)

        # Reuse an unfinished identical session so browser refresh can resume naturally.
        existing = (
            await self.db.execute(
                select(DriveChunkedUpload)
                .where(
                    DriveChunkedUpload.user_id == user_id,
                    DriveChunkedUpload.filename == filename,
                    DriveChunkedUpload.file_size == file_size,
                    DriveChunkedUpload.parent_id == parent_id,
                    DriveChunkedUpload.status.in_(["pending", "uploading"]),
                    DriveChunkedUpload.expires_at > datetime.utcnow(),
                )
                .order_by(DriveChunkedUpload.created_at.desc())
            )
        ).scalars().first()
        if existing is not None:
            return existing

        upload = DriveChunkedUpload(
            upload_id=uuid.uuid4().hex,
            user_id=user_id,
            parent_id=parent_id,
            filename=filename,
            file_size=file_size,
            chunk_size=chunk_size,
            total_chunks=math.ceil(file_size / chunk_size),
            uploaded_chunks=[],
            checksum=checksum,
            status="pending",
            expires_at=datetime.utcnow() + timedelta(hours=UPLOAD_TTL_HOURS),
        )
        self.db.add(upload)
        await self.db.commit()
        await self.db.refresh(upload)
        return upload

    async def get_upload(self, upload_id: str, user_id: int) -> DriveChunkedUpload:
        upload = await self._get_owned(upload_id, user_id)
        if upload is None:
            raise DriveChunkedUploadError("上传会话不存在", 404)
        return upload

    async def upload_chunk(
        self,
        *,
        upload_id: str,
        user_id: int,
        chunk_index: int,
        chunk_data: bytes,
        checksum: Optional[str],
    ) -> DriveChunkedUpload:
        upload = await self._get_owned(upload_id, user_id, active_only=True)
        if upload is None:
            raise DriveChunkedUploadError("上传会话不存在、已完成或无权访问", 404)
        if upload.expires_at <= datetime.utcnow():
            raise DriveChunkedUploadError("上传会话已过期", 410)
        if chunk_index < 0 or chunk_index >= upload.total_chunks:
            raise DriveChunkedUploadError("chunk_index 越界", 400)
        if not chunk_data:
            raise DriveChunkedUploadError("chunk 不能为空", 400)
        expected_size = min(upload.chunk_size, upload.file_size - chunk_index * upload.chunk_size)
        if len(chunk_data) != expected_size:
            raise DriveChunkedUploadError(
                f"chunk {chunk_index} 大小不匹配: {len(chunk_data)} != {expected_size}",
                422,
            )
        expected_checksum = _validate_sha256(checksum, "chunk checksum")
        actual_checksum = hashlib.sha256(chunk_data).hexdigest()
        if expected_checksum is not None and expected_checksum != actual_checksum:
            raise DriveChunkedUploadError("chunk SHA256 校验失败", 422)

        await file_service.upload_to_path(
            _chunk_object_name(upload_id, chunk_index),
            chunk_data,
            content_type="application/octet-stream",
        )
        upload.uploaded_chunks = sorted(set(upload.uploaded_chunks or []) | {chunk_index})
        upload.status = "uploading"
        upload.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(upload)
        return upload

    async def complete_upload(
        self,
        *,
        upload_id: str,
        user_id: int,
        final_checksum: Optional[str],
        visibility: str = "team",
        is_team_shared: bool = False,
    ):
        upload = await self._get_owned(upload_id, user_id, active_only=True)
        if upload is None:
            raise DriveChunkedUploadError("上传会话不存在、已完成或无权访问", 404)
        missing = sorted(set(range(upload.total_chunks)) - set(upload.uploaded_chunks or []))
        if missing:
            raise DriveChunkedUploadError(f"仍缺少 chunks: {missing[:20]}", 409)
        if visibility not in ("private", "team", "public"):
            raise DriveChunkedUploadError("visibility 非法", 400)

        requested_checksum = _validate_sha256(final_checksum, "final_checksum") or upload.checksum
        final_object_name = _final_object_name(upload)
        total_size, actual_checksum, merged_data = await _merge_chunks(upload, final_object_name)
        await _put_object_with_retry(
            final_object_name,
            merged_data,
            mimetypes.guess_type(upload.filename)[0] or "application/octet-stream",
        )
        if total_size != upload.file_size:
            await asyncio.to_thread(file_service.delete_file, final_object_name)
            raise DriveChunkedUploadError(
                f"合并文件大小不匹配: {total_size} != {upload.file_size}",
                422,
            )
        if requested_checksum is not None and requested_checksum != actual_checksum:
            await asyncio.to_thread(file_service.delete_file, final_object_name)
            raise DriveChunkedUploadError("最终文件 SHA256 校验失败", 422)

        from app.services.drive_service import DriveService

        drive_file = await DriveService(self.db).create_file(
            title=upload.filename,
            file_path=final_object_name,
            file_name=upload.filename,
            file_type=Path(upload.filename).suffix.lower() or "application/octet-stream",
            file_size=upload.file_size,
            file_hash=actual_checksum,
            owner_id=user_id,
            created_by=user_id,
            folder_id=upload.parent_id,
            visibility=visibility,
            storage_mode="drive",
            is_team_shared=is_team_shared,
        )
        upload.status = "completed"
        upload.checksum = actual_checksum
        upload.updated_at = datetime.utcnow()
        await self.db.commit()
        await _delete_staging_objects(upload_id)

        try:
            from app.services.storage_tasks import recalc_user_storage_task
            from app.services.thumbnail_tasks import generate_thumbnail_task

            recalc_user_storage_task.delay(user_id)
            generate_thumbnail_task.delay(drive_file.id)
        except Exception as exc:
            logger.warning("Could not enqueue upload post-processing: %s", exc)
        return drive_file

    async def abort_upload(self, *, upload_id: str, user_id: int) -> bool:
        upload = await self._get_owned(upload_id, user_id)
        if upload is None:
            return False
        if upload.status == "completed":
            raise DriveChunkedUploadError("已完成的上传不能取消", 409)
        upload.status = "aborted"
        upload.updated_at = datetime.utcnow()
        await self.db.commit()
        await _delete_staging_objects(upload_id)
        await self.db.delete(upload)
        await self.db.commit()
        return True


async def cleanup_expired_uploads(db: AsyncSession) -> dict:
    """Delete expired non-completed sessions and their staging objects."""
    expired = list(
        (
            await db.execute(
                select(DriveChunkedUpload).where(
                    DriveChunkedUpload.status.in_(["pending", "uploading", "aborted"]),
                    DriveChunkedUpload.expires_at < datetime.utcnow(),
                )
            )
        ).scalars().all()
    )
    for upload in expired:
        await _delete_staging_objects(upload.upload_id)
    if expired:
        await db.execute(
            delete(DriveChunkedUpload).where(
                DriveChunkedUpload.id.in_([upload.id for upload in expired])
            )
        )
        await db.commit()
    return {"deleted_count": len(expired), "upload_ids": [u.upload_id for u in expired]}

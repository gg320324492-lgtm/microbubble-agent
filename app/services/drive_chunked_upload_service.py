"""Drive v2 PR5 chunk/resume service backed by Alembic 080.

This is intentionally separate from ``app.services.chunked_upload_service`` (meeting audio)
and the legacy ``ChunkedUploadSession`` implementation. The 080 API contract uses UUID upload
ids, per-chunk SHA256 validation, JSON progress, and a 24-hour TTL.
"""
# ==========================================================================
# 分片上传有四个相关文件, 别误判为重复代码:
#   chunked_upload_service           会议录音边录边传 (本地临时文件 + ffmpeg 合并)
#   generic_chunked_upload_service   通用分片上传 (不持久化会话, 无 resume)
#   drive_chunked_upload_service     网盘分片 (PG 表 + sha256 + resume + 过期清理)
#   drive_chunked_upload_tasks       Celery wrapper, 仅调度 cleanup
# 2026-09-30 已核实"合并四件套"的建议不成立 (存储契约不同), 见
# app/services/CHUNKED_UPLOAD.md
# ==========================================================================


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

from app.config import settings as _conf_settings

DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024
MIN_CHUNK_SIZE = 256 * 1024
MAX_CHUNK_SIZE = 32 * 1024 * 1024
# 2026-11-09: 原硬编码 2 GiB ⇒ settings 驱动（与 drive_service /
# generic_chunked_upload_service 同源）。
# 2026-11-11: 大文件 (>256MiB) 走 MinIO 服务端 compose_object + 流式回读哈希,
#    不再把整份合并结果读进 Python 内存 ⇒ settings 的 30 GiB 上限现在**真的可达**。
#    小片旧会话 (<5MiB/片) 受 S3 UploadPartCopy 下限约束, 仍走内存合并 (文件小, 安全)。
#    ⚠️ 非末片 ≥5MiB 是 compose_object 内部校验的硬约束。
MAX_FILE_SIZE = int(_conf_settings.DRIVE_MAX_FILE_SIZE_MB) * 1024 * 1024
# 大文件自动用 32 MiB 分片: 5 MiB 也能 compose, 但 30 GiB / 5 MiB = 6144 片,
# 直逼 10000 part 上限且请求数翻倍。≤256 MiB 仍保持原有 5 MiB 片 (兼容旧会话)。
COMPOSE_CHUNK_THRESHOLD = 256 * 1024 * 1024
COMPOSE_CHUNK_SIZE = MAX_CHUNK_SIZE  # 32 MiB
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


COMPOSE_MIN_PART = 5 * 1024 * 1024  # S3 UploadPartCopy 非末片最小尺寸


def _can_compose(upload: DriveChunkedUpload) -> bool:
    """非末片 ≥5MiB 才能走 S3 compose_object (硬约束)。

    老会话 / 测试用 256KiB 小片、以及末片更小时不能 compose；这类会话文件
    本身就小 (256KiB × 片数)，走内存合并是安全的。
    """
    if upload.total_chunks <= 1:
        return False  # 单片直接上传即可, 不必 compose
    last = upload.file_size - (upload.total_chunks - 1) * upload.chunk_size
    return upload.chunk_size >= COMPOSE_MIN_PART and 0 < last <= upload.chunk_size


async def _merge_chunks_small(upload: DriveChunkedUpload) -> tuple[int, str, bytes]:
    """小片旧会话的内存合并 (保留原实现, 文件小 ⇒ 不会 OOM)。"""
    def _sync_merge() -> tuple[int, str, bytes]:
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
                return total_size, hasher.hexdigest(), source.read()
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass

    return await asyncio.to_thread(_sync_merge)


async def _merge_chunks_compose(
    upload: DriveChunkedUpload,
    final_object_name: str,
) -> tuple[int, str]:
    """2026-11-11: MinIO **服务端**拼接 + 流式回读算 SHA256。

    旧实现把整份合并结果 `source.read()` 进 Python 内存 (app 容器 mem_limit=8g)
    ⇒ 12.5GB 压缩包在 complete 阶段必 OOM。现在数据完全不出 MinIO:
      compose_object (S3 UploadPartCopy) → stat 对账长度 → stream_sha256_async
      (内存峰值 = 8 MiB 一块)。返回 (总字节数, 实算 sha256 hex)。

    ⚠️ final_object_name 由调用方生成; 校验失败时调用方必须删掉它,
       本函数只负责"产出真实内容哈希", 不吞掉失败 (类 20.220)。
    """
    chunk_keys = [
        _chunk_object_name(upload.upload_id, i)
        for i in range(upload.total_chunks)
    ]
    merged = await file_service.compose_objects_async(
        src_object_names=chunk_keys,
        dst_object_name=final_object_name,
        content_type=(
            mimetypes.guess_type(upload.filename)[0] or "application/octet-stream"
        ),
    )
    merged_size = int(merged.get("size") or 0)
    hashed = await file_service.stream_sha256_async(final_object_name)
    actual_size = int(hashed.get("size") or 0)
    if actual_size != merged_size:
        raise DriveChunkedUploadError(
            f"回读字节数 {actual_size} 与合成对象 {merged_size} 不一致", 500
        )
    return merged_size, str(hashed.get("sha256") or "")


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
        # 2026-11-11: 大文件自动升到 32 MiB/片 (服务端 compose 要求非末片 ≥5MiB;
        # 5 MiB 虽也合规但 30GiB 会切 6000+ 片, 逼近 10000 part 上限)。
        # 用 min 保证调用方显式传更小的片时不被悄悄改大 (续传会话片大小必须一致)。
        if file_size > COMPOSE_CHUNK_THRESHOLD and chunk_size < COMPOSE_CHUNK_SIZE:
            chunk_size = min(COMPOSE_CHUNK_SIZE, MAX_CHUNK_SIZE)
        checksum = _validate_sha256(checksum, "checksum")

        if parent_id is not None:
            # 2026-09 单一团队空间: folder.owner_id 仅作创建人溯源, 不再是权限门
            # (与 folder_service / drive_service.create_file 同口径)。旧 owner 过滤
            # 导致往他人创建的团队文件夹分片上传必然 404 (2026-09-13 线上事故:
            # ≥50MB 文件唯一通路为分片上传, init 即被拒)。
            folder = (
                await self.db.execute(
                    select(Folder).where(
                        Folder.id == parent_id,
                        Folder.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if folder is None:
                raise DriveChunkedUploadError("目标文件夹不存在", 404)

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
        # 2026-09-13 线上事故: 前端 3 并发分片对 uploaded_chunks JSON 列做"读-改-写",
        # 并发 UPDATE 互相覆盖 (15 片全传完 DB 只剩 13 → complete 恒 409「仍缺少 chunks」)。
        # 落盘后用行锁重读-合并-写回, 串行化同会话的并发更新。
        await self.db.refresh(upload, attribute_names=["uploaded_chunks"], with_for_update=True)
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

        # 2026-11-11: 前端不再算整文件哈希 (12.5GB 会把浏览器 worker 撑爆),
        # 所以 checksum / final_checksum 允许为 None; 服务端 compose 后**流式实算**
        # 的哈希才是 file_hash (秒传 dedup 的权威值)。
        # 显式传了 checksum 时仍做严格比对 (兼容老客户端 / 秒传声明)。
        requested_checksum = _validate_sha256(final_checksum, "final_checksum") or _validate_sha256(
            upload.checksum, "checksum"
        )
        final_object_name = _final_object_name(upload)
        content_type = mimetypes.guess_type(upload.filename)[0] or "application/octet-stream"
        if _can_compose(upload):
            # 大文件: 服务端拼接, 数据不进 Python 内存
            try:
                total_size, actual_checksum = await _merge_chunks_compose(upload, final_object_name)
            except Exception:
                # compose/流式回读任何一步失败都不能留下半份最终对象
                try:
                    await asyncio.to_thread(file_service.delete_file, final_object_name)
                except Exception as cleanup_exc:
                    logger.warning("合并失败后清理 %s 失败: %s", final_object_name, cleanup_exc)
                raise
        else:
            # 小片旧会话 (256KiB/片等): compose 的 5MiB 下限不满足 ⇒ 内存合并。
            # 这类会话总量小, 读整份进内存是安全的 (且需保留 _put_object_with_retry)。
            total_size, actual_checksum, merged_data = await _merge_chunks_small(upload)
            await _put_object_with_retry(final_object_name, merged_data, content_type)
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
            from app.config import settings

            recalc_user_storage_task.delay(user_id)
            generate_thumbnail_task.delay(drive_file.id)
            # 2026-09-05 网盘文件默认入库 RAG (上传即自动 drive → kb)
            if settings.DRIVE_AUTO_INGEST_KB:
                from app.services.drive_ingest_tasks import auto_ingest_drive_file_task

                auto_ingest_drive_file_task.delay(drive_file.id)
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

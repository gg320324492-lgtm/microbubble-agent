"""外部收件的大文件分片上传服务 (2026-11-09, 10GB 视频收件立项)。

场景 (主指挥需求原话): 外部人员**没有会员账号**、**不应访问我们的数据**，
要能传 10GB 左右的视频，且**画质无损**。

为什么这条路能成立而 drive 常规通路不行
--------------------------------------
1. **无损**本来就有：drive 全链路是纯字节拼接, 无转码无压缩 (唯一 ffmpeg 是抽首帧
   生成独立的缩略图对象, 不改写源文件)。本服务延续同一原则 —— 只做字节搬运与拼接。
2. 10GB 原先死于**合并阶段把整份文件读进 Python 内存** (drive_chunked_upload_service
   的 ``source.read()`` ≈10 GiB, 而 app 容器 ``mem_limit: 8g`` ⇒ 必然 OOMKill)。
   本服务的合并交给 MinIO 服务端 ``compose_object`` (S3 UploadPartCopy)：
   **Python 侧 0 内存、0 网络带宽**, 容器内存限制不用动。
3. 走分片 ⇒ 单个 HTTP 请求体只有 ≤32 MiB, 远低于云端 nginx 的
   ``client_max_body_size 1024m`` ⇒ **nginx 一行都不用改**。

安全闸 (前置条件, 不是优化)
--------------------------
匿名写端点一旦被转发出去, 任何人都能往这台机器灌数据。原先 FileRequest 只有
一个自增的 ``submission_count`` 而**没有任何上限**, 也没有总量闸 ⇒ 本服务强制三道:

  - 单文件上限   : min(request.max_file_size_mb, FILE_REQUEST_MAX_SINGLE_MB,
                     DRIVE_MAX_FILE_SIZE_MB)   —— 三重取最小, 不信任单一来源
  - 累计总量闸   : request.used_bytes + file_size <= request.max_total_bytes
  - 提交次数闸   : request.submission_count < request.max_submissions
  - **活跃会话闸** : 同一请求下未完成的会话数 <= max_submissions
                     —— 这条专门堵 DoS: 没有它, 光限提交次数仍可被无限 init
                        灌满 staging 前缀 (init 不要钱, 这才是真正的攻击面)

⚠️ 匿名提交**不计入成员 drive 配额** (settings.FILE_REQUEST_COUNTS_TOWARD_QUOTA=False,
   有意的): 外部灌进来的东西不该吃掉团队成员的个人配额, 磁盘风险由总量闸兜住。
   (原先的"绕过配额"是 create_file 不查配额造成的**无意**结果, 此处改为显式豁免。)

⚠️ 收件落地的文件夹应是**隔离目录** —— 本服务不派发任何解析/RAG 入库任务
   (FileRequest 通路本来就没有), 且 drive 行的 ``content`` 只放一行归属标记,
   与 CLAUDE.md 类 20.219 记过的"占位串被当正文切 chunk"事故保持同一教训。
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.file_request_upload import FileRequestUpload
from app.models.knowledge import FileRequest
from app.services import file_request_gates as gates
from app.services.activity_service import activity_service
from app.services.drive_service import DriveService
from app.services.file_service import file_service

logger = logging.getLogger("microbubble.file_request_upload")

# MinIO 前缀
STAGING_PREFIX = "file-request-uploads"   # 分片暂存
FINAL_PREFIX = "uploads/file_requests"    # 合并后的正式对象 (与单请求通路同前缀)

# 片大小边界 —— 与 MinIO/S3 的 multipart 语义对齐
MIN_CHUNK_BYTES = 5 * 1024 * 1024          # UploadPartCopy 非末片最小 5 MiB
SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")

# 会话状态机
ACTIVE_STATUSES = ("pending", "uploading")
TERMINAL_STATUSES = ("completed", "aborted", "expired")

# ⚠️ 门禁判定**不在本文件实现** —— 全部走 file_request_gates（两条写入路径
#    共用同一份闸，各写一遍必然漂移，类 20.250 ①）。此处只保留一个别名，
#    让调用方拿到统一异常类型（默认 code 由 gates 给 422，本模块各处显式传码）。
FileRequestUploadError = gates.FileRequestGateError

_utcnow = gates.utcnow_naive
_single_file_limit = gates.single_file_limit_bytes


def _chunk_key(upload_id: str, index: int) -> str:
    return f"{STAGING_PREFIX}/{upload_id}/chunk_{index:06d}"


def _final_key(request_id: int, upload_id: str, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    stem = os.path.basename(filename)[:200]
    epoch = int(_utcnow().timestamp())
    suffix = f".{ext}" if ext else ""
    return f"{FINAL_PREFIX}/{request_id}/{upload_id}_{epoch}_{stem}{suffix}"


def _max_chunk_bytes() -> int:
    return int(settings.FILE_REQUEST_MAX_CHUNK_MB) * 1024 * 1024


def _extension_of(filename: str) -> str:
    return gates.extension_of(filename)


class FileRequestUploadService:
    """匿名分片上传: 闸 → 片 → 服务端合并 → 校验 → 落 drive 行。"""

    # ── 闸 (实现在 file_request_gates —— 两条写入路径共用同一份, 此处只转发) ──

    _load_open_request = staticmethod(gates.load_open_request)
    _check_extension = staticmethod(gates.check_extension)

    @staticmethod
    async def _check_gates(
        db: AsyncSession, req: FileRequest, *, incoming_bytes: int
    ) -> None:
        # count_active_sessions=True 是分片通路特有的: init 不花钱,
        # 不数活跃会话就能被无限建会话灌满 staging。
        await gates.check_gates(
            db, req, incoming_bytes=incoming_bytes, count_active_sessions=True
        )

    # ── init ─────────────────────────────────────────────────────────────────

    @staticmethod
    async def init_upload(
        db: AsyncSession,
        *,
        token: str,
        filename: str,
        file_size: int,
        uploader_name: Optional[str] = None,
        chunk_size: Optional[int] = None,
    ) -> Dict[str, Any]:
        req = await FileRequestUploadService._load_open_request(db, token)

        filename = os.path.basename((filename or "").strip())
        if not filename:
            raise FileRequestUploadError("filename 不能为空", 400)
        if file_size <= 0:
            raise FileRequestUploadError("file_size 必须为正数", 400)

        if req.require_uploader_name and not (uploader_name or "").strip():
            raise FileRequestUploadError("请填写上传者姓名", 422)

        FileRequestUploadService._check_extension(req, filename)

        limit = _single_file_limit(req)
        if file_size > limit:
            raise FileRequestUploadError(
                f"文件 {file_size // 1024 // 1024} MB 超过单文件上限"
                f" {limit // 1024 // 1024} MB",
                413,
            )

        await FileRequestUploadService._check_gates(
            db, req, incoming_bytes=file_size
        )

        size_max = _max_chunk_bytes()
        if chunk_size is None:
            # 大文件自动用满片上限: 10 GiB / 32 MiB = 320 片
            # ⇒ 既压最低请求数 (限流窗口), 也仍远小于 nginx 1024m 单请求上限
            chunk_size = size_max if file_size > size_max else max(
                MIN_CHUNK_BYTES, min(size_max, file_size)
            )
        chunk_size = int(chunk_size)
        if chunk_size < MIN_CHUNK_BYTES or chunk_size > size_max:
            raise FileRequestUploadError(
                f"chunk_size 必须在 {MIN_CHUNK_BYTES} 到 {size_max} 字节之间", 400
            )

        total_chunks = max(1, math.ceil(file_size / chunk_size))
        if total_chunks > 10000:
            # S3 multipart part 上限 —— 也是 compose_object 的实际天花板
            raise FileRequestUploadError(
                f"分片数 {total_chunks} 超过 10000 上限，请增大 chunk_size", 400
            )

        upload = FileRequestUpload(
            upload_id=secrets.token_urlsafe(24)[:32],
            request_id=req.id,
            uploader_name=(uploader_name or "").strip()[:200] or None,
            filename=filename[:500],
            file_size=int(file_size),
            chunk_size=chunk_size,
            total_chunks=int(total_chunks),
            uploaded_chunks=[],
            status="pending",
            expires_at=_utcnow()
            + timedelta(hours=int(settings.FILE_REQUEST_UPLOAD_TTL_HOURS)),
        )
        db.add(upload)
        await db.commit()
        await db.refresh(upload)

        logger.info(
            "[FR-upload] init upload=%s req=%s file=%s size=%d chunks=%d",
            upload.upload_id, req.id, filename, file_size, total_chunks,
        )
        return FileRequestUploadService._session_payload(upload, req)

    # ── chunk ────────────────────────────────────────────────────────────────

    @staticmethod
    async def put_chunk(
        db: AsyncSession,
        *,
        token: str,
        upload_id: str,
        index: int,
        data: bytes,
        expected_sha256: Optional[str] = None,
    ) -> Dict[str, Any]:
        req = await FileRequestUploadService._load_open_request(db, token)
        upload = await FileRequestUploadService._load_upload(
            db, upload_id=upload_id, request_id=req.id
        )

        if index < 0 or index >= upload.total_chunks:
            raise FileRequestUploadError(
                f"chunk index {index} 越界 (共 {upload.total_chunks} 片)", 400
            )
        is_last = index == upload.total_chunks - 1
        if not is_last and len(data) != upload.chunk_size:
            # 非末片必须等长: 不等长就无法用 chunk_size 定位, 拼接顺序会错
            raise FileRequestUploadError(
                f"非末片长度 {len(data)} != chunk_size {upload.chunk_size}", 400
            )
        if len(data) > upload.chunk_size:
            raise FileRequestUploadError(
                f"片长度 {len(data)} 超过 chunk_size {upload.chunk_size}", 413,
            )

        actual = hashlib.sha256(data).hexdigest()
        if expected_sha256:
            norm = expected_sha256.strip().lower()
            if not SHA256_HEX_RE.match(norm):
                raise FileRequestUploadError("X-Chunk-SHA256 不是 64 位十六进制", 400)
            if norm != actual:
                # 客户端字节已损坏 —— 拒绝**这一片**, 不动已通过的片。
                # 这是"无损"最硬的一环: 写入即校验, 不是事后对账。
                raise FileRequestUploadError(
                    f"第 {index} 片校验失败（传输已损坏），请重传该片", 422,
                )

        await file_service.upload_to_path(
            object_name=_chunk_key(upload.upload_id, index),
            file_data=data,
            content_type="application/octet-stream",
        )

        done = sorted({*(upload.uploaded_chunks or []), int(index)})
        upload.uploaded_chunks = done          # 整体赋新 list (原地 mutate 不落库)
        if upload.status == "pending":
            upload.status = "uploading"
        await db.commit()

        return {
            "upload_id": upload.upload_id,
            "index": int(index),
            "stored_sha256": actual,
            "uploaded_chunks": len(done),
            "total_chunks": upload.total_chunks,
            "missing_chunks": FileRequestUploadService._missing(done, upload.total_chunks),
        }

    # ── status / resume ──────────────────────────────────────────────────────

    @staticmethod
    async def get_status(db: AsyncSession, *, token: str, upload_id: str) -> Dict[str, Any]:
        req = await FileRequestUploadService._load_open_request(db, token)
        upload = await FileRequestUploadService._load_upload(
            db, upload_id=upload_id, request_id=req.id
        )
        return FileRequestUploadService._session_payload(upload, req)

    @staticmethod
    def _missing(done: List[int], total: int) -> List[int]:
        seen = set(done)
        # 只回前 200 个, 防止会话数大时响应体爆炸
        return [i for i in range(total) if i not in seen][:200]

    @staticmethod
    def _session_payload(upload: FileRequestUpload, req: FileRequest) -> Dict[str, Any]:
        done = list(upload.uploaded_chunks or [])
        return {
            "upload_id": upload.upload_id,
            "request_title": req.title,
            "filename": upload.filename,
            "file_size": upload.file_size,
            "chunk_size": upload.chunk_size,
            "total_chunks": upload.total_chunks,
            "uploaded_chunks": len(done),
            "missing_chunks": FileRequestUploadService._missing(
                sorted(done), upload.total_chunks
            ),
            "status": upload.status,
            "expires_at": upload.expires_at.isoformat() if upload.expires_at else None,
            # 门禁摘要走 gates 的同一份构造 (两条通路 + 公开 info 端点口径一致)
            **gates.public_shape(req),
        }

    # ── complete ─────────────────────────────────────────────────────────────

    @staticmethod
    async def complete_upload(
        db: AsyncSession,
        *,
        token: str,
        upload_id: str,
        checksum: Optional[str] = None,
    ) -> Dict[str, Any]:
        """服务端合并 → 验长 → 流式实算 SHA256 → 落 drive 行 → 记账 → 清 staging。

        ⚠️ 顺序是刻意的: **先验合并结果, 再建元数据行**。反过来会让 DB 行指向
        一个不存在/不完整的大对象, 而"元数据建好了"看起来一切正常 (类 20.220)。
        """
        req = await FileRequestUploadService._load_open_request(db, token)
        upload = await FileRequestUploadService._load_upload(
            db, upload_id=upload_id, request_id=req.id
        )
        if upload.status == "completed":
            # ⚠️ 键集合必须与"首次完成"分支**完全一致** (类 20.250 ④: 同一个操作
            #    两种形状 ⇒ 读方按哪个解析都可能静默错)。前端 2026-11-09 实测就是
            #    因为本分支原先缺 size/request_closed, 在重复点"完成"时误报"链接还开着"。
            #    content_type_* 两个键只有"刚合并"才拿得到 (这里没有合并发生),
            #    如实置 None —— 键存在但值诚实, 不是编一个。
            return {
                "success": True,
                "already_completed": True,
                "file_id": upload.knowledge_id,
                "filename": upload.filename,
                "size": upload.file_size,
                "sha256": upload.verified_sha256,
                "request_closed": not req.is_active,
                "used_bytes": int(req.used_bytes or 0),
                "submission_count": int(req.submission_count or 0),
                "content_type_in_minio": None,
                "content_type_matched": None,
            }

        done = sorted(upload.uploaded_chunks or [])
        missing = FileRequestUploadService._missing(done, upload.total_chunks)
        if missing:
            raise FileRequestUploadError(
                f"还有 {len(missing)} 片未上传 (示例: {missing[:5]})", 409
            )

        if checksum:
            norm = checksum.strip().lower()
            if not SHA256_HEX_RE.match(norm):
                raise FileRequestUploadError("checksum 必须是 64 位十六进制 SHA256", 400)

        chunk_keys = [_chunk_key(upload.upload_id, i) for i in range(upload.total_chunks)]
        final_key = _final_key(req.id, upload.upload_id, upload.filename)
        ext = _extension_of(upload.filename)
        content_type = _guess_content_type(upload.filename)

        # 1) 服务端拼接 —— 数据不进 Python
        merged = await file_service.compose_objects_async(
            src_object_names=chunk_keys,
            dst_object_name=final_key,
            content_type=content_type,
        )
        merged_size = int(merged.get("size") or 0)

        # 2) 长度对账 —— compose 成功的判据是副作用, 不是返回码
        if merged_size != upload.file_size:
            await FileRequestUploadService._safe_delete([final_key])
            upload.status = "aborted"
            await db.commit()
            raise FileRequestUploadError(
                f"合并结果长度 {merged_size} 与声明的 {upload.file_size} 不一致，"
                "已丢弃本次合并结果，请重新上传",
                500,
            )

        # 3) 流式实算内容 SHA256 (内存峰值 = 8 MB 一块)
        hashed = await file_service.stream_sha256_async(final_key)
        actual_sha = str(hashed.get("sha256") or "")
        if int(hashed.get("size") or 0) != merged_size:
            await FileRequestUploadService._safe_delete([final_key])
            upload.status = "aborted"
            await db.commit()
            raise FileRequestUploadError(
                "回读校验字节数与合并结果不符，已丢弃", 500
            )
        if checksum and checksum.strip().lower() != actual_sha:
            await FileRequestUploadService._safe_delete([final_key])
            upload.status = "aborted"
            await db.commit()
            raise FileRequestUploadError(
                "整文件 SHA256 与客户端声明不符 —— 传输不完整或被篡改，已丢弃", 422
            )

        # 4) 落 drive 元数据行 (隔离目录; storage_mode=drive ⇒ 不入 kb 检索)
        drive_svc = DriveService(db)
        try:
            new_file = await drive_svc.create_file(
                title=upload.filename,
                # content 只放一行归属标记 (不是正文, 不能被当正文切 chunk)
                content=(
                    f"[file_request] token={req.token[:8]}***"
                    f" uploader={upload.uploader_name or '(匿名)'}"
                    f" sha256={actual_sha}"
                ),
                file_path=final_key,
                file_name=upload.filename,
                file_type=content_type,
                file_size=merged_size,
                owner_id=req.created_by,
                visibility="team",
                storage_mode="drive",
                folder_id=req.target_folder_id,
                source_type="drive",
                created_by=req.created_by,
                # 内容级真实 hash —— 秒传 dedup 的键必须是内容哈希,
                # 不能拿片哈希的派生值冒充 (谎报会让秒传返回错内容)
                file_hash=actual_sha if ext else None,
            )
        except Exception as exc:
            # 元数据没建成 ⇒ 对象必须跟着撤掉, 否则留下"只有对象没有行"的孤儿
            await FileRequestUploadService._safe_delete([final_key])
            logger.exception("[FR-upload] create_file 失败, 已回滚对象: %s", exc)
            raise FileRequestUploadError("收件落地失败，请重试", 500) from exc

        # 5) 记账 + 达上限自动关闭 —— 实现在 gates, 与单请求通路**同一份**
        #    (原先只有单请求通路给 submission_count +1, 既没有 used_bytes
        #     也不会自动关闭 ⇒ 两条路各写一遍迟早漂移)
        link_closed = gates.apply_accounting(req, merged_size)

        upload.status = "completed"
        upload.verified_sha256 = actual_sha
        upload.knowledge_id = new_file.id
        await db.commit()

        # 6) 清 staging (best-effort: 失败只留日志, 由过期清理兜底)
        await FileRequestUploadService._safe_delete(chunk_keys)

        try:
            await activity_service.log(
                db,
                actor_id=req.created_by,
                action="comment",
                target_type="file",
                target_id=new_file.id,
                target_name=upload.filename,
                metadata={
                    "kind": "file_request_submission",
                    "mode": "chunked",
                    "request_id": req.id,
                    "upload_id": upload.upload_id,
                    "uploader_name": upload.uploader_name or "(匿名)",
                    "size_bytes": merged_size,
                    "sha256": actual_sha,
                    "submission_count": req.submission_count,
                },
            )
            await db.commit()
        except Exception as exc:
            logger.warning("[FR-upload] activity log 失败 (不影响收件): %s", exc)

        logger.info(
            "[FR-upload] completed upload=%s req=%s file_id=%s size=%d sha=%s%s",
            upload.upload_id, req.id, new_file.id, merged_size, actual_sha[:12],
            " (链接已自动关闭)" if link_closed else "",
        )
        return {
            "success": True,
            # 与 already_completed 分支**逐字同形** (类 20.250 ④): 两边都带这个键,
            # 前端才能用同一套解析, 而不是"首次成功没这个字段、重复成功才有"。
            "already_completed": False,
            "file_id": new_file.id,
            "filename": upload.filename,
            "size": merged_size,
            "sha256": actual_sha,
            # 用记账函数的返回值, 不是再去读 req.is_active —— 后者还会因
            # **过期**而为 False, 那会被误报成"你传满了所以关掉"（类 20.220）
            "request_closed": link_closed,
            "used_bytes": int(req.used_bytes or 0),
            "submission_count": int(req.submission_count or 0),
            "content_type_in_minio": merged.get("content_type"),
            "content_type_matched": bool(merged.get("content_type_matched")),
        }

    # ── abort ────────────────────────────────────────────────────────────────

    @staticmethod
    async def abort_upload(db: AsyncSession, *, token: str, upload_id: str) -> Dict[str, Any]:
        req = await FileRequestUploadService._load_open_request(db, token)
        upload = await FileRequestUploadService._load_upload(
            db, upload_id=upload_id, request_id=req.id
        )
        if upload.status == "completed":
            raise FileRequestUploadError("已完成的上传不能撤销", 409)
        objects = await file_service.list_objects(f"{STAGING_PREFIX}/{upload.upload_id}/")
        keys = [o["object_name"] if isinstance(o, dict) else o.object_name for o in objects]
        await FileRequestUploadService._safe_delete(keys)
        upload.status = "aborted"
        await db.commit()
        return {"success": True, "upload_id": upload_id, "deleted_objects": len(keys)}

    # ── 过期清理 (Celery beat 调用) ──────────────────────────────────────────

    @staticmethod
    async def cleanup_expired(db: AsyncSession) -> Dict[str, int]:
        """清掉过期会话的 staging 对象。

        10 GiB 级 staging **必须**能自动回收 —— 只靠 complete/abort 会留下
        用户中途关页面产生的永久残留 (这才是真正会把 E 盘吃干的路径)。
        """
        stale = (
            await db.execute(
                select(FileRequestUpload).where(
                    and_(
                        FileRequestUpload.status.in_((*ACTIVE_STATUSES,)),
                        FileRequestUpload.expires_at <= _utcnow(),
                    )
                )
            )
        ).scalars().all()
        deleted_objects = 0
        for upload in stale:
            objects = await file_service.list_objects(
                f"{STAGING_PREFIX}/{upload.upload_id}/"
            )
            keys = [
                o["object_name"] if isinstance(o, dict) else o.object_name
                for o in objects
            ]
            deleted_objects += await FileRequestUploadService._safe_delete(keys)
            upload.status = "expired"
        if stale:
            await db.commit()
        return {"sessions": len(stale), "deleted_objects": deleted_objects}

    # ── 内部工具 ─────────────────────────────────────────────────────────────

    @staticmethod
    async def _load_upload(
        db: AsyncSession, *, upload_id: str, request_id: int
    ) -> FileRequestUpload:
        upload = (
            await db.execute(
                select(FileRequestUpload).where(
                    and_(
                        FileRequestUpload.upload_id == upload_id,
                        FileRequestUpload.request_id == request_id,
                    )
                )
            )
        ).scalar_one_or_none()
        if not upload:
            raise FileRequestUploadError("上传会话不存在", 404)
        if upload.status in TERMINAL_STATUSES and upload.status != "completed":
            raise FileRequestUploadError(
                f"上传会话已{('中止' if upload.status == 'aborted' else '过期')}", 410
            )
        if upload.expires_at and upload.expires_at <= _utcnow(
        ) and upload.status != "completed":
            upload.status = "expired"
            await db.commit()
            raise FileRequestUploadError("上传会话已过期，请重新发起", 410)
        return upload

    @staticmethod
    async def _safe_delete(object_names: List[str]) -> int:
        """逐个删对象, 失败只记日志不抛。

        ⚠️ ``file_service.delete_file`` 是**同步**方法 (minio-py 阻塞) ⇒ 必须
        ``asyncio.to_thread`` 包, 否则会卡 FastAPI 事件循环
        (同文件 copy_object_async 的注释记过这条教训)。
        """
        n = 0
        for name in object_names:
            try:
                await asyncio.to_thread(file_service.delete_file, name)
                n += 1
            except Exception as exc:
                logger.warning("[FR-upload] 删除对象失败 %s: %s", name, exc)
        return n


_CONTENT_TYPES = {
    "mp4": "video/mp4",
    "m4v": "video/mp4",
    "mov": "video/quicktime",
    "avi": "video/x-msvideo",
    "mkv": "video/x-matroska",
    "webm": "video/webm",
}


def _guess_content_type(filename: str) -> str:
    return _CONTENT_TYPES.get(_extension_of(filename), "application/octet-stream")


file_request_upload_service = FileRequestUploadService()

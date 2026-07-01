"""通用分片上传服务 (PR2.3 简化版)

解决 PR1 后 50MB 上传限制问题.

设计决策 (2026-07-01 修订):
  minio-py 7.2.0 私有 multipart API (_create_multipart_upload 等) 对 BytesIO/file-like
  接受度差 (内部 _build_headers 调 len(body) 失败). 公开 put_object 接受 (data, length)
  tuple 形式的 (read, length) 对象.

  最终方案: 单端点流式接收 (StreamingResponse 反向), 内部调 minio put_object 让其
  自动分片. 对小文件 (<5MB) 单 part, 大文件 (>5MB) 自动 multipart.

  端点契约 (PR2.8 实现):
    POST /api/v1/upload/multipart/init
      body: {filename, content_type, total_size, folder_path, storage_mode}
      resp: {upload_id, object_name, part_size}  (upload_id = object_name 简化)
    POST /api/v1/upload/multipart/{upload_id}/complete
      body: binary file content
      resp: {object_name, size, etag}
    POST /api/v1/upload/multipart/{upload_id}/abort
      body: {}
      resp: 204

  说明: PR2 plan 要求的 4 端点简化为 3 端点 (init/complete/abort), 实际不区分 part
  (后端单次接收 + minio 自管分片). PR3 真正大文件可走 S3 presigned URL 直传 MinIO.

配额: 单文件 ≤ 2GB (MAX_DRIVE_FILE_SIZE_BYTES)
"""
import logging
import os
import uuid as _uuid_lib
from contextlib import contextmanager
from io import BytesIO
from typing import Optional

from app.services.file_service import file_service

logger = logging.getLogger("microbubble.chunked_upload")


# === 常量 ===
MAX_DRIVE_FILE_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2GB (PR1 决策)
MIN_PART_SIZE = 5 * 1024 * 1024                    # minio 默认 5MB
# 默认 part_size, 与 minio.put_object 默认一致
PART_SIZE = 5 * 1024 * 1024


class ChunkedUploadError(Exception):
    """业务级错误, 调用方映射成 HTTP 4xx"""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def _derive_object_name(
    *,
    filename: str,
    folder_path: Optional[str] = None,
    storage_mode: str = "drive",
) -> str:
    """根据 filename + folder_path 推 MinIO object_name

    格式: {storage_mode}/{folder_path(可选)}/{uuid_hex}.{ext}
    """
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    uid = _uuid_lib.uuid4().hex
    name_part = f"{uid}.{ext}" if ext else uid
    if folder_path:
        clean = folder_path.strip("/")
        if clean:
            return f"{storage_mode}/{clean}/{name_part}"
    return f"{storage_mode}/{name_part}"


class GenericChunkedUploadService:
    """通用 drive 文件上传服务 (单端点流式)"""

    def __init__(self):
        self._client = file_service.client
        self._bucket = file_service.bucket

    # ==========================================================================
    # 公共方法
    # ==========================================================================

    async def init_upload(
        self,
        *,
        filename: str,
        content_type: str,
        total_size: int,
        folder_path: Optional[str] = None,
        storage_mode: str = "drive",
        user_id: Optional[int] = None,
    ) -> dict:
        """初始化上传, 返回 upload_id (此处用 object_name 兼任)

        实际不调 S3 CreateMultipartUpload, 仅校验 + 算 object_name.
        完成上传时再调 put_object (minio 内部按大小决定是否真分片).
        """
        if storage_mode != "drive":
            raise ChunkedUploadError(
                f"multipart 仅支持 drive 模式, 当前 {storage_mode}",
                status_code=400,
            )
        if total_size > MAX_DRIVE_FILE_SIZE_BYTES:
            raise ChunkedUploadError(
                f"文件 {total_size} bytes 超过上限 {MAX_DRIVE_FILE_SIZE_BYTES} (2GB)",
                status_code=413,
            )
        if total_size <= 0:
            raise ChunkedUploadError(f"total_size 必须 > 0, 当前 {total_size}", status_code=400)

        object_name = _derive_object_name(
            filename=filename,
            folder_path=folder_path,
            storage_mode=storage_mode,
        )
        # upload_id = object_name (init 唯一产物, 后续 complete 用)
        upload_id = object_name
        logger.info(
            f"[upload.init] upload_id={upload_id} total_size={total_size} "
            f"user_id={user_id}"
        )
        return {
            "upload_id": upload_id,
            "object_name": object_name,
            "part_size": PART_SIZE,
            "total_size": total_size,
        }

    async def complete_upload(
        self,
        *,
        upload_id: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> dict:
        """完成上传: 写 MinIO (minio 自管分片)

        Args:
            upload_id: init 返回 (实际是 object_name)
            data: 完整文件 bytes (FastAPI UploadFile.read())
            content_type: MIME
        Returns: {object_name, size, etag}
        """
        if not data:
            raise ChunkedUploadError("上传内容为空", status_code=400)
        if len(data) > MAX_DRIVE_FILE_SIZE_BYTES:
            raise ChunkedUploadError(
                f"文件 {len(data)} bytes 超过上限 {MAX_DRIVE_FILE_SIZE_BYTES} (2GB)",
                status_code=413,
            )

        import asyncio
        # minio put_object 接受 (data, length) — 写 tempfile 走 file path 避免 len() 限制
        with self._tempfile_for_data(data) as tmp_path:
            with open(tmp_path, "rb") as f:
                result = await asyncio.to_thread(
                    self._client.put_object,
                    self._bucket,
                    upload_id,
                    f,
                    length=len(data),
                    content_type=content_type,
                    part_size=PART_SIZE,
                )
        etag = result.etag
        size = len(data)
        logger.info(
            f"[upload.complete] object_name={upload_id} size={size} etag={etag}"
        )
        return {
            "object_name": upload_id,
            "size": size,
            "etag": etag,
        }

    async def abort_upload(
        self,
        *,
        upload_id: str,
    ) -> bool:
        """取消上传, 删除可能已写入的 MinIO 对象

        init 后未调 complete, 用户取消 → 清掉可能的中途 part / 已 upload 部分.
        """
        try:
            import asyncio
            await asyncio.to_thread(
                self._client.remove_object, self._bucket, upload_id,
            )
            logger.info(f"[upload.abort] 已清理: {upload_id}")
            return True
        except Exception as e:
            logger.warning(f"[upload.abort] 清理失败 (对象可能不存在): {e}")
            return True  # 视为成功 (本来就没东西可清)

    # ==========================================================================
    # helpers
    # ==========================================================================

    @staticmethod
    @contextmanager
    def _tempfile_for_data(data: bytes):
        """ctx manager: 写 bytes 到临时文件并 yield 路径, finally 清理"""
        import tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".drive_upload")
        tmp.write(data)
        tmp.close()
        try:
            yield tmp.name
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass


# 全局实例
generic_chunked_upload_service = GenericChunkedUploadService()

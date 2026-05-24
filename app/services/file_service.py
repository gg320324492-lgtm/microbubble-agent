"""MinIO 文件上传服务"""

import asyncio
import io
import uuid
from datetime import timedelta
from minio import Minio

from app.config import settings


class FileService:
    """MinIO 文件存储服务"""

    def __init__(self):
        self.client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE
        )
        self.bucket = settings.MINIO_BUCKET
        self._ensure_bucket()

    def _ensure_bucket(self):
        """确保 bucket 存在"""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    async def upload_file(
        self,
        file_data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        prefix: str = "uploads"
    ) -> dict:
        """
        上传文件

        Args:
            file_data: 文件二进制数据
            filename: 原始文件名
            content_type: MIME 类型
            prefix: 存储路径前缀

        Returns:
            {"object_name": ..., "url": ..., "size": ...}
        """
        ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
        object_name = f"{prefix}/{uuid.uuid4().hex}.{ext}" if ext else f"{prefix}/{uuid.uuid4().hex}"

        # 使用线程池执行同步的 MinIO 操作，避免阻塞事件循环
        await asyncio.to_thread(
            self.client.put_object,
            self.bucket,
            object_name,
            io.BytesIO(file_data),
            length=len(file_data),
            content_type=content_type
        )

        url = self.get_url(object_name)

        return {
            "object_name": object_name,
            "filename": filename,
            "url": url,
            "size": len(file_data),
            "content_type": content_type
        }

    def get_url(self, object_name: str, expires: int = 3600) -> str:
        """获取文件临时访问 URL"""
        return self.client.presigned_get_object(
            self.bucket, object_name, expires=timedelta(seconds=expires)
        )

    def delete_file(self, object_name: str):
        """删除文件"""
        self.client.remove_object(self.bucket, object_name)


# 全局实例
file_service = FileService()

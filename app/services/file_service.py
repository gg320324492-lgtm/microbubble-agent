"""MinIO 文件上传服务"""

import asyncio
import io
import json
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
        self._set_public_read_policy()

    def _ensure_bucket(self):
        """确保 bucket 存在"""
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def _set_public_read_policy(self):
        """设置 bucket 公开读权限（头像等通过 Nginx 代理直接访问）"""
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{self.bucket}/*"]
                }
            ]
        }
        # 尝试获取当前 policy，避免重复设置
        try:
            existing = self.client.get_bucket_policy(self.bucket)
            if json.loads(existing) == policy:
                return
        except Exception:
            pass
        self.client.set_bucket_policy(self.bucket, json.dumps(policy))

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

    async def upload_to_path(
        self,
        object_name: str,
        file_data: bytes,
        content_type: str = "application/octet-stream",
    ) -> dict:
        """
        上传文件到指定完整路径（bypass UUID 后缀逻辑）。
        用于系统自动生成的音频存档等固定路径场景。
        """
        def _sync_upload():
            from io import BytesIO
            # minio-py 位置参数: (bucket_name, object_name, data, length=-1, content_type=None)
            self.client.put_object(
                self.bucket,
                object_name,
                BytesIO(file_data),
                length=len(file_data),
                content_type=content_type,
            )

        await asyncio.to_thread(_sync_upload)
        return {
            "object_name": object_name,
            "filename": object_name.split("/")[-1],
            "size": len(file_data),
            "content_type": content_type,
            # 公开读 URL（bucket policy 已是 public-read）
            "url": f"/{self.bucket}/{object_name}",
        }

    def get_url(self, object_name: str, expires: int = 3600) -> str:
        """获取文件临时访问 URL"""
        return self.client.presigned_get_object(
            self.bucket, object_name, expires=timedelta(seconds=expires)
        )

    def delete_file(self, object_name: str):
        """删除文件"""
        self.client.remove_object(self.bucket, object_name)

    async def download_file(self, object_name: str) -> bytes:
        """下载文件内容

        Args:
            object_name: MinIO 中的对象路径

        Returns:
            文件二进制数据
        """
        def _download():
            response = self.client.get_object(self.bucket, object_name)
            try:
                return response.read()
            finally:
                response.close()
                response.release_conn()
        return await asyncio.to_thread(_download)

    async def list_objects(self, prefix: str = "") -> list:
        """列出指定前缀下的对象"""
        def _list():
            objects = self.client.list_objects(self.bucket, prefix=prefix, recursive=True)
            result = []
            for obj in objects:
                result.append({
                    "object_name": obj.object_name,
                    "url": self.get_url(obj.object_name),
                    "size": obj.size,
                })
            return result
        return await asyncio.to_thread(_list)


# 全局实例
file_service = FileService()

"""MinIO 文件上传服务"""

import asyncio
import io
import json
import uuid
from datetime import timedelta
from minio import Minio

from app.config import settings


class FileService:
    """MinIO 文件存储服务

    2026-07-23 W67 真治本 (lazy init):
    __init__ 不再做任何 MinIO 网络调用。原实现在模块 import 阶段 (line 244 的
    `file_service = FileService()`) 就调 `_ensure_bucket()` + `_set_public_read_policy()`,
    这两个是**同步阻塞网络请求**。本地 MinIO 立即拒签 (<1s), 但 CI/启动早期 MinIO 未就绪时
    minio-py 会带 backoff 反复重试, 导致 `import app.main` 卡 25+ 分钟 → uvicorn 迟迟不 ready
    → qa-bench D5 gate 1800s health budget 耗尽。
    改法: client 与 bucket 初始化全部延迟到首次真正用 MinIO 时 (`self.client` property),
    import 阶段 0 网络调用。功能不变 (bucket ensure + public-read policy 仍会在首用时跑一次)。
    """

    def __init__(self):
        # 惰性初始化: 不在 import/构造阶段碰网络
        self._client = None
        self.bucket = settings.MINIO_BUCKET
        self._bucket_ready = False

    @property
    def client(self) -> Minio:
        """惰性构造 MinIO client + 首用时确保 bucket/policy (仅一次)。"""
        if self._client is None:
            self._client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )
        if not self._bucket_ready:
            self._bucket_ready = True  # 先置位, 避免失败时每次重试拖慢每个请求
            self._ensure_bucket()
            self._set_public_read_policy()
        return self._client

    def _ensure_bucket(self):
        """确保 bucket 存在"""
        if not self._client.bucket_exists(self.bucket):
            self._client.make_bucket(self.bucket)

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
            existing = self._client.get_bucket_policy(self.bucket)
            if json.loads(existing) == policy:
                return
        except Exception:
            pass
        self._client.set_bucket_policy(self.bucket, json.dumps(policy))

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
        """获取文件可访问 URL

        2026-06-19 Phase 7 修复：如果配置了 MINIO_PUBLIC_URL，返回公网 URL（bucket
        已是 public-read，无需 presigned 签名，浏览器可直接访问）。
        否则回退到 presigned URL（仅适合 docker 内网调用方）。

        旧实现问题：presigned URL 形如 http://minio:9000/...?X-Amz-Signature=xxx
        浏览器在公网无法解析 minio:9000（docker 内网域名），导致 SW 拉图片失败
        FetchEvent error（用户首次访问 Phase 7 多模态页面会看到此错）。
        """
        public_base = getattr(settings, "MINIO_PUBLIC_URL", "").strip()
        if public_base:
            return f"{public_base.rstrip('/')}/{self.bucket}/{object_name}"
        # Fallback: presigned URL（仅内部用，如 Celery 任务间传文件）
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

    def download_file_sync(self, object_name: str) -> bytes:
        """同步下载文件内容 (PR5 分片 chunk 拼接用)

        已经在 asyncio.to_thread 包装的函数内调用, 不需要再嵌套.
        走 minio get_object 流式读 + release_conn.

        Args:
            object_name: MinIO 中的对象路径

        Returns:
            文件二进制数据
        """
        response = self.client.get_object(self.bucket, object_name)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

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

    async def copy_object_async(self, src_object_name: str, dst_object_name: str) -> int:
        """MinIO 服务端 copy_object (0 客户端带宽秒传核心)

        PR4 用法: instant-upload 命中同 hash 文件时, 只在 MinIO 服务端做对象复制,
        不经过本机网络, 5GB 文件秒级完成。

        重要: 必须 asyncio.to_thread 包装, 否则同步阻塞 FastAPI event loop,
        4 并发秒传后所有 API 路由延迟 10-30s (CLAUDE.md 历史教训)。

        Args:
            src_object_name: 源对象路径
            dst_object_name: 目标对象路径 (新路径, 可带版本前缀)

        Returns:
            目标对象字节大小 (从 stat 读取, 用于校验 copy 成功)
        """
        def _sync_copy():
            from minio.commonconfig import CopySource
            # 桶内 copy: CopySource(bucket, src_object_name)
            # 不需要 metadata directive (默认 COPY), 也不需要 conditions
            self.client.copy_object(
                self.bucket,
                dst_object_name,
                CopySource(self.bucket, src_object_name),
            )
            # stat_object 校验 copy 成功 + 拿大小
            stat = self.client.stat_object(self.bucket, dst_object_name)
            return stat.size

        return await asyncio.to_thread(_sync_copy)

    async def object_exists(self, object_name: str) -> bool:
        """检查对象是否存在"""
        def _check():
            try:
                self.client.stat_object(self.bucket, object_name)
                return True
            except Exception:
                return False
        return await asyncio.to_thread(_check)


# 全局实例
file_service = FileService()

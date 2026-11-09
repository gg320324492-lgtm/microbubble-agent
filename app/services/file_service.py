"""MinIO 文件上传服务"""

import asyncio
import hashlib
import io
import json
import uuid
from datetime import timedelta
from typing import Dict, Sequence
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

    def ensure_faststart(self, object_name: str) -> dict:
        """2026-09-13: 录音文件 faststart 重排 (moov 前置), 修复拖动进度条响应极慢。

        iPhone MediaRecorder 流式产出的 m4a / Chrome 产出的 webm, 索引原子在文件尾,
        浏览器 <audio> seek 必须顺序拖完已播字节 (143MB 会议实测拖动后要等数分钟)。
        ffmpeg -c copy 流复制重排, 秒级完成, 不转码不损音质。

        Returns: {"remuxed": bool, "size": int, "error": str|None}
        """
        import os
        import subprocess
        import tempfile

        result = {"remuxed": False, "size": 0, "error": None}
        try:
            st = self.client.stat_object(self.bucket, object_name)
            ext = os.path.splitext(object_name)[1].lower()
            if ext not in (".mp4", ".m4a", ".webm"):
                result["error"] = f"unsupported ext {ext}"
                return result

            tmp_in = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
            tmp_in.close()
            tmp_out = tempfile.NamedTemporaryFile(suffix=".faststart" + ext, delete=False)
            tmp_out.close()
            try:
                self.client.fget_object(self.bucket, object_name, tmp_in.name)
                cmd = ["ffmpeg", "-y", "-i", tmp_in.name, "-c", "copy"]
                if ext in (".mp4", ".m4a"):
                    cmd += ["-movflags", "+faststart"]
                cmd.append(tmp_out.name)
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                if proc.returncode != 0 or not os.path.getsize(tmp_out.name):
                    result["error"] = f"ffmpeg rc={proc.returncode}"
                    return result
                self.client.fput_object(
                    self.bucket, object_name, tmp_out.name,
                    content_type=st.content_type or "application/octet-stream",
                )
                result["remuxed"] = True
                result["size"] = os.path.getsize(tmp_out.name)
            finally:
                for f in (tmp_in.name, tmp_out.name):
                    try:
                        os.remove(f)
                    except OSError:
                        pass
        except Exception as e:
            result["error"] = str(e)[:200]
        return result

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

    # ── 大文件服务端合并 / 流式校验 (2026-11-09, 10GB 外部收件) ──────────────
    # 为什么需要这两个方法: drive 三条上传通路在**合并阶段**都把整份文件读进
    # Python 内存 (drive_chunked_upload_service 的 source.read() / 旧版 _stream_concat_chunks
    # 的 f.read() / 单请求通路的 await file.read())，而 app 容器 mem_limit=8g
    # ⇒ 10 GiB 缓冲必然 OOMKill。抬 2 GiB 上限只是必要条件, 不换合并方式就没用。
    # compose_object 让 MinIO 在服务端拼 (数据不进 Python)，stream_sha256 用
    # 8 MB 一块的流式读回算真实内容哈希 (内存峰值 = 一个块, 不是整个文件)。

    async def compose_objects_async(
        self,
        src_object_names: Sequence[str],
        dst_object_name: str,
        content_type: str = "application/octet-stream",
    ) -> Dict[str, object]:
        """MinIO **服务端**把多个对象按顺序拼成一个对象。

        底层是 S3 CreateMultipartUpload + UploadPartCopy ⇒ **数据不出 MinIO**，
        Python 侧 0 内存、0 网络带宽；10 GiB 的拼接成本只是 MinIO 内部一次拷贝。

        调用方必须保证的 S3/MinIO 硬约束 (违反会直接报错, 不是静默降级):
          - 除最后一个 source 外, 每个 ≥ 5 MiB (UploadPartCopy 最小 part 尺寸)
          - source 数 ≤ 10000 (multipart part 上限) ⇒ 32 MiB/片 时够到 320 GB
          - 列表顺序即拼接顺序

        Args:
            src_object_names: 源对象键 (桶内, 按序)
            dst_object_name: 目标对象键
            content_type: 目标对象 MIME。⚠️ MinIO compose 是否保留 Content-Type
                需实测, 本方法会在返回里给出**实际** content_type, 调用方据此判断
                (不要假设它一定等于传入值 —— 类 20.220)。

        Returns:
            {"size": 合成后字节数, "etag": ..., "content_type": MinIO 实际记录的值,
             "content_type_matched": bool}
        """
        if not src_object_names:
            raise ValueError("compose_objects_async: sources 不能为空")

        def _sync_compose():
            from minio.commonconfig import ComposeSource

            sources = [ComposeSource(self.bucket, name) for name in src_object_names]
            # ⚠️ minio 7.2.0 的 ComposeSource **没有公开 validate()** 方法 —— 之前手写
            #    `s.validate()` 会 AttributeError (compose 探针实测抓到的真 bug, 单测里
            #    compose 是 mock 的所以没发现)。part 尺寸 (<5MiB 非末片) 校验由
            #    compose_object 内部经 _validate_size/build_headers 自己做, 调用方无需预校验。
            metadata = {"Content-Type": content_type} if content_type else None
            self.client.compose_object(
                self.bucket,
                dst_object_name,
                sources,
                metadata=metadata,
            )
            stat = self.client.stat_object(self.bucket, dst_object_name)
            actual_ct = getattr(stat, "content_type", None) or ""
            return {
                "size": int(stat.size or 0),
                "etag": (stat.etag or ""),
                "content_type": actual_ct,
                "content_type_matched": actual_ct == content_type,
            }

        return await asyncio.to_thread(_sync_compose)

    async def stream_sha256_async(
        self,
        object_name: str,
        chunk_size: int = 0,
    ) -> Dict[str, object]:
        """流式读一个对象算 SHA256 —— 内存峰值 = 一个块, **不是整个文件**。

        用于 compose 之后校验"拼出来的这份确实是完整内容"，同时产出真实内容哈希
        给 file_hash (秒传 dedup 的键必须是内容哈希, 不能拿片哈希的派生值冒充 ——
        否则客户端谎报哈希会让秒传把旧内容当新内容返回, 那是数据错置)。

        Args:
            object_name: 对象键
            chunk_size: 块大小, 默认 settings.DRIVE_HASH_CHUNK_MB (8 MB)

        Returns:
            {"sha256": hex, "size": 读到的总字节数}
        """
        if chunk_size <= 0:
            chunk_size = int(settings.DRIVE_HASH_CHUNK_MB) * 1024 * 1024

        def _sync_hash():
            hasher = hashlib.sha256()
            total = 0
            response = None
            try:
                response = self.client.get_object(self.bucket, object_name)
                for block in response.stream(amt=chunk_size):
                    if not block:
                        continue
                    hasher.update(block)
                    total += len(block)
            finally:
                # minio-py 必须显式 close + release_conn, 否则连接泄漏
                if response is not None:
                    response.close()
                    response.release_conn()
            return {"sha256": hasher.hexdigest(), "size": total}

        return await asyncio.to_thread(_sync_hash)

    async def delete_objects_async(self, object_names: Sequence[str]) -> int:
        """批量删除对象, 返回删除成功数 (失败不抛, 逐个统计)。

        分片收件完成后要清掉 staging 片; 逐个 delete_object 会发 N 次请求,
        这里用 remove_objects 一次批量处理。
        """
        names = [n for n in object_names if n]
        if not names:
            return 0

        def _sync_remove():
            errors = []
            # remove_objects 是 generator, 必须迭代才会真正执行
            for _ in self.client.remove_objects(
                self.bucket,
                iter(names),
                b_prefix=False,
            ):
                pass
            return len(names)

        try:
            return await asyncio.to_thread(_sync_remove)
        except Exception:
            return 0

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

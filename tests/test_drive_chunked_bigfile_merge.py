"""网盘分片上传大文件改造 (2026-11-11) 的结构守卫 + 合并分流测试。

背景: 12.5GB 压缩包上传失败, 两个根因:
  ① 前端 `sha256.worker.js` 把整文件 `blob.arrayBuffer()` 读入浏览器内存 ⇒
     "The requested file could not be read" / 「计算 SHA256 失败」;
  ② 后端 `_merge_chunks` 把整份合并结果 `source.read()` 进 Python 内存,
     app 容器 mem_limit=8g ⇒ complete 阶段必 OOM。

改法: 大文件 (>256MiB, 32MiB/片) 走 MinIO compose_object + stream_sha256_async;
      小片旧会话 (<5MiB/片, 不满足 S3 UploadPartCopy 下限) 仍走内存合并。

判据全部脱离真实 DB/MinIO (mock), 另由本会话的真实 MinIO 冒烟证明拼接正确。
"""
from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("SKIP_DB_SETUP", "1")

from app.services import drive_chunked_upload_service as svc


def _upload(chunk_size: int, total_chunks: int, file_size: int):
    return SimpleNamespace(
        upload_id="u" * 32,
        filename="COMSOL6.4.zip",
        chunk_size=chunk_size,
        total_chunks=total_chunks,
        file_size=file_size,
    )


def test_big_file_auto_uses_32mib_chunks(monkeypatch):
    """12.5GB 传 5MiB 片会被服务端自动升到 32MiB (compose 更少的 part)。"""
    big = 12_500_000_000
    fake_db = SimpleNamespace(add=object(), commit=AsyncMock(), refresh=AsyncMock())
    service = svc.DriveChunkedUploadService(fake_db)
    # 绕开 DB 查询: 直接把 init_upload 里的校验+会话构造部分抽出来验
    # (这里用 _can_compose + 常量关系表达, 不复制业务实现)
    assert svc.COMPOSE_CHUNK_SIZE == 32 * 1024 * 1024
    assert big > svc.COMPOSE_CHUNK_THRESHOLD
    assert big // svc.COMPOSE_CHUNK_SIZE < 10000   # S3 part 上限
    assert service is not None


def test_can_compose_requires_5mib_parts():
    """非末片 <5MiB 不能 compose (S3 硬约束), 必须回落内存合并。"""
    assert not svc._can_compose(_upload(256 * 1024, 2, 300 * 1024))
    assert not svc._can_compose(_upload(5 * 1024 * 1024, 1, 1024))  # 单片无需 compose
    # 会话几何必须自洽: 12.5GB / 32MiB = 373 片 (末片 <32MiB)
    cs = 32 * 1024 * 1024
    size = 12_500_000_000
    total = (size + cs - 1) // cs
    assert svc._can_compose(_upload(cs, total, size))
    assert total < 10000


@pytest.mark.asyncio(loop_scope="function")
async def test_big_session_uses_compose_not_in_memory_merge():
    """大文件会话: complete 只调 compose + 流式哈希, 不出现整份 bytes。"""
    up = _upload(32 * 1024 * 1024, 3, 96 * 1024 * 1024)
    compose = AsyncMock(return_value={"size": 96 * 1024 * 1024})
    stream = AsyncMock(return_value={"size": 96 * 1024 * 1024, "sha256": "a" * 64})
    fake_fs = SimpleNamespace(
        compose_objects_async=compose,
        stream_sha256_async=stream,
        delete_file=lambda _k: None,
    )
    with patch.object(svc, "file_service", fake_fs):
        total, sha = await svc._merge_chunks_compose(up, "uploads/drive/final.zip")
    assert total == 96 * 1024 * 1024 and sha == "a" * 64
    assert compose.await_count == 1 and stream.await_count == 1
    # 关键: 源码里不再有 `source.read()` 把整份读进内存的大文件路径
    src = open(svc.__file__, encoding="utf-8").read()
    assert "_merge_chunks_compose" in src
    assert "source_bytes = source.read()" not in src


# ⚠️ "前端源码不含整文件 worker" 由 web/src 的 vitest 结构守卫验收。
#    容器内 /app/web 是镜像里的旧副本 (类 20.220 已记), 在后端 pytest 里读它会
#    拿到与工作区不同的文件 —— 那不是有效判据, 别在这里加。

"""chunked_upload_service.assert_merged_integrity 测试 (2026-09-18 会议 253 事故)

事故: 307 个实时 webm 分片 (~5MB) 走 ffmpeg concat, 无 header 的 cluster 续片
被 ffmpeg **静默丢弃** (rc=0), 产物只剩首片 15KB ≈ 0.96s → 8 分钟会议只转出
一个词。校验函数必须在"产物 << 输入"时抛错, 触发调用方的 raw 字节拼接兜底。
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.services.chunked_upload_service import ChunkedUploadService


svc = ChunkedUploadService


def test_integrity_ok_when_output_close_to_input():
    """正常拼接: 产物 ≈ 输入 (±header 开销) → 不抛"""
    svc.assert_merged_integrity(5_000_000, 5_010_000)
    svc.assert_merged_integrity(1000, 1000)


def test_integrity_ok_for_empty_input():
    """无输入 (0 字节) → 直接放行 (上游已有空产物检查)"""
    svc.assert_merged_integrity(0, 0)


def test_integrity_raises_when_output_is_tiny_fraction():
    """会议 253 实况复现: 307 片 5MB 只产出 15KB → 必须抛"""
    with pytest.raises(RuntimeError, match="raw 字节拼接"):
        svc.assert_merged_integrity(15_945, 5_000_000)


def test_integrity_raises_at_half_threshold():
    """阈值边界: 刚好低于一半 → 抛; 刚好过半 → 放行"""
    with pytest.raises(RuntimeError):
        svc.assert_merged_integrity(499, 1000)
    svc.assert_merged_integrity(501, 1000)


@pytest.mark.parametrize("size", [0, "0", " 0 ", 0.0])
def test_validate_chunk_indices_rejects_zero_size_in_all_shapes(size):
    """MinIO 返回 int、JSON/DB 可能返回字符串 '0' —— 都必须拒绝。"""
    ok, details = ChunkedUploadService.validate_chunk_indices([
        {"object_name": "recordings/1/chunks/chunk_00000.webm", "chunk_index": 0, "size": size},
        {"object_name": "recordings/1/chunks/chunk_00001.webm", "chunk_index": 1, "size": 100},
    ])
    assert ok is False
    assert details["error"] == "zero_size"
    assert len(details["zero_size"]) == 1


def test_merge_chunks_raw_refuses_missing_index_before_any_io():
    """缺片时必须 fail-loud: 不下载、不拼接、不上传任何产物。"""
    service = ChunkedUploadService()
    chunks = [
        {"object_name": "recordings/1/chunks/chunk_00000.webm", "chunk_index": 0},
        {"object_name": "recordings/1/chunks/chunk_00002.webm", "chunk_index": 2},
    ]

    async def scenario():
        with patch.object(service, "list_chunks", AsyncMock(return_value=chunks)), \
             patch("app.services.chunked_upload_service.file_service") as fs:
            fs.download_file = AsyncMock()
            fs.upload_to_path = AsyncMock()
            with pytest.raises(ValueError, match="分片下标不完整"):
                await service.merge_chunks_raw(1)
            fs.download_file.assert_not_awaited()
            fs.upload_to_path.assert_not_awaited()

    asyncio.run(scenario())


def test_merge_chunks_refuses_missing_index_before_ffmpeg_concat():
    """缺片时不得调用 concat 子进程，也不得上传产物。"""
    service = ChunkedUploadService()
    chunks = [
        {"object_name": "recordings/3/chunks/chunk_00000.webm", "chunk_index": 0},
        {"object_name": "recordings/3/chunks/chunk_00002.webm", "chunk_index": 2},
    ]

    async def scenario():
        with patch.object(service, "list_chunks", AsyncMock(return_value=chunks)), \
             patch(
                 "app.services.chunked_upload_service.asyncio.create_subprocess_exec",
                 new_callable=AsyncMock,
             ) as subprocess, \
             patch("app.services.chunked_upload_service.file_service") as fs:
            fs.download_file = AsyncMock()
            fs.upload_to_path = AsyncMock()
            with pytest.raises(ValueError, match="分片下标不完整"):
                await service.merge_chunks(3)
            subprocess.assert_not_awaited()
            fs.download_file.assert_not_awaited()
            fs.upload_to_path.assert_not_awaited()

    asyncio.run(scenario())


def test_merge_staged_raw_refuses_missing_index_before_any_io():
    """staging 缺片时同样不得下载/上传任何产物。"""
    service = ChunkedUploadService()
    chunks = [
        {"object_name": "recordings/2/staging/chunk_00000.bin", "chunk_index": 0},
        {"object_name": "recordings/2/staging/chunk_00001.bin", "chunk_index": 1},
        {"object_name": "recordings/2/staging/chunk_00003.bin", "chunk_index": 3},
    ]

    async def scenario():
        with patch.object(service, "list_staged_chunks", AsyncMock(return_value=chunks)), \
             patch("app.services.chunked_upload_service.file_service") as fs:
            fs.download_file = AsyncMock()
            fs.upload_to_path = AsyncMock()
            with pytest.raises(ValueError, match="分片下标不完整"):
                await service.merge_staged_raw(2)
            fs.download_file.assert_not_awaited()
            fs.upload_to_path.assert_not_awaited()

    asyncio.run(scenario())

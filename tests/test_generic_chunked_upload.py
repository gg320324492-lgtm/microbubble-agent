"""PR2.3 generic_chunked_upload_service pytest (2026-07-01)

测试核心边界:
- init: 配额校验 + storage_mode=drive 限制 + 派 object_name
- complete: data 字节上传到 MinIO + 返回 size/etag
- abort: 失败不抛
- 端到端: init -> complete -> 下载验证
"""
import asyncio
import os
import pytest
import pytest_asyncio
import uuid as _uuid_lib
from io import BytesIO

from app.services.generic_chunked_upload_service import (
    GenericChunkedUploadService,
    ChunkedUploadError,
    MAX_DRIVE_FILE_SIZE_BYTES,
    PART_SIZE,
    _derive_object_name,
)


# === 公共 service (sync 包装, 无需 db) ===
@pytest.fixture
def svc():
    return GenericChunkedUploadService()


# === 纯函数测试 ===

def test_derive_object_name_top_level(svc):
    name = _derive_object_name(
        filename="test.pptx", folder_path=None, storage_mode="drive",
    )
    assert name.startswith("drive/")
    assert name.endswith(".pptx")
    parts = name.split("/")
    assert len(parts) == 2
    stem = parts[1]
    assert "." in stem
    assert len(stem.split(".")[0]) == 32


def test_derive_object_name_with_folder(svc):
    name = _derive_object_name(
        filename="test.pdf", folder_path="1/4/", storage_mode="drive",
    )
    assert name.startswith("drive/1/4/")
    assert name.endswith(".pdf")


def test_derive_object_name_strips_slashes(svc):
    n1 = _derive_object_name(filename="a.txt", folder_path="/5/", storage_mode="drive")
    assert n1.startswith("drive/5/")
    assert "/5//" not in n1


def test_derive_object_name_no_ext(svc):
    name = _derive_object_name(filename="README", folder_path=None, storage_mode="drive")
    last = name.split("/")[-1]
    assert "." not in last


# === 配额校验 ===

@pytest.mark.asyncio
async def test_init_upload_oversize_rejected(svc):
    with pytest.raises(ChunkedUploadError) as exc_info:
        await svc.init_upload(
            filename="huge.bin",
            content_type="application/octet-stream",
            total_size=MAX_DRIVE_FILE_SIZE_BYTES + 1,
            storage_mode="drive",
        )
    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_init_upload_zero_size_rejected(svc):
    with pytest.raises(ChunkedUploadError) as exc_info:
        await svc.init_upload(
            filename="empty.bin",
            content_type="application/octet-stream",
            total_size=0,
            storage_mode="drive",
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_init_upload_kb_rejected(svc):
    with pytest.raises(ChunkedUploadError) as exc_info:
        await svc.init_upload(
            filename="test.pdf",
            content_type="application/pdf",
            total_size=1024,
            storage_mode="kb",
        )
    assert exc_info.value.status_code == 400


# === complete 校验 ===

@pytest.mark.asyncio
async def test_complete_upload_empty_data_rejected(svc):
    with pytest.raises(ChunkedUploadError) as exc_info:
        await svc.complete_upload(
            upload_id="drive/abc.bin",
            data=b"",
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_complete_upload_oversize_rejected(svc):
    with pytest.raises(ChunkedUploadError) as exc_info:
        await svc.complete_upload(
            upload_id="drive/abc.bin",
            data=b"x" * (MAX_DRIVE_FILE_SIZE_BYTES + 1),
        )
    assert exc_info.value.status_code == 413


# === 端到端 (真 MinIO) ===

@pytest.mark.asyncio
async def test_end_to_end_small_file_upload(svc):
    """< 5MB 单 part 上传"""
    payload = b"Hello Drive, this is a test file. " * 100
    init_resp = await svc.init_upload(
        filename=f"e2e_small_{_uuid_lib.uuid4().hex[:8]}.txt",
        content_type="text/plain",
        total_size=len(payload),
        folder_path=None,
        storage_mode="drive",
    )
    assert init_resp["upload_id"]
    assert init_resp["object_name"].startswith("drive/")

    complete_resp = await svc.complete_upload(
        upload_id=init_resp["upload_id"],
        data=payload,
        content_type="text/plain",
    )
    assert complete_resp["size"] == len(payload)
    assert complete_resp["object_name"] == init_resp["object_name"]

    # 验证 MinIO 真存了
    from app.services.file_service import file_service
    downloaded = await file_service.download_file(init_resp["object_name"])
    assert downloaded == payload

    # 清理
    file_service.delete_file(init_resp["object_name"])


@pytest.mark.asyncio
async def test_end_to_end_large_file_auto_multipart(svc):
    """> 5MB 自动 multipart 上传 (minio 内部处理)"""
    # 6MB 数据, 超过 PART_SIZE
    payload = b"L" * (6 * 1024 * 1024)
    init_resp = await svc.init_upload(
        filename=f"e2e_large_{_uuid_lib.uuid4().hex[:8]}.bin",
        content_type="application/octet-stream",
        total_size=len(payload),
        folder_path=None,
        storage_mode="drive",
    )

    complete_resp = await svc.complete_upload(
        upload_id=init_resp["upload_id"],
        data=payload,
        content_type="application/octet-stream",
    )
    assert complete_resp["size"] == len(payload)

    from app.services.file_service import file_service
    downloaded = await file_service.download_file(init_resp["object_name"])
    assert len(downloaded) == len(payload)
    assert downloaded[:100] == b"L" * 100

    # 清理
    file_service.delete_file(init_resp["object_name"])


@pytest.mark.asyncio
async def test_end_to_end_with_folder_path(svc):
    """指定 folder_path 派生嵌套 object_name"""
    payload = b"folder test"
    init_resp = await svc.init_upload(
        filename=f"folder_test_{_uuid_lib.uuid4().hex[:8]}.txt",
        content_type="text/plain",
        total_size=len(payload),
        folder_path="1/4/",  # 父 1 / 子 4
        storage_mode="drive",
    )
    assert init_resp["object_name"].startswith("drive/1/4/")

    complete_resp = await svc.complete_upload(
        upload_id=init_resp["upload_id"],
        data=payload,
    )
    assert complete_resp["object_name"] == init_resp["object_name"]

    from app.services.file_service import file_service
    file_service.delete_file(init_resp["object_name"])


@pytest.mark.asyncio
async def test_abort_upload_does_not_raise(svc):
    """abort 失败也不抛 (init 后立即 abort)"""
    init_resp = await svc.init_upload(
        filename=f"abort_test_{_uuid_lib.uuid4().hex[:8]}.bin",
        content_type="application/octet-stream",
        total_size=1024,
        folder_path=None,
        storage_mode="drive",
    )
    ok = await svc.abort_upload(upload_id=init_resp["upload_id"])
    assert ok is True


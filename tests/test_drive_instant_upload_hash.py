"""tests/test_drive_instant_upload_hash.py — 秒传 hash 落库 + 命中 e2e (2026-10-10)

背景 (主指挥侦察确认的缺陷链):
- knowledge 表 storage_mode='drive' 有 336 行, 只有 3 行有 file_hash → 秒传永远 miss。
- 根因: 小文件 multipart 上传端点 POST /api/v1/drive/files/upload 的 Form 参数列表
  里**没有 file_hash**, create_file() 也没传 → 上传的 hash 从未落库。
  (分片上传路径 DriveChunkedUploadService.complete_upload 早已服务端算 SHA256 落库,
  本仓另一条独立的 drive_chunked_uploads.py 路由 — 不在此测试范围。)

本测试证明修复后:
1. upload 带 file_hash → knowledge.file_hash 落库。
2. 再用同一 file_hash 调 /files/instant-upload → instant=true (命中 dedup)。
3. upload 不带 file_hash → file_hash 为 None (向后兼容, 不炸)。

MinIO 隔离: 上传端点的 init/complete 与秒传的 copy_object 都真连 MinIO。
本测试 monkeypatch 掉这些 MinIO 触点 (只验"hash 透传 + dedup 命中"这条业务链),
不依赖真实对象存储 —— CI 无 MinIO 也能跑。
"""
from __future__ import annotations

import hashlib
import uuid

import pytest
from sqlalchemy import select

import app.models  # noqa: F401  # 触发所有 model 注册
from app.config import settings
from app.models.knowledge import Knowledge

HASH_HEX = hashlib.sha256(b"instant-upload-e2e-payload").hexdigest()


# ==========================================================================
# MinIO 触点 stub helpers
# ==========================================================================


async def _fake_init_upload(**kwargs):
    return {
        "upload_id": uuid.uuid4().hex,
        "object_name": "drive-uploads/fake/final",
    }


def _make_fake_complete_upload(size: int):
    async def _fake_complete_upload(**kwargs):
        return {"object_name": f"uploads/drive/fake/{uuid.uuid4().hex}.bin", "size": size}

    return _fake_complete_upload


async def _fake_abort_upload(**kwargs):
    return None


def _patch_upload_minio(monkeypatch, size: int):
    """替换上传端点里的 MinIO 触点 (generic_chunked_upload_service) 与 Celery .delay。"""
    from app.api.v1 import drive_files as df

    monkeypatch.setattr(df.generic_chunked_upload_service, "init_upload", _fake_init_upload)
    monkeypatch.setattr(
        df.generic_chunked_upload_service, "complete_upload", _make_fake_complete_upload(size)
    )
    monkeypatch.setattr(df.generic_chunked_upload_service, "abort_upload", _fake_abort_upload)

    # 上传末尾的 fire-and-forget Celery .delay (broker 不在测试环境): no-op
    class _NoDelay:
        def delay(self, *a, **k):
            return None

    import app.services.thumbnail_tasks as thumb
    import app.services.storage_tasks as store

    monkeypatch.setattr(thumb, "generate_thumbnail_task", _NoDelay())
    monkeypatch.setattr(store, "recalc_user_storage_task", _NoDelay())


def _patch_instant_copy(monkeypatch, size: int):
    """替换秒传 MinIO copy_object → 返回复制字节数 (不真连对象存储)。"""
    from app.services import drive_service as ds

    async def _fake_copy(src, dst):
        return size

    monkeypatch.setattr(ds.file_service, "copy_object_async", _fake_copy)


async def _cleanup_knowledge(db, ids):
    from sqlalchemy import delete as sql_delete, text

    if not ids:
        return
    try:
        await db.execute(text("SET session_replication_role = 'replica'"))
        await db.execute(sql_delete(Knowledge).where(Knowledge.id.in_(ids)))
        await db.commit()
    except Exception:
        await db.rollback()


# ==========================================================================
# 场景 1: upload 带 file_hash → 落库
# ==========================================================================


@pytest.mark.asyncio
async def test_upload_with_file_hash_persists_hash(client, db, test_member, auth_headers, monkeypatch):
    """POST /drive/files/upload 带 file_hash → knowledge.file_hash == 传入值。"""
    size = 1234
    _patch_upload_minio(monkeypatch, size)

    created_ids = []
    try:
        resp = await client.post(
            "/api/v1/drive/files/upload",
            data={
                "filename": "hash-test.txt",
                "visibility": "team",
                "storage_mode": "drive",
                "is_team_shared": "false",
                "file_hash": HASH_HEX,
            },
            files={"file": ("hash-test.txt", b"x" * size, "text/plain")},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        file_id = body["id"]
        created_ids.append(file_id)

        row = (
            await db.execute(select(Knowledge).where(Knowledge.id == file_id))
        ).scalar_one()
        assert row.file_hash == HASH_HEX, "file_hash 必须落库"
    finally:
        await _cleanup_knowledge(db, created_ids)


# ==========================================================================
# 场景 2: 上传后同 hash 秒传命中
# ==========================================================================


@pytest.mark.asyncio
async def test_instant_upload_hits_after_upload_with_hash(
    client, db, test_member, auth_headers, monkeypatch
):
    """upload 落 hash → instant-upload 同 hash → instant=true + dedup 命中。"""
    size = 2048
    _patch_upload_minio(monkeypatch, size)
    _patch_instant_copy(monkeypatch, size)

    created_ids = []
    try:
        up = await client.post(
            "/api/v1/drive/files/upload",
            data={
                "filename": "dedup-src.bin",
                "visibility": "team",
                "storage_mode": "drive",
                "is_team_shared": "false",
                "file_hash": HASH_HEX,
            },
            files={"file": ("dedup-src.bin", b"y" * size, "application/octet-stream")},
            headers=auth_headers,
        )
        assert up.status_code == 201, up.text
        created_ids.append(up.json()["id"])

        inst = await client.post(
            "/api/v1/drive/files/instant-upload",
            json={
                "file_hash": HASH_HEX,
                "file_name": "dedup-src.bin",
                "file_size": size,
                "visibility": "team",
                "is_team_shared": True,
            },
            headers=auth_headers,
        )
        assert inst.status_code == 200, inst.text
        payload = inst.json()
        assert payload["instant"] is True, f"应命中秒传, 实际: {payload}"
        assert payload["file_id"] is not None
        created_ids.append(payload["file_id"])
    finally:
        await _cleanup_knowledge(db, created_ids)


# ==========================================================================
# 场景 3: 不带 file_hash → 向后兼容 (file_hash 为 None, 不炸)
# ==========================================================================


@pytest.mark.asyncio
async def test_upload_without_file_hash_still_works(
    client, db, test_member, auth_headers, monkeypatch
):
    """旧调用方不传 file_hash → 上传照常成功, knowledge.file_hash 为 None。"""
    size = 999
    _patch_upload_minio(monkeypatch, size)

    created_ids = []
    try:
        resp = await client.post(
            "/api/v1/drive/files/upload",
            data={
                "filename": "no-hash.txt",
                "visibility": "team",
                "storage_mode": "drive",
                "is_team_shared": "false",
            },
            files={"file": ("no-hash.txt", b"z" * size, "text/plain")},
            headers=auth_headers,
        )
        assert resp.status_code == 201, resp.text
        file_id = resp.json()["id"]
        created_ids.append(file_id)

        row = (
            await db.execute(select(Knowledge).where(Knowledge.id == file_id))
        ).scalar_one()
        assert row.file_hash is None
    finally:
        await _cleanup_knowledge(db, created_ids)

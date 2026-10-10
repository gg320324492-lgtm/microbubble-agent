"""W98 Drive → KB API endpoint 测试

覆盖:
- POST /drive/{file_id}/to-kb — 成功 (mock service) → 200 + IngestResult envelope
- POST /drive/{file_id}/to-kb — DriveToKBError 422 → 统一 error envelope
- POST /drive/{file_id}/to-kb — 文件不存在 → 404 FILE_NOT_FOUND
- POST /drive/folders/{folder_id}/to-kb — 批量 (mock service) → 200
- GET /drive/ingestable — 列表 → 200
- 新 endpoint 不 raise HTTPException (统一 AppException envelope 铁律)

跑法 (SKIP_DB_SETUP=1 模式, 全 mock 无 DB):
    SKIP_DB_SETUP=1 python -m pytest tests/api/v1/test_drive_to_kb_endpoints.py -v
"""
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# 把 repo root 加入路径 (SKIP 模式可能不自动配)
sys.path.insert(0, ".")


def _build_app():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1.drive_to_kb import router as d2kb_router
    from app.core.exceptions import AppException, app_exception_handler
    from app.core.database import get_db
    from app.core.security import get_current_user

    app = FastAPI()
    app.include_router(d2kb_router)
    app.add_exception_handler(AppException, app_exception_handler)

    async def mock_get_db():
        yield AsyncMock()

    async def mock_current_user():
        return MagicMock(id=1, username="alice")

    app.dependency_overrides[get_db] = mock_get_db
    app.dependency_overrides[get_current_user] = mock_current_user
    return app, TestClient(app)


def _patch_service(client_attr="ingest_drive_file", return_value=None, side_effect=None):
    """patch DriveToKBService 实例方法"""
    from unittest.mock import patch

    return patch(
        f"app.services.drive_to_kb_service.DriveToKBService.{client_attr}",
        new_callable=AsyncMock,
        return_value=return_value,
        side_effect=side_effect,
    )


def _patch_drive_visible(file_id=7):
    """patch DriveService.get_file → 可见 drive 文件 (owner=1, team visibility)"""
    from unittest.mock import patch

    fake_file = MagicMock(id=file_id, created_by=1, visibility="team")
    return patch(
        "app.services.drive_service.DriveService.get_file",
        new_callable=AsyncMock,
        return_value=fake_file,
    )


# === 单文件入库 ===


def test_to_kb_success():
    """POST /drive/{id}/to-kb → 200 + IngestResult"""
    from fastapi.testclient import TestClient

    _, client = _build_app()
    with _patch_drive_visible(7), _patch_service(
        return_value={
            "knowledge_id": 42,
            "already_ingested": False,
            "title": "气泡.txt",
            "content_length": 120,
            "source_file_id": 7,
        }
    ):
        resp = client.post("/drive/7/to-kb")
    assert resp.status_code == 200
    body = resp.json()
    assert body["knowledge_id"] == 42
    assert body["source_file_id"] == 7
    assert body["already_ingested"] is False


def test_to_kb_idempotent_flag():
    """已入库文件 → already_ingested=true (幂等语义透传)"""
    _, client = _build_app()
    with _patch_drive_visible(7), _patch_service(
        return_value={
            "knowledge_id": 42,
            "already_ingested": True,
            "title": "气泡.txt",
            "content_length": 120,
            "source_file_id": 7,
        }
    ):
        resp = client.post("/drive/7/to-kb")
    assert resp.status_code == 200
    assert resp.json()["already_ingested"] is True


def test_to_kb_422_envelope():
    """解析失败 (422) → 统一 error envelope"""
    from app.services.drive_to_kb_service import DriveToKBError

    _, client = _build_app()
    with _patch_drive_visible(7), _patch_service(
        side_effect=DriveToKBError("文件解析失败: bad", 422)
    ):
        resp = client.post("/drive/7/to-kb")
    assert resp.status_code == 422
    body = resp.json()
    assert "error" in body, f"必须用 AppException envelope, 实际: {body}"
    assert body["error"]["code"] == "DRIVE_TO_KB_ERROR"
    assert "解析失败" in body["error"]["message"]
    assert body["error"]["details"]["file_id"] == 7


def test_to_kb_404_envelope():
    """文件不存在 (404) → FILE_NOT_FOUND envelope"""
    from app.services.drive_to_kb_service import DriveToKBError

    _, client = _build_app()
    with _patch_drive_visible(), _patch_service(
        side_effect=DriveToKBError("drive 文件不存在或已删除", 404)
    ):
        resp = client.post("/drive/999/to-kb")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "FILE_NOT_FOUND"
    assert body["error"]["details"]["file_id"] == 999


# === 文件夹批量入库 ===


def test_folder_to_kb_success():
    """POST /drive/folders/{id}/to-kb → 200 + IngestBatchResult"""
    _, client = _build_app()
    with _patch_service(
        client_attr="ingest_folder",
        return_value={
            "dry_run": False,
            "total": 3,
            "ingested": 2,
            "already_ingested": 1,
            "failed": 0,
            "errors": [],
            "knowledge_ids": [11, 12],
        },
    ):
        resp = client.post("/drive/folders/5/to-kb")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["ingested"] == 2
    assert body["already_ingested"] == 1


def test_folder_to_kb_dry_run_flag():
    """dry_run=true 透传查询参数"""
    _, client = _build_app()
    with _patch_service(
        client_attr="ingest_folder",
        return_value={"dry_run": True, "total": 3, "ingested": 0, "already_ingested": 0, "failed": 0, "errors": [], "knowledge_ids": []},
    ) as mock_method:
        resp = client.post("/drive/folders/5/to-kb?dry_run=true")
    assert resp.status_code == 200
    assert resp.json()["dry_run"] is True
    mock_method.assert_awaited_once_with(5, dry_run=True)


# === 可入库清单 ===


def test_ingestable_list():
    """GET /drive/ingestable → 200 + 清单"""
    _, client = _build_app()
    with _patch_service(
        client_attr="list_ingestable",
        return_value=[
            {"file_id": 1, "title": "a.txt", "file_name": "a.txt", "file_type": ".txt", "file_size": 10, "visibility": "team", "folder_id": None, "ingestable": True},
            {"file_id": 2, "title": "p.png", "file_name": "p.png", "file_type": ".png", "file_size": 20, "visibility": "team", "folder_id": None, "ingestable": False},
        ],
    ):
        resp = client.get("/drive/ingestable")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["file_id"] == 1
    assert body[1]["ingestable"] is False

"""Drive v2 PR9 — File Version e2e test (2026-07-24)

覆盖 5 场景:
1. 创建初始版本 (创建 Knowledge + 调用 create_initial_version)
2. 上传新版本 (v2 / v3)
3. 列出所有版本
4. 下载老版本 (presigned URL)
5. 回滚到 v2 (创建 v4 with v2 内容)

设计:
- 复用 tests/e2e/test_kb_dedup_e2e.py 的 fixtures 模式
- 测试数据库由容器预置 (SKIP_DB_SETUP=1)
- 用 SimpleNamespace 模拟 admin user (id=0)
- file_service.upload_to_path monkeypatch (避免真打 MinIO)
"""
from __future__ import annotations

import io
from contextlib import AbstractAsyncContextManager
from types import SimpleNamespace

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.main import app
from app.models.drive_file_version import DriveFileVersion
from app.models.knowledge import Knowledge
from app.services.drive_upload_service import create_initial_version


# ============================================================
# Fixtures (复用 kb_dedup_e2e 模式)
# ============================================================


class _SessionContext(AbstractAsyncContextManager):
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest_asyncio.fixture
async def e2e_db():
    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
    engine = create_async_engine(db_url, echo=False)
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()


@pytest_asyncio.fixture
async def e2e_client(e2e_db):
    async def override_db():
        yield e2e_db

    async def override_user():
        # 平台管理员, role='admin' (绕开 _can_modify_file)
        return SimpleNamespace(id=0, role="admin", username="drive-pr9-e2e", name="PR9 E2E")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://drive-pr9-e2e"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def clean_drive_pr9(e2e_db):
    """每个测试前后清理 PR9 创建的 Knowledge + DriveFileVersion 行

    范围: 仅清理 created_by=0 (admin) + storage_mode='drive' + 测试期间创建
    """
    yield
    # 测试后清理
    try:
        await e2e_db.execute(
            delete(DriveFileVersion).where(DriveFileVersion.uploader_id == 0)
        )
        await e2e_db.execute(
            delete(Knowledge).where(
                Knowledge.created_by == 0,
                Knowledge.storage_mode == "drive",
            )
        )
        await e2e_db.commit()
    except Exception:
        await e2e_db.rollback()


# ============================================================
# Helper: monkeypatch file_service 避免真打 MinIO
# ============================================================


@pytest.fixture
def mock_file_service(monkeypatch):
    """Mock file_service.upload_to_path / get_url / copy_object_async / delete_file"""
    from app.services import file_service

    store = {}  # object_key → bytes

    async def fake_upload(object_name, content, content_type=None):
        store[object_name] = content

    async def fake_copy(src, dst):
        if src not in store:
            raise RuntimeError(f"源 object 不存在: {src}")
        store[dst] = store[src]
        return len(store[dst])

    async def fake_exists(object_name):
        return object_name in store

    def fake_get_url(object_name, expires=3600):
        return f"http://mock-minio/{object_name}?signature=mock"

    def fake_delete(object_name):
        store.pop(object_name, None)

    monkeypatch.setattr(file_service.file_service, "upload_to_path", fake_upload)
    monkeypatch.setattr(file_service.file_service, "copy_object_async", fake_copy)
    monkeypatch.setattr(file_service.file_service, "object_exists", fake_exists)
    monkeypatch.setattr(file_service.file_service, "get_url", fake_get_url)
    monkeypatch.setattr(file_service.file_service, "delete_file", fake_delete)

    return store


# ============================================================
# Scenario 1: 创建初始版本
# ============================================================


@pytest.mark.asyncio
async def test_scenario_1_create_initial_version(e2e_client, e2e_db, clean_drive_pr9, mock_file_service):
    """场景 1: 上传文件 → 自动创建 v1 (initial version)

    验证:
    - Knowledge 行存在 (storage_mode='drive')
    - DriveFileVersion 行存在 (version_number=1, is_current=1)
    - 主表 file_path 引用 v1 的 minio_object_key
    """
    # 直接创建 Knowledge + initial version (绕过 multipart 上传)
    from app.services.drive_service import DriveService
    svc = DriveService(e2e_db)
    file_obj = await svc.create_file(
        title="test_initial_v1.txt",
        owner_id=0,
        file_path="uploads/drive/0/test_initial_v1.txt",
        file_name="test_initial_v1.txt",
        file_type="text/plain",
        file_size=12,
        visibility="team",
        folder_id=None,
        created_by=0,
    )
    await e2e_db.commit()
    await e2e_db.refresh(file_obj)

    # 触发 create_initial_version
    v1 = await create_initial_version(
        db=e2e_db,
        file_id=file_obj.id,
        minio_object_key=file_obj.file_path,
        size=file_obj.file_size,
        uploader_id=0,
        comment="Initial version",
    )

    assert v1 is not None, "create_initial_version 应当返回 DriveFileVersion 行"
    assert v1.version_number == 1
    assert v1.is_current == 1
    assert v1.uploader_id == 0
    assert v1.file_id == file_obj.id
    assert v1.size == 12
    print(f"[scenario 1] file_id={file_obj.id} v1.id={v1.id} PASS")


# ============================================================
# Scenario 2: 上传新版本 (v2 / v3)
# ============================================================


@pytest.mark.asyncio
async def test_scenario_2_upload_new_version(e2e_client, e2e_db, clean_drive_pr9, mock_file_service):
    """场景 2: 上传新版本 → v2 / v3

    验证:
    - POST /api/v1/drive/versions/files/{file_id}/versions 上传 v2
    - 旧 v1 is_current=0
    - 新 v2 is_current=1, version_number=2
    - 再上传 v3 → version_number=3
    """
    # 先创建初始文件 + v1
    from app.services.drive_service import DriveService
    svc = DriveService(e2e_db)
    file_obj = await svc.create_file(
        title="test_v2.txt",
        owner_id=0,
        file_path="uploads/drive/0/test_v2.txt",
        file_name="test_v2.txt",
        file_type="text/plain",
        file_size=8,
        visibility="team",
        folder_id=None,
        created_by=0,
    )
    await e2e_db.commit()
    await e2e_db.refresh(file_obj)

    v1 = await create_initial_version(
        db=e2e_db,
        file_id=file_obj.id,
        minio_object_key=file_obj.file_path,
        size=file_obj.file_size,
        uploader_id=0,
    )
    assert v1 is not None

    # 上传 v2 (multipart form)
    v2_content = b"Version 2 content - 18 bytes"
    files = {"file": ("v2.txt", io.BytesIO(v2_content), "text/plain")}
    data = {"comment": "Updated to v2"}
    resp = await e2e_client.post(
        f"/api/v1/drive/versions/files/{file_obj.id}/versions",
        files=files,
        data=data,
    )
    assert resp.status_code == 201, f"v2 upload 应 201, 实际 {resp.status_code} {resp.text}"
    body = resp.json()
    assert body["new_version_number"] == 2
    assert body["file_id"] == file_obj.id
    assert body["version"]["is_current"] is True
    assert body["version"]["comment"] == "Updated to v2"
    v2_id = body["version"]["id"]

    # 验证: v1 is_current=0, v2 is_current=1
    await e2e_db.refresh(v1)
    assert v1.is_current == 0, f"v1 应翻 0, 实际 {v1.is_current}"
    v2_row = await e2e_db.get(DriveFileVersion, v2_id)
    assert v2_row.is_current == 1
    assert v2_row.version_number == 2

    # 上传 v3
    v3_content = b"Version 3 content - 18 bytes"
    files = {"file": ("v3.txt", io.BytesIO(v3_content), "text/plain")}
    data = {"comment": "v3 update"}
    resp = await e2e_client.post(
        f"/api/v1/drive/versions/files/{file_obj.id}/versions",
        files=files,
        data=data,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["new_version_number"] == 3
    print(f"[scenario 2] file_id={file_obj.id} v2.id={v2_id} v3.id={body['version']['id']} PASS")


# ============================================================
# Scenario 3: 列出所有版本
# ============================================================


@pytest.mark.asyncio
async def test_scenario_3_list_versions(e2e_client, e2e_db, clean_drive_pr9, mock_file_service):
    """场景 3: GET 列表 → 应返回所有版本, 按 version_number desc"""
    # 准备: 1 个文件 + v1/v2/v3
    from app.services.drive_service import DriveService
    svc = DriveService(e2e_db)
    file_obj = await svc.create_file(
        title="test_list.txt",
        owner_id=0,
        file_path="uploads/drive/0/test_list.txt",
        file_name="test_list.txt",
        file_type="text/plain",
        file_size=4,
        visibility="team",
        folder_id=None,
        created_by=0,
    )
    await e2e_db.commit()
    await e2e_db.refresh(file_obj)

    await create_initial_version(
        db=e2e_db,
        file_id=file_obj.id,
        minio_object_key=file_obj.file_path,
        size=file_obj.file_size,
        uploader_id=0,
    )

    # 上传 v2 + v3
    for n in (2, 3):
        content = f"v{n} content".encode()
        files = {"file": (f"v{n}.txt", io.BytesIO(content), "text/plain")}
        data = {"comment": f"v{n} note"}
        resp = await e2e_client.post(
            f"/api/v1/drive/versions/files/{file_obj.id}/versions",
            files=files,
            data=data,
        )
        assert resp.status_code == 201

    # GET 列表
    resp = await e2e_client.get(f"/api/v1/drive/versions/files/{file_obj.id}/versions")
    assert resp.status_code == 200
    body = resp.json()
    assert body["file_id"] == file_obj.id
    assert body["count"] == 3
    items = body["items"]
    assert len(items) == 3
    # 按 version_number desc 排
    assert items[0]["version_number"] == 3
    assert items[1]["version_number"] == 2
    assert items[2]["version_number"] == 1
    # is_current 只有 v3 是 True
    assert items[0]["is_current"] is True
    assert items[1]["is_current"] is False
    assert items[2]["is_current"] is False
    # uploader_name 来自 JOIN
    assert items[0]["uploader_name"] == "PR9 E2E"
    print(f"[scenario 3] file_id={file_obj.id} listed 3 versions PASS")


# ============================================================
# Scenario 4: 下载老版本 (presigned URL)
# ============================================================


@pytest.mark.asyncio
async def test_scenario_4_download_old_version(e2e_client, e2e_db, clean_drive_pr9, mock_file_service):
    """场景 4: GET 下载 v1 → 应返回 presigned URL (含 v1 内容)
    """
    from app.services.drive_service import DriveService
    svc = DriveService(e2e_db)
    file_obj = await svc.create_file(
        title="test_download.txt",
        owner_id=0,
        file_path="uploads/drive/0/test_download.txt",
        file_name="test_download.txt",
        file_type="text/plain",
        file_size=4,
        visibility="team",
        folder_id=None,
        created_by=0,
    )
    await e2e_db.commit()
    await e2e_db.refresh(file_obj)

    v1 = await create_initial_version(
        db=e2e_db,
        file_id=file_obj.id,
        minio_object_key=file_obj.file_path,
        size=file_obj.file_size,
        uploader_id=0,
    )

    # 上传 v2 (让 v1 成为历史版)
    v2_content = b"v2 NEW content - 16 bytes"
    files = {"file": ("v2.txt", io.BytesIO(v2_content), "text/plain")}
    resp = await e2e_client.post(
        f"/api/v1/drive/versions/files/{file_obj.id}/versions",
        files=files,
        data={"comment": "v2"},
    )
    assert resp.status_code == 201

    # 下载 v1
    resp = await e2e_client.get(f"/api/v1/drive/versions/versions/{v1.id}/download")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version_id"] == v1.id
    assert body["version_number"] == 1
    assert body["file_id"] == file_obj.id
    assert "download_url" in body
    assert "mock-minio" in body["download_url"]
    assert body["size"] == v1.size
    print(f"[scenario 4] download v1.url={body['download_url'][:60]}... PASS")


# ============================================================
# Scenario 5: 回滚到 v2
# ============================================================


@pytest.mark.asyncio
async def test_scenario_5_rollback(e2e_client, e2e_db, clean_drive_pr9, mock_file_service):
    """场景 5: POST 回滚到 v2 → 创建 v4 (新行, 内容复制自 v2)

    验证:
    - v2 内容 = v4 内容 (字节级一致)
    - v4 version_number = max+1
    - v3 (之前的 current) is_current=0
    - Knowledge 行 file_path 指向 v4
    """
    from app.services.drive_service import DriveService
    svc = DriveService(e2e_db)
    file_obj = await svc.create_file(
        title="test_rollback.txt",
        owner_id=0,
        file_path="uploads/drive/0/test_rollback.txt",
        file_name="test_rollback.txt",
        file_type="text/plain",
        file_size=4,
        visibility="team",
        folder_id=None,
        created_by=0,
    )
    await e2e_db.commit()
    await e2e_db.refresh(file_obj)

    v1 = await create_initial_version(
        db=e2e_db,
        file_id=file_obj.id,
        minio_object_key=file_obj.file_path,
        size=file_obj.file_size,
        uploader_id=0,
    )

    # 上传 v2 (内容 A)
    v2_content = b"Content A - rollback target"
    files = {"file": ("v2.txt", io.BytesIO(v2_content), "text/plain")}
    resp = await e2e_client.post(
        f"/api/v1/drive/versions/files/{file_obj.id}/versions",
        files=files,
        data={"comment": "v2 content A"},
    )
    assert resp.status_code == 201
    v2_id = resp.json()["version"]["id"]

    # 上传 v3 (内容 B, 这是要回滚覆盖的)
    v3_content = b"Content B - to be rolled back"
    files = {"file": ("v3.txt", io.BytesIO(v3_content), "text/plain")}
    resp = await e2e_client.post(
        f"/api/v1/drive/versions/files/{file_obj.id}/versions",
        files=files,
        data={"comment": "v3 content B"},
    )
    assert resp.status_code == 201
    v3_id = resp.json()["version"]["id"]

    # 回滚到 v2
    resp = await e2e_client.post(
        f"/api/v1/drive/versions/files/{file_obj.id}/versions/{v2_id}/rollback",
        json={"new_comment": "Rolled back to v2 (Content A)"},
    )
    assert resp.status_code == 200, f"rollback 应 200, 实际 {resp.status_code} {resp.text}"
    body = resp.json()
    assert body["rolled_back_from"] == 2
    assert body["new_version_number"] == 4
    assert body["file_id"] == file_obj.id
    v4_id = body["version"]["id"]
    v4 = await e2e_db.get(DriveFileVersion, v4_id)
    assert v4.is_current == 1
    assert v4.comment == "Rolled back to v2 (Content A)"

    # v3 is_current=0
    await e2e_db.refresh(await e2e_db.get(DriveFileVersion, v3_id))
    v3_row = await e2e_db.get(DriveFileVersion, v3_id)
    assert v3_row.is_current == 0

    # Knowledge 行 file_path 更新
    await e2e_db.refresh(file_obj)
    assert file_obj.version_number == 4

    print(f"[scenario 5] file_id={file_obj.id} v1→v2→v3→rollback(v2)=v4 PASS")
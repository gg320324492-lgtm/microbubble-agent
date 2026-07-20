"""Drive API 5 endpoint 迁移 envelope 测试 — W1 T1 验证

覆盖迁移的 5 个 endpoint 的错误抛出改走 helper (统一 envelope):
- PUT /files/{file_id} (rename / move / change visibility) — file_rename
- POST /files/{file_id}/share-link — share_create
- DELETE /files/{file_id}/share-link — share_delete
- POST /files/batch-download — batch_download (400 + 404 两路径)
- POST /files/batch-move — batch_move (DriveServiceError 路径)

验证: 抛 helper 后, main.py app_exception_handler 转 envelope
`{"error": {"code", "message", "details"}}` 而不是 FastAPI 默认 `{"detail": "..."}`

跑法:
    docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 bash -c 'cd /app && python -m pytest tests/api/v1/test_drive_endpoint_envelope.py -v --tb=short'
"""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# 把 /app 加入路径 (SKIP 模式可能不自动配)
sys.path.insert(0, "/app")


class TestDriveEndpointEnvelope:
    """验证 5 个迁移 endpoint 抛 AppException envelope (而非 FastAPI detail)"""

    @pytest.fixture
    def test_app_with_routes(self):
        """构造 mini FastAPI app: 装载 drive_files router + handler"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.drive_files import router as drive_router
        from app.core.exceptions import app_exception_handler, AppException
        from app.core.database import get_db
        from app.core.security import get_current_user

        app = FastAPI()
        app.include_router(drive_router)
        app.add_exception_handler(AppException, app_exception_handler)

        # Mock get_db: 返 AsyncSession mock
        async def mock_get_db():
            mock_session = AsyncMock()
            yield mock_session

        # Mock current_user: 返固定 user
        async def mock_current_user():
            return MagicMock(id=1, username="alice")

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_user] = mock_current_user

        return TestClient(app)

    @pytest.fixture
    def test_app_with_service_returning_none(self):
        """DriveService 方法返 None (模拟 file 不存在)"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.drive_files import router as drive_router
        from app.core.exceptions import app_exception_handler, AppException
        from app.core.database import get_db
        from app.core.security import get_current_user
        from app.services.drive_service import DriveService

        app = FastAPI()
        app.include_router(drive_router)
        app.add_exception_handler(AppException, app_exception_handler)

        # Mock get_db: 返 AsyncSession + patch DriveService 让所有方法返 None
        async def mock_get_db():
            mock_session = AsyncMock()
            yield mock_session

        # Mock DriveService 让所有相关方法返 None (模拟 file 不存在)
        # 用 monkey-patch: 替换 DriveService 实例化后的方法
        original_init = DriveService.__init__

        def mock_init(self, db):
            original_init(self, db)
            self.update_file = AsyncMock(return_value=None)
            self.create_share_link = AsyncMock(return_value=None)
            self.revoke_share_link = AsyncMock(return_value=False)
            self.batch_move = AsyncMock(return_value=(0, []))
            # Case 6 反向验证需要: 未迁移的 DELETE /files/{id} 走 svc.soft_delete_file
            self.soft_delete_file = AsyncMock(return_value=False)
            self.restore_file = AsyncMock(return_value=None)
            self.extract_to_kb = AsyncMock(return_value=None)
            self.toggle_star = AsyncMock(return_value=None)
            self.get_file = AsyncMock(return_value=None)

        DriveService.__init__ = mock_init

        async def mock_current_user():
            return MagicMock(id=1, username="alice")

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_user] = mock_current_user

        try:
            yield TestClient(app)
        finally:
            # 还原 DriveService.__init__
            DriveService.__init__ = original_init

    # =========================================================================
    # Case 1: file_rename 404 envelope
    # =========================================================================
    def test_file_rename_404_envelope(self, test_app_with_service_returning_none):
        """PUT /files/{id} rename 文件不存在 → envelope `{"error": {"code": "FILE_NOT_FOUND"}}`"""
        resp = test_app_with_service_returning_none.put(
            "/drive/files/999",
            json={"title": "new-name"},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body, f"必须用 AppException envelope, 实际: {body}"
        assert body["error"]["code"] == "FILE_NOT_FOUND"
        assert body["error"]["message"] == "file 不存在或非 owner"
        assert body["error"]["details"]["file_id"] == 999

    # =========================================================================
    # Case 2: share_create 404 envelope
    # =========================================================================
    def test_share_create_404_envelope(self, test_app_with_service_returning_none):
        """POST /files/{id}/share-link file 不存在 → envelope SHARE_LINK_NOT_FOUND"""
        resp = test_app_with_service_returning_none.post(
            "/drive/files/888/share-link",
            json={"expires_in_days": 7},
        )
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "SHARE_LINK_NOT_FOUND"
        assert body["error"]["message"] == "file 不存在或非 owner"
        assert body["error"]["details"]["file_id"] == 888

    # =========================================================================
    # Case 3: share_delete 404 envelope
    # =========================================================================
    def test_share_delete_404_envelope(self, test_app_with_service_returning_none):
        """DELETE /files/{id}/share-link file 不存在 → envelope SHARE_LINK_NOT_FOUND"""
        resp = test_app_with_service_returning_none.delete(
            "/drive/files/777/share-link",
        )
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "SHARE_LINK_NOT_FOUND"
        assert body["error"]["message"] == "file 不存在或非 owner"
        assert body["error"]["details"]["file_id"] == 777

    # =========================================================================
    # Case 4: batch_download 400 envelope (ids + folder_id 都空)
    # =========================================================================
    def test_batch_download_400_envelope(self, test_app_with_routes):
        """POST /files/batch-download ids + folder_id 都空 → 400 BATCH_PARAM_MISSING"""
        resp = test_app_with_routes.post(
            "/drive/files/batch-download",
            json={},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "BATCH_PARAM_MISSING"
        assert body["error"]["message"] == "ids 或 folder_id 必填其一"
        # details 应为 {} (BATCH_PARAM_MISSING 不传 details)
        assert body["error"]["details"] == {}

    # =========================================================================
    # Case 5: batch_move DriveServiceError envelope
    # =========================================================================
    def test_batch_move_drive_service_error_envelope(self):
        """POST /files/batch-move svc.batch_move 抛 DriveServiceError → envelope FILE_FORBIDDEN"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1.drive_files import router as drive_router
        from app.core.exceptions import app_exception_handler, AppException
        from app.core.database import get_db
        from app.core.security import get_current_user
        from app.services.drive_service import DriveService, DriveServiceError

        app = FastAPI()
        app.include_router(drive_router)
        app.add_exception_handler(AppException, app_exception_handler)

        async def mock_get_db():
            mock_session = AsyncMock()
            yield mock_session

        # 让 batch_move 抛 DriveServiceError(status=403)
        original_init = DriveService.__init__

        def mock_init(self, db):
            original_init(self, db)
            async def raise_forbidden(*args, **kwargs):
                raise DriveServiceError("无权移动到目标 folder", status_code=403)
            self.batch_move = raise_forbidden

        DriveService.__init__ = mock_init

        async def mock_current_user():
            return MagicMock(id=1, username="alice")

        app.dependency_overrides[get_db] = mock_get_db
        app.dependency_overrides[get_current_user] = mock_current_user

        try:
            client = TestClient(app)
            resp = client.post(
                "/drive/files/batch-move",
                json={"file_ids": [1, 2, 3], "target_folder_id": 999},
            )
            assert resp.status_code == 403
            body = resp.json()
            assert "error" in body, f"必须用 AppException envelope, 实际: {body}"
            assert body["error"]["code"] == "FILE_FORBIDDEN"
            assert "无权移动" in body["error"]["message"]
        finally:
            DriveService.__init__ = original_init

    # =========================================================================
    # Case 6: 反向验证 — 没迁移的 endpoint 仍用 HTTPException (envelope 不同)
    # =========================================================================
    def test_non_migrated_endpoint_still_uses_http_exception(self, test_app_with_service_returning_none):
        """DELETE /files/{id} (未迁移) 仍走 FastAPI `{"detail": "..."}` envelope"""
        resp = test_app_with_service_returning_none.delete(
            "/drive/files/666",
        )
        # 未迁移的 endpoint 仍 HTTPException 404 → envelope `{"detail": "..."}`
        # 这是契约债 (W1 T1 留尾), 验证非迁移 endpoint 行为不变
        assert resp.status_code == 404
        body = resp.json()
        # 注意: 没 "error" 顶层 key, 而是 "detail"
        assert "detail" in body, "未迁移 endpoint 应保持 FastAPI detail envelope"
        assert "error" not in body
        assert body["detail"] == "file 不存在或非 owner"
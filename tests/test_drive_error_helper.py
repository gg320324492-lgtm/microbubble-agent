"""app/api/v1/_drive_error_helper.py 单元测试

覆盖 helper:
- raise_app_error 抛出 AppException (code/message/status_code/details 4 字段全对)
- helper 抛出后, main.py app_exception_handler 会转 envelope `{"error": {"code", "message", "details"}}`
- 错误码常量字符串正确
- 详细测试 envelope 在 FastAPI testclient 下实际输出
"""
import pytest


class TestRaiseAppError:
    """raise_app_error helper 直接抛 AppException 子类"""

    def test_raises_app_exception_with_correct_fields(self):
        from app.api.v1._drive_error_helper import raise_app_error
        from app.core.exceptions import AppException

        with pytest.raises(AppException) as exc_info:
            raise_app_error(404, "FILE_NOT_FOUND", "文件 5 不存在", file_id=5)

        exc = exc_info.value
        assert exc.status_code == 404
        assert exc.code == "FILE_NOT_FOUND"
        assert exc.message == "文件 5 不存在"
        assert exc.details == {"file_id": 5}

    def test_default_details_empty_dict(self):
        from app.api.v1._drive_error_helper import raise_app_error
        from app.core.exceptions import AppException

        with pytest.raises(AppException) as exc_info:
            raise_app_error(403, "FILE_FORBIDDEN", "无权操作")

        assert exc_info.value.details == {}

    def test_passes_through_details_kwargs(self):
        from app.api.v1._drive_error_helper import raise_app_error
        from app.core.exceptions import AppException

        with pytest.raises(AppException) as exc_info:
            raise_app_error(
                409, "FILE_CONFLICT", "filename 冲突",
                filename="x.pdf", owner_id=42,
            )

        assert exc_info.value.details == {"filename": "x.pdf", "owner_id": 42}


class TestErrorCodeConstants:
    """错误码常量字符串值"""

    def test_resource_not_found_codes(self):
        from app.api.v1._drive_error_helper import (
            ERR_FILE_NOT_FOUND, ERR_FOLDER_NOT_FOUND, ERR_SESSION_NOT_FOUND,
        )
        assert ERR_FILE_NOT_FOUND == "FILE_NOT_FOUND"
        assert ERR_FOLDER_NOT_FOUND == "FOLDER_NOT_FOUND"
        assert ERR_SESSION_NOT_FOUND == "SESSION_NOT_FOUND"

    def test_forbidden_codes(self):
        from app.api.v1._drive_error_helper import (
            ERR_FILE_FORBIDDEN, ERR_FOLDER_FORBIDDEN,
        )
        assert ERR_FILE_FORBIDDEN == "FILE_FORBIDDEN"
        assert ERR_FOLDER_FORBIDDEN == "FOLDER_FORBIDDEN"

    def test_validation_codes(self):
        from app.api.v1._drive_error_helper import (
            ERR_INVALID_VISIBILITY, ERR_INVALID_FILE_SIZE, ERR_FILE_EMPTY,
            ERR_BATCH_PARAM_MISSING,
        )
        assert ERR_INVALID_VISIBILITY == "INVALID_VISIBILITY"
        assert ERR_INVALID_FILE_SIZE == "INVALID_FILE_SIZE"
        assert ERR_FILE_EMPTY == "FILE_EMPTY"
        assert ERR_BATCH_PARAM_MISSING == "BATCH_PARAM_MISSING"

    def test_share_link_codes(self):
        from app.api.v1._drive_error_helper import (
            ERR_SHARE_LINK_NOT_FOUND, ERR_SHARE_LINK_EXPIRED, ERR_SHARE_LINK_PASSWORD,
        )
        assert ERR_SHARE_LINK_NOT_FOUND == "SHARE_LINK_NOT_FOUND"
        assert ERR_SHARE_LINK_EXPIRED == "SHARE_LINK_EXPIRED"
        assert ERR_SHARE_LINK_PASSWORD == "SHARE_LINK_PASSWORD_INVALID"


class TestHelperIntegration:
    """helper 与 main.py app_exception_handler 集成 (FastAPI testclient)

    验证抛 helper 后, 全局 handler 转 envelope `{"error": {"code", "message", "details"}}`
    """

    @pytest.fixture
    def test_app(self):
        """构造 mini FastAPI app 装载 raise_app_error + handler"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1._drive_error_helper import raise_app_error
        from app.core.exceptions import app_exception_handler, AppException

        app = FastAPI()
        app.add_exception_handler(AppException, app_exception_handler)

        @app.get("/trigger-404")
        async def trigger_404():
            raise_app_error(404, "FILE_NOT_FOUND", "文件 99 不存在", file_id=99)

        @app.get("/trigger-403-no-details")
        async def trigger_403_no_details():
            raise_app_error(403, "FILE_FORBIDDEN", "无权操作")

        return TestClient(app)

    def test_envelope_format_404(self, test_app):
        """404 envelope `{"error": {"code", "message", "details"}}`"""
        resp = test_app.get("/trigger-404")
        assert resp.status_code == 404
        body = resp.json()
        assert "error" in body
        assert body["error"]["code"] == "FILE_NOT_FOUND"
        assert body["error"]["message"] == "文件 99 不存在"
        assert body["error"]["details"] == {"file_id": 99}

    def test_envelope_format_403_empty_details(self, test_app):
        """403 envelope, details 为空 dict (不是 null)"""
        resp = test_app.get("/trigger-403-no-details")
        assert resp.status_code == 403
        body = resp.json()
        assert body["error"]["code"] == "FILE_FORBIDDEN"
        assert body["error"]["message"] == "无权操作"
        assert body["error"]["details"] == {}  # 不是 None!


class TestContractVsHTTPException:
    """对比 helper (AppException) vs HTTPException envelope 差异

    这是审计的核心目的: 验证为什么不能用 HTTPException (envelope 不一致)
    """

    def test_app_exception_envelope_has_error_key(self):
        """AppException envelope 有 `error` 顶层 key"""
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.api.v1._drive_error_helper import raise_app_error
        from app.core.exceptions import app_exception_handler, AppException

        app = FastAPI()
        app.add_exception_handler(AppException, app_exception_handler)

        @app.get("/test")
        async def test():
            raise_app_error(404, "FILE_NOT_FOUND", "msg")

        resp = TestClient(app).get("/test")
        body = resp.json()
        assert "error" in body
        assert "detail" not in body  # 没有 FastAPI 默认 detail 字段

    def test_http_exception_envelope_has_detail_key(self):
        """HTTPException envelope 用 `detail` 顶层 key (FastAPI 默认)"""
        from fastapi import FastAPI, HTTPException
        from fastapi.testclient import TestClient

        app = FastAPI()

        @app.get("/test")
        async def test():
            raise HTTPException(status_code=404, detail="msg")

        resp = TestClient(app).get("/test")
        body = resp.json()
        assert "detail" in body
        assert "error" not in body  # 没有统一 envelope
        assert body["detail"] == "msg"

    def test_dual_envelope_pain(self):
        """前端必须双 fallback 的契约债证明"""
        from fastapi import FastAPI, HTTPException
        from fastapi.testclient import TestClient
        from app.api.v1._drive_error_helper import raise_app_error
        from app.core.exceptions import app_exception_handler, AppException

        app = FastAPI()
        app.add_exception_handler(AppException, app_exception_handler)

        @app.get("/app-exc")
        async def app_exc():
            raise_app_error(404, "FILE_NOT_FOUND", "msg")

        @app.get("/http-exc")
        async def http_exc():
            raise HTTPException(status_code=404, detail="msg")

        client = TestClient(app)
        # 前端 useDriveFiles.js 必须这样 fallback:
        # e.response?.data?.error?.message || e.response?.data?.detail || '...'
        app_body = client.get("/app-exc").json()
        http_body = client.get("/http-exc").json()

        # AppException 路径
        assert app_body["error"]["message"] == "msg"  # error.message 命中
        assert app_body.get("detail") is None  # 无 detail fallback
        # HTTPException 路径
        assert http_body["detail"] == "msg"  # detail 命中
        assert http_body.get("error") is None  # 无 error fallback
        # 前端 fallback 链必须覆盖两种 envelope:
        assert (app_body.get("error", {}).get("message")
                or app_body.get("detail")
                or "default") == "msg"
        assert (http_body.get("error", {}).get("message")
                or http_body.get("detail")
                or "default") == "msg"
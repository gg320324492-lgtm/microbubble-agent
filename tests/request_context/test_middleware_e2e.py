"""W87-H-1 — FastAPI middleware X-Request-ID 透传 e2e 测试

派工 v6 §5 反馈类 20.28:
- request_id 必 HTTP 入口设
- middleware 优先级: client header 优先, fallback uuid4
- middleware 出口回写 response header (客户端可串联追踪)
"""
import uuid

import pytest
from fastapi.testclient import TestClient


class TestRequestContextMiddleware:
    """FastAPI middleware 端到端验证 (派工 v6 §5 反馈类 20.28)"""

    def test_response_has_x_request_id(self):
        """响应头必含 X-Request-ID (middleware 出口回写)"""
        # 用 TestClient 直接测 /health 端点 (无需 DB, 走 ASGITransport)
        from app.main import app

        with TestClient(app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            assert "X-Request-ID" in response.headers
            # uuid4 格式 check
            rid = response.headers["X-Request-ID"]
            try:
                uuid.UUID(rid)
                valid_uuid = True
            except ValueError:
                valid_uuid = False
            assert valid_uuid, f"X-Request-ID 应是 UUID 格式, got: {rid}"

    def test_client_supplied_x_request_id_echoed_back(self):
        """客户端透传 X-Request-ID → 响应回写同一 ID (分布式追踪串联)"""
        from app.main import app

        client_rid = "client-trace-abc123"

        with TestClient(app) as client:
            response = client.get(
                "/health",
                headers={"X-Request-ID": client_rid},
            )
            assert response.status_code == 200
            assert response.headers["X-Request-ID"] == client_rid

    def test_request_context_does_not_leak_across_requests(self):
        """不同请求的 request_id 隔离 (防止 next request 拿到上次的)"""
        from app.main import app

        with TestClient(app) as client:
            # 第一次请求: 客户端设 ID
            r1 = client.get(
                "/health",
                headers={"X-Request-ID": "first-rid"},
            )
            assert r1.headers["X-Request-ID"] == "first-rid"

            # 第二次: 不设, 应生成新 UUID
            r2 = client.get("/health")
            r2_rid = r2.headers["X-Request-ID"]
            assert r2_rid != "first-rid"
            # uuid4 format
            try:
                uuid.UUID(r2_rid)
                assert True
            except ValueError:
                pytest.fail(f"X-Request-ID 应是 UUID 格式, got: {r2_rid}")

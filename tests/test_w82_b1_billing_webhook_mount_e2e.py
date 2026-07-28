"""W82 第 1 批 B-1 P0: billing webhook router mount regression coverage."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.api.v1.billing_webhooks import router


ROOT = Path(__file__).resolve().parents[1]


def test_billing_webhook_routes_are_defined() -> None:
    paths = {
        (method, route.path.removeprefix(router.prefix))
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }
    assert {("POST", "/stripe"), ("POST", "/alipay"), ("POST", "/wechat_pay")} <= paths


def test_application_router_loader_mounts_billing_webhooks() -> None:
    source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module != "app.api.v1":
            continue
        for alias in node.names:
            if alias.name == "billing_webhooks":
                imported = True
                break
    assert imported, "main.py must import billing_webhooks in its application router list"
    assert "billing_webhooks.router" in source
    assert '"/api/v1"' in source


@pytest.mark.asyncio
async def test_mounted_webhook_path_is_not_404() -> None:
    """Mounted app exposes the endpoint; missing required signature may be 422."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")

    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/billing/webhooks/stripe", content=b"{}")

    assert response.status_code != 404
    assert response.status_code in (400, 401, 403, 422)

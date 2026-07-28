"""W82 第 1 批 B-1 P0: commercial tenant auth regression coverage.

The tenant management router is an admin-only surface.  These tests cover both
its dependency declarations and the observable unauthenticated response without
requiring a running PostgreSQL instance.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.api.v1.tenants import router
from app.core.security import get_current_admin_user


TENANT_PATHS = {
    ("POST", ""): "create_tenant",
    ("GET", ""): "list_tenants",
    ("GET", "/{tenant_id}"): "get_tenant",
    ("PATCH", "/{tenant_id}"): "update_tenant",
    ("POST", "/{tenant_id}/rotate-key"): "rotate_api_key",
    ("POST", "/{tenant_id}/suspend"): "suspend_tenant",
    ("POST", "/{tenant_id}/reactivate"): "reactivate_tenant",
    ("DELETE", "/{tenant_id}"): "delete_tenant",
}


def _routes_by_method_and_path() -> dict[tuple[str, str], APIRoute]:
    return {
        (method, route.path.removeprefix(router.prefix)): route
        for route in router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    }


def test_all_tenant_management_endpoints_require_admin_dependency() -> None:
    routes = _routes_by_method_and_path()
    assert set(TENANT_PATHS).issubset(routes)
    for key, endpoint_name in TENANT_PATHS.items():
        route = routes[key]
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        assert get_current_admin_user in dependency_calls, (
            f"{endpoint_name} ({key[0]} {key[1]}) must require admin auth"
        )


@pytest.mark.asyncio
async def test_unauthenticated_tenant_request_is_rejected() -> None:
    """A request without Bearer credentials must never reach tenant_service."""
    test_app = FastAPI()
    test_app.include_router(router)

    transport = httpx.ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/commercial/tenants")

    assert response.status_code in (401, 403)

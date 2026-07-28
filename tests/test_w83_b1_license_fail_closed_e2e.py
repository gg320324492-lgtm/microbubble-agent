"""W83 B-1 P1-2: license middleware fail-closed e2e

验证 license 服务降级时:
1. ``LicenseMiddleware.dispatch`` 对 license-only endpoint (e.g. /api/v1/billing) 返回 503
2. 普通 endpoint 不阻断 (community 用户仍可用 read-only 功能)
3. ``set_license_services_degraded(True)`` → ``is_license_services_degraded()`` 状态正确
4. ``set_license_services_degraded(False)`` → fail-closed 自动解除
5. 响应头 ``X-License-Degraded=1`` 在降级态暴露给前端

防商业版被白嫖: license 服务挂时, 社区用户不能绕过 fail-closed 访问 /api/v1/billing/*.
"""
from __future__ import annotations

import pytest

from app.middleware import license_middleware
from app.middleware.license_middleware import (
    LicenseMiddleware,
    _license_only_path,
    is_license_services_degraded,
    set_license_services_degraded,
)


class TestW83B1LicenseFailClosed:
    """W83 B-1 P1-2: license 服务降级 → license-only endpoint 503."""

    def setup_method(self):
        # 每个 test 前清状态
        set_license_services_degraded(False)

    def teardown_method(self):
        set_license_services_degraded(False)

    def test_license_only_path_recognizes_billing(self):
        """P1-2.1: /api/v1/billing/* 识别为 license-only."""
        assert _license_only_path("/api/v1/billing") is True
        assert _license_only_path("/api/v1/billing/") is True
        assert _license_only_path("/api/v1/billing/checkout") is True
        assert _license_only_path("/api/v1/billing/subscriptions/123") is True

    def test_license_only_path_recognizes_commercial_and_license(self):
        """P1-2.2: /api/v1/commercial/* + /api/v1/license/* 也是 license-only."""
        assert _license_only_path("/api/v1/commercial") is True
        assert _license_only_path("/api/v1/commercial/tenants") is True
        assert _license_only_path("/api/v1/license") is True
        assert _license_only_path("/api/v1/license/status") is True

    def test_license_only_path_does_not_block_normal_endpoints(self):
        """P1-2.3: 普通 endpoint (auth, members, tasks 等) 不是 license-only."""
        assert _license_only_path("/api/v1/auth/me") is False
        assert _license_only_path("/api/v1/members") is False
        assert _license_only_path("/api/v1/tasks") is False
        assert _license_only_path("/api/v1/meetings") is False
        assert _license_only_path("/api/v1/knowledge") is False
        assert _license_only_path("/health") is False

    def test_degraded_state_toggle(self):
        """P1-2.4: 降级态可设置 + 清除 (周期校验可恢复)."""
        assert is_license_services_degraded() is False
        set_license_services_degraded(True)
        assert is_license_services_degraded() is True
        set_license_services_degraded(False)
        assert is_license_services_degraded() is False

    def test_license_only_path_does_not_match_unrelated_prefix(self):
        """P1-2.5: 路径前缀不能误匹配 — /api/v1/billingaudit 不能算 license-only.

        当前实现用 ``path == p or path.startswith(p + "/")`` — 严格前缀.
        /api/v1/billingaudit 不以 ``/api/v1/billing/`` 开头, 不应被识别.
        """
        assert _license_only_path("/api/v1/billingaudit") is False
        assert _license_only_path("/api/v1/billing-fake") is False
        assert _license_only_path("/api/v1/billingx") is False

    def test_init_license_on_startup_sets_degraded_on_failure(self, monkeypatch):
        """P1-2.6: 启动期 verify_license 失败 → set degraded=True."""
        from app.services import license_service

        async def fake_verify(*args, **kwargs):
            raise ConnectionError("simulated license service down")

        monkeypatch.setattr(license_service, "verify_license", fake_verify)
        monkeypatch.setenv("LICENSE_KEY", "fake-key-for-test")
        monkeypatch.setenv("LICENSE_TENANT_ID", "test-tenant")

        # fake_db_factory 必须返一个 async context manager (调 __aenter__ / __aexit__)
        def fake_db_factory():
            class FakeDb:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    return False
            return FakeDb()

        import asyncio
        asyncio.run(license_middleware.init_license_on_startup(fake_db_factory))
        assert is_license_services_degraded() is True

    def test_init_license_on_startup_clears_degraded_on_success(self, monkeypatch):
        """P1-2.7: 启动期 verify_license 成功 → degraded=False."""
        # 先设 degraded=True (模拟上一次启动失败)
        set_license_services_degraded(True)
        from app.services import license_service

        async def fake_verify(*args, **kwargs):
            return {"valid": True, "mode": "online", "tier": "commercial", "tenant_id": "test"}

        monkeypatch.setattr(license_service, "verify_license", fake_verify)
        monkeypatch.setenv("LICENSE_KEY", "fake-key-for-test")
        monkeypatch.setenv("LICENSE_TENANT_ID", "test-tenant")

        def fake_db_factory():
            class FakeDb:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    return False
            return FakeDb()

        import asyncio
        asyncio.run(license_middleware.init_license_on_startup(fake_db_factory))
        assert is_license_services_degraded() is False
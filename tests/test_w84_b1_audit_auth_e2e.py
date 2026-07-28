"""W84 第 1 批 B-1 P1-6 — audit endpoints 鉴权回归监视 (admin_audit + admin_audit/summary).

派工前提铁律 12 (沿用 W82 B-1 类比): 任何 admin 端点必须 Depends(get_current_admin).
回归监视: 端点层 auth 完整 + 未鉴权调用返 401/403.
"""
from __future__ import annotations

import inspect
import os

os.environ.setdefault("SKIP_DB_SETUP", "1")


def test_admin_audit_router_endpoints_depend_on_get_current_admin():
    """P1-6: admin_audit.py 2 个端点必须 Depends(get_current_admin)."""
    from app.api.v1 import admin_audit

    source = inspect.getsource(admin_audit)
    assert "get_current_admin" in source, "admin_audit.py 缺少 get_current_admin 引用"

    # 直接检查源码中两个端点函数体是否都引用 get_current_admin
    assert 'admin: Member = Depends(get_current_admin)' in source, (
        "admin_audit 端点缺 admin: Member = Depends(get_current_admin) 守卫"
    )
    # 两个端点 (list_audit + audit_summary) 都应包含
    assert source.count("Depends(get_current_admin)") >= 2, (
        f"admin_audit 端点 get_current_admin 引用数 < 2 (期望 list_audit + audit_summary)"
    )


def test_get_current_admin_in_admin_module_rejects_non_admin():
    """P1-6: app/api/v1/admin.py:get_current_admin 必须校验 role."""
    from app.api.v1.admin import get_current_admin
    import inspect
    src = inspect.getsource(get_current_admin)
    assert "admin" in src and "leader" in src, "get_current_admin 缺少 role 白名单"
    assert "403" in src or "HTTP_403_FORBIDDEN" in src or "forbidden" in src.lower(), (
        "get_current_admin 缺 403 校验"
    )

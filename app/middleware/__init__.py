"""
商业化 middleware 集合 (W73 第 1 批 B-1)

- TenantMiddleware: 多租户 header 注入
- LicenseMiddleware: License 状态注入 (state + header)
"""
from app.middleware.tenant_middleware import TenantMiddleware, PUBLIC_PATH_PREFIXES
from app.middleware.license_middleware import (
    LicenseMiddleware, init_license_on_startup, get_license_state, set_license_state,
)

__all__ = [
    "TenantMiddleware",
    "PUBLIC_PATH_PREFIXES",
    "LicenseMiddleware",
    "init_license_on_startup",
    "get_license_state",
    "set_license_state",
]
"""
License Middleware (W73 第 1 批 B-1)

启动时校验 (load_license_from_env) + 周期校验 (Celery beat hourly):
- 启动期: 读 LICENSE_KEY 环境变量, 调 verify_license 在线校验
- 周期: 定时再校验, 过期/吊销自动切 read-only
- 请求期: 仅记录 license 状态到 request.state.license (不强制 fail, 让 endpoint 决定)

不破坏老路径: 仅在 app/middleware/license_middleware.py 新增.

W83 B-1 P1-2 修复 (license fail-closed):
- license 服务挂时**拒绝** license-only endpoint (防商业版被白嫖)
- 普通 endpoint 仍 allow (不影响 community 版用户)
- ``_LICENSE_SERVICES_DEGRADED`` 进程级标记: verify_license 失败时置 True
- ``_license_only_path()`` 精确匹配 license-only 路径前缀
- 周期校验 (Celery) 会恢复标记, 让 license 服务恢复后自动解除 fail-closed
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

logger = logging.getLogger(__name__)


# 启动期 license 状态 (process-level 单例, 由 init_license() 注入)
_LICENSE_STATE: dict = {
    "valid": False,
    "mode": "unknown",  # online / offline_grace / read_only / unknown
    "tier": "community",
    "expires_at": None,
    "tenant_id": None,
}

# W83 B-1 P1-2: license 服务降级标记
# True = verify_license 连续失败 (服务挂 / 网络断), middleware 进入 fail-closed
# Celery 周期校验成功后会清回 False, 让服务恢复后自动解除.
_LICENSE_SERVICES_DEGRADED: bool = False

# W83 B-1 P1-2: license-only endpoint 前缀 (商业版独占, community 不可访问)
# 防止 license 服务挂时被白嫖 (community 用户绕过 fail-closed 访问商业版 endpoint).
# 周期校验后 _LICENSE_SERVICES_DEGRADED 清回 False, fail-closed 自动解除.
_LICENSE_ONLY_PATH_PREFIXES = (
    "/api/v1/billing",           # 计费 (Phase 8 商业化)
    "/api/v1/commercial",        # 商业版管理 (Phase 8 商业化)
    "/api/v1/license",           # license 自查/续费
)


def _license_only_path(path: str) -> bool:
    """W83 B-1 P1-2: 判断 path 是否为 license-only endpoint (商业版独占)."""
    return any(path == p or path.startswith(p + "/") or path.startswith(p + "?") for p in _LICENSE_ONLY_PATH_PREFIXES)


def is_license_services_degraded() -> bool:
    """W83 B-1 P1-2: 外部检测 license 服务是否处于降级态."""
    return _LICENSE_SERVICES_DEGRADED


def set_license_services_degraded(degraded: bool) -> None:
    """W83 B-1 P1-2: 由周期校验/Celery 写入降级态."""
    global _LICENSE_SERVICES_DEGRADED
    _LICENSE_SERVICES_DEGRADED = degraded


def get_license_state() -> dict:
    """获取当前进程 license 状态 (Celery / API 共享)."""
    return dict(_LICENSE_STATE)


def set_license_state(state: dict) -> None:
    """更新 license 状态 (verify_license 调用方写入)."""
    _LICENSE_STATE.update(state)


async def init_license_on_startup(db_session_factory) -> dict:
    """启动期 license 校验 (从 LICENSE_KEY 环境变量读).

    Returns: 当前 license 状态 dict.
    """
    license_key = os.getenv("LICENSE_KEY")
    tenant_id = os.getenv("LICENSE_TENANT_ID", "default")
    if not license_key:
        logger.info("LICENSE_KEY not set, running in community (read_only) mode")
        set_license_state({
            "valid": False, "mode": "read_only", "tier": "community",
            "tenant_id": tenant_id, "reason": "LICENSE_KEY not configured",
        })
        set_license_services_degraded(False)  # 没设 key 不是降级, 是没启用
        return get_license_state()

    # 在线校验 (调用 license_service)
    try:
        from app.services.license_service import verify_license
        async with db_session_factory() as db:
            result = await verify_license(db, license_key, tenant_id, online=True)
        set_license_state(result)
        set_license_services_degraded(False)  # 校验成功, 服务正常
        logger.info("license verified on startup: mode=%s tier=%s", result.get("mode"), result.get("tier"))
    except Exception as e:
        logger.error("license verify on startup failed: %s", e)
        set_license_state({
            "valid": False, "mode": "read_only", "tier": "community",
            "tenant_id": tenant_id, "reason": f"startup verify failed: {e}",
        })
        # W83 B-1 P1-2: 启动期 verify 失败 → 标记服务降级, middleware 进入 fail-closed
        # 防止商业版被白嫖 (社区用户绕过 license 服务访问 /api/v1/billing 等).
        set_license_services_degraded(True)
    return get_license_state()


class LicenseMiddleware(BaseHTTPMiddleware):
    """把当前 license 状态注入到 request.state.license (供 endpoint 读取).

    W83 B-1 P1-2: license 服务降级时 (verify_license 连续失败),
    license-only endpoint 返回 503 (防商业版被白嫖), 普通 endpoint 仍 allow.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # W83 B-1 P1-2: license 服务降级态 + license-only path → fail-closed 503
        # 普通 endpoint 不阻断 (community 用户仍可访问 read-only 功能).
        if _LICENSE_SERVICES_DEGRADED and _license_only_path(request.url.path):
            logger.warning(
                "license fail-closed: services degraded, blocking license-only path=%s",
                request.url.path,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "LICENSE_SERVICES_UNAVAILABLE",
                        "message": "license 服务暂时不可用, 商业版功能暂停访问, 请稍后重试",
                        "details": {"path": request.url.path, "reason": "license_services_degraded"},
                    }
                },
                headers={"Retry-After": "60"},
            )
        request.state.license = get_license_state()
        response = await call_next(request)
        # 在响应头暴露 license 模式 (供前端展示)
        mode = request.state.license.get("mode", "unknown")
        response.headers["X-License-Mode"] = mode
        # W83 B-1 P1-2: 降级态暴露给前端 (供运维监控)
        if _LICENSE_SERVICES_DEGRADED:
            response.headers["X-License-Degraded"] = "1"
        return response
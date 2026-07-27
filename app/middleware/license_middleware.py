"""
License Middleware (W73 第 1 批 B-1)

启动时校验 (load_license_from_env) + 周期校验 (Celery beat hourly):
- 启动期: 读 LICENSE_KEY 环境变量, 调 verify_license 在线校验
- 周期: 定时再校验, 过期/吊销自动切 read-only
- 请求期: 仅记录 license 状态到 request.state.license (不强制 fail, 让 endpoint 决定)

不破坏老路径: 仅在 app/middleware/license_middleware.py 新增.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


# 启动期 license 状态 (process-level 单例, 由 init_license() 注入)
_LICENSE_STATE: dict = {
    "valid": False,
    "mode": "unknown",  # online / offline_grace / read_only / unknown
    "tier": "community",
    "expires_at": None,
    "tenant_id": None,
}


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
        return get_license_state()

    # 在线校验 (调用 license_service)
    try:
        from app.services.license_service import verify_license
        async with db_session_factory() as db:
            result = await verify_license(db, license_key, tenant_id, online=True)
        set_license_state(result)
        logger.info("license verified on startup: mode=%s tier=%s", result.get("mode"), result.get("tier"))
    except Exception as e:
        logger.error("license verify on startup failed: %s", e)
        set_license_state({
            "valid": False, "mode": "read_only", "tier": "community",
            "tenant_id": tenant_id, "reason": f"startup verify failed: {e}",
        })
    return get_license_state()


class LicenseMiddleware(BaseHTTPMiddleware):
    """把当前 license 状态注入到 request.state.license (供 endpoint 读取)."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request.state.license = get_license_state()
        response = await call_next(request)
        # 在响应头暴露 license 模式 (供前端展示)
        mode = request.state.license.get("mode", "unknown")
        response.headers["X-License-Mode"] = mode
        return response
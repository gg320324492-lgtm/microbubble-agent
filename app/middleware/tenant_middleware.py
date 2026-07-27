"""
多租户 Middleware (W73 第 1 批 B-1)

启动时校验 + 周期校验:
- 从请求头自动注入 tenant_id 到 request.state
- 公共路径 (plans / health) 跳过
- 不强制 API key (仅注入, 验证留给 endpoint)

不破坏老路径: 仅在 app/middleware/tenant_middleware.py 新增,
由 app/main.py 在 billing router 注册前挂载 (W74 起).
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# 公共路径前缀 — 不要求 tenant header
PUBLIC_PATH_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/commercial/billing/plans",  # 套餐定义公开查询
    "/commercial/license/check",  # License 校验公开端点
)


class TenantMiddleware(BaseHTTPMiddleware):
    """自动从请求头注入 tenant_id 到 request.state.tenant_id."""

    def __init__(self, app, public_prefixes: Optional[Iterable[str]] = None):
        super().__init__(app)
        self.public_prefixes = tuple(public_prefixes or PUBLIC_PATH_PREFIXES)

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        is_public = any(path.startswith(p) for p in self.public_prefixes)

        tenant_id = request.headers.get("X-Tenant-ID")
        api_key = request.headers.get("X-API-Key")

        if not is_public:
            if not tenant_id:
                logger.debug("missing X-Tenant-ID header on protected path: %s", path)
            # 不强制 fail, 让 endpoint 自身用 Depends 校验

        request.state.tenant_id = tenant_id
        request.state.api_key = api_key
        request.state.is_public = is_public
        return await call_next(request)
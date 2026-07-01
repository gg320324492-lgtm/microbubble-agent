"""audit_middleware — v2 PR7 自动审计中间件

做什么:
- 拦截所有 /api/v1/* 请求 (除 /health, /openapi.json 等公共端点)
- 记录到 audit_log 表 (同步 commit, 失败不阻塞主流程)
- user_id 自动从 Authorization Bearer token 解析 (轻量, 不查 DB)

不做什么:
- 不解析完整 user object (查 DB 太慢, 中间件每请求都跑)
- 不记录 /api/v1/* 外的请求 (前端静态资源 + 健康检查会让表体积爆炸)
- 不异步写 (审计数据可靠性优先; 同步 commit + try/except 兜底)

token 解析:
- 同 rate_limit_middleware 的 decode_token (复用 JWT 解析逻辑)
- payload['sub'] 是 user_id, parse 失败 → user_id=None (匿名)

action 分类 (按 path prefix):
- 写操作 (POST/PUT/PATCH/DELETE) → 'write'
- GET → 'read'
- /auth/login → 'login'
- /file-requests/{token}/submit → 'file_request_submit'
- /share-link → 'share_token_create'
- 其他 read/write 自动判断
"""
import logging
import re
import sys
from time import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import async_session

logger = logging.getLogger("microbubble.audit_middleware")


# 不记录的公共端点前缀 (静态资源 / 健康检查 / openapi)
SKIP_PATH_PREFIXES = (
    "/health",
    "/",
    "/openapi.json",
    "/docs",
    "/redoc",
    "/favicon.ico",
    "/assets/",
    "/static/",
    "/manifest",
)


def _classify_action(method: str, path: str) -> str:
    """从 method + path 推 action 字符串

    优先级 (从具体到通用):
      1. /auth/login → 'login'
      2. /file-requests/{token}/submit → 'file_request_submit'
      3. /share-link → 'share_token_create'
      4. /comments (POST/DELETE) → 'comment_create' / 'comment_delete'
      5. /ws/notifications → 'ws_connect' (实际写在 ws handler 里, 这里记录 GET probe)
      6. GET → 'read'
      7. 其他写 → 'write' (兜底)
    """
    method = method.upper()
    if path == "/api/v1/auth/login" and method == "POST":
        return "login"

    # file request 公开提交 (anonymous)
    if re.match(r"^/api/v1/file-requests/[^/]+/submit$", path) and method == "POST":
        return "file_request_submit"

    # share link create
    if re.match(r"^/api/v1/drive/files/\d+/share-link$", path) and method in ("POST",):
        return "share_token_create"

    # ws (只记录 GET/POST probe, 真实 connect 走 ws handler)
    if path.startswith("/api/v1/ws/"):
        return "ws_connect"

    # CRUD 默认
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return "write"
    if method == "GET":
        return "read"
    return "read"


def _extract_resource(method: str, path: str) -> tuple:
    """从 path 抽 (resource_type, resource_id)

    例:
      GET /api/v1/drive/files/42 → ('file', '42')
      POST /api/v1/notifications/5/read → ('notification', '5')
    """
    parts = path.strip("/").split("/")
    # /api/v1/<group>/<resource>[/<id>][/<action>]
    if len(parts) < 3 or parts[0] != "api" or parts[1] != "v1":
        return (None, None)
    group = parts[2]
    if not group or group in ("health",):
        return (None, None)
    resource_type = group
    resource_id = None
    if len(parts) >= 4 and parts[3].isdigit():
        resource_id = parts[3]
    return (resource_type, resource_id)


async def _audit_request(
    *,
    user_id,
    ip_address: str,
    user_agent: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: int,
):
    """同步写入 audit log (独立 session, 不影响请求主 session)"""
    try:
        # 独立 session (避免与请求主 session 竞争, audit 失败不污染主事务)
        async with async_session() as session:
            from app.services.audit_service import audit_service
            action = _classify_action(method, path)
            resource_type, resource_id = _extract_resource(method, path)
            await audit_service.log(
                session,
                user_id=user_id,
                ip_address=ip_address,
                user_agent=user_agent,
                method=method,
                path=path,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                status_code=status_code,
                duration_ms=duration_ms,
                metadata=None,  # PR7 audit_service.log kwarg = metadata (mapped to meta_data col)
            )
    except Exception as e:
        # audit 失败绝对不能阻塞主请求
        logger.warning(
            f"[AuditMiddleware] log 失败: method={method} path={path} "
            f"status={status_code} error={e}",
            exc_info=True,
        )


def _get_client_ip(request: Request) -> str:
    """从 X-Forwarded-For 头提取真实 IP (与 rate_limit.py 一致)"""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        ip = xff.split(",")[0].strip()
        if ip:
            return ip[:45]
    if request.client:
        return request.client.host[:45]
    return "unknown"


def _parse_token_user_id(request: Request):
    """轻量解析 JWT → user_id (复用 security.py 解析逻辑, 不查 DB)"""
    try:
        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return None
        token = auth[7:]
        # 复用 rate_limit 同一套 decode, 避免重复导入
        from app.core.rate_limit import _try_attach_user_id  # noqa
        # _try_attach_user_id 写到 request.state.user_id 后立刻 commit 时被读
        # 这里直接调 decode_token (简化路径)
        from app.core.security import decode_token
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        sub = payload.get("sub")
        if not sub:
            return None
        try:
            return int(sub)
        except (ValueError, TypeError):
            return None
    except Exception:
        return None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """PR7 自动审计中间件 — BaseHTTPMiddleware 范式 (add_middleware)

    add_middleware 范式在 fastapi 比 @app.middleware 装饰器范式更可靠:
    装饰器范式在某些 starlette 版本 + app setup 时序组合下会被吞掉
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # PR7 debug: 强制 trace
        import sys
        print(f"[RequestLoggingMiddleware] dispatch ENTER method={request.method} path={path}", file=sys.stderr, flush=True)

        # 跳过公共端点
        if any(path.startswith(p) for p in SKIP_PATH_PREFIXES):
            return await call_next(request)

        # 仅审计 /api/v1/*
        if not path.startswith("/api/v1/"):
            return await call_next(request)

        method = request.method
        ip = _get_client_ip(request)
        ua = (request.headers.get("User-Agent") or "")[:1000]
        user_id = _parse_token_user_id(request)

        start = time()
        try:
            response = await call_next(request)
        except Exception:
            duration = int((time() - start) * 1000)
            await _audit_request(
                user_id=user_id, ip_address=ip, user_agent=ua,
                method=method, path=path, status_code=500, duration_ms=duration,
            )
            raise

        duration = int((time() - start) * 1000)
        await _audit_request(
            user_id=user_id, ip_address=ip, user_agent=ua,
            method=method, path=path,
            status_code=response.status_code, duration_ms=duration,
        )

        return response


async def audit_middleware_legacy(request: Request, call_next):
    """Legacy 装饰器范式 (与 rate_limit_middleware 同); main.py 当前用 RequestLoggingMiddleware 类"""
    path = request.url.path

    if any(path.startswith(p) for p in SKIP_PATH_PREFIXES):
        return await call_next(request)
    if not path.startswith("/api/v1/"):
        return await call_next(request)

    method = request.method
    ip = _get_client_ip(request)
    ua = (request.headers.get("User-Agent") or "")[:1000]
    user_id = _parse_token_user_id(request)

    start = time()
    try:
        response = await call_next(request)
    except Exception:
        duration = int((time() - start) * 1000)
        await _audit_request(
            user_id=user_id, ip_address=ip, user_agent=ua,
            method=method, path=path, status_code=500, duration_ms=duration,
        )
        raise

    duration = int((time() - start) * 1000)
    await _audit_request(
        user_id=user_id, ip_address=ip, user_agent=ua,
        method=method, path=path,
        status_code=response.status_code, duration_ms=duration,
    )
    return response

    method = request.method
    ip = _get_client_ip(request)
    ua = (request.headers.get("User-Agent") or "")[:1000]
    user_id = _parse_token_user_id(request)

    start = time()
    # 调用下游 handler
    try:
        response = await call_next(request)
    except Exception:
        # handler 内异常 → 让上层 catch 之前先记一笔 (5xx without response)
        duration = int((time() - start) * 1000)
        await _audit_request(
            user_id=user_id,
            ip_address=ip,
            user_agent=ua,
            method=method,
            path=path,
            status_code=500,
            duration_ms=duration,
        )
        raise

    duration = int((time() - start) * 1000)
    # 同步 audit (PR7 决定: 可靠性优先, 审计必须落库)
    # 代价: 1-3ms 延迟 (commit), 不阻塞主流程太久
    # 失败: try/except 兜底, audit 失败不抛 (主响应已生成, 不能 5xx)
    await _audit_request(
        user_id=user_id,
        ip_address=ip,
        user_agent=ua,
        method=method,
        path=path,
        status_code=response.status_code,
        duration_ms=duration,
    )

    return response

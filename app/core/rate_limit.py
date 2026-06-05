"""全站 API 限流器 — 按类型分级"""

import time
from collections import defaultdict
from fastapi import Request, HTTPException, status


class RateLimiter:
    """基于滑动窗口的内存限流器"""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = defaultdict(list)

    def _cleanup(self, key: str):
        cutoff = time.time() - self.window_seconds
        self._attempts[key] = [t for t in self._attempts[key] if t > cutoff]

    def check(self, key: str):
        self._cleanup(key)
        if len(self._attempts[key]) >= self.max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"请求过于频繁，请 {self.window_seconds} 秒后重试"
            )

    def record(self, key: str):
        self._attempts[key].append(time.time())


# 分级限流器实例
_rate_limiters = {
    "auth": RateLimiter(max_attempts=5, window_seconds=60),      # 认证：5次/分钟
    "write": RateLimiter(max_attempts=30, window_seconds=60),    # 写操作：30次/分钟
    "read": RateLimiter(max_attempts=100, window_seconds=60),    # 读操作：100次/分钟
    "upload": RateLimiter(max_attempts=10, window_seconds=60),   # 上传：10次/分钟
}


def _get_rate_limit_type(request: Request) -> str:
    """根据请求路径和方法判断限流类型"""
    path = request.url.path
    method = request.method

    # 认证端点
    if "/auth/" in path:
        return "auth"

    # 上传端点
    if "/upload" in path:
        return "upload"

    # 写操作
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return "write"

    # 读操作
    return "read"


def _get_client_key(request: Request) -> str:
    """获取客户端标识（IP + 用户）"""
    client_ip = request.client.host if request.client else "unknown"
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"{client_ip}:user:{user_id}"
    return f"{client_ip}:anon"


async def rate_limit_middleware(request: Request, call_next):
    """全站限流中间件"""
    from starlette.responses import JSONResponse

    # 跳过健康检查和 WebSocket
    if request.url.path in ("/health", "/docs", "/openapi.json"):
        return await call_next(request)

    limit_type = _get_rate_limit_type(request)
    limiter = _rate_limiters[limit_type]
    client_key = f"{limit_type}:{_get_client_key(request)}"

    try:
        limiter.check(client_key)
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"error": {"code": "RATE_LIMIT_EXCEEDED", "message": e.detail}},
        )

    limiter.record(client_key)

    response = await call_next(request)

    # 添加限流信息到响应头
    limiter._cleanup(client_key)
    remaining = limiter.max_attempts - len(limiter._attempts[client_key])
    response.headers["X-RateLimit-Limit"] = str(limiter.max_attempts)
    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
    response.headers["X-RateLimit-Reset"] = str(int(time.time() + limiter.window_seconds))

    return response


# 保留旧的登录限流器（向后兼容）
login_limiter = RateLimiter(max_attempts=5, window_seconds=300)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

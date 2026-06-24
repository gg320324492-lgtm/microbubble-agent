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
    "auth": RateLimiter(max_attempts=20, window_seconds=60),      # 真认证动作：登录/刷新/改密 20次/分钟
    "write": RateLimiter(max_attempts=30, window_seconds=60),    # 写操作：30次/分钟
    "read": RateLimiter(max_attempts=200, window_seconds=60),    # 读操作：200次/分钟
    "upload": RateLimiter(max_attempts=10, window_seconds=60),   # 上传：10次/分钟
}

# /auth/ 下细分：只对真正敏感的认证动作保留 20/min 限流
_AUTH_SENSITIVE_PATHS = frozenset({
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/auth/change-password",
    "/api/v1/auth/reset-password",
    "/api/v1/auth/init-password",
})

# 2026-06-18 用户强烈反馈：/auth/me 即便 200/min 也被高频 polling 触发 429
# （MainLayout / MeetingView 每次 reactive set value 都触发 useUserStore 重新拉 /auth/me）
# 完全豁免限流 —— /auth/me 是只读 GET，且需要 JWT 鉴权（未带 token 401 直接拒），
# 攻击成本高，无防护必要。设超大值兜底
_AUTH_UNLIMITED_PATHS = frozenset({
    "/api/v1/auth/me",  # 当前用户信息（高频 polling：页面加载/Pinia 初始化/token 校验/reactive 触发）
})


def _get_rate_limit_type(request: Request) -> str:
    """根据请求路径和方法判断限流类型

    返回 "unlimited" 表示跳过限流（/auth/me 等安全只读端点）
    """
    path = request.url.path
    method = request.method

    # /auth/me 等高频只读端点 → 不限流（JWT 鉴权已防滥用）
    if path in _AUTH_UNLIMITED_PATHS:
        return "unlimited"

    # v31.2: 检索质量埋点端点 - POST/PATCH 完全豁免（前端每次搜索 2 次埋点, 不该限流）,
    # GET stats/logs 走 read tier (200/min) 防滥用.
    # v31.2.1 防御: 若路径是 /api/v1/auth/ 下的"auth 子路径嵌入 analytics 字符串"
    # (e.g. 未来加 POST /api/v1/auth/analytics/export), 不应走 /analytics 豁免
    # —— 顺序 2 优先顺序 3, 会被绕过 /auth/ 敏感端点 20/min 限流. 守卫: /auth/
    # 子路径必须走下方 /auth/ 细分分支（按 sensitive/write/read 分级）.
    if "/analytics" in path and not path.startswith("/api/v1/auth/"):
        if method in ("POST", "PATCH", "PUT"):
            return "unlimited"
        return "read"

    # /auth/ 路径细分（4 类）：
    #  1. 白名单内（login/refresh/change-password 等敏感） → auth tier (20/min)
    #  2. 写操作（PUT /auth/profile 等） → write tier (30/min)
    #  3. 其他 /auth/* 只读 → read tier (200/min)
    #  4. 其他 /auth/* 未列出 → auth tier fallback（防 401 风暴）
    if "/auth/" in path:
        if path in _AUTH_SENSITIVE_PATHS:
            return "auth"
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            return "write"
        return "read"

    # 上传端点
    if "/upload" in path:
        return "upload"

    # 写操作
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return "write"

    # 读操作
    return "read"


def _get_client_key(request: Request) -> str:
    """获取客户端标识（IP + 用户）

    v31.2: 改用 get_client_ip() 而非 request.client.host
    - 旧: 生产环境 Nginx 反向代理后 client.host 全部 127.0.0.1, 限流退化为全站共享额度
    - 新: get_client_ip() 正确读 X-Forwarded-For 头, 真实 per-IP 限流
    """
    client_ip = get_client_ip(request)
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
    # 2026-06-18 /auth/me 等安全只读端点完全不限流（JWT 已鉴权）
    if limit_type == "unlimited":
        return await call_next(request)
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
    """获取真实客户端 IP（按 XFF 优先级回退，v31.2.1 修复空 IP 兜底）

    优先级:
      1. X-Forwarded-For 第一段（反向代理标准，左数最近为真实客户端）
      2. request.client.host（直连 / 测试环境）
      3. "unknown"（兜底，禁止返回空字符串）

    v31.2.1 修复: XFF 首段为空（", 1.2.3.4" / "   " / ",,,,,"）时，
    旧实现 .split(",")[0].strip() 返空串 → 多请求共享空 IP key 触发共享配额.
    现统一兜底为 "unknown"，让 Nginx 通常无此问题的前提下，万一绕过 Nginx
    直打后端的攻击者也无法用空 XFF 共享 200/min 配额.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
        if ip:                                  # v31.2.1: 空 IP 必须兜底
            return ip
        return "unknown"
    return request.client.host if request.client else "unknown"

"""全站 API 限流器 — 按类型分级"""

import re
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
    "sse": RateLimiter(max_attempts=10, window_seconds=60),      # v31.2.3: SSE 长连接 10次/分钟
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

# v31.2.2: 检索质量埋点端点精确路径匹配 (取代 v31.2.1 的 substring "/analytics")
# 用 regex 而非 frozenset, 是因为 PATCH /search-event/{event_id}/click 含动态 event_id
# 之前用 substring "/analytics" 匹配会导致未来加 /api/v1/auth/analytics/... 嵌套路径
# 绕过 /auth/ 限流 (v31.2.1 用 startswith 守卫临时挡, B3 方案彻底消除 substring 风险)
# 4 个 endpoint:
#   POST   /api/v1/analytics/search-event
#   PATCH  /api/v1/analytics/search-event/{event_id}/click  (event_id 必须 int)
#   GET    /api/v1/analytics/stats
#   GET    /api/v1/analytics/logs
_ANALYTICS_PATH_RE = re.compile(
    r"^/api/v1/analytics/search-event$"
    r"|^/api/v1/analytics/search-event/\d+/click$"
    r"|^/api/v1/analytics/stats$"
    r"|^/api/v1/analytics/logs$"
)

# v31.2.3: SSE (text/event-stream) 长连接端点精确路径匹配
# 当前: POST /api/v1/chat/stream (Agent 对话流式输出)
# 未来加其他 SSE 端点, 扩展 regex 即可 (例如语音 TTS stream)
_SSE_PATH_RE = re.compile(
    r"^/api/v1/chat/stream$"
)

# v31.2.3: /auth/ 路径前缀匹配 (取代 substring "/auth/" in path)
# 之前 substring '"/auth/" in path' 会误匹配 /api/v1/authentication/...
# (不带 / 后缀但含 "auth" 子串). prefix 匹配要求路径以 '/api/v1/auth/'
# 开头或严格等于 '/api/v1/auth', 彻底消除 substring 误匹配风险.
def _is_under_auth(path: str) -> bool:
    return path == "/api/v1/auth" or path.startswith("/api/v1/auth/")


def _get_rate_limit_type(request: Request) -> str:
    """根据请求路径和方法判断限流类型

    返回 "unlimited" 表示跳过限流（/auth/me 等安全只读端点）
    """
    path = request.url.path
    method = request.method

    # /auth/me 等高频只读端点 → 不限流（JWT 鉴权已防滥用）
    if path in _AUTH_UNLIMITED_PATHS:
        return "unlimited"

    # v31.2.3: SSE 长连接 (text/event-stream) 独立 tier
    # SSE 一次连接占用几秒到几分钟 (流式 chat), 按 read tier 200/min 算只能
    # 并发 200 个用户, 太少. 单独给 10/min 配额, 让前端能区分流式限流 vs 普通读.
    # 当前只 1 个 SSE 端点: POST /api/v1/chat/stream (Agent 对话)
    # 未来加其他 SSE 端点, 在 _SSE_PATH_RE 加 regex 即可
    if _SSE_PATH_RE.match(path):
        return "sse"

    # v31.2: 检索质量埋点端点 - POST/PATCH 完全豁免（前端每次搜索 2 次埋点, 不该限流）,
    # GET stats/logs 走 read tier (200/min) 防滥用.
    # v31.2.1 防御: substring "/analytics" + startswith("/api/v1/auth/") 守卫
    # v31.2.2 B3 方案: 改用 _ANALYTICS_PATH_RE 精确路径匹配, 彻底消除 substring
    # 误匹配风险. 例如未来加 POST /api/v1/auth/analytics/export 不会命中 regex
    # (因为 regex 只匹配 /api/v1/analytics/ 前缀), 自动走下方 /auth/ 细分.
    if _ANALYTICS_PATH_RE.match(path):
        if method in ("POST", "PATCH", "PUT"):
            return "unlimited"
        return "read"

    # /auth/ 路径细分（4 类）：
    #  1. 白名单内（login/refresh/change-password 等敏感） → auth tier (20/min)
    #  2. 写操作（PUT /auth/profile 等） → write tier (30/min)
    #  3. 其他 /auth/* 只读 → read tier (200/min)
    #  4. 其他 /auth/* 未列出 → auth tier fallback（防 401 风暴）
    # v31.2.3: 改用 _is_under_auth() prefix 匹配, 取代 substring "/auth/" in path
    # (修复 /api/v1/authentication/... 等带 auth 子串但非 /auth/ 路径的误匹配)
    if _is_under_auth(path):
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


def _try_attach_user_id(request: Request) -> None:
    """v31.2.2: 尝试从 Authorization Bearer token 解析 user_id 写入 request.state.

    行为:
      - 无 Authorization header → 不写, user_id=None (走 {ip}:anon 配额)
      - 无效/过期 token → 不写, user_id=None (同匿名, 不抛 401)
      - 有效 access token → 解析 payload, 写入 request.state.user_id = int(sub)

    注意: 这是限流 middleware 用的**轻量级**token 解析, 不查 DB (性能考虑).
    即使 token 对应的 member 已被删, user_id 仍写入 (限流 key 仍独立).
    真鉴权由 Depends(get_current_user) / Depends(get_current_user_optional) 在 endpoint
    入口处理. 这里只用作限流维度的 key.
    """
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return
    token = auth[7:]  # 去掉 "Bearer " 前缀
    try:
        # 复用 security.decode_token, 但加 import 守卫避免循环引用
        from app.core.security import decode_token
        payload = decode_token(token)
    except Exception:
        return  # 无效/过期 token → 视为匿名, 不写 user_id
    if payload.get("type") != "access":
        return
    sub = payload.get("sub")
    if not sub:
        return
    try:
        request.state.user_id = int(sub)
    except (ValueError, TypeError):
        return  # sub 不是 int → 静默忽略


async def rate_limit_middleware(request: Request, call_next):
    """全站限流中间件"""
    from starlette.responses import JSONResponse

    # 跳过健康检查和 WebSocket
    if request.url.path in ("/health", "/docs", "/openapi.json"):
        return await call_next(request)

    # v31.2.2: 解析 Bearer token (optional, 不强制登录) 写入 request.state.user_id
    # 解析成功 → user_id 用于限流 key ({ip}:user:{uid}) —— 登录用户独立配额
    # 解析失败 / 无 token → user_id=None → 限流 key 用 {ip}:anon —— 按 IP 限流
    # 这让 _get_client_key 自动按登录维度区分, 不再退化到全站共享 200/min
    _try_attach_user_id(request)

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
    # v31.2.3: 加 X-RateLimit-Policy 让前端能识别触发的 tier,
    # 用于 tier-aware UX (auth 429 → 跳登录页; read 429 → 降级到缓存)
    limiter._cleanup(client_key)
    remaining = limiter.max_attempts - len(limiter._attempts[client_key])
    response.headers["X-RateLimit-Limit"] = str(limiter.max_attempts)
    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
    response.headers["X-RateLimit-Reset"] = str(int(time.time() + limiter.window_seconds))
    response.headers["X-RateLimit-Policy"] = limit_type

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

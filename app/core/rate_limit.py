"""全站 API 限流器 — 按类型分级"""

import re
import time
from collections import defaultdict
from fastapi import Request, HTTPException, status


class RateLimiter:
    """基于滑动窗口的内存限流器

    v31.2.x 默认使用. 优势: 零依赖, 快 (<1ms check).
    劣势: docker compose restart 全清零, 攻击者赶在窗口重置前打满.
    """

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


class AsyncRedisRateLimiter:
    """基于 Redis ZSET 的滑动窗口限流器 (v31.2.4)

    ZSET key: "rl:{tier}:{client_key}", score=timestamp, value=timestamp (str)
    check 流程:
      1. ZREMRANGEBYSCORE 清窗口外的旧 timestamp
      2. ZCARD 计数
      3. 若 >= max_attempts → 429
      4. 否则 ZADD 新 timestamp + EXPIRE 窗口+1s

    优势:
      - 抗 docker restart (Redis 持久化, 默认 RDB 每分钟 snapshot)
      - 跨实例共享 (未来多 worker / 多 pod)
      - 真实滑动窗口 (vs 内存版 ZADD 后 N 个 timestamp)
    劣势:
      - Redis 不可用时需要 fallback (不能拒绝所有请求)
      - 单次 check 多 1 次 round-trip (~1ms)

    当前状态 (v31.2.6): 全站统一使用本类 (含 login_limiter).
    RateLimiter (内存版) 保留为向后兼容类, 当前已无 caller.
    """

    def __init__(self, max_attempts: int = 5, window_seconds: int = 300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds

    def _redis_key(self, key: str) -> str:
        return f"rl:{key}"  # rl = rate limit

    async def check(self, key: str):
        """async check, 返回 None = 通过, raise HTTPException = 限流"""
        from app.core.redis import get_redis
        try:
            r = await get_redis()
            now = time.time()
            cutoff = now - self.window_seconds
            rkey = self._redis_key(key)
            # 1. 清窗口外
            await r.zremrangebyscore(rkey, 0, cutoff)
            # 2. 计数
            count = await r.zcard(rkey)
            if count >= self.max_attempts:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"请求过于频繁，请 {self.window_seconds} 秒后重试",
                    headers={"Retry-After": str(self.window_seconds)},  # v31.2.6
                )
        except HTTPException:
            raise  # 429 必须抛
        except Exception:
            # Redis 不可用 / 网络错 → 静默降级, 不阻断请求
            pass

    async def record(self, key: str):
        """async record, 失败也静默降级"""
        from app.core.redis import get_redis
        try:
            r = await get_redis()
            now = time.time()
            rkey = self._redis_key(key)
            # ZADD 新 timestamp + EXPIRE 窗口+1s (清理用)
            await r.zadd(rkey, {str(now): now})
            await r.expire(rkey, self.window_seconds + 1)
        except Exception:
            pass  # Redis 故障 → 静默降级, 不阻断

    async def remaining(self, key: str) -> int:
        """返当前剩余配额 (给响应头 X-RateLimit-Remaining 用)"""
        from app.core.redis import get_redis
        try:
            r = await get_redis()
            now = time.time()
            cutoff = now - self.window_seconds
            rkey = self._redis_key(key)
            await r.zremrangebyscore(rkey, 0, cutoff)
            count = await r.zcard(rkey)
            return max(0, self.max_attempts - count)
        except Exception:
            return self.max_attempts  # fallback: 不知道, 返满配额


# 分级限流器实例
# v31.2.5: 切到 AsyncRedisRateLimiter（Redis ZSET 持久化）
# 优势: 抗 docker compose restart, 跨实例共享, 真实滑动窗口
# 劣势: 多 1 次 Redis round-trip (~1ms), Redis 不可用时静默降级 (try/except)
_rate_limiters = {
    "auth": AsyncRedisRateLimiter(max_attempts=20, window_seconds=60),      # 真认证动作：登录/刷新/改密 20次/分钟
    "write": AsyncRedisRateLimiter(max_attempts=30, window_seconds=60),     # 写操作：30次/分钟
    "read": AsyncRedisRateLimiter(max_attempts=200, window_seconds=60),     # 读操作：200次/分钟
    "upload": AsyncRedisRateLimiter(max_attempts=10, window_seconds=60),    # 上传：10次/分钟
    "sse": AsyncRedisRateLimiter(max_attempts=10, window_seconds=60),       # v31.2.3: SSE 长连接 10次/分钟
    "drive_upload": AsyncRedisRateLimiter(max_attempts=50, window_seconds=60),  # PR2.10: drive 上传 50次/分 (批量友好)
    "drive_list": AsyncRedisRateLimiter(max_attempts=300, window_seconds=60),  # PR2.10: drive 列表 300次/分 (高频浏览)
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

    # PR2.10: 课题组网盘 drive 端点 tier 区分
    # 路径匹配 /api/v1/drive/* 和 /api/v1/upload/multipart/*
    # drive 上传 (POST/单端点流) 50次/分, drive 列表 (GET) 300次/分
    # 端点: POST /drive/files/upload, POST /upload/multipart/complete, POST /upload/multipart/init, POST /drive/files/batch-download
    if path.startswith("/api/v1/drive/") or path.startswith("/api/v1/upload/"):
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            return "drive_upload"
        return "drive_list"

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
    """全站限流中间件

    v31.2.5: 切到 AsyncRedisRateLimiter (Redis ZSET 持久化)
    - 抗 docker compose restart (Redis 默认 RDB 每分钟 snapshot)
    - 跨实例共享 (未来多 worker / 多 pod)
    - Redis 故障时静默降级 (limiter.check/record 内部 try/except)
    """
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
        await limiter.check(client_key)
    except HTTPException as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"error": {"code": "RATE_LIMIT_EXCEEDED", "message": e.detail}},
            headers=dict(e.headers) if e.headers else None,  # v31.2.6 转发 Retry-After
        )

    await limiter.record(client_key)

    response = await call_next(request)

    # 添加限流信息到响应头
    # v31.2.3: 加 X-RateLimit-Policy 让前端能识别触发的 tier,
    # 用于 tier-aware UX (auth 429 → 跳登录页; read 429 → 降级到缓存)
    # v31.2.5: remaining 从 Redis (await limiter.remaining) 而非内存 dict 读
    remaining = await limiter.remaining(client_key)
    response.headers["X-RateLimit-Limit"] = str(limiter.max_attempts)
    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
    response.headers["X-RateLimit-Reset"] = str(int(time.time() + limiter.window_seconds))
    response.headers["X-RateLimit-Policy"] = limit_type

    return response


# v31.2.6: login_limiter 切到 Redis ZSET 持久化 (抗 docker restart / 跨 worker 共享).
# 与 middleware auth tier 区别: middleware 是 20/min (覆盖所有 _AUTH_SENSITIVE_PATHS),
# login_limiter 是更严的 5/300s (仅登录密码错误) — 防爆破.
# 调用方 auth.py 用 "login:" 前缀 → Redis key 变 rl:login:{ip}, 与 middleware 的
# rl:auth:{ip}:... 等 tier prefix 命名一致.
# AsyncRedisRateLimiter.check 抛出的 HTTPException 已带 Retry-After 头 (v31.2.6).
login_limiter = AsyncRedisRateLimiter(max_attempts=5, window_seconds=300)


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

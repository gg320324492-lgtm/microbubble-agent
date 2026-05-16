"""简单的内存限流器"""

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


login_limiter = RateLimiter(max_attempts=5, window_seconds=300)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

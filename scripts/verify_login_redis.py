"""v31.2.6 登录限流抗重启验证

策略: 灌满 login_limiter (5/300s) 到 5/5, 然后 docker compose restart app,
      新进程处理第 6 次请求应该看到 429 + Retry-After: 300 响应头,
      证明 Redis ZSET 持久化生效 + Retry-After 头正确传递.

依赖: 当前 host 暴露 docker, 容器名 microbubble-agent-app-1, Redis 健康.
"""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request


BASE = "localhost:8000"
APP_CONTAINER = "microbubble-agent-app-1"


def post_login(xff: str, password: str = "wrong") -> tuple[int, dict]:
    """POST /api/v1/auth/login — 返 (status, headers_dict, body)."""
    req = urllib.request.Request(
        f"http://{BASE}/api/v1/auth/login",
        data=json.dumps({"username": "wangtianzhi", "password": password}).encode(),
        headers={"Content-Type": "application/json", "X-Forwarded-For": xff},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        body = resp.read()
        # HTTP header 大小写不敏感, 但 uvicorn 写出来是小写, 用 lowercase map
        headers = {k.strip().lower(): v.strip() for k, v in resp.getheaders()}
        return resp.status, headers, body
    except urllib.error.HTTPError as e:
        headers = {k.strip().lower(): v.strip() for k, v in e.headers.items()}
        return e.code, headers, e.read()


def redis_cli(*args: str) -> str:
    """Redis 命令 wrapper (subprocess)."""
    return subprocess.check_output(
        ["docker", "exec", "microbubble-agent-redis-1", "redis-cli", *args],
        text=True,
    ).strip()


def redis_zcard(key: str) -> int:
    return int(redis_cli("ZCARD", key))


def redis_ttl(key: str) -> int:
    return int(redis_cli("TTL", key))


def wait_healthy(timeout: int = 30) -> bool:
    """等 /health 返 200."""
    for i in range(timeout):
        try:
            resp = urllib.request.urlopen(f"http://{BASE}/health", timeout=2)
            if resp.status == 200:
                print(f"  healthy after {i+1}s")
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def main():
    xff = "203.0.113.66"  # 固定 XFF 隔离 IP 维度 (RFC 5737 TEST-NET-3)
    rkey = f"rl:login:{xff}"  # AsyncRedisRateLimiter._redis_key 加 "rl:" 前缀
    print(f"=== v31.2.6 登录限流抗重启验证 ===\n")
    print(f"  XFF={xff}")
    print(f"  Redis key={rkey}\n")

    # 0. Pre-clean: 确保起点为 0
    redis_cli("DEL", rkey)
    print(f"  Pre-cleaned {rkey}\n")

    # 1. 灌 5 次错误密码 (期望全 401, 但限流计数 +1)
    print("--- 阶段 1: 灌 5 次错误密码 (期望全 401) ---")
    for i in range(1, 6):
        status, headers, body = post_login(xff)
        retry_after = headers.get("retry-after")
        policy = headers.get("x-ratelimit-policy")
        remaining = headers.get("x-ratelimit-remaining")
        print(f"  Attempt {i}: status={status} retry-after={retry_after} policy={policy} remaining={remaining}")
        if status != 401:
            print(f"  FAIL: expected 401, got {status}: {body[:200]}")
            redis_cli("DEL", rkey)
            return False
    print("  PASS: 5 次错误密码全 401 (计数 +5)")

    # 2. 第 6 次请求: 应触发 429 + Retry-After: 300
    print("\n--- 阶段 2: 第 6 次请求 (期望 429 + Retry-After: 300) ---")
    status, headers, body = post_login(xff)
    retry_after = headers.get("retry-after")
    policy = headers.get("x-ratelimit-policy")
    remaining = headers.get("x-ratelimit-remaining")
    print(f"  status={status} retry-after={retry_after} policy={policy} remaining={remaining}")
    print(f"  body={body[:200].decode('utf-8', errors='replace')}")
    if status != 429:
        print(f"  FAIL: expected 429, got {status}")
        redis_cli("DEL", rkey)
        return False
    if retry_after != "300":
        print(f"  FAIL: Retry-After 期望 '300', 实际 {retry_after!r}")
        redis_cli("DEL", rkey)
        return False
    if policy != "auth":
        # middleware 的 auth tier 也 set 了 policy=auth, 但 login_limiter 触发时
        # middleware 已经通过 + 不写头 (因为异常在 endpoint 内 raise, 不是 middleware JSONResponse)
        # → 此时 policy 可能不存在, 接受 None 或 'auth'
        # 但登录 endpoint 在 middleware 之后, middleware 已经 record + 写了成功头
        # (因为 limit < max_attempts 中间件通过), 然后 endpoint 抛 HTTPException
        # FastAPI 默认用 HTTPException 的 detail, 不会覆盖中间件设置的头
        # 所以 policy/remaining 可能存在
        if policy is not None and policy != "auth":
            print(f"  WARN: unexpected policy {policy!r} (期望 None 或 'auth')")
    print("  PASS: 429 + Retry-After: 300 正确")

    # 3. 看 Redis ZSET + TTL
    print("\n--- 阶段 3: Redis ZSET 检查 ---")
    zcard = redis_zcard(rkey)
    ttl = redis_ttl(rkey)
    print(f"  ZCARD={zcard} (期望 5) TTL={ttl}s (期望 290-301)")
    if zcard != 5:
        print(f"  FAIL: ZCARD 应为 5, 实际 {zcard}")
        redis_cli("DEL", rkey)
        return False
    if not (290 <= ttl <= 301):
        print(f"  FAIL: TTL 应在 [290, 301], 实际 {ttl}")
        redis_cli("DEL", rkey)
        return False
    print("  PASS: Redis ZSET 5 个 timestamp + TTL 正常")

    # 4. docker compose restart app
    print("\n--- 阶段 4: docker compose restart app (抗重启关键) ---")
    result = subprocess.run(
        ["docker", "compose", "restart", "app"],
        capture_output=True, text=True, timeout=60,
    )
    print(f"  restart exit code: {result.returncode}")
    if result.returncode != 0:
        print(f"  FAIL: restart failed: {result.stderr}")
        return False

    print("  等待 app healthy...")
    if not wait_healthy():
        print("  FAIL: app 没起来")
        return False

    # 5. 重启后请求: ZSET 已经有 5 个 timestamp, 第 6 次请求
    #    - login_limiter.check 看到 5 → 5 >= 5 → 429 + Retry-After: 300
    #    (因为 Redis ZSET 持久化, 新进程读到的就是 5 个 timestamp)
    print("\n--- 阶段 5: 重启后请求 (期望第 1 次就 429, 证明 Redis 持久化) ---")
    status, headers, body = post_login(xff)
    retry_after = headers.get("retry-after")
    policy = headers.get("x-ratelimit-policy")
    print(f"  status={status} retry-after={retry_after} policy={policy}")
    if status != 429:
        print(f"  FAIL: 重启后第 1 次未触发 429, 实际 {status} (Redis 持久化未生效!)")
        redis_cli("DEL", rkey)
        return False
    if retry_after != "300":
        print(f"  FAIL: 重启后 Retry-After 期望 '300', 实际 {retry_after!r}")
        redis_cli("DEL", rkey)
        return False
    print("  PASS: 重启后第 1 次即触发 429 + Retry-After: 300")

    # 6. 清理
    redis_cli("DEL", rkey)
    print("\n" + "=" * 60)
    print("v31.2.6 登录限流抗重启验证 PASS")
    print("=" * 60)
    return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
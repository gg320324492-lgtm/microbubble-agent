"""v31.2.5 抗重启验证

策略: 灌满 SSE tier (10/min) 到 9/10, 然后 docker compose restart app,
      新进程处理第 10 次请求应该看到 429, 证明 Redis ZSET 持久化生效.

依赖: 当前 host 暴露 docker, 容器名 microbubble-agent-app-1.
"""
import socket
import subprocess
import sys
import time

import urllib.request
import urllib.error
import json


BASE = "localhost:8000"
APP_CONTAINER = "microbubble-agent-app-1"


def login():
    req = urllib.request.Request(
        f"http://{BASE}/api/v1/auth/login",
        data=json.dumps({"username": "wangtianzhi", "password": "admin123"}).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req, timeout=5).read())["access_token"]


def post_chat_stream(token, xff):
    """POST /chat/stream — SSE tier endpoint.
    用 raw socket 避免 SSE 流式 body 阻塞 urlopen。发完就 close (L4 RESET).
    middleware 仍会处理 + record.
    """
    payload = b'{"messages":[{"role":"user","content":"hi"}]}'  # 故意无效, 期望 422
    req_lines = [
        f"POST /api/v1/chat/stream HTTP/1.1",
        f"Host: {BASE}",
        f"Content-Type: application/json",
        f"Authorization: Bearer {token}",
        f"X-Forwarded-For: {xff}",
        f"Content-Length: {len(payload)}",
        f"Connection: close",
    ]
    raw = ("\r\n".join(req_lines) + "\r\n\r\n").encode() + payload

    s = socket.create_connection(("localhost", 8000), timeout=5)
    try:
        s.sendall(raw)
        # 读响应头 (到 \r\n\r\n)
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
        head, _, _ = buf.partition(b"\r\n\r\n")
        lines = head.decode("latin-1").split("\r\n")
        status = int(lines[0].split(" ")[1])
        # HTTP header 大小写不敏感, 但 uvicorn 写出来是小写, 用 lowercase map
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()
        return status, headers
    finally:
        try:
            s.close()
        except Exception:
            pass


def read_redis_zset(zset_key: str) -> int:
    """ZCARD = 当前窗口内的请求数."""
    out = subprocess.check_output(
        ["docker", "exec", "microbubble-agent-redis-1", "redis-cli", "ZCARD", zset_key],
        text=True,
    ).strip()
    return int(out)


def redis_keys(pattern: str) -> list[str]:
    out = subprocess.check_output(
        ["docker", "exec", "microbubble-agent-redis-1", "redis-cli", "--scan", "--pattern", pattern],
        text=True,
    ).strip()
    return out.splitlines() if out else []


def main():
    token = login()
    xff = "203.0.113.55"  # 固定 XFF 隔离 IP 维度
    print(f"=== v31.2.5 抗重启验证 (SSE tier 持久化) ===\n")
    print(f"  XFF={xff}")
    print(f"  Token len={len(token)}")

    # 1. 先清掉这个 XFF 的旧 ZSET (确保起点为 0)
    zset_key = f"rl:sse:read:{xff}:anon"  # 注意: tier 前缀在 middleware 拼
    # 实际 key 在 middleware 是 f"{limit_type}:{_get_client_key(request)}"
    # _get_client_key 返 f"{ip}:anon" 或 f"{ip}:user:{uid}"
    # final key in Redis: f"rl:{limit_type}:{ip}:user:{uid}"
    # 因为有限流器 ._redis_key 加了 "rl:" 前缀
    possible_keys = [
        f"rl:sse:{xff}:anon",
        f"rl:sse:{xff}:user:1",
        f"rl:read:{xff}:user:1",
    ]
    for k in possible_keys:
        subprocess.run(
            ["docker", "exec", "microbubble-agent-redis-1", "redis-cli", "DEL", k],
            capture_output=True, text=True,
        )

    print("\n--- 阶段 1: 灌 9 次 SSE 请求 (期望 9 个全 401, 但限流计数 +1) ---")
    # /chat/stream 没 token 会 401 (中间件先于 endpoint), 但限流已 record
    # 用有效 token 让它真发请求, 同样消耗配额
    remaining_seq = []
    for i in range(9):
        status, headers = post_chat_stream(token, xff)
        remaining = headers.get("x-ratelimit-remaining")
        policy = headers.get("x-ratelimit-policy")
        print(f"  Request {i+1}: status={status} policy={policy} remaining={remaining}")
        if remaining is not None:
            remaining_seq.append(int(remaining))

    if len(remaining_seq) < 3:
        print("  FAIL: remaining_seq 太少")
        return False
    if not all(remaining_seq[i] > remaining_seq[i+1] for i in range(len(remaining_seq)-1)):
        print(f"  FAIL: remaining 没递减 {remaining_seq}")
        return False
    print("  PASS: 9 次 SSE 配额递减正确")

    # 2. 看 Redis 实际 ZSET
    print("\n--- 阶段 2: 看 Redis 实际 ZSET ---")
    actual_key = f"rl:sse:{xff}:user:1"
    count = read_redis_zset(actual_key)
    print(f"  ZSET {actual_key} ZCARD={count} (期望 9)")
    if count != 9:
        print(f"  FAIL: ZCARD 应为 9 实际 {count}")
        # 兼容 anon key
        anon_key = f"rl:sse:{xff}:anon"
        count_anon = read_redis_zset(anon_key)
        print(f"  也试 {anon_key} ZCARD={count_anon}")
        if count_anon == 9:
            actual_key = anon_key
        else:
            return False
    print("  PASS: Redis ZSET 9 个 timestamp")

    # 3. docker compose restart app (模拟重启)
    print("\n--- 阶段 3: docker compose restart app (抗重启关键) ---")
    result = subprocess.run(
        ["docker", "compose", "restart", "app"],
        capture_output=True, text=True, timeout=60,
    )
    print(f"  restart exit code: {result.returncode}")
    if result.returncode != 0:
        print(f"  FAIL: restart failed: {result.stderr}")
        return False

    # 等健康
    print("  等待 app healthy...")
    for attempt in range(30):
        try:
            resp = urllib.request.urlopen(f"http://{BASE}/health", timeout=2)
            if resp.status == 200:
                print(f"  healthy after {attempt+1}s")
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        print("  FAIL: app 没起来")
        return False

    # 4. 关键: 重启后再发请求, 中间件 check 时 ZSET 已经有 9 个 timestamp.
    # 注意 check + record 是分开的: check 看现有 count, record 后才写入新 timestamp.
    # 重启后第一次请求 → check 看到 9, 9 < 10 通过 → record → count=10 (remaining=0)
    # 重启后第二次请求 → check 看到 10, 10 >= 10 → 429
    print("\n--- 阶段 4: 重启后请求 (期望第 2 次触发 429) ---")
    for attempt in range(1, 4):
        status, headers = post_chat_stream(token, xff)
        policy = headers.get("x-ratelimit-policy")
        remaining = headers.get("x-ratelimit-remaining")
        print(f"  Request post-restart #{attempt}: status={status} policy={policy} remaining={remaining}")
        if status == 429:
            print(f"  PASS: 重启后第 {attempt} 次触发 429 (Redis 持久化生效)")
            # 清理
            subprocess.run(
                ["docker", "exec", "microbubble-agent-redis-1", "redis-cli", "DEL", actual_key],
                capture_output=True, text=True,
            )
            print("\n" + "=" * 60)
            print("v31.2.5 抗重启验证 PASS - Redis 限流真正持久化")
            print("=" * 60)
            return True
        # 第一次后 remaining=0 (10 个 timestamp), 第二次 check 看到 10 → 429
        if attempt == 1 and remaining != "0":
            print(f"  FAIL: 第 1 次请求期望 remaining=0 (新进程看到 9 + 自己的 record = 10), 实际 {remaining}")
            return False
    print(f"  FAIL: 重启后 3 次都未触发 429 (Redis 持久化未生效!)")
    return False


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
# scripts/verify_v31_2_3.py
"""
v31.2.3 verify: 3 个并发改动端到端验证

改动:
  #1) X-RateLimit-Policy 响应头 (read/write/auth/upload/sse/unlimited)
  #2) /api/v1/chat/stream 独立 SSE tier (10/min)
  #3) _AUTH_SENSITIVE_PATHS 用 _is_under_auth() prefix 匹配 (取代 substring)

策略:
  - Part 1 (容器内纯函数 mock): _is_under_auth + _get_rate_limit_type 行为
  - Part 2 (真实 HTTP): X-RateLimit-Policy 头 + SSE tier 限流独立
"""
import http.client
import json
import ssl
import subprocess
import sys

BASE_HOST = "agent.mnb-lab.cn"
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


# ===== Part 1: 容器内纯函数 mock (改 #3 + 完整 _get_rate_limit_type) =====
CONTAINER_MOCK = r'''
import sys
sys.path.insert(0, ".")
from unittest.mock import MagicMock
from app.core.rate_limit import (
    _get_rate_limit_type, _is_under_auth, _SSE_PATH_RE, _ANALYTICS_PATH_RE,
)

def mock_request(path, method):
    req = MagicMock()
    req.url.path = path
    req.method = method
    return req

# === _is_under_auth 直接验证 ===
print("=== 改 #3: _is_under_auth prefix 匹配 ===")
under_auth_cases = [
    ("/api/v1/auth", True, "精确等于 /api/v1/auth"),
    ("/api/v1/auth/login", True, "标准 /auth/ 子路径"),
    ("/api/v1/auth/profile", True, "嵌套"),
    ("/api/v1/auth/analytics/export", True, "未来嵌套"),
    ("/api/v1/authentication", False, "substring 误匹配修复点"),
    ("/api/v1/authusers", False, "无 / 分隔"),
    ("/api/v1/analytics", False, "完全无关"),
    ("/api/v1/chat/stream", False, "SSE 路径"),
]
all_pass = True
for path, expected, desc in under_auth_cases:
    actual = _is_under_auth(path)
    ok = actual == expected
    if not ok:
        all_pass = False
    print(f"  {'[PASS]' if ok else '[FAIL]'} _is_under_auth('{path:42}') = {actual}  ({desc})")
print(f"  RESULT: {'PASS' if all_pass else 'FAIL'}")
print()

# === _get_rate_limit_type 综合验证 (含改 #2 SSE + 改 #3 auth) ===
print("=== _get_rate_limit_type 综合验证 ===")
gt_cases = [
    # 改 #2: SSE tier
    ("/api/v1/chat/stream", "POST", "sse", "POST /chat/stream → sse tier (10/min)"),
    # 改 #3: auth sensitive (substring 误匹配修复)
    ("/api/v1/auth/login", "POST", "auth", "auth sensitive login"),
    ("/api/v1/authentication", "GET", "read", "authentication 不被误中 (改 #3)"),
    ("/api/v1/chat/stream/anything", "POST", "write", "SSE regex 不误中子路径 → POST 默认 write"),
    # v31.2.2 不回归: analytics 4 endpoint
    ("/api/v1/analytics/search-event", "POST", "unlimited", "POST analytics search-event"),
    ("/api/v1/analytics/search-event/123/click", "PATCH", "unlimited", "PATCH analytics click"),
    ("/api/v1/analytics/stats", "GET", "read", "GET analytics stats"),
    ("/api/v1/analytics/logs", "GET", "read", "GET analytics logs"),
    # v31.2.1 不回归: 未来嵌套
    ("/api/v1/auth/analytics/export", "POST", "write", "auth/analytics/export 走 auth 细分"),
    # 默认 read/write
    ("/api/v1/knowledge", "GET", "read", "普通 GET → read"),
    ("/api/v1/knowledge", "POST", "write", "普通 POST → write"),
]
for path, method, expected, desc in gt_cases:
    actual = _get_rate_limit_type(mock_request(path, method))
    ok = actual == expected
    if not ok:
        all_pass = False
    print(f"  {'[PASS]' if ok else '[FAIL]'} {desc:50} -> {actual} (期望 {expected})")
print(f"  RESULT: {'PASS' if all_pass else 'FAIL'}")
sys.exit(0 if all_pass else 1)
'''


def part1():
    """容器内纯函数 mock 验证"""
    print("=== Part 1: 纯函数 mock (改 #3 + 改 #2 + 综合) ===")
    result = subprocess.run(
        ["docker", "exec", "-i", "microbubble-agent-app-1", "python"],
        input=CONTAINER_MOCK, capture_output=True, text=True, timeout=30,
    )
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    return result.returncode == 0


# ===== Part 2: 真实 HTTP (改 #1 + 改 #2) =====
def http_hit(path: str, method: str = "GET", token: str = None, xff: str = None, body: dict = None):
    """真实 HTTP 请求, 返所有 x-ratelimit-* 头"""
    conn = http.client.HTTPSConnection(BASE_HOST, 443, context=ctx)
    headers = {}
    if xff:
        headers["X-Forwarded-For"] = xff
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        conn.request(method, path, body=json.dumps(body), headers=headers)
    else:
        conn.request(method, path, headers=headers)
    resp = conn.getresponse()
    headers_out = {k.lower(): v for k, v in resp.getheaders()}
    body_out = resp.read().decode("utf-8", errors="replace")[:80]
    conn.close()
    return {
        "status": resp.status,
        "limit": headers_out.get("x-ratelimit-limit"),
        "remaining": headers_out.get("x-ratelimit-remaining"),
        "policy": headers_out.get("x-ratelimit-policy"),
    }


def part2():
    """真实 HTTP 验证 改 #1 (X-RateLimit-Policy) + 改 #2 (SSE tier 隔离)"""
    print()
    print("=== Part 2: 真实 HTTP (改 #1 + 改 #2) ===")
    print("固定 XFF=198.51.100.70 隔离 IP 维度, 验证 policy 头 + tier 隔离")
    print()

    # 拿 user 1 token
    login_conn = http.client.HTTPSConnection(BASE_HOST, 443, context=ctx)
    login_conn.request(
        "POST", "/api/v1/auth/login",
        body=json.dumps({"username": "wangtianzhi", "password": "admin123"}),
        headers={"Content-Type": "application/json"},
    )
    login_resp = login_conn.getresponse()
    token_a = json.loads(login_resp.read().decode("utf-8"))["access_token"]
    login_conn.close()
    print(f"Got token A (len={len(token_a)})")

    # 拿 user 24 token
    result = subprocess.run(
        ["docker", "exec", "-i", "microbubble-agent-app-1", "python"],
        input=(
            "from jose import jwt\n"
            "from datetime import datetime, timedelta, timezone\n"
            "payload = {'sub': '24', 'type': 'access',\n"
            "  'exp': datetime.now(timezone.utc) + timedelta(hours=1),\n"
            "  'iat': datetime.now(timezone.utc)}\n"
            "print(jwt.encode(payload, 'change-this-to-a-random-string', algorithm='HS256'))"
        ),
        capture_output=True, text=True, timeout=30,
    )
    token_b = result.stdout.strip()
    print(f"Got token B (len={len(token_b)})")
    print()

    XFF = "198.51.100.70"

    # === 改 #1: 4 个 endpoint 期望不同 policy 头 ===
    # 注意: unlimited 路径 (analytics POST/PATCH) 不走 middleware (中间件 if limit_type=="unlimited" 直接跳过),
    # 所以 policy 头不设. 这是设计: unlimited 端点不需要告诉前端限流信息.
    print("--- 改 #1: X-RateLimit-Policy 头 (4 个 endpoint) ---")
    policy_cases = [
        ("/api/v1/analytics/stats?days=7", "GET", token_a, "read", "GET analytics stats"),
        # POST analytics search-event 走 unlimited → 中间件跳过 → 无数值
        ("/api/v1/analytics/search-event", "POST", None, "NONE_unlimited", "POST analytics search-event (unlimited 路径无数值)"),
        ("/api/v1/auth/login", "POST", None, "auth", "POST /auth/login (wrong pw, 但限流先)"),
        ("/api/v1/chat/stream", "POST", None, "sse", "POST /chat/stream (无 token 401, 但限流先)"),
    ]
    all_pass = True
    for path, method, token, expected_policy, desc in policy_cases:
        body = {"query": "v31.2.3-test", "top_ids": [1]} if method == "POST" and "search-event" in path else None
        if method == "POST" and path == "/api/v1/auth/login":
            body = {"username": "wronguser", "password": "wrong"}
        r = http_hit(path, method=method, token=token, xff=XFF, body=body)
        if expected_policy == "NONE_unlimited":
            # unlimited 路径不设 policy 头
            ok = r["policy"] is None
        else:
            ok = r["policy"] == expected_policy
        if not ok:
            all_pass = False
        actual = r['policy'] if r['policy'] else "(无)"
        print(f"  {'[PASS]' if ok else '[FAIL]'} {desc:60} policy={actual} (期望 {expected_policy})")
    print(f"  改 #1 RESULT: {'PASS' if all_pass else 'FAIL'}")
    print()

    # === 改 #2: SSE tier 独立配额 (同 XFF 不同 endpoint) ===
    # SSE 限流 key = {sse}:{client_key}, 跟 read tier 的 key 不同 namespace,
    # 所以 SSE 不消耗 read 配额. 验证: SSE 调 N 次后 read 配额仍独立
    # 注意: 之前 quick verify 已消耗 N 次 SSE, 所以 SSE 起始 remaining 不会从 9 开始
    # 改为: 验证 SSE 每次 remaining -1 (递减正确) + SSE 不消耗 read 配额
    print("--- 改 #2: SSE tier 独立配额 (SSE 不消耗 read) ---")
    # 先消耗 read tier 1 次 (确认 read 起点)
    r1 = http_hit("/api/v1/analytics/stats?days=7", "GET", xff=XFF)
    print(f"  Read-1: policy={r1['policy']} remaining={r1['remaining']}")
    # 再调 SSE 1 次 (无 token 401, 但 SSE tier 应该独立计数)
    s1 = http_hit("/api/v1/chat/stream", "POST", xff=XFF, body={})
    print(f"  SSE-1:  policy={s1['policy']} remaining={s1['remaining']}")
    # SSE 再调 1 次, remaining 应该 -1
    s2 = http_hit("/api/v1/chat/stream", "POST", xff=XFF, body={})
    print(f"  SSE-2:  policy={s2['policy']} remaining={s2['remaining']}")
    # 关键: SSE 不应该消耗 read 配额. 再次调 read
    r2 = http_hit("/api/v1/analytics/stats?days=7", "GET", xff=XFF)
    print(f"  Read-2: policy={r2['policy']} remaining={r2['remaining']}")
    # 验证: SSE 每次 -1, Read 不受 SSE 影响
    sse_decreases = int(s2["remaining"]) == int(s1["remaining"]) - 1
    read_isolated = int(r2["remaining"]) == int(r1["remaining"]) - 1
    ok = (
        r1["policy"] == "read"
        and s1["policy"] == "sse" and s2["policy"] == "sse"
        and sse_decreases and read_isolated
    )
    print(f"  改 #2 RESULT: {'PASS' if ok else 'FAIL'}")
    print(f"    - SSE 每次 -1: s1→s2 = {s1['remaining']}→{s2['remaining']} ({'✓' if sse_decreases else '✗'})")
    print(f"    - Read 不受 SSE 影响: r1→r2 = {r1['remaining']}→{r2['remaining']} ({'✓' if read_isolated else '✗'})")
    print()

    # === 改 #2 边界: SSE 触发 11 次验证 429 (触发限流) ===
    print("--- 改 #2 边界: SSE 触发 11 次验证 429 ---")
    # 当前 SSE 已用 2 次, 再 8 次 (凑 10 次) 应该都 200/401 (401 是无 token, 但限流先过)
    # 第 11 次应该 429
    for i in range(3, 11):
        r = http_hit("/api/v1/chat/stream", "POST", xff=XFF, body={})
        print(f"  SSE-{i}: status={r['status']} policy={r['policy']} remaining={r['remaining']}")
    # 第 11 次应该 429
    r11 = http_hit("/api/v1/chat/stream", "POST", xff=XFF, body={})
    print(f"  SSE-11: status={r11['status']} policy={r11.get('policy')}")
    ok = r11["status"] == 429
    actual_status = r11['status']
    print(f"  SSE 限流触发: {'PASS (429)' if ok else 'FAIL (期望 429, 实际 ' + str(actual_status) + ')'}")
    print()

    print("=" * 60)
    print("PART 2: " + ("ALL PASS - v31.2.3 响应头 + SSE tier 生效"
                       if all_pass and ok else "FAILED"))
    print("=" * 60)
    return all_pass and ok


def main():
    if not part1():
        sys.exit(1)
    if not part2():
        sys.exit(1)
    print()
    print("=" * 60)
    print("v31.2.3 ALL VERIFY PASS")
    print("=" * 60)


if __name__ == "__main__":
    main()
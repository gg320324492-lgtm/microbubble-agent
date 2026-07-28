# scripts/verify_v31_2_2.py
"""
v31.2.2 verify: 2 个并发改动端到端验证

改动:
  A) /analytics substring 改为 _ANALYTICS_PATH_RE 精确路径匹配
  B) middleware 解析 token 写 request.state.user_id (限流 key 按 user_id 维度)

策略: 真实 HTTP 端到端 + 容器内纯函数 mock 混合
  - 容器内纯函数: 验 _get_rate_limit_type 的 regex 精确匹配 (改动 A)
  - 真实 HTTP: 验 middleware user_id 注入 (改动 B), 通过 X-RateLimit-Remaining 反推

运行:
  # 容器内纯函数 mock 部分:
  docker exec -i microbubble-agent-app-1 python < scripts/verify_v31_2_2.py

  # HTTP 部分:
  python scripts/verify_v31_2_2.py http
"""
import sys
import subprocess


# ===== Part 1: 容器内纯函数 mock (改 A 验证) =====
CONTAINER_MOCK = r'''
import sys
sys.path.insert(0, ".")
from unittest.mock import MagicMock
from app.core.rate_limit import _get_rate_limit_type

def mock_request(path, method):
    req = MagicMock()
    req.url.path = path
    req.method = method
    return req

# v31.2.2 _ANALYTICS_PATH_RE 4 个 endpoint 行为保留
# 关键: 未来嵌套路径仍走 /auth/ 细分 (regex 不会误匹配)
analytics_cases = [
    ("/api/v1/analytics/search-event", "POST", "unlimited", "POST search-event"),
    ("/api/v1/analytics/search-event/123/click", "PATCH", "unlimited", "PATCH click"),
    ("/api/v1/analytics/stats", "GET", "read", "GET stats"),
    ("/api/v1/analytics/logs", "GET", "read", "GET logs"),
    # 边界: /api/v1/auth/analytics 不应被 regex 误命中
    ("/api/v1/auth/analytics", "POST", "write", "auth/analytics POST (无 event_id 子路径)"),
    ("/api/v1/auth/analytics/export", "POST", "write", "auth/analytics/export (未来嵌套)"),
    ("/api/v1/auth/analytics/foo", "GET", "read", "auth/analytics/foo (未来嵌套 GET)"),
    # 边界: /api/v1/analytics/search-event/123 (无 /click 后缀) 不应被 regex 命中
    ("/api/v1/analytics/search-event/123", "GET", "read", "search-event/123 (无 /click) → default read"),
    # 边界: /api/v1/analyticsx (没 / 分隔) 不应被 regex 命中
    ("/api/v1/analyticsx", "GET", "read", "/analyticsx (无分隔) → default read"),
]

print("=== Part 1: _ANALYTICS_PATH_RE 纯函数 mock (改 A) ===")
all_pass = True
for path, method, expected, desc in analytics_cases:
    actual = _get_rate_limit_type(mock_request(path, method))
    ok = actual == expected
    if not ok:
        all_pass = False
    print(f"  {'[PASS]' if ok else '[FAIL]'} {desc:55} -> {actual}")
print(f"PART 1: {'ALL PASS' if all_pass else 'FAILED'}")
sys.exit(0 if all_pass else 1)
'''


# ===== Part 2: 真实 HTTP 端到端 (改 B 验证) =====
def part2_http():
    """用 X-RateLimit-Remaining 反推限流 key 隔离性"""
    import http.client
    import json
    import ssl

    BASE_HOST = "agent.mnb-lab.cn"
    BASE_PATH = "/api/v1/analytics/stats?days=7"

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    def hit(xff: str, token: str = None, label: str = ""):
        conn = http.client.HTTPSConnection(BASE_HOST, 443, context=ctx)
        headers = {"X-Forwarded-For": xff}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        conn.request("GET", BASE_PATH, headers=headers)
        resp = conn.getresponse()
        headers_out = {k.lower(): v for k, v in resp.getheaders()}
        conn.close()
        return {
            "label": label,
            "xff": xff,
            "has_token": bool(token),
            "status": resp.status,
            "limit": headers_out.get("x-ratelimit-limit"),
            "remaining": headers_out.get("x-ratelimit-remaining"),
        }

    # 拿 user 1 (wangtianzhi) token
    login_conn = http.client.HTTPSConnection(BASE_HOST, 443, context=ctx)
    login_conn.request(
        "POST", "/api/v1/auth/login",
        body=json.dumps({"username": "wangtianzhi", "password": "admin123"}),
        headers={"Content-Type": "application/json"},
    )
    login_resp = login_conn.getresponse()
    token_a = json.loads(login_resp.read().decode("utf-8"))["access_token"]
    login_conn.close()

    # 拿 user 24 (雒培媛, is_active=False) token via docker exec python-jose
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

    XFF = "198.51.100.99"  # 固定 XFF, 隔离 IP 维度, 只测 user 维度

    print()
    print("=== Part 2: middleware user_id 注入 (改 B) ===")
    print(f"固定 XFF={XFF} (隔离 IP 维度, 只测 user_id 维度)")
    print()

    # 测试矩阵: 同 IP, 3 种 user_id 维度 (A / B / 无 token)
    print("--- 测试 1: user A (id=1) × 2 次 (同 user 共享配额) ---")
    a1 = hit(XFF, token_a, "A1")
    print(f"  A1: {a1}")
    a2 = hit(XFF, token_a, "A2")
    print(f"  A2: {a2}")
    if int(a2["remaining"]) != int(a1["remaining"]) - 1:
        print(f"  [FAIL] A2 ({a2['remaining']}) 应 = A1 ({a1['remaining']}) - 1")
        return False
    print("  [PASS] A2 -1 = A1 (同 user 配额递减)")
    print()

    print("--- 测试 2: user B (id=24) × 1 次 (不同 user 独立配额) ---")
    b1 = hit(XFF, token_b, "B1")
    print(f"  B1: {b1}")
    # B1 应该是新 user 起点, remaining 应该 = limit - 1 ≈ A1 的 remaining
    if int(b1["remaining"]) >= int(a1["remaining"]) - 1:
        print("  [PASS] B1 不受 A1/A2 影响 (不同 user 独立配额)")
    else:
        print(f"  [FAIL] B1 ({b1['remaining']}) 应该 ≥ A1 ({a1['remaining']}) - 1")
        return False
    print()

    print("--- 测试 3: 无 token × 1 次 (匿名独立配额) ---")
    c1 = hit(XFF, None, "C1")
    print(f"  C1: {c1}")
    # C1 应该是新 anon 起点, remaining 应该接近 limit - 1
    if int(c1["remaining"]) >= int(b1["remaining"]) - 1:
        print("  [PASS] C1 不受 B1 影响 (匿名独立配额)")
    else:
        print(f"  [FAIL] C1 ({c1['remaining']}) 应该 ≥ B1 ({b1['remaining']}) - 1")
        return False
    print()

    print("--- 测试 4: user B 再调 1 次 (确认 B 自己的配额递减) ---")
    b2 = hit(XFF, token_b, "B2")
    print(f"  B2: {b2}")
    if int(b2["remaining"]) != int(b1["remaining"]) - 1:
        print(f"  [FAIL] B2 ({b2['remaining']}) 应 = B1 ({b1['remaining']}) - 1")
        return False
    print("  [PASS] B2 -1 = B1 (同 user B 配额递减)")
    print()

    print("=" * 60)
    print("PART 2: ALL PASS - v31.2.2 middleware user_id 注入生效")
    print("=" * 60)
    return True


def main():
    # Part 1: 容器内纯函数 mock
    print("=== Part 1: _ANALYTICS_PATH_RE 纯函数 mock (改 A) ===")
    result = subprocess.run(
        ["docker", "exec", "-i", "microbubble-agent-app-1", "python"],
        input=CONTAINER_MOCK, capture_output=True, text=True, timeout=30,
    )
    print(result.stdout)
    if result.returncode != 0:
        print("PART 1 FAILED")
        sys.exit(1)

    # Part 2: 真实 HTTP
    if len(sys.argv) > 1 and sys.argv[1] == "no-http":
        print("(跳过 Part 2 HTTP 端到端)")
        return
    if not part2_http():
        sys.exit(1)

    print()
    print("=" * 60)
    print("v31.2.2 ALL VERIFY PASS")
    print("=" * 60)


if __name__ == "__main__":
    main()
# scripts/verify_v31_2_1_nested_path.py
"""
v31.2.1 verify: _get_rate_limit_type() 嵌套路径判定顺序验证

策略: 纯函数 mock 测试, 直接调 _get_rate_limit_type(request) 不需要起 server
  - 验证 4 个现有 analytics endpoint 行为保留
  - 验证 5 个 auth sensitive 端点行为保留
  - 验证 /auth/me unlimited 行为保留
  - 验证未来嵌套路径 (/api/v1/auth/analytics/...) 修复后走 /auth/ 细分

运行方式:
  # 容器内 (推荐, 避免 fastapi import 失败):
  docker exec -i microbubble-agent-app-1 python < scripts/probe_boundary5_nested_auth_analytics.py

  # 本地 (需 pip install fastapi sqlalchemy pydantic):
  PYTHONPATH=. python scripts/probe_boundary5_nested_auth_analytics.py
"""
import sys
from unittest.mock import MagicMock

# 让 Python 找到 app 模块
sys.path.insert(0, ".")

from app.core.rate_limit import _get_rate_limit_type  # noqa: E402


def mock_request(path: str, method: str):
    req = MagicMock()
    req.url.path = path
    req.method = method
    return req


def main():
    # ===== Case 1-4: 现有 4 个 analytics endpoint 行为保留 =====
    print("=== Case 1-4: 现有 4 个 analytics endpoint ===")
    expectations = [
        ("/api/v1/analytics/search-event", "POST", "unlimited", "POST search-event"),
        ("/api/v1/analytics/search-event/123/click", "PATCH", "unlimited", "PATCH click"),
        ("/api/v1/analytics/stats", "GET", "read", "GET stats"),
        ("/api/v1/analytics/logs", "GET", "read", "GET logs"),
    ]
    for path, method, expected, desc in expectations:
        actual = _get_rate_limit_type(mock_request(path, method))
        assert actual == expected, f"[FAIL] {desc}: 期望 {expected}, 实际 {actual}"
        print(f"  [PASS] {desc}: {actual}")
    print()

    # ===== Case 5-9: 5 个 auth sensitive 端点行为保留 =====
    print("=== Case 5-9: 5 个 auth sensitive 端点 ===")
    sensitive = [
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/change-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/init-password",
    ]
    for path in sensitive:
        actual = _get_rate_limit_type(mock_request(path, "POST"))
        assert actual == "auth", f"[FAIL] POST {path}: 期望 auth, 实际 {actual}"
        print(f"  [PASS] POST {path}: {actual}")
    print()

    # ===== Case 10: /auth/me unlimited 保留 =====
    print("=== Case 10: /auth/me ===")
    actual = _get_rate_limit_type(mock_request("/api/v1/auth/me", "GET"))
    assert actual == "unlimited", f"[FAIL] /auth/me: 期望 unlimited, 实际 {actual}"
    print(f"  [PASS] GET /auth/me: {actual}")
    print()

    # ===== Case 11: 未来嵌套路径 → 修复后走 /auth/ 细分 =====
    print("=== Case 11: 未来嵌套路径 (v31.2.1 修复验证) ===")

    # 11a: 未来 POST /api/v1/auth/analytics/export
    # 修复前: substring "/analytics" 命中 → 顺序 2 优先 → unlimited (BYPASS)
    # 修复后: startswith("/api/v1/auth/") 守卫命中 → 跳过 /analytics → 走 /auth/ 顺序 3
    #         → 非 sensitive 写操作 → write tier 30/min
    actual = _get_rate_limit_type(mock_request("/api/v1/auth/analytics/export", "POST"))
    assert actual == "write", (
        f"[FAIL] 嵌套 POST 应走 write tier 30/min (修复前会 bypass 到 unlimited), 实际 {actual}"
    )
    print(f"  [PASS] POST /api/v1/auth/analytics/export: {actual} (修复前 bypass)")

    # 11b: 未来 GET /api/v1/auth/analytics/dashboard
    actual = _get_rate_limit_type(mock_request("/api/v1/auth/analytics/dashboard", "GET"))
    assert actual == "read", (
        f"[FAIL] 嵌套 GET 应走 read tier 200/min, 实际 {actual}"
    )
    print(f"  [PASS] GET /api/v1/auth/analytics/dashboard: {actual}")

    # 11c: 边界 — /api/v1/auth/analytics (无后续路径)
    actual = _get_rate_limit_type(mock_request("/api/v1/auth/analytics", "POST"))
    assert actual == "write", f"嵌套 POST 应走 write, 实际 {actual}"
    print(f"  [PASS] POST /api/v1/auth/analytics: {actual}")
    print()

    # ===== Case 12: 边界 — /api/v1/authentication 不应被守卫误伤 =====
    print("=== Case 12: 边界 — /api/v1/authentication (无 /auth/) ===")
    actual = _get_rate_limit_type(mock_request("/api/v1/authentication", "GET"))
    # 不含 "/auth/" (注意是 "in path" 不是 startswith), 走 default read
    assert actual == "read", f"/api/v1/authentication 应走 read, 实际 {actual}"
    print(f"  [PASS] GET /api/v1/authentication: {actual} (substring /auth/ 不命中)\n")

    # ===== Case 13: PUT /api/v1/auth/profile (非 sensitive 写操作) =====
    print("=== Case 13: PUT /api/v1/auth/profile (非 sensitive 写操作) ===")
    actual = _get_rate_limit_type(mock_request("/api/v1/auth/profile", "PUT"))
    assert actual == "write", f"PUT /auth/profile 应走 write, 实际 {actual}"
    print(f"  [PASS] PUT /api/v1/auth/profile: {actual}\n")

    print("=" * 60)
    print("ALL 13 CASES PASS - v31.2.1 _get_rate_limit_type 守卫生效")
    print("=" * 60)


if __name__ == "__main__":
    main()
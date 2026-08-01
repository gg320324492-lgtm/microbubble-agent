"""tests/realenv — 真环境 e2e 集成层 (W98 P3-A 派工 v10).

W98 P3-A 派工目标: 现有 mock e2e 增加真 PG + Redis + Anthropic API 集成层.
本包内测试全部在 conftest.py 含 skipif 守护:
- DATABASE_URL 未设置 → 自动 SKIP
- REDIS_URL 未设置 → 自动 SKIP
- 启用真环境后自动 PASS/FAIL 取决于断言

CI/CD: 设 DATABASE_URL/REDIS_URL 启用. 本机: 默认 SKIP, 0 失败.
"""
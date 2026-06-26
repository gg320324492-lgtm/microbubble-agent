---
name: rate-limit-redis-2026-06-26
description: v31.2.5 启用 AsyncRedisRateLimiter (Redis ZSET 持久化) 抗 docker restart + middleware await 化 + raw socket SSE 响应头解析
metadata:
  type: reference
---

# v31.2.5 Rate-Limit Redis 持久化收官（2026-06-26）

## 触发
v31.2.4 已实现 AsyncRedisRateLimiter 类（Redis ZSET 滑动窗口），但 `_rate_limiters` 字典仍是 `RateLimiter`（in-memory dict），新类未接入 middleware。`docker compose restart app` 会清零所有计数。

## 关键改动（[app/core/rate_limit.py:118-126](app/core/rate_limit.py#L118-L126)）
- 5 个 tier 实例（auth/write/read/upload/sse）全换 `AsyncRedisRateLimiter`
- `rate_limit_middleware` 3 处同步调用 await 化
- `remaining` 改用 `await limiter.remaining(key)`（Redis O(1) ZCARD）取代内存 `len(_attempts[key])`

## 4 条铁律
1. **check + record 必须分开**（不能合并）。第 N+1 次请求才能触发 429（N 是 max_attempts）。这跟 GC 标记-清除两阶段是同一个道理
2. **uvicorn 响应头是小写**，raw socket 自定义 parse 必须 `headers[k.strip().lower()]`
3. **SSE 流式响应必须 raw socket 主动断**，不能用 `urllib.request.urlopen`（会阻塞等 body）
4. **in-memory 限流只适合单进程不重启**，生产必须持久化到 Redis/PostgreSQL

## 验证脚本
[scripts/verify_v31_2_5_restart.py](scripts/verify_v31_2_5_restart.py) — 灌 9 次 SSE → restart app → 第 2 次请求触发 429

## 完整 v31.2.x 链路
v31.2 → 2.1 → 2.2 → 2.3 → 2.4 → 2.5 全部 PASS，限流基建**可观测 + 可推理 + 抗误匹配 + 抗重启**。

参考 [CLAUDE.md 2026-06-26 v31.2.5 section](#2026-06-26-v3125-rate-limit-收官redis-zset-持久化) 完整沉淀。
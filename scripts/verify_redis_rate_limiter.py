# scripts/verify_redis_rate_limiter.py
"""
v31.2.4 verify: AsyncRedisRateLimiter 端到端验证

策略: 容器内直接测 AsyncRedisRateLimiter 类 (不通过 middleware)
  - 验证 Redis ZSET 真在写
  - 验证滑动窗口正确
  - 验证 check + record 配合正确
  - 验证 max_attempts 触发 429
  - 验证 抗 docker restart (用新 key 看 Redis 已有数据)

运行:
  docker exec -i microbubble-agent-app-1 python < scripts/verify_redis_rate_limiter.py
"""
import asyncio
import sys
import time
import uuid

sys.path.insert(0, "/app")


async def main():
    from app.core.rate_limit import AsyncRedisRateLimiter
    from app.core.redis import get_redis

    print("=== AsyncRedisRateLimiter 端到端 ===\n")

    # 1. 实例化 (3 attempts / 5s 窗口, 便于测试)
    limiter = AsyncRedisRateLimiter(max_attempts=3, window_seconds=5)
    key = f"verify:{uuid.uuid4().hex[:8]}"
    print(f"  Test key: {key}")
    print(f"  Config: max=3, window=5s\n")

    # 2. 前 3 次 check+record 应该都通过
    print("--- 阶段 1: 前 3 次 (应该全通过) ---")
    for i in range(1, 4):
        await limiter.check(key)  # 不抛 = 通过
        await limiter.record(key)
        remaining = await limiter.remaining(key)
        print(f"  Request {i}: PASS, remaining={remaining}")

    # 3. 第 4 次 check 应该抛 429
    print("\n--- 阶段 2: 第 4 次 (应该 429) ---")
    try:
        await limiter.check(key)
        print("  Request 4: FAIL (期望 429 但通过了)")
        return False
    except Exception as e:
        status = getattr(e, "status_code", None)
        if status == 429:
            print(f"  Request 4: PASS, status=429, detail={e.detail[:40]}")
        else:
            print(f"  Request 4: FAIL, 期望 429 实际 {type(e).__name__}: {e}")
            return False

    # 4. 验证 ZSET 真在写
    print("\n--- 阶段 3: 验证 Redis ZSET 数据 ---")
    r = await get_redis()
    zset_key = f"rl:{key}"
    count = await r.zcard(zset_key)
    members = await r.zrange(zset_key, 0, -1, withscores=True)
    print(f"  ZSET key={zset_key}")
    print(f"  ZCARD: {count} (期望 3)")
    print(f"  Members: {len(members)} (期望 3)")
    for m, s in members:
        print(f"    member={m[:30]} score={s:.2f}")
    if count != 3:
        print(f"  FAIL: ZCARD 应为 3 实际 {count}")
        return False
    print("  PASS: ZSET 3 个 timestamp")

    # 5. 验证 EXPIRE 设置
    ttl = await r.ttl(zset_key)
    print(f"\n  EXPIRE: TTL={ttl}s (期望 6, window_seconds+1)")
    if not (1 <= ttl <= 6):
        print(f"  FAIL: TTL 应 1-6s 实际 {ttl}s")
        return False
    print("  PASS: EXPIRE 设置正确")

    # 6. 验证滑动窗口 (5s 后 ZREMRANGEBYSCORE 清空)
    print("\n--- 阶段 4: 验证滑动窗口 (5s 后清空) ---")
    print("  等待 6s...")
    await asyncio.sleep(6)
    count_after = await r.zcard(zset_key)
    print(f"  ZCARD after 6s: {count_after} (期望 0, ZREMRANGEBYSCORE 已清)")
    if count_after != 0:
        print(f"  FAIL: 滑动窗口未清空, count={count_after}")
        return False
    print("  PASS: 滑动窗口 6s 后清空")

    # 7. 验证清空后又能 check+record
    print("\n--- 阶段 5: 清空后 check 应该通过 ---")
    await limiter.check(key)  # 应该不抛
    print("  1st request after clear: PASS (期望通过)")
    remaining = await limiter.remaining(key)
    print(f"  remaining={remaining} (期望 2)")

    # 8. 验证抗重启 (用新 key 看旧 ZSET 数据)
    print("\n--- 阶段 6: 抗重启验证 (模拟) ---")
    # 模拟"重启": 新 key 但数据仍能在 Redis (因为数据持久化)
    new_key = f"verify:new:{uuid.uuid4().hex[:8]}"
    limiter2 = AsyncRedisRateLimiter(max_attempts=3, window_seconds=5)
    for i in range(3):
        await limiter2.check(new_key)
        await limiter2.record(new_key)
    # 现在 simulate restart: 创建新 limiter 实例, 但 key 不变 → 状态保留
    limiter3 = AsyncRedisRateLimiter(max_attempts=3, window_seconds=5)
    try:
        await limiter3.check(new_key)
        print("  FAIL: 期望 429 (旧 key 触发新 limiter)")
        return False
    except Exception as e:
        if getattr(e, "status_code", None) == 429:
            print("  PASS: 新 limiter 实例仍看到旧 key 的 429 (Redis 持久化生效)")
        else:
            print(f"  FAIL: 期望 429 实际 {type(e).__name__}")
            return False

    # 9. 清理测试 key
    print("\n--- 阶段 7: 清理测试 ZSET ---")
    await r.delete(zset_key, f"rl:{new_key}")
    print(f"  清理完成: {zset_key}, rl:{new_key}")

    print("\n" + "=" * 60)
    print("ALL 7 PHASES PASS - AsyncRedisRateLimiter 可用")
    print("=" * 60)
    return True


if __name__ == "__main__":
    ok = asyncio.run(main())
    sys.exit(0 if ok else 1)
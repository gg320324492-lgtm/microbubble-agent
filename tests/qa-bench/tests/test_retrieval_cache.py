"""qa-bench retrieval_cache 单测 — v3.1 D3

8 test cases (per plan):
1. LRU eviction (max_size 限制)
2. TTL expiration
3. Thread-safe concurrent access
4. stats() 计数正确
5. clear() 后 hit rate 归零
6. key 碰撞 (不同 query 不同 key)
7. persistence (save/load round-trip)
8. empty cache get 返回 None

设计原则 (2026-07-22 D3 沉淀):
- 每个 test 必须独立 (clear between tests)
- TTL test 用 monkey-patched time 而非 sleep (sub-second 验证)
- thread-safe test 用 threading + barrier 确保并发
- persistence test 用 tmp_path 隔离文件
"""
import json
import sys
import threading
import time
from pathlib import Path

# Windows GBK console 兼容
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 允许 import tests/qa-bench/retrieval_cache.py (../retrieval_cache.py)
_qa_bench_dir = Path(__file__).parent.parent
sys.path.insert(0, str(_qa_bench_dir))
sys.path.insert(0, str(_qa_bench_dir / "tests"))

from retrieval_cache import (  # noqa: E402
    RetrievalCache,
    get_default_cache,
    reset_default_cache,
)


# === Case 1: LRU eviction (max_size 限制) ===
def test_lru_eviction():
    """超 max_size 触发 LRU 驱逐最旧 entry."""
    cache = RetrievalCache(ttl=3600, max_size=3)
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    cache.set("k3", "v3")
    # 满了 — 再 set 应驱逐 k1 (最旧)
    cache.set("k4", "v4")
    assert cache.get("k1") is None, "k1 应被驱逐"
    assert cache.get("k2") == "v2"
    assert cache.get("k3") == "v3"
    assert cache.get("k4") == "v4"
    stats = cache.stats()
    assert stats["evictions"] == 1, f"应记 1 次 eviction: {stats}"
    assert stats["size"] == 3
    print("  ✅ Case 1: LRU eviction 触发 (max_size=3, set 4 key 驱逐最旧)")


# === Case 2: TTL expiration ===
def test_ttl_expiration():
    """过期 entry 自动失效."""
    # 用 1s TTL + 短暂 sleep 验证
    cache = RetrievalCache(ttl=1, max_size=10)
    cache.set("k1", "v1")
    assert cache.get("k1") == "v1"
    time.sleep(1.2)
    assert cache.get("k1") is None, "1.2s 后应过期"
    stats = cache.stats()
    assert stats["expirations"] == 1, f"应记 1 次 expiration: {stats}"
    print("  ✅ Case 2: TTL expiration 触发 (1s TTL + 1.2s sleep)")


# === Case 3: Thread-safe concurrent access ===
def test_thread_safety():
    """多线程并发 set/get 不应丢失或损坏."""
    cache = RetrievalCache(ttl=3600, max_size=1000)
    errors = []

    def worker(start: int):
        try:
            for i in range(start, start + 50):
                cache.set(f"key_{i}", f"val_{i}")
                _ = cache.get(f"key_{i}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(t * 100,)) for t in range(5)]
    barrier = threading.Barrier(len(threads))

    def worker_with_barrier(start: int):
        try:
            barrier.wait()  # 确保 5 线程同时起跑
            for i in range(start, start + 50):
                cache.set(f"key_{i}", f"val_{i}")
                _ = cache.get(f"key_{i}")
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=worker_with_barrier, args=(t * 100,))
        for t in range(5)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"线程异常: {errors}"
    stats = cache.stats()
    # 至少 set 250 次 (5 线程 × 50)
    assert stats["sets"] >= 250, f"应记 ≥250 sets: {stats}"
    # size 不应超 max_size
    assert stats["size"] <= stats["max_size"], f"size 超 max_size: {stats}"
    print(f"  ✅ Case 3: Thread-safe (5 线程 × 50 ops, {stats['sets']} sets, 0 error)")


# === Case 4: stats() 计数正确 ===
def test_stats_counts():
    """hits / misses / sets 计数准确."""
    cache = RetrievalCache(ttl=3600, max_size=10)
    cache.set("k1", "v1")
    cache.set("k2", "v2")
    cache.get("k1")  # hit
    cache.get("k1")  # hit
    cache.get("missing")  # miss
    cache.get("missing2")  # miss
    stats = cache.stats()
    assert stats["hits"] == 2, f"hits 应为 2: {stats}"
    assert stats["misses"] == 2, f"misses 应为 2: {stats}"
    assert stats["sets"] == 2, f"sets 应为 2: {stats}"
    assert stats["hit_rate_pct"] == 50.0, f"hit_rate 应为 50%: {stats}"
    assert stats["size"] == 2
    print("  ✅ Case 4: stats() 计数正确 (2 hits + 2 misses + 2 sets = 50% hit rate)")


# === Case 5: clear() 后 hit rate 归零 ===
def test_clear_resets():
    """clear() 清空 data + stats."""
    cache = RetrievalCache(ttl=3600, max_size=10)
    cache.set("k1", "v1")
    cache.get("k1")  # hit
    cache.get("missing")  # miss
    assert cache.stats()["hits"] == 1
    cache.clear()
    stats = cache.stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 0
    assert stats["sets"] == 0
    assert stats["size"] == 0
    assert stats["hit_rate_pct"] == 0.0
    assert cache.get("k1") is None, "clear 后应 miss"
    print("  ✅ Case 5: clear() 重置 data + stats, hit rate 归零")


# === Case 6: key 碰撞 (不同 query 不同 key) ===
def test_key_uniqueness():
    """不同 query / filters / model / mode 必产生不同 key."""
    base = RetrievalCache.make_key("今天王天志忙什么?")
    # 不同 query
    k2 = RetrievalCache.make_key("杜同贺做什么?")
    assert base != k2, "不同 query 应不同 key"
    # 同 query, 不同 thinking_mode
    k3 = RetrievalCache.make_key("今天王天志忙什么?", thinking_mode="fast")
    assert base != k3, "不同 mode 应不同 key"
    # 同 query, 不同 filters
    k4 = RetrievalCache.make_key(
        "今天王天志忙什么?", filters={"category": "task"}
    )
    assert base != k4, "不同 filters 应不同 key"
    # 同 query, 不同 model
    k5 = RetrievalCache.make_key("今天王天志忙什么?", model_name="haiku")
    assert base != k5, "不同 model 应不同 key"
    # 同 query + 同 mode + 同 model + 同 filters → 应一致
    k6 = RetrievalCache.make_key("今天王天志忙什么?", thinking_mode="balanced")
    assert base == k6, "同参数应一致 (deterministic)"
    # 空白不影响 (strip)
    k7 = RetrievalCache.make_key("  今天王天志忙什么?  ")
    assert base == k7, "strip 后应一致"
    print("  ✅ Case 6: key 唯一性 (4 维度差异 + deterministic + strip)")


# === Case 7: persistence (save/load round-trip) ===
def test_persistence_round_trip(tmp_path=None):
    """save → clear → load → 数据回来."""
    import tempfile
    tmp_dir = Path(tempfile.mkdtemp())
    cache_path = str(tmp_dir / "test_cache.json")

    # write
    cache = RetrievalCache(ttl=3600, max_size=10, persistence_path=cache_path)
    cache.set("k1", {"events": ["a", "b"], "score": 9})
    cache.set("k2", ["text_response"])
    assert cache.save()
    assert Path(cache_path).exists()

    # clear + reload
    cache.clear()
    assert cache.get("k1") is None

    new_cache = RetrievalCache(
        ttl=3600, max_size=10, persistence_path=cache_path
    )
    assert new_cache.load()
    v1 = new_cache.get("k1")
    assert v1 is not None and v1["score"] == 9, f"k1 加载值: {v1}"
    v2 = new_cache.get("k2")
    assert v2 == ["text_response"], f"k2 加载值: {v2}"

    # 验证文件内容合法 JSON
    with open(cache_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["version"] == 1
    assert len(data["entries"]) == 2
    print(f"  ✅ Case 7: save/load round-trip ({cache_path}, 2 entries 完整)")


# === Case 8: empty cache get 返回 None ===
def test_empty_cache():
    """全新 cache get 必返 None (不抛异常)."""
    cache = RetrievalCache(ttl=3600, max_size=10)
    assert cache.get("nonexistent") is None
    assert cache.get("anything") is None
    # get miss 计入 misses (按 plan 设计)
    stats = cache.stats()
    assert stats["hits"] == 0
    assert stats["misses"] == 2, f"2 次 miss get 应记 2 misses: {stats}"
    assert stats["size"] == 0
    assert stats["hit_rate_pct"] == 0.0
    print("  ✅ Case 8: empty cache get 返 None, hits=0, misses=2 (按设计计入)")


# === Bonus: get_default_cache + reset (lazy init singleton) ===
def test_default_cache_singleton():
    """get_default_cache 返同一 instance (singleton)."""
    reset_default_cache()
    import os as _os
    _os.environ["RETRIEVAL_CACHE_TTL"] = "1800"
    _os.environ["RETRIEVAL_CACHE_MAX_SIZE"] = "50"
    c1 = get_default_cache()
    c2 = get_default_cache()
    assert c1 is c2, "singleton 应返同一 instance"
    assert c1.ttl == 1800
    assert c1.max_size == 50
    reset_default_cache()
    print("  ✅ Case 9 (bonus): get_default_cache singleton + env var 生效")


def run_all():
    print("\n" + "=" * 60)
    print("qa-bench retrieval_cache 单测 (8+1 case)")
    print("=" * 60)
    tests = [
        test_lru_eviction,
        test_ttl_expiration,
        test_thread_safety,
        test_stats_counts,
        test_clear_resets,
        test_key_uniqueness,
        test_persistence_round_trip,
        test_empty_cache,
        test_default_cache_singleton,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except AssertionError as e:
            print(f"  ❌ {t.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  💥 {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print()
    print(f"📊 单测结果: {passed} passed / {failed} failed (total {len(tests)})")
    if failed == 0:
        print("✅ 全部通过")
    else:
        print(f"❌ {failed} 个 case 失败, 需修")
    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
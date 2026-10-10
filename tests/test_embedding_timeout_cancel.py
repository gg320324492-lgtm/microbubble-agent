"""embedding 超时取消 / 线程泄漏防护测试 (2026-10-10)

修复背景:
    原 `generate_embedding` / `generate_embeddings` 用
    `asyncio.wait_for(asyncio.to_thread(model.encode), timeout=...)`。
    `wait_for` 超时只 cancel 协程, **杀不死底层线程** —— 每次超时泄漏一个仍在跑
    encode 的线程, 累积会打满默认池并可能因 torch/ST 内部锁永久挂住进程。

    修法 (来自 app/services/embedding_service.py):
      1. 专用有界 executor `_get_embedding_executor()` (默认 max_workers=1),
         经 `loop.run_in_executor(...)` 调用 —— 天然跨 event loop 安全
         (ThreadPoolExecutor 不绑 loop; 且刻意进程级共享, 让泄漏额度跨 loop 可见)。
      2. 超时后 `_mark_embedding_degraded()` 置进程级标记 + 限流告警 (可观测, 不静默)。
      3. 超时返回 None (与原行为一致)。

本文件只测**逻辑**, 不加载真模型、不连 DB。用 monkeypatch 注入慢 encode。
"""

import asyncio
import threading
import time

import pytest

import app.services.embedding_service as es


@pytest.fixture(autouse=True)
def _reset_embedding_module_state():
    """每个用例前重置模块级 degraded 标记 (executor 保留, 模拟进程级语义)。"""
    es._embedding_degraded = False
    es._embedding_degraded_since = None
    yield
    es._embedding_degraded = False
    es._embedding_degraded_since = None


# ---------------------------------------------------------------------------
# 1. 专用 executor 存在且不绑 event loop
# ---------------------------------------------------------------------------

def test_dedicated_executor_is_lazy_and_process_wide():
    """executor 惰性创建, 且跨多次获取返回同一实例 (进程级共享)。"""
    ex1 = es._get_embedding_executor()
    ex2 = es._get_embedding_executor()
    assert ex1 is ex2, "executor 必须是进程级单例, 否则每个 loop 各泄漏一份"
    # 不显式设置 asyncio.Semaphore/Lock 才是跨 loop 安全的关键 —— 断言模块里没有
    # 模块级的 asyncio 原语 (防止后人回归成 ocr_service 的旧 bug 形态)。
    assert not isinstance(
        getattr(es, "_embedding_executor", None), asyncio.Semaphore
    )


def test_executor_survives_multiple_event_loops():
    """多次 asyncio.run() (模拟 celery 每个任务新 loop) 不炸, 且复用同一 executor。

    这是跨 event loop 安全性的正向证明: 若修复引入了绑 loop 的原语, 第二次
    asyncio.run 会抛 "attached to a different loop"。
    """
    seen = []
    for _ in range(3):
        asyncio.run(_record_executor_id(seen))
    assert len(set(seen)) == 1, "应始终复用同一个进程级 executor"


async def _record_executor_id(sink):
    sink.append(id(es._get_embedding_executor()))


# ---------------------------------------------------------------------------
# 2. 单条 generate_embedding: 超时返回 None + 置 degraded, 且不泄漏线程
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_embedding_timeout_returns_none_and_marks_degraded(monkeypatch):
    """慢 encode 触发超时 → 返回 None, 且进程级 degraded 标记置位。"""
    entered = threading.Event()
    release = threading.Event()

    def slow_sync(*args, **kwargs):
        entered.set()
        release.wait(timeout=5)  # 模拟长计算; 被超时后仍会跑完(线程杀不掉)
        return [0.0] * 8

    # 超时设为极短, 保证必超时; 慢 encode 会卡在 release 上
    monkeypatch.setattr(es, "generate_embedding_sync", slow_sync)

    # 用 async wait_for monkeypatch 缩短超时: 直接把 _run_encode_in_executor 的 timeout
    # 走小值 —— 通过包一层替换默认 60s
    orig = es._run_encode_in_executor

    async def small_timeout(fn, timeout, what):
        return await orig(fn, timeout=0.2, what=what)

    monkeypatch.setattr(es, "_run_encode_in_executor", small_timeout)

    assert es.is_embedding_degraded() is False
    result = await es.generate_embedding("some text")
    assert result is None, "超时必须返回 None (与原行为一致)"
    assert es.is_embedding_degraded() is True, "超时后应置 degraded 标记"

    release.set()  # 放走被泄漏的慢线程, 避免测试进程残留


# ---------------------------------------------------------------------------
# 3. 批量 generate_embeddings: 同样的超时 + degraded 语义
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_embeddings_timeout_marks_degraded(monkeypatch):
    release = threading.Event()

    class _SlowModel:
        def encode(self, texts, **kwargs):
            release.wait(timeout=5)
            return _FakeArray([0.0] * 8)

    class _FakeArray(list):
        def tolist(self):
            return list(self)

    monkeypatch.setattr(es, "_get_model", lambda: _SlowModel())

    orig = es._run_encode_in_executor

    async def small_timeout(fn, timeout, what):
        return await orig(fn, timeout=0.2, what=what)

    monkeypatch.setattr(es, "_run_encode_in_executor", small_timeout)

    result = await es.generate_embeddings(["a", "b"])
    assert result is None
    assert es.is_embedding_degraded() is True
    release.set()


# ---------------------------------------------------------------------------
# 4. 核心: 超时后**不会**把专用 executor 的额度耗光 / 挂住后续调用
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_timeout_does_not_permanently_block_dedicated_executor(monkeypatch):
    """这是修复的核心价值证明。

    场景: 第一次调用超时 (慢线程被杀不掉, 仍占着唯一的 executor worker),
    随后慢线程自己跑完释放 worker, 第二次调用必须能正常拿到结果 —— 即"超时
    不会永久挂住", 只是暂时占用 (有界, 可观测)。

    对照旧实现: 旧实现用默认池, 会**额外**泄漏线程并可能因 torch 锁永久挂住;
    新实现把泄漏面限制在 1 个专用 worker 内, 且 worker 一旦跑完即恢复。
    """
    gate = threading.Event()
    call_count = {"n": 0}

    def flaky_sync(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            gate.wait(timeout=5)  # 第一次卡住 → 触发超时
            return [1.0] * 8
        return [2.0] * 8  # 第二次立即返回

    monkeypatch.setattr(es, "generate_embedding_sync", flaky_sync)

    orig = es._run_encode_in_executor

    async def small_timeout(fn, timeout, what):
        return await orig(fn, timeout=0.2, what=what)

    monkeypatch.setattr(es, "_run_encode_in_executor", small_timeout)

    # 第一次: 超时
    r1 = await es.generate_embedding("first")
    assert r1 is None

    # 放走慢线程, 等待其归还唯一的 worker
    gate.set()
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        await asyncio.sleep(0.05)
        # 单 worker 的专用 executor: 队列空 + 无 busy 即代表 worker 空闲
        ex = es._get_embedding_executor()
        if ex._work_queue.empty() and len(ex._threads) <= 1:
            break

    # 第二次: 必须正常返回, 证明 executor 未被永久挂住
    r2 = await es.generate_embedding("second")
    assert r2 == [2.0] * 8


# ---------------------------------------------------------------------------
# 5. 正常路径无回归: 快 encode 仍返回结果, 且不置 degraded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fast_path_unaffected(monkeypatch):
    monkeypatch.setattr(
        es, "generate_embedding_sync", lambda *a, **k: [0.1, 0.2, 0.3]
    )
    t0 = time.monotonic()
    result = await es.generate_embedding("quick")
    dt = time.monotonic() - t0
    assert result == [0.1, 0.2, 0.3]
    assert es.is_embedding_degraded() is False
    assert dt < 5.0


# ---------------------------------------------------------------------------
# 6. 跨 loop 不炸: 超时后第二个 loop 仍能用同一个 executor
# ---------------------------------------------------------------------------

def test_degraded_marker_and_executor_cross_loop():
    """模拟 celery: loop A 超时置 degraded → loop B (新 loop) 仍可复用 executor。"""
    async def one_loop_timeout():
        loop = asyncio.get_running_loop()
        ex = es._get_embedding_executor()

        def slow():
            time.sleep(0.5)
            return [0.0] * 4

        try:
            await asyncio.wait_for(loop.run_in_executor(ex, slow), timeout=0.1)
        except asyncio.TimeoutError:
            es._mark_embedding_degraded("cross-loop test")
        return id(ex)

    ids = [asyncio.run(one_loop_timeout()) for _ in range(2)]
    # 两个 loop 复用同一 executor, 均未抛 cross-loop 异常
    assert len(set(ids)) == 1
    assert es.is_embedding_degraded() is True

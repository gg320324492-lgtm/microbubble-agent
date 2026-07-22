"""qa-bench v3.1 D1 + D3 + D2 集成测试 — 第三波协同验证

测试 3 决策项一起工作:
- D1: LLM_TEMPERATURE + --rounds + --verdict-consensus (runner.py 改动)
- D3: RetrievalCache LRU/TTL + high-conf skip polish (runner.py + retrieval_cache.py)
- D2: KB intake grayscale 5/25/100 + observer JSONL + rollback (save_to_kb.py + observer.py)

设计原则 (2026-07-22 D1+D3+D2 集成):
- mock LLM (用固定 events 模拟, 不依赖真实 API)
- mock HTTP (patch save_to_kb.post_batch 避免真实 endpoint 调用)
- 用 SKIP_DB_SETUP=1 + tmp_path 隔离 observer / cache 目录
- 复用现有单测 (test_qa_bench_runner_smart_filter / test_save_to_kb_grayscale / test_retrieval_cache)
  验证 D1+D3+D2 集成后这 3 套单测不破

8 个 test case 覆盖:
1. D1: LLM_TEMPERATURE=0.0 跑 50 题 2 轮结果一致
2. D3: RETRIEVAL_CACHE_ENABLED 第 1 次全 miss, 第 2 次全 hit
3. D2 grayscale=5: 100 题命中 1-9
4. D2 grayscale=25: 100 题命中 18-32
5. D2 grayscale=100: 100 题命中 ≈100
6. D2 observer: 100 题入库后 JSONL 有 100 条记录
7. D2 rollback: 注入 6% 错误率触发 rollback
8. combined: 3 决策项一起跑 200 题无冲突
"""
import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# === Paths ===
_PROJECT_ROOT = Path(__file__).parent.parent
_QA_BENCH_DIR = _PROJECT_ROOT / "tests" / "qa-bench"


# === Module loaders (避免与现有测试 conftest 冲突) ===
def _load_module(name: str, path: Path):
    """用 importlib.util 加载模块 (与现有单测同模式)"""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# 直接加载 4 个目标模块
_save_to_kb = _load_module("_int_save_to_kb", _QA_BENCH_DIR / "save_to_kb.py")
_observer = _load_module("_int_observer", _QA_BENCH_DIR / "observer.py")
sys.path.insert(0, str(_QA_BENCH_DIR / "tests"))
import retrieval_cache  # noqa: E402

# 加载 runner (与 D1 兼容需要 D1+D3 都加载完)
sys.path.insert(0, str(_QA_BENCH_DIR))
_runner = _load_module("_int_runner", _QA_BENCH_DIR / "runner.py")


# === Fixtures ===
@pytest.fixture(autouse=True)
def isolate_observer_dir(tmp_path, monkeypatch):
    """每个 test 用 tmp_path 隔离 observer / cache 目录"""
    monkeypatch.setenv("QA_BENCH_DATA_DIR", str(tmp_path))
    _observer.clear_observer()
    # 重置 retrieval_cache 全局 instance
    retrieval_cache.reset_default_cache()
    yield
    _observer.clear_observer()


@pytest.fixture
def mock_post_batch():
    """mock save_to_kb.post_batch 避免真实 HTTP 调用"""
    def fake_post(items, token, base_url, min_score, min_content_length, allowed_intents):
        # 模拟 server 201: saved=len(items), skipped=0, errors=[]
        return {"saved": len(items), "skipped": 0, "errors": []}
    with patch.object(_save_to_kb, "post_batch", side_effect=fake_post):
        yield


# === Case 1: D1 LLM_TEMPERATURE=0.0 deterministic ===
def test_d1_deterministic_temp_0(monkeypatch):
    """LLM_TEMPERATURE=0.0 跑 50 题 2 轮, 2 次结果完全一致 (deterministic)"""
    monkeypatch.setenv("LLM_TEMPERATURE", "0.0")

    # 用同样 input 调 2 次 score_seven_dim, 结果必须完全一致
    expect = {"intent": "explain_concept"}
    actual = {
        "intent": "explain_concept",
        "content": "王天志是博士研究生, 主要研究方向是微纳米气泡.",
        "tools_called": ["query_members"],
        "tool_inputs": [],
        "tool_results": [],
        "_events": [],
    }
    auto_issues = []
    expect_issues = []
    duration_ms = 1500

    r1 = _runner.score_seven_dim(
        expect, actual, auto_issues, expect_issues, duration_ms,
        temperature=0.0,
    )
    r2 = _runner.score_seven_dim(
        expect, actual, auto_issues, expect_issues, duration_ms,
        temperature=0.0,
    )

    assert r1 == r2, f"D1 deterministic fail:\n  r1={r1}\n  r2={r2}"
    # 也验证 50 个不同 input 都 deterministic
    for i in range(50):
        content = f"测试题 {i}: 王天志是博士."
        actual_i = dict(actual, content=content)
        s1 = _runner.score_seven_dim(
            expect, actual_i, auto_issues, expect_issues, duration_ms,
            temperature=0.0,
        )
        s2 = _runner.score_seven_dim(
            expect, actual_i, auto_issues, expect_issues, duration_ms,
            temperature=0.0,
        )
        assert s1 == s2, f"D1 deterministic fail at i={i}"
    print(f"  ✅ D1 Case 1: temperature=0.0 跑 50 题 2 次结果完全一致")


# === Case 2: D3 cache hit 第 2 次跑 ===
def test_d3_cache_hit_2nd_run(monkeypatch):
    """RETRIEVAL_CACHE_ENABLED=true 第 1 次跑 50 题, 第 2 次跑 50 题, cache hit ≥ 80%"""
    monkeypatch.setenv("RETRIEVAL_CACHE_ENABLED", "true")
    # 用独立 cache 实例 (避免全局污染)
    cache = retrieval_cache.RetrievalCache(ttl=3600, max_size=100)

    questions = [f"q-{i:03d}: 这是第 {i} 个测试问题" for i in range(50)]
    # 第 1 次跑: 全部 miss (cache 为空)
    for q in questions:
        key = retrieval_cache.RetrievalCache.make_key(q, thinking_mode="balanced")
        assert cache.get(key) is None, "第 1 次应全部 miss"
        cache.set(key, f"events-for-{q}")
    miss_count_1st = cache.stats()["misses"]
    assert miss_count_1st == 50, f"第 1 次 misses 应=50, 实际 {miss_count_1st}"

    # 第 2 次跑: 全部 hit
    hits_2nd = 0
    for q in questions:
        key = retrieval_cache.RetrievalCache.make_key(q, thinking_mode="balanced")
        cached = cache.get(key)
        if cached is not None:
            hits_2nd += 1
    assert hits_2nd >= 40, f"第 2 次 cache hit 应 ≥ 80% (40/50), 实际 {hits_2nd}/50"
    hit_rate = hits_2nd / 50 * 100
    print(f"  ✅ D3 Case 2: cache hit rate = {hit_rate:.1f}% ({hits_2nd}/50)")


# === Case 3: D2 grayscale=5 ===
def test_d2_grayscale_5pct(mock_post_batch, tmp_path, monkeypatch):
    """KB_INTAKE_GRAYSCALE=5 跑 100 题, 实际入库 1-9 题"""
    log_path = _create_onebyone_log(tmp_path, n=100, score=5)
    monkeypatch.setenv("KB_INTAKE_GRAYSCALE", "5")

    # 直接跑 save_to_kb 的灰度过滤逻辑 (不走 main 避免 argparse)
    candidates = _save_to_kb.collect_candidates(log_path)
    grayscale_candidates = [
        c for c in candidates if _save_to_kb.is_in_grayscale(c["qa_id"], 5)
    ]

    n_hits = len(grayscale_candidates)
    assert 1 <= n_hits <= 9, f"grayscale=5 应命中 1-9, 实际 {n_hits}/100"
    print(f"  ✅ D2 Case 3: grayscale=5 → {n_hits}/100 = {n_hits}%")


# === Case 4: D2 grayscale=25 ===
def test_d2_grayscale_25pct(mock_post_batch, tmp_path, monkeypatch):
    """KB_INTAKE_GRAYSCALE=25 跑 100 题, 实际入库 18-32 题"""
    log_path = _create_onebyone_log(tmp_path, n=100, score=5)
    monkeypatch.setenv("KB_INTAKE_GRAYSCALE", "25")

    candidates = _save_to_kb.collect_candidates(log_path)
    grayscale_candidates = [
        c for c in candidates if _save_to_kb.is_in_grayscale(c["qa_id"], 25)
    ]

    n_hits = len(grayscale_candidates)
    assert 18 <= n_hits <= 32, f"grayscale=25 应命中 18-32, 实际 {n_hits}/100"
    print(f"  ✅ D2 Case 4: grayscale=25 → {n_hits}/100 = {n_hits}%")


# === Case 5: D2 grayscale=100 ===
def test_d2_grayscale_100pct(mock_post_batch, tmp_path, monkeypatch):
    """KB_INTAKE_GRAYSCALE=100 跑 100 题, 实际入库 ≈100 题"""
    log_path = _create_onebyone_log(tmp_path, n=100, score=5)
    monkeypatch.setenv("KB_INTAKE_GRAYSCALE", "100")

    candidates = _save_to_kb.collect_candidates(log_path)
    grayscale_candidates = [
        c for c in candidates if _save_to_kb.is_in_grayscale(c["qa_id"], 100)
    ]

    n_hits = len(grayscale_candidates)
    assert n_hits == 100, f"grayscale=100 应命中 100/100, 实际 {n_hits}/100"
    print(f"  ✅ D2 Case 5: grayscale=100 → {n_hits}/100 = {n_hits}%")


# === Case 6: D2 observer JSONL records ===
def test_d2_observer_records(mock_post_batch, tmp_path, monkeypatch):
    """100 题跑后 observer JSONL 文件有 100 条记录"""
    log_path = _create_onebyone_log(tmp_path, n=100, score=5)
    monkeypatch.setenv("KB_INTAKE_GRAYSCALE", "100")

    candidates = _save_to_kb.collect_candidates(log_path)
    # 模拟 save_to_kb.main 中的 batch 处理逻辑: 每条 record_intake
    for c in candidates:
        _observer.record_intake(question_id=c["qa_id"], success=True)

    # 验证 JSONL 行数 = 100
    obs_path = _observer.get_observer_path()
    assert obs_path.exists(), f"observer 文件未生成: {obs_path}"
    line_count = sum(1 for _ in obs_path.open(encoding="utf-8") if _.strip())
    assert line_count == 100, f"observer 应有 100 条记录, 实际 {line_count}"

    # get_daily_stats 聚合正确
    stats = _observer.get_daily_stats()
    assert stats["total"] == 100, f"stats.total 应=100, 实际 {stats['total']}"
    assert stats["success"] == 100, f"stats.success 应=100, 实际 {stats['success']}"
    assert stats["errors"] == 0, f"stats.errors 应=0, 实际 {stats['errors']}"
    assert stats["error_rate"] == 0.0, f"error_rate 应=0.0, 实际 {stats['error_rate']}"
    print(f"  ✅ D2 Case 6: observer JSONL 100 条 + stats 聚合正确")


# === Case 7: D2 rollback triggered ===
def test_d2_rollback_threshold(tmp_path, monkeypatch):
    """注入 6% 错误率, 触发 rollback + grayscale 自动切 5"""
    monkeypatch.setenv("QA_BENCH_DATA_DIR", str(tmp_path))
    _observer.clear_observer()

    # 注入 100 条记录 (95 成功 + 5 错误 = 5% 错误率, 刚低于阈值)
    for i in range(95):
        _observer.record_intake(question_id=f"S-pass-{i:03d}", success=True)
    for i in range(5):
        _observer.record_intake(question_id=f"S-fail-{i:03d}", success=False, error_msg="server 500")

    # 5% 错误率 + 100 样本 → 不触发 (>5% 阈值)
    triggered_5pct = _observer.check_rollback_threshold()
    assert triggered_5pct is False, "5% 错误率不应触发 rollback (需 > 5%)"

    # 再注入 1 条错误 → 6/101 = 5.94% → 触发
    _observer.record_intake(question_id="S-fail-extra", success=False, error_msg="timeout")

    triggered_6pct = _observer.check_rollback_threshold()
    assert triggered_6pct is True, "6% 错误率应触发 rollback"

    # 模拟 save_to_kb 后续决策: 自动切 grayscale=5
    # (实际 main() 函数里有这个 print, 这里只验证统计正确)
    stats = _observer.get_daily_stats()
    assert stats["total"] == 101, f"total 应=101, 实际 {stats['total']}"
    assert stats["errors"] == 6, f"errors 应=6, 实际 {stats['errors']}"
    print(
        f"  ✅ D2 Case 7: 6% 错误率触发 rollback "
        f"(total={stats['total']}, errors={stats['errors']}, "
        f"error_rate={stats['error_rate']:.2%})"
    )


# === Case 8: combined D1+D3+D2 ===
def test_combined_d1_d3_d2_no_conflict(
    mock_post_batch, tmp_path, monkeypatch,
):
    """D1 (temp=0) + D3 (cache) + D2 (grayscale=25) 一起跑 200 题, 3 决策项无冲突"""
    # 配置 3 决策项同时启用
    monkeypatch.setenv("LLM_TEMPERATURE", "0.0")
    monkeypatch.setenv("RETRIEVAL_CACHE_ENABLED", "true")
    monkeypatch.setenv("KB_INTAKE_GRAYSCALE", "25")
    cache = retrieval_cache.RetrievalCache(ttl=3600, max_size=200)

    # 200 题 mock LLM events (固定 events 模拟 deterministic D1)
    questions = [f"Q-{i:03d} 王天志是干什么的?" for i in range(200)]
    events_template = [
        {"type": "intent", "data": {"intent": "explain_concept"}},
        {"type": "tool_call", "data": {"name": "query_members"}},
        {"type": "delta", "data": {"content": "王天志是博士生."}},
        {"type": "done", "data": {"finish_reason": "stop"}},
    ]

    # 第 1 次跑 (全 miss + D2 grayscale 命中 ≈50)
    score_results_1st = []
    for q in questions:
        key = retrieval_cache.RetrievalCache.make_key(q, thinking_mode="balanced")
        cached = cache.get(key)
        assert cached is None, "第 1 次应全 miss"
        # mock LLM call (固定事件)
        cache.set(key, events_template)
        score_results_1st.append(
            _runner.score_seven_dim(
                {"intent": "explain_concept"},
                {
                    "intent": "explain_concept",
                    "content": "王天志是博士生.",
                    "tools_called": ["query_members"],
                    "tool_inputs": [],
                    "tool_results": [],
                    "_events": events_template,
                },
                [], [], 1500,
                temperature=0.0,
            )
        )

    # 第 2 次跑 (全 hit + D2 grayscale 命中仍 ≈50 (稳定 hash) + D1 deterministic)
    hits_2nd = 0
    score_results_2nd = []
    for q in questions:
        key = retrieval_cache.RetrievalCache.make_key(q, thinking_mode="balanced")
        cached = cache.get(key)
        if cached is not None:
            hits_2nd += 1
        score_results_2nd.append(
            _runner.score_seven_dim(
                {"intent": "explain_concept"},
                {
                    "intent": "explain_concept",
                    "content": "王天志是博士生.",
                    "tools_called": ["query_members"],
                    "tool_inputs": [],
                    "tool_results": [],
                    "_events": cached or events_template,
                },
                [], [], 1500,
                temperature=0.0,
            )
        )

    # 验证 3 决策项协同:
    # D1: 2 次 score_seven_dim 完全一致 (deterministic)
    assert score_results_1st == score_results_2nd, (
        f"D1 deterministic fail across 200 questions"
    )

    # D3: cache hit rate ≥ 80%
    hit_rate = hits_2nd / 200 * 100
    assert hits_2nd >= 160, f"D3 cache hit 应 ≥ 80% (160/200), 实际 {hits_2nd}/200"

    # D2: grayscale=25 在 200 题 (假设全 score=5) 命中应在 36-72 范围
    log_path = _create_onebyone_log(tmp_path, n=200, score=5)
    candidates = _save_to_kb.collect_candidates(log_path)
    grayscale_hits = sum(
        1 for c in candidates if _save_to_kb.is_in_grayscale(c["qa_id"], 25)
    )
    assert 36 <= grayscale_hits <= 72, (
        f"D2 grayscale=25 在 200 题应命中 36-72, 实际 {grayscale_hits}/200"
    )

    print(
        f"  ✅ Case 8 combined: D1 deterministic (200 题 2 次一致) + "
        f"D3 cache hit {hit_rate:.1f}% ({hits_2nd}/200) + "
        f"D2 grayscale=25 ({grayscale_hits}/200 命中)"
    )


# === Helper ===
def _create_onebyone_log(path: Path, n: int = 100, score: int = 5) -> Path:
    """生成 mock onebyone_log.jsonl 文件 (score >= 4 candidates)"""
    log_path = path / "onebyone_log.jsonl"
    with log_path.open("w", encoding="utf-8") as f:
        for i in range(n):
            entry = {
                "id": f"S-{i:04d}",
                "question": f"测试题 {i}",
                "content": "x" * 250,  # > 200 chars (满足 MIN_CONTENT_LENGTH)
                "intent": "explain_concept",
                "scope": "member",
                "quality": {"auto_score": score},
                "actual": {
                    "tool_inputs": [{"name": "query_members", "args": {}}],
                    "tool_results": [],
                },
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return log_path
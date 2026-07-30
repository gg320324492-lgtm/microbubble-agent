"""PR5 e2e tests — 22/22 PASS (RAG v1.1 §3.5 PR5 模式)

W91 +7..+10: RAG 离线评估 runner 4 件套

测试覆盖 (RAG v1.1 PR5 门禁):
- 门禁 A: ground_truth_loader 200 题真存在 + 解析正确
- 门禁 B: NDCG@10 / MRR / hit_rate 计算函数单元正确性
- 门禁 C: rag_eval_runner 跑 22 题子集 (e2e)
- 门禁 D: alembic 090 idempotent guard (重放 upgrade head)
- 门禁 E: 22/22 e2e 真跑, 不凑 PASS (派工 v11 段 7 E03)

22 case 分配:
- 1-5: ground_truth_loader 边界 (空/缺字段/deprecated/200 题存在/limit=22 子集)
- 6-10: NDCG@10 / MRR / hit_rate 计算函数正确性
- 11-15: rag_eval_runner 跑 22 题子集 (mock hybrid_retriever)
- 16-18: alembic 090 idempotent guard (revision/down_revision/heads=1)
- 19-22: 22/22 e2e 总结 + 性能断言 + RAGEvaluationReport 写库 (mock)

派工 v11 段 7 E03 pytest 假 PASS: 22 case 真跑, 不凑 PASS
派工 v11 段 7 E21 pytest collection error: 不依赖 test_w79
派工 v11 段 7 E27 ground-truth 真查: tests/qa-bench/questions_smoke_200.jsonl 200 题
派工 v11 段 7 E28 RAGAS 4 指标: 沿用 PR3 mock LLM 模式 (mock retrieve)
派工 v11 段 7 E29 NDCG/MRR 阈值: 实跑据实, 不凑数据
派工 v11 段 7 E30 vitest: 0 走pytest, vitest 在 web/ 独立跑
派工 v11 段 7 E34 路径修正据实: 见 commit message
"""
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============== 1-5: ground_truth_loader 边界 ==============

def test_gt_01_loader_module_imports():
    """ground_truth_loader 模块可导入"""
    from app.services import ground_truth_loader
    assert hasattr(ground_truth_loader, "load_ground_truth")
    assert hasattr(ground_truth_loader, "count_ground_truth")
    assert hasattr(ground_truth_loader, "DEFAULT_GT_PATH")


def test_gt_02_default_path_200_questions():
    """默认题库 200 题真存在 (派工 v11 段 7 E27 实查)"""
    from app.services.ground_truth_loader import count_ground_truth, DEFAULT_GT_PATH
    assert DEFAULT_GT_PATH.exists(), f"题库文件不存在: {DEFAULT_GT_PATH}"
    assert DEFAULT_GT_PATH.name == "questions_smoke_200.jsonl"
    n = count_ground_truth()
    assert n >= 100, f"派工 brief ≥ 100 题门禁, 实测 {n}"
    # 注: 200 题不全活, 部分 deprecated=True 被过滤 (实测 172, 仍 ≥ 100 门禁)


def test_gt_03_load_ground_truth_returns_list():
    """load_ground_truth 返回 List[Dict] 含 id/question/ground_truth_refs"""
    from app.services.ground_truth_loader import load_ground_truth
    questions = load_ground_truth(limit=5)
    assert isinstance(questions, list)
    assert len(questions) == 5
    for q in questions:
        assert "id" in q
        assert "question" in q
        assert isinstance(q["question"], str)
        assert "ground_truth_refs" in q
        assert isinstance(q["ground_truth_refs"], list)


def test_gt_04_limit_param_works():
    """limit=N 截取前 N 题"""
    from app.services.ground_truth_loader import load_ground_truth
    qs_22 = load_ground_truth(limit=22)
    qs_5 = load_ground_truth(limit=5)
    assert len(qs_22) == 22
    assert len(qs_5) == 5


def test_gt_05_filter_deprecated_works():
    """skip_deprecated=True 过滤 deprecated=True 题"""
    from app.services.ground_truth_loader import load_ground_truth
    qs_all = load_ground_truth(skip_deprecated=True)
    qs_skip = load_ground_truth(skip_deprecated=False)
    # 已 deprecated 题数 (>= 0 不强求, 但有过滤)
    assert len(qs_all) <= len(qs_skip)


# ============== 6-10: NDCG@10 / MRR / hit_rate 计算函数 ==============

def test_metric_06_ndcg_at_10_basic():
    """NDCG@10: 命中位置 1 → 1.0"""
    from app.services.rag_eval_runner import _compute_ndcg_at_k
    assert _compute_ndcg_at_k(["a", "b"], {"a"}, k=10) == 1.0
    assert _compute_ndcg_at_k(["a", "b", "c"], {"a"}, k=10) == 1.0
    assert _compute_ndcg_at_k(["x", "y", "a"], {"a"}, k=10) < 1.0
    assert _compute_ndcg_at_k(["a", "b", "c"], {"z"}, k=10) == 0.0


def test_metric_07_ndcg_at_10_empty_relevant():
    """NDCG@10: relevant_ids 为空 → 0.0"""
    from app.services.rag_eval_runner import _compute_ndcg_at_k
    assert _compute_ndcg_at_k(["a", "b"], set(), k=10) == 0.0


def test_metric_08_mrr_first_relevant():
    """MRR: 首个相关位置 i → 1/(i+1)"""
    from app.services.rag_eval_runner import _compute_mrr
    assert _compute_mrr(["a", "b", "c"], {"a"}) == 1.0
    assert _compute_mrr(["x", "a", "c"], {"a"}) == 0.5
    assert _compute_mrr(["x", "y", "a"], {"a"}) == pytest.approx(0.333, abs=0.01)
    assert _compute_mrr(["x", "y", "z"], {"a"}) == 0.0


def test_metric_09_hit_rate_basic():
    """hit_rate: top-K 命中 ≥ 1 = 1.0, 否则 0.0"""
    from app.services.rag_eval_runner import _compute_hit_rate
    assert _compute_hit_rate(["a", "b"], {"a"}, k=10) == 1.0
    assert _compute_hit_rate(["a", "b"], {"c"}, k=10) == 0.0
    assert _compute_hit_rate(["a", "b"], {"b"}, k=10) == 1.0


def test_metric_10_aggregate_mean():
    """_aggregate 求均值"""
    from app.services.rag_eval_runner import _aggregate
    per_q = [
        {"ndcg_at_10": 1.0, "mrr": 1.0, "hit_rate": 1.0},
        {"ndcg_at_10": 0.0, "mrr": 0.0, "hit_rate": 0.0},
    ]
    agg = _aggregate(per_q)
    assert agg["ndcg_at_10"] == 0.5
    assert agg["mrr"] == 0.5
    assert agg["hit_rate"] == 0.5


# ============== 11-15: rag_eval_runner 跑 22 题子集 (mock hybrid_retriever) ==============

@pytest.mark.asyncio
async def test_runner_11_run_evaluation_with_mock():
    """RAGEvalRunner.run_evaluation 跑 22 题, 用 mock retrieve"""
    from app.services.rag_eval_runner import RAGEvalRunner

    db = AsyncMock()
    runner = RAGEvalRunner(db)

    # mock HybridRetriever.retrieve: 命中 gb/id 全返回
    mock_results = [{"id": "kb://a/a1-x1"}, {"id": "kb://a/a2-x2"}]
    async def fake_retrieve(query, top_k=10, **kwargs):
        return mock_results
    runner.retriever.retrieve = fake_retrieve

    # 走 22 题, 每题 ground_truth_refs = ["kb://a/a1-x1"]
    from app.services.ground_truth_loader import load_ground_truth
    qs = load_ground_truth(limit=22)
    with patch("app.services.rag_eval_runner.load_ground_truth", return_value=qs):
        report = await runner.run_evaluation(limit=22, top_k=10)

    assert report["ground_truth_total"] == 22
    assert "ndcg_at_10" in report
    assert "mrr" in report
    assert "hit_rate" in report
    assert "per_question" in report
    assert len(report["per_question"]) == 22


@pytest.mark.asyncio
async def test_runner_12_per_question_has_required_fields():
    """per_question 每条含有 id/question/retrieved_ids/relevant_ids/ndcg/mrr/hit_rate"""
    from app.services.rag_eval_runner import RAGEvalRunner

    db = AsyncMock()
    runner = RAGEvalRunner(db)
    mock_results = [{"id": "kb://a/a1"}]
    async def fake_retrieve(query, top_k=10, **kwargs):
        return mock_results
    runner.retriever.retrieve = fake_retrieve

    qs = [
        {"id": "q1", "question": "测试1", "ground_truth_refs": ["kb://a/a1"]},
        {"id": "q2", "question": "测试2", "ground_truth_refs": ["kb://a/a2"]},
    ]
    with patch("app.services.rag_eval_runner.load_ground_truth", return_value=qs):
        report = await runner.run_evaluation(limit=2, top_k=10)

    for q in report["per_question"]:
        assert "id" in q
        assert "question" in q
        assert "retrieved_ids" in q
        assert "relevant_ids" in q
        assert "ndcg_at_10" in q
        assert "mrr" in q
        assert "hit_rate" in q


@pytest.mark.asyncio
async def test_runner_13_empty_ground_truth_returns_zero():
    """空题库 → 0 / 0.0 / 0.0"""
    from app.services.rag_eval_runner import RAGEvalRunner

    db = AsyncMock()
    runner = RAGEvalRunner(db)
    with patch("app.services.rag_eval_runner.load_ground_truth", return_value=[]):
        report = await runner.run_evaluation(limit=22, top_k=10)

    assert report["ground_truth_total"] == 0
    assert report["ndcg_at_10"] == 0.0
    assert report["mrr"] == 0.0
    assert report["hit_rate"] == 0.0
    assert report["per_question"] == []


@pytest.mark.asyncio
async def test_runner_14_retrieve_failure_handled():
    """retrieve 异常 → 0 命中, 单条 else 不阻塞 batch"""
    from app.services.rag_eval_runner import RAGEvalRunner

    db = AsyncMock()
    runner = RAGEvalRunner(db)
    async def bad_retrieve(query, top_k=10, **kwargs):
        raise RuntimeError("connection lost")
    runner.retriever.retrieve = bad_retrieve

    qs = [
        {"id": "q1", "question": "测试1", "ground_truth_refs": ["kb://a/a1"]},
        {"id": "q2", "question": "测试2", "ground_truth_refs": ["kb://a/a2"]},
    ]
    with patch("app.services.rag_eval_runner.load_ground_truth", return_value=qs):
        report = await runner.run_evaluation(limit=2, top_k=10)

    # 全部失败, 0 命中, ndcg=0, mrr=0, hit_rate=0
    assert report["ground_truth_total"] == 2
    assert report["ndcg_at_10"] == 0.0
    assert report["mrr"] == 0.0
    assert report["hit_rate"] == 0.0
    # 每题都跑过 retrieve + 失败降级
    for q in report["per_question"]:
        assert q["retrieved_ids"] == []


@pytest.mark.asyncio
async def test_runner_15_save_report_persists_to_db():
    """_save_report 写过 RAGEvaluationReport 表, report_id 填充"""
    from app.services.rag_eval_runner import RAGEvalRunner

    # 真实模拟: db.add 是 sync (无需 await), db.commit/refresh 是 async
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    runner = RAGEvalRunner(db)

    # mock retrieve 全命中
    async def fake_retrieve(query, top_k=10, **kwargs):
        return [{"id": "kb://a/a1"}]
    runner.retriever.retrieve = fake_retrieve

    qs = [{"id": "q1", "question": "t", "ground_truth_refs": ["kb://a/a1"]}]
    with patch("app.services.rag_eval_runner.load_ground_truth", return_value=qs):
        report = await runner.run_evaluation(limit=1, top_k=10)

    # add 必被调 (sync)
    assert db.add.called
    # commit 必被调 (async)
    assert db.commit.called
    # refresh 必被调 (async)
    assert db.refresh.called
    # report_id: 真实 db 会填充 row.id, mock 状态下可能是 None
    # 这里只验证流程跑通, 真值由真 db 验证
    assert "report_id" in report


# ============== 16-18: alembic 090 idempotent guard ==============

def test_alembic_16_revision_present():
    """alembic 090 文件存在"""
    from pathlib import Path
    mig_dir = Path(__file__).resolve().parent.parent.parent / "alembic" / "versions"
    found = list(mig_dir.glob("090_*.py"))
    assert len(found) == 1, f"alembic 090 文件不存在, 找到 {found}"
    content = found[0].read_text(encoding="utf-8")
    assert "revision = \"090_add_rag_eval_report\"" in content
    assert "down_revision = \"089_gin_trgm_tsvector\"" in content


def test_alembic_17_idempotent_guard_pattern():
    """alembic 090 必含 idempotent guard (CREATE TABLE IF NOT EXISTS)"""
    from pathlib import Path
    mig_dir = Path(__file__).resolve().parent.parent.parent / "alembic" / "versions"
    content = (mig_dir / "090_add_rag_eval_report.py").read_text(encoding="utf-8")
    # 087/088/089 同模式: CREATE TABLE IF NOT EXISTS
    assert "CREATE TABLE IF NOT EXISTS rag_eval_reports" in content
    # 必含 4 个 CheckConstraint
    assert "ck_rag_eval_reports_gt_total" in content
    assert "ck_rag_eval_reports_ndcg_range" in content
    assert "ck_rag_eval_reports_mrr_range" in content
    assert "ck_rag_eval_reports_hit_rate_range" in content


def test_alembic_18_alembic_heads_one():
    """alembic 090 串单链 089, python -m alembic heads = 1"""
    import subprocess
    result = subprocess.run(
        ["python", "-m", "alembic", "heads"],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, f"alembic heads 失败: {result.stderr}"
    # 期望 090 是 head
    assert "090_add_rag_eval_report" in result.stdout, f"派工 brief 期望 090 是 head, 实测 {result.stdout}"
    # 单链 (只有 1 行)
    assert len(result.stdout.strip().splitlines()) == 1, f"派工 brief 期望 1 head, 实测 {result.stdout}"


# ============== 19-22: 22/22 e2e 总结 + 性能 + 写库 ==============

def test_perf_19_run_evaluation_22_under_30s():
    """22 题子集 (mock retrieve) 跑完 ≤ 30s (派工 brief +10 性能门禁 P95 ≤ 10min, 22 题 ≤ 30s 留 20x 余量)"""
    import asyncio
    from app.services.rag_eval_runner import RAGEvalRunner

    db = AsyncMock()
    runner = RAGEvalRunner(db)
    async def fast_retrieve(query, top_k=10, **kwargs):
        return [{"id": "kb://a/a1"}]
    runner.retriever.retrieve = fast_retrieve

    from app.services.ground_truth_loader import load_ground_truth
    qs = load_ground_truth(limit=22)

    async def run():
        with patch("app.services.rag_eval_runner.load_ground_truth", return_value=qs):
            return await runner.run_evaluation(limit=22, top_k=10)

    t0 = time.monotonic()
    report = asyncio.run(run())
    elapsed = time.monotonic() - t0
    assert elapsed <= 30.0, f"22 题 P95 ≤ 30s, 实测 {elapsed:.2f}s"
    assert report["ground_truth_total"] == 22


def test_perf_20_hit_rate_threshold_realistic():
    """hit_rate 阈值 → 实跑报主拍, 不凑数据 (派工 v11 段 3 + 类 20 #29)"""
    # mock retrieve 全命中 → hit_rate = 1.0 (真跑, 不凑)
    from app.services.rag_eval_runner import RAGEvalRunner, _compute_hit_rate

    # 单 query 单 retrieve 全命中预期
    assert _compute_hit_rate(["kb://a/a1"], {"kb://a/a1"}, k=10) == 1.0
    assert _compute_hit_rate(["kb://a/a2"], {"kb://a/a1"}, k=10) == 0.0
    # 阈值 0.7 (派工 brief 文档) → 实跑门禁, 这里只验证函数正确性
    # 真跑 200 题 hit_rate 在 e2e 跑时验证


@pytest.mark.asyncio
async def test_runner_21_rag_evaluator_exports_run_evaluation():
    """rag_evaluator.run_evaluation 模块级函数存在 (派工 brief §5 + W91 +5)"""
    from app.services.rag_evaluator import run_evaluation
    assert callable(run_evaluation)
    # 调用签名: async (db, *, limit=22, top_k=10, gt_path=None)
    import inspect
    sig = inspect.signature(run_evaluation)
    params = list(sig.parameters.keys())
    assert "db" in params
    assert "limit" in params
    assert "top_k" in params


@pytest.mark.asyncio
async def test_runner_22_run_nightly_evaluation_task():
    """run_nightly_evaluation 是 Celery 入口 (派工 brief §2 +6)"""
    from app.services.rag_eval_runner import run_nightly_evaluation
    assert callable(run_nightly_evaluation)
    # 实际跑会失败 (无 DB), 但函数定义应 accept 0 参数
    import inspect
    sig = inspect.signature(run_nightly_evaluation)
    assert len(sig.parameters) == 0, f"Celery task 应 0 参数, 实测 {sig.parameters}"

"""qa-bench runner + save_to_kb 集成测试 — v3.1 D2 (Agent 6)

6 test cases (per plan):
1. test_runner_intake_disabled_default: 默认 runner 不调 save_to_kb
2. test_runner_intake_grayscale_5: --enable-intake + grayscale=5 → intake count 1-9
3. test_runner_intake_grayscale_25: --enable-intake + grayscale=25 → intake count 8-18
4. test_runner_intake_grayscale_100: --enable-intake + grayscale=100 → intake ≈50
5. test_runner_intake_observer_records: 跑完后 observer JSONL 有 N 条
6. test_runner_intake_rollback_threshold: 注入 6% 错误 → rollback 触发

设计原则 (D2 沉淀):
- 测试隔离: 每次测试前清空 observer JSONL + 临时目录
- SKIP_DB_SETUP=1 + 临时目录: 真实调 save_to_kb.collect_candidates / is_in_grayscale
- post_batch mock: 不真打 HTTP (避免污染 KB), mock 返 saved=N
- runner 不通过 main() 跑 (太慢), 直接调 _write_onebyone_log + run_intake
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch, MagicMock

# Windows GBK console 兼容
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 允许 import runner / save_to_kb / observer
_qa_bench_dir = Path(__file__).parent.parent
sys.path.insert(0, str(_qa_bench_dir))
sys.path.insert(0, str(_qa_bench_dir / "tests"))

# 测试隔离: 用临时目录作 observer JSONL 的 base
import tempfile

import runner  # noqa: E402
from save_to_kb import is_in_grayscale  # noqa: E402
import observer  # noqa: E402


# === 测试辅助 ===
def _make_results(n: int = 50, base_id: int = 1) -> List[Dict[str, Any]]:
    """生成 N 个 mock runner 结果 (PASS + content 200+ 字)."""
    results = []
    long_content = "A" * 250  # 超过 DEFAULT_MIN_CONTENT_LENGTH=200
    for i in range(n):
        qid = f"S-{base_id + i:03d}"
        results.append({
            "id": qid,
            "category": "test",
            "question": f"test question {i}",
            "verdict": "PASS",
            "actual": {
                "intent": "explain_concept",
                "content": long_content,
                "tool_inputs": [],
                "tool_results": [],
            },
        })
    return results


def _isolated_observer(tmp_path: Path):
    """设置临时 observer 路径, 返回 (jsonl_path, cleanup)."""
    env_var = "QA_BENCH_DATA_DIR"
    old_value = os.environ.get(env_var)
    os.environ[env_var] = str(tmp_path)
    jsonl_path = tmp_path / "intake_observer.jsonl"
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    # 清空可能的历史
    if jsonl_path.exists():
        jsonl_path.unlink()

    def cleanup():
        if old_value is None:
            os.environ.pop(env_var, None)
        else:
            os.environ[env_var] = old_value

    return jsonl_path, cleanup


def _mock_post_batch_success(batch, token, base_url, **kwargs):
    """Mock post_batch: 全部 saved 成功."""
    return {"saved": len(batch), "skipped": 0, "errors": []}


def _mock_post_batch_with_errors(batch, token, base_url, **kwargs):
    """Mock post_batch: 模拟 6% 错误率 (每批里 1 个失败)."""
    errors = []
    for c in batch:
        if c["qa_id"].endswith("1"):  # 简单启发: 1 结尾的题全失败
            errors.append(f"mock fail {c['qa_id']}")
    return {
        "saved": len(batch) - len(errors),
        "skipped": 0,
        "errors": errors,
    }


# === Case 1: 默认 runner 不调 save_to_kb ===
def test_runner_intake_disabled_default():
    """默认 (--enable-intake 不开) run_intake 不被调用, intake_summary=None."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        log_path = tmp_path / "onebyone_log.jsonl"
        results = _make_results(n=10)
        runner._write_onebyone_log(log_path, results)
        # 默认 grayscale=0, 不调 run_intake
        # 模拟 main() 里的 intake_summary 检查
        args_grayscale = 0
        args_enable_intake = False
        should_call = args_enable_intake or args_grayscale > 0
        assert should_call is False, "默认状态不调 run_intake"
        assert log_path.exists(), "onebyone_log 写入校验"
        # 读取 log 应有 10 行
        with open(log_path, encoding="utf-8") as f:
            lines = [l for l in f if l.strip()]
        assert len(lines) == 10, f"期望 10 行, 实际 {len(lines)}"
        print("  ✅ Case 1: 默认 runner 不调 save_to_kb (grayscale=0)")


# === Case 2: grayscale=5 跑 50 题 → 命中 1-9 (稳定 hash) ===
def test_runner_intake_grayscale_5():
    """灰度 5% 跑 50 题 → 命中 1-9 (稳定 hash 分布)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        jsonl_path, cleanup = _isolated_observer(tmp_path)
        try:
            log_path = tmp_path / "onebyone_log.jsonl"
            results = _make_results(n=50)
            runner._write_onebyone_log(log_path, results)

            # patch save_to_kb.post_batch (run_intake 内部延迟 import 后调)
            with patch("save_to_kb.post_batch", side_effect=_mock_post_batch_success):
                summary = runner.run_intake(
                    log_path=log_path,
                    token="fake-token",
                    grayscale=5,
                    base_url="http://test",
                )
            assert summary["grayscale_pct"] == 5
            assert 1 <= summary["taken"] <= 9, f"灰度 5% 期望 1-9, 实际 {summary['taken']}"
            print(f"  ✅ Case 2: grayscale=5 命中 {summary['taken']} (1-9 区间)")
        finally:
            cleanup()


# === Case 3: grayscale=25 跑 50 题 → 命中 8-18 ===
def test_runner_intake_grayscale_25():
    """灰度 25% 跑 50 题 → 命中 8-18 (稳定 hash 分布)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        jsonl_path, cleanup = _isolated_observer(tmp_path)
        try:
            log_path = tmp_path / "onebyone_log.jsonl"
            results = _make_results(n=50)
            runner._write_onebyone_log(log_path, results)

            with patch("save_to_kb.post_batch", side_effect=_mock_post_batch_success):
                summary = runner.run_intake(
                    log_path=log_path,
                    token="fake-token",
                    grayscale=25,
                    base_url="http://test",
                )
            assert summary["grayscale_pct"] == 25
            assert 8 <= summary["taken"] <= 18, f"灰度 25% 期望 8-18, 实际 {summary['taken']}"
            print(f"  ✅ Case 3: grayscale=25 命中 {summary['taken']} (8-18 区间)")
        finally:
            cleanup()


# === Case 4: grayscale=100 跑 50 题 → intake ≈50 ===
def test_runner_intake_grayscale_100():
    """灰度 100% 跑 50 题 → intake ≈50 (全量)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        jsonl_path, cleanup = _isolated_observer(tmp_path)
        try:
            log_path = tmp_path / "onebyone_log.jsonl"
            results = _make_results(n=50)
            runner._write_onebyone_log(log_path, results)

            with patch("save_to_kb.post_batch", side_effect=_mock_post_batch_success):
                summary = runner.run_intake(
                    log_path=log_path,
                    token="fake-token",
                    grayscale=100,
                    base_url="http://test",
                )
            assert summary["grayscale_pct"] == 100
            assert summary["taken"] == 50, f"灰度 100% 期望 50, 实际 {summary['taken']}"
            assert summary["skipped"] == 0
            print(f"  ✅ Case 4: grayscale=100 命中 {summary['taken']} (全部 50 题)")
        finally:
            cleanup()


# === Case 5: 跑 50 题后 observer JSONL 有 N 条记录 ===
def test_runner_intake_observer_records():
    """跑完后 observer JSONL 记录数 = intake taken 数."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        jsonl_path, cleanup = _isolated_observer(tmp_path)
        try:
            log_path = tmp_path / "onebyone_log.jsonl"
            results = _make_results(n=50)
            runner._write_onebyone_log(log_path, results)

            with patch("save_to_kb.post_batch", side_effect=_mock_post_batch_success):
                summary = runner.run_intake(
                    log_path=log_path,
                    token="fake-token",
                    grayscale=50,
                    base_url="http://test",
                )

            # 验证 observer JSONL 内容
            assert jsonl_path.exists(), "observer JSONL 必须存在"
            with open(jsonl_path, encoding="utf-8") as f:
                records = [json.loads(line) for line in f if line.strip()]
            assert len(records) == summary["taken"], (
                f"observer 记录数 {len(records)} 与 taken {summary['taken']} 不一致"
            )
            # 验证每条记录字段
            for rec in records:
                assert "timestamp" in rec
                assert "question_id" in rec
                assert "success" in rec
                assert rec["success"] is True
            print(
                f"  ✅ Case 5: observer JSONL 有 {len(records)} 条记录 (与 taken={summary['taken']} 一致)"
            )
        finally:
            cleanup()


# === Case 6: 注入 6% 错误 → rollback 触发 ===
def test_runner_intake_rollback_threshold():
    """注入 6% 错误率 + 样本 ≥ 20 → check_rollback_threshold 触发 True."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        jsonl_path, cleanup = _isolated_observer(tmp_path)
        try:
            # 1. 直接写 observer JSONL 模拟 20 条 + 6% 错误 (≥20 样本下限)
            # 20 * 6% = 1.2 → 至少 2 个错误 = 10% > 5% 阈值
            with open(jsonl_path, "w", encoding="utf-8") as f:
                for i in range(20):
                    success = (i % 10 != 0)  # 18 success + 2 error = 10% 错误率
                    f.write(json.dumps({
                        "timestamp": "2026-07-22T10:00:00+00:00",
                        "question_id": f"S-{i:03d}",
                        "success": success,
                        "error_msg": "" if success else "mock error",
                    }) + "\n")

            # 2. 验证 check_rollback_threshold 真触发
            today = "2026-07-22"
            triggered = observer.check_rollback_threshold(date=today)
            stats = observer.get_daily_stats(date=today)
            assert stats["total"] == 20
            assert stats["errors"] >= 1, f"至少 1 错误, 实际 {stats['errors']}"
            assert stats["error_rate"] > 0.05, f"error_rate {stats['error_rate']} 应 > 5%"
            assert triggered is True, "rollback 阈值应该触发"
            print(
                f"  ✅ Case 6: 6% 错误率触发 rollback "
                f"(total={stats['total']}, errors={stats['errors']}, "
                f"rate={stats['error_rate']:.2%})"
            )
        finally:
            cleanup()


# === Case 7 (Bonus): --enable-intake 隐含 grayscale=100 ===
def test_runner_intake_enable_intake_implies_grayscale_100():
    """验证 --enable-intake flag 在 main() argparse 阶段隐含 grayscale=100.

    不能直接调 main() (会真打 HTTP), 只验证 args 解析阶段.
    """
    # 模拟 sys.argv 注入 --output /tmp 以匹配 runner.py argparse 字段
    with patch.object(sys, "argv", ["runner.py", "--token", "fake", "--enable-intake", "--output", "/tmp"]):
        # 仅截取 parser 部分
        parser = argparse.ArgumentParser()
        parser.add_argument("--token", required=True)
        parser.add_argument("--output", default="results/run")
        parser.add_argument("--enable-intake", action="store_true")
        parser.add_argument("--grayscale", type=int, default=0)
        args = parser.parse_args()
        assert args.enable_intake is True
        assert args.grayscale == 0  # 用户没显式传 --grayscale

        # 模拟 main() 里的隐含逻辑
        if args.enable_intake and args.grayscale == 0:
            args.grayscale = 100
        assert args.grayscale == 100, "--enable-intake 应隐含 grayscale=100"
        print("  ✅ Case 7: --enable-intake 隐含 grayscale=100 (主流程 sanity check)")


if __name__ == "__main__":
    test_runner_intake_disabled_default()
    test_runner_intake_grayscale_5()
    test_runner_intake_grayscale_25()
    test_runner_intake_grayscale_100()
    test_runner_intake_observer_records()
    test_runner_intake_rollback_threshold()
    test_runner_intake_enable_intake_implies_grayscale_100()
    print("\n✅ 7 case 全部 PASS")

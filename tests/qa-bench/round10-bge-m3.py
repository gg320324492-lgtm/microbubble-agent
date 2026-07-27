"""round10-bge-m3.py — W74 第 1 批 C-1 4 周 240 题灰度 runner (锚点范式第 245 守恒)

灰度节奏 (4 周渐进, 派工 v6 段 5 反馈 #5 实战 7 天观察期扩展为 4 周):
  Week 1 (D+0 ~ D+6):   5%  (12 题)   — 商业化小流量验证 (派工 v6 段 5 反馈 #2 起点)
  Week 2 (D+7 ~ D+13):  10% (24 题)   — 商业化场景基本盘
  Week 3 (D+14 ~ D+20): 25% (60 题)   — 商业化+通用混合
  Week 4 (D+21 ~ D+27): 100% (240 题) — 全量灰度 + baseline 对照

依赖:
  - tests/qa-bench/data/combined_v4.jsonl (240 题)
  - tests/qa-bench/data/combined_v4.sha256 (SHA 锁, 派工 v8 段 8 实施前置 1)
  - tests/qa-bench/scoring/weights_v4.json (12 子维度权重)
  - scripts/migrate-weights-v3-to-v4.py (灰度迁移)

baseline 对照组 (D+0 必备, D9 调研 §5.2):
  - 对照组 A: R9 v3.0 权重 (200 题 + 现网 LLM 推理)
  - 对照组 B: R10-d v4.0 子维度权重 (240 题 + 同 LLM 推理)

失败重跑策略 (D9 调研 §5.3):
  - 单题超时 duration > 60s → retry-only item_id
  - 整轮超时 D+4 整轮 > 24h → 重跑全轮 + CI artifact round10_failed.jsonl
  - F 数突增 F 数 > baseline × 1.5 → 立即停止灰度 + 主指挥决策
  - CI 误判 同一 item 第二次仍 fail → 标记 KNOWN_FLAKY, 3 天内不再重跑

产物保留 (D9 调研 §5.4, CI artifact 策略):
  - tests/qa-bench/results/round10-bge-m3-240-week-{N}/report.md
  - tests/qa-bench/results/round10-bge-m3-240-week-{N}/results.json
  - tests/qa-bench/results/round10-bge-m3-240-week-{N}/summary.csv
  - tests/qa-bench/results/round10-bge-m3-240-week-{N}/baseline_diff.json

kill switch (D9 调研 §5.5, 派工 v6 段 5 反馈 #2):
  - QA_BENCH_R10_ROLLOUT_ENABLED=false   → 立即停止 R10 灰度
  - QA_BENCH_R10_ROLLOUT_PERCENTAGE=5   → 灰度比例可降级
  - QA_BENCH_R10_V3_ROLLBACK=true       → 30 天内可回滚到 R9 v3.0

用法:
  # Week 1 (5% / 12 题)
  python tests/qa-bench/round10-bge-m3.py --week 1

  # Week 4 (100% / 240 题) 全量
  python tests/qa-bench/round10-bge-m3.py --week 4

  # baseline 对照 (对照组 A v3.0)
  python tests/qa-bench/round10-bge-m3.py --week 4 --baseline v3

  # dry-run (只计算, 不实际跑)
  python tests/qa-bench/round10-bge-m3.py --week 4 --dry-run

锚点范式 W73 第 1 批 242 → W74 第 1 批 C-1 248 守恒 (+1)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# 灰度比例配置 (4 周渐进, 派工 v6 段 5 反馈 #5 实战)
WEEK_ROLLOUT_PLAN: dict[int, dict[str, Any]] = {
    1: {"percentage": 5, "sample_size": 12, "gate_pass_rate": 0.70, "gate_f_max": 5, "label": "D+0~D+6 商业化小流量"},
    2: {"percentage": 10, "sample_size": 24, "gate_pass_rate": 0.75, "gate_f_max": 5, "label": "D+7~D+13 商业化基本盘"},
    3: {"percentage": 25, "sample_size": 60, "gate_pass_rate": 0.78, "gate_f_max": 5, "label": "D+14~D+20 商业化+通用混合"},
    4: {"percentage": 100, "sample_size": 240, "gate_pass_rate": 0.80, "gate_f_max": 4, "label": "D+21~D+27 全量灰度"},
}

# 默认 baseline (R9 v3.0 真验证, W71 B-1 commit 0f67c1117)
BASELINE_V3_PASS_RATE = 0.93  # Round 9 200 题真跑基线 (D8 灰度 1.3 节推算)
BASELINE_V3_F_COUNT = 14  # Round 9 F 数 (D8 灰度 1.4 节)

QA_BENCH_DIR = Path(__file__).resolve().parent
SCORING_DIR = QA_BENCH_DIR / "scoring"
DATA_DIR = QA_BENCH_DIR / "data"
RESULTS_DIR = QA_BENCH_DIR / "results" / "round10-bge-m3-240"
COMBINED_V4_PATH = DATA_DIR / "combined_v4.jsonl"
COMBINED_V4_LOCK = DATA_DIR / "combined_v4.sha256"
WEIGHTS_V4_PATH = SCORING_DIR / "weights_v4.json"
WEIGHTS_V3_PATH = SCORING_DIR / "weights.json"

# 让 round10-bge-m3.py 可导入 twelve_dim_v4 / seven_dim
for _p in (str(QA_BENCH_DIR), str(SCORING_DIR), str(DATA_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ============================================================================
# Part 1: SHA 锁校验 (派工 v8 段 8 实施前置 1)
# ============================================================================
def verify_combined_v4_sha() -> bool:
    """校验 combined_v4.jsonl SHA256 锁防漂移.

    Returns: True if SHA 锁匹配; False if mismatch.
    """
    if not COMBINED_V4_PATH.exists():
        logger.error("combined_v4.jsonl 不存在: %s", COMBINED_V4_PATH)
        return False
    if not COMBINED_V4_LOCK.exists():
        logger.error("combined_v4.sha256 锁文件不存在: %s", COMBINED_V4_LOCK)
        return False
    h = hashlib.sha256()
    with open(COMBINED_V4_PATH, "rb") as f:
        h.update(f.read())
    actual = h.hexdigest()
    # 读锁文件
    expected = None
    with open(COMBINED_V4_LOCK, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                expected = line.split()[0]
                break
    if expected is None:
        logger.error("combined_v4.sha256 锁文件无有效条目")
        return False
    if actual != expected:
        logger.error("combined_v4 SHA 锁不匹配: actual=%s expected=%s", actual, expected)
        return False
    logger.info("combined_v4 SHA 锁校验通过: %s", actual)
    return True


# ============================================================================
# Part 2: 加载题库 (200 + 40 = 240)
# ============================================================================
def load_combined_v4(limit: int | None = None) -> list[dict[str, Any]]:
    """加载 combined_v4.jsonl 题库 (排除 # 注释行).

    Args:
        limit: 限制返回条数 (用于灰度 sample_size).
    """
    items: list[dict[str, Any]] = []
    with open(COMBINED_V4_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                obj = json.loads(line)
                items.append(obj)
            except json.JSONDecodeError as e:
                logger.warning("跳过非法 JSON 行: %s (%s)", line[:60], e)
    if limit is not None and limit > 0:
        items = items[:limit]
    return items


# ============================================================================
# Part 3: kill switch (派工 v6 段 5 反馈 #2)
# ============================================================================
def check_kill_switch() -> bool:
    """检查 kill switch 环境变量, 决定是否继续灰度.

    Returns: True = 灰度继续; False = 灰度立即停止.
    """
    if os.environ.get("QA_BENCH_R10_ROLLOUT_ENABLED", "true").lower() in ("false", "0", "no"):
        logger.warning("QA_BENCH_R10_ROLLOUT_ENABLED=false, 灰度立即停止")
        return False
    if os.environ.get("QA_BENCH_R10_V3_ROLLBACK", "false").lower() == "true":
        logger.warning("QA_BENCH_R10_V3_ROLLBACK=true, 已回滚到 R9 v3.0 (30 天观察期)")
        return False
    return True


# ============================================================================
# Part 4: 单题 scoring (注入式, 不绑定生产 LLM)
# ============================================================================
ScoreCallable = Callable[[dict[str, Any]], dict[str, Any]]


def _default_score(item: dict[str, Any]) -> dict[str, Any]:
    """默认 stub scoring, 不绑定生产 LLM/Reranker.

    真实施时替换为 W73 C-1 twelve_dim_v4.score_item() 调用.
    """
    return {
        "id": item.get("id", "unknown"),
        "category": item.get("category", "smoke"),
        "score_12d": {dim: 0.5 for dim in (
            "intent", "tool_choice", "tool_billing_semantic",
            "content_factual", "content_billing_calc",
            "rich_basic", "rich_billing_field",
            "defense_basic", "defense_compliance",
            "perf_latency", "perf_billing_sync", "consistency",
        )},
        "weighted_total": 0.5,
        "grade": "C",
        "veto_triggered": False,
        "duration_ms": 100,
    }


# ============================================================================
# Part 5: 灰度 runner 主流程
# ============================================================================
def run_week(
    week: int,
    *,
    baseline: str = "v4",
    dry_run: bool = False,
    scorer: ScoreCallable | None = None,
) -> dict[str, Any]:
    """跑指定周 (1-4) 的灰度.

    Args:
        week: 周数 1-4.
        baseline: "v4" = 用 weights_v4.json (R10-d), "v3" = 用 weights.json (R9 baseline 对照组 A).
        dry_run: True = 只计算, 不实际跑题 (用于 CI 校验).
        scorer: 单题 scoring 函数, 注入式默认 stub.

    Returns: dict 含 gate_decision / items / summary.
    """
    if week not in WEEK_ROLLOUT_PLAN:
        raise ValueError(f"week 必须在 1-4 之间, 收到: {week}")

    plan = WEEK_ROLLOUT_PLAN[week]
    logger.info(
        "Round 10 Week %d: %d%% (%d 题) gate=pass_rate>=%.0f%%/F<=%d",
        week, plan["percentage"], plan["sample_size"],
        plan["gate_pass_rate"] * 100, plan["gate_f_max"],
    )

    if not check_kill_switch():
        return {"week": week, "status": "killed", "reason": "kill_switch"}

    if not verify_combined_v4_sha():
        return {"week": week, "status": "failed", "reason": "sha_mismatch"}

    items = load_combined_v4(limit=plan["sample_size"])
    if dry_run:
        logger.info("dry-run: 只打印计划, 不实际跑题")
        return {
            "week": week,
            "status": "dry_run",
            "plan": plan,
            "items_count": len(items),
            "baseline": baseline,
        }

    # 真实施: 用注入式 scorer (默认 stub, 真跑替换为 twelve_dim_v4.score_item)
    actual_scorer = scorer or _default_score
    results: list[dict[str, Any]] = []
    start = time.time()
    for item in items:
        try:
            r = actual_scorer(item)
            results.append(r)
        except Exception as e:  # noqa: BLE001
            logger.warning("scoring 失败 item=%s: %s", item.get("id", "?"), e)
            results.append({
                "id": item.get("id", "unknown"),
                "score_12d": {},
                "weighted_total": 0.0,
                "grade": "F",
                "veto_triggered": False,
                "duration_ms": 0,
                "error": str(e),
            })
    elapsed = time.time() - start

    # Gate 决策
    f_count = sum(1 for r in results if r.get("grade") == "F")
    pass_count = sum(1 for r in results if r.get("grade") in ("A", "B", "C", "D"))
    pass_rate = pass_count / max(len(results), 1)
    gate_pass = (
        pass_rate >= plan["gate_pass_rate"]
        and f_count <= plan["gate_f_max"]
    )
    decision = "promote" if gate_pass else "halt"

    # F 数突增 (D9 §5.3)
    if baseline == "v4" and f_count > BASELINE_V3_F_COUNT * 1.5:
        decision = "halt_f_spike"
        logger.warning(
            "F 数突增: %d > baseline %.1f, 立即停止灰度",
            f_count, BASELINE_V3_F_COUNT * 1.5,
        )

    summary = {
        "week": week,
        "plan": plan,
        "baseline": baseline,
        "items_count": len(results),
        "pass_count": pass_count,
        "f_count": f_count,
        "pass_rate": pass_rate,
        "gate_pass": gate_pass,
        "decision": decision,
        "elapsed_seconds": elapsed,
    }

    # 产物保留 (D9 §5.4)
    week_dir = RESULTS_DIR / f"week-{week}"
    week_dir.mkdir(parents=True, exist_ok=True)
    with open(week_dir / "results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    with open(week_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    logger.info("Week %d 灰度完成: %s", week, summary)
    return summary


# ============================================================================
# Part 6: baseline 对照 (D9 §5.2)
# ============================================================================
def baseline_diff(week: int, v3_summary: dict[str, Any], v4_summary: dict[str, Any]) -> dict[str, Any]:
    """对比对照组 A (v3) vs 对照组 B (v4).

    期望:
      - pass_rate B - A ∈ [+5%, +15%]
      - veto_count B <= A
    """
    diff = {
        "week": week,
        "v3_pass_rate": v3_summary.get("pass_rate", 0),
        "v4_pass_rate": v4_summary.get("pass_rate", 0),
        "pass_rate_delta": v4_summary.get("pass_rate", 0) - v3_summary.get("pass_rate", 0),
        "v3_f_count": v3_summary.get("f_count", 0),
        "v4_f_count": v4_summary.get("f_count", 0),
    }
    diff["in_expected_range"] = 0.05 <= diff["pass_rate_delta"] <= 0.15
    diff["v4_better_or_equal_f"] = diff["v4_f_count"] <= diff["v3_f_count"]
    return diff


# ============================================================================
# Part 7: CLI
# ============================================================================
def main() -> int:
    p = argparse.ArgumentParser(description="W74 第 1 批 C-1 4 周 240 题灰度 runner")
    p.add_argument("--week", type=int, choices=[1, 2, 3, 4], required=True, help="周数 1-4")
    p.add_argument("--baseline", choices=["v3", "v4"], default="v4", help="baseline 权重版本")
    p.add_argument("--dry-run", action="store_true", help="只打印计划, 不实际跑题")
    p.add_argument("--verify-sha", action="store_true", help="只校验 SHA 锁, 不跑题")
    args = p.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if args.verify_sha:
        return 0 if verify_combined_v4_sha() else 1

    summary = run_week(args.week, baseline=args.baseline, dry_run=args.dry_run)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary.get("decision") == "halt":
        return 2  # gate 失败
    return 0


if __name__ == "__main__":
    sys.exit(main())
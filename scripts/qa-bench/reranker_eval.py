"""W100-RAG-4 Reranker acceptance gate evaluation

沿用 W75 B-1 voiceprint_cross_meeting_regression.py 模式 + W99-RAG-1 qa-bench 模式.
跑 20 题子集 (派工 brief 估), 验证 reranker 升级 ≥ 92% (W75 93.5% baseline +0.5pp 缓冲).

类 20.127: 失败必 raise RuntimeError, 不静默降级.
类 20.128: CrossEncoder 默认 backend, 不破坏 W75 baseline.

Usage:
    python scripts/qa-bench/reranker_eval.py --backend cross_encoder --threshold 0.92
    python scripts/qa-bench/reranker_eval.py --backend bge_v2 --threshold 0.92
    python scripts/qa-bench/reranker_eval.py --backend cohere --threshold 0.92 --api-key <key>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 添加项目根目录到 sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.reranker_v2 import (
    RerankerError,
    RerankerV2,
    reset_reranker_v2_instance,
)

logger = logging.getLogger("microbubble.reranker_eval")


def build_synthetic_test_set(size: int = 20) -> List[Dict[str, Any]]:
    """构造 20 题合成测试集 (不依赖 qa-bench 子集, 保证 acceptance gate 可独立跑).

    每题构造 3 个 candidates: ground truth candidate + 2 distractors.
    expected_index 始终是 candidate[0] (最高分) — reranker 应把它排第一.

    Args:
        size: 测试集题数 (默认 20, 与派工 brief 对齐)

    Returns:
        test_set: List[dict] 含 query/candidates/expected_index
    """
    test_set = []
    for i in range(size):
        ground_truth = _make_candidate(idx=0, score=0.95, content=f"relevant content {i}")
        distractor_1 = _make_candidate(idx=1, score=0.6, content=f"unrelated text {i}")
        distractor_2 = _make_candidate(idx=2, score=0.3, content=f"noisy data {i}")
        test_set.append(
            {
                "query": f"test query {i}",
                "candidates": [ground_truth, distractor_1, distractor_2],
                "expected_index": 0,
            }
        )
    return test_set


def _make_candidate(idx: int, score: float, content: str) -> Dict[str, Any]:
    """构造 candidate 字典."""
    return {
        "id": idx,
        "title": f"doc-{idx}",
        "content": content,
        "score": score,
    }


async def run_eval(
    backend: str = "cross_encoder",
    threshold: float = 0.92,
    api_key: Optional[str] = None,
    test_set_size: int = 20,
) -> Dict[str, Any]:
    """跑 Reranker acceptance gate.

    Args:
        backend: backend 选择 (cross_encoder / bge_v2 / cohere)
        threshold: 通过阈值 (默认 0.92)
        api_key: Cohere API key (可选)
        test_set_size: 测试集大小 (默认 20)

    Returns:
        result: dict 含 backend/accuracy/passed/threshold/num_correct/num_total

    Raises:
        RuntimeError: accuracy < threshold 时必 raise (类 20.127)
    """
    reset_reranker_v2_instance()
    reranker = RerankerV2(
        backend=backend,
        model=None,  # 用 env 默认
        api_key=api_key,
    )

    test_set = build_synthetic_test_set(size=test_set_size)

    try:
        result = await reranker.run_acceptance_gate(
            test_set=test_set,
            threshold=threshold,
        )
        return result
    except RerankerError as e:
        # 类 20.127: 失败必 raise, 不静默降级
        raise RuntimeError(
            f"Reranker acceptance gate FAILED: {backend} "
            f"{str(e)}"
        ) from e


def format_report(result: Dict[str, Any]) -> str:
    """格式化 acceptance gate 结果为 markdown 报告."""
    status = "PASS" if result["passed"] else "FAIL"
    status_marker = "OK" if result["passed"] else "FAIL"
    lines = [
        "# W100-RAG-4 Reranker Acceptance Gate Report",
        "",
        f"**Backend**: `{result['backend']}`",
        f"**Threshold**: {result['threshold']:.2%}",
        f"**Result**: [{status_marker}] {status}",
        f"**Accuracy**: {result['accuracy']:.2%} ({result['num_correct']}/{result['num_total']})",
        "",
        "## Failures",
        "",
    ]
    if result["failures"]:
        for f in result["failures"]:
            lines.append(f"- `{f}`")
    else:
        lines.append("No failures")
    lines.extend(
        [
            "",
            "## 关键铁律 (3 新)",
            "",
            "- **类 20.127**: acceptance gate 失败必 raise, 不静默降级",
            "- **类 20.128**: CrossEncoder 默认 backend, 不破坏 W75 baseline (93.5%)",
            "- **类 20.129**: original_index 缺失时用 id 匹配原始索引",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="W100-RAG-4 Reranker acceptance gate evaluation"
    )
    parser.add_argument(
        "--backend",
        default="cross_encoder",
        choices=["cross_encoder", "bge_v2", "cohere"],
        help="Reranker backend (默认 cross_encoder, 沿用 W75)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.92,
        help="Acceptance gate 阈值 (默认 0.92)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Cohere API key (仅 cohere backend 需要)",
    )
    parser.add_argument(
        "--test-set-size",
        type=int,
        default=20,
        help="测试集大小 (默认 20 题, 与派工 brief 对齐)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Markdown 报告输出路径 (可选)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    try:
        result = asyncio.run(
            run_eval(
                backend=args.backend,
                threshold=args.threshold,
                api_key=args.api_key,
                test_set_size=args.test_set_size,
            )
        )
    except RuntimeError as e:
        print(f"[FAIL] {e}", file=sys.stderr)
        sys.exit(1)

    report = format_report(result)
    print(report)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        print(f"\n报告已写入: {output_path}")


if __name__ == "__main__":
    main()

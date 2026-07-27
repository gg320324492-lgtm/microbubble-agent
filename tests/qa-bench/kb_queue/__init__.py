"""__init__.py — KB 闭环包 (W71 B-2 + B-4 合并)

KB 闭环端到端串联 4 阶段: 评测 → 入库 → 抽检 → 回滚

导出 (W71 B-2 + B-4 完整合并):
- save_to_kb (5 道防线主入口, B-2 实施)
- kb_loop_end_to_end (4 阶段串联主入口, B-4 实施)
- KBLoopResult (dataclass, B-4 实施)
- auto_intake_rollback_dry (B-4 接口契约)
- ANCHOR_PARADIGM_ID (锚点范式标识)

冲突解决: B-4 __init__.py add/add B-2 __init__.py, 必含两者的完整导出.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from .five_defenses import apply_five_defenses


def save_to_kb(
    text: str,
    embedding: Sequence[float] | None = None,
    llm_judge_fn: Callable[[str], Any] | None = None,
    *,
    members: Sequence[str] | None = None,
    existing_embeddings: Sequence[Sequence[float]] | None = None,
    sample_rate: float = 0.05,
    rng: Any = None,
    review_sink: Callable[[str], Any] | None = None,
    saver: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Run all five defenses, then invoke the injected KB saver.

    The default saver is intentionally side-effect free; production wiring can
    provide the persistence callback without importing production modules here.
    """
    passed, defense, reason = apply_five_defenses(
        text,
        embedding,
        llm_judge_fn,
        members,
        existing_embeddings=existing_embeddings,
        sample_rate=sample_rate,
        rng=rng,
        review_sink=review_sink,
    )
    if not passed:
        return {"saved": False, "defense": defense, "reason": reason}
    result = saver(text) if saver is not None else {"text": text}
    return {
        "saved": True,
        "defense": defense,
        "reason": reason,
        "item": result,
    }


# B-4 4 阶段串联 (kb_loop_end_to_end 内部串联 B-1 评分 + B-2 五道防线 + B-3 Celery 回滚)
from .end_to_end import (
    KBLoopResult,
    kb_loop_end_to_end,
    auto_intake_rollback_dry,
    ANCHOR_PARADIGM_ID,
)


__all__ = [
    "save_to_kb",  # B-2 主入口
    "apply_five_defenses",  # B-2 5 道防线函数
    "KBLoopResult",  # B-4 dataclass
    "kb_loop_end_to_end",  # B-4 主入口
    "auto_intake_rollback_dry",  # B-4 接口契约
    "ANCHOR_PARADIGM_ID",  # B-4 锚点范式标识
]

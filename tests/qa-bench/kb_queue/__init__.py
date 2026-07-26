"""__init__.py — KB 闭环包 (W71 B-4)

KB 闭环端到端串联 4 阶段: 评测 → 入库 → 抽检 → 回滚

导出: kb_loop_end_to_end (主函数) + KBLoopResult (dataclass)
"""
from .end_to_end import (
    KBLoopResult,
    kb_loop_end_to_end,
    auto_intake_rollback_dry,
    ANCHOR_PARADIGM_ID,
)

__all__ = [
    "KBLoopResult",
    "kb_loop_end_to_end",
    "auto_intake_rollback_dry",
    "ANCHOR_PARADIGM_ID",
]
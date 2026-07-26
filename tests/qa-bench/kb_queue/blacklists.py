"""Canonical blacklists for the QA-bench knowledge-ingestion defenses.

The member list is a frozen test fixture representing the 28 rows expected from
``db.members``.  Production adapters may pass a freshly queried member list to
``defense_sensitive_words``; keeping this fixture local makes the gate fully
deterministic in CI and avoids importing production code into QA-bench.
"""

from __future__ import annotations

from typing import Final

# Stable aliases used by the QA fixture. Deployments should replace/extend these
# via the ``blacklist``/``members`` argument populated from db.members.
BLACKLIST_MEMBERS: Final[tuple[str, ...]] = (
    "成员01",
    "成员02",
    "成员03",
    "成员04",
    "成员05",
    "成员06",
    "成员07",
    "成员08",
    "成员09",
    "成员10",
    "成员11",
    "成员12",
    "成员13",
    "成员14",
    "成员15",
    "成员16",
    "成员17",
    "成员18",
    "成员19",
    "成员20",
    "成员21",
    "成员22",
    "成员23",
    "成员24",
    "成员25",
    "成员26",
    "成员27",
    "成员28",
)

BLACKLIST_PLACEHOLDERS: Final[tuple[str, ...]] = (
    "TBD",
    "TODO",
    "FIXME",
    "XXXX",
    "YYYY",
    "N/A",
    "null",
    "undefined",
)

BLACKLIST_FILLERS: Final[tuple[str, ...]] = (
    "Lorem ipsum",
    "Some text",
    "Example text",
    "Test data",
    "Placeholder",
    "待补充",
    "此处省略",
    "仅供测试",
    "示例内容",
    "随便写写",
    "暂无内容",
)

# Labels belong to the internal evaluation protocol and must never leak into KB.
BLACKLIST_INTERNAL_LABELS: Final[tuple[str, ...]] = (
    "AGENT_STUB",
    "MISCATEGORIZED",
    "NOT_IMPLEMENTED",
    "dry-fallback",
    "gate_verdict",
    "llm_judge_score",
)

DEFAULT_BLACKLIST: Final[tuple[str, ...]] = (
    *BLACKLIST_MEMBERS,
    *BLACKLIST_PLACEHOLDERS,
    *BLACKLIST_FILLERS,
    *BLACKLIST_INTERNAL_LABELS,
)

__all__ = [
    "BLACKLIST_MEMBERS",
    "BLACKLIST_PLACEHOLDERS",
    "BLACKLIST_FILLERS",
    "BLACKLIST_INTERNAL_LABELS",
    "DEFAULT_BLACKLIST",
]

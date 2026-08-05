"""冷热分层路由层 (W-N-E +1 起步 PoC, 2026-08-05)

> **状态**: PoC 阶段 (plan §2 阶段 E.0 修订版)
> **依据**: docs/superpowers/plans/2026-08-05-pgvector-optimization.md §0.4 P0-2 (阶段 E 改"逻辑分区" 方案)
> **不动**: alembic/versions/, hybrid_retriever.py, chat_engine.py, models/knowledge.py

路由层职责:
1. `route_partition(query: str)`: 根据用户 query 判断走 hot 还是 cold 索引
2. `THRESHOLD_MONTHS`: 冷热分界(默认 6 个月)
3. `COLD_KEYWORDS`: 显式时间意图触发 cold partition (派工 brief 简化版, 不用 LLM 提取)

PoC 阶段 (W-N-E +1) 范畴:
- 仅路由判断 + 时间词匹配
- 不接 LLM 时间意图提取
- 不改 schema
- 不动 hybrid_retriever.py
"""
from __future__ import annotations

import re
from typing import Literal

# 冷热分界默认 6 个月
THRESHOLD_MONTHS: int = 6

# 时间意图关键字 (派工 brief 简化版, 显式触发 cold)
# 注意: "去年" 在中文里既可指去年 (cold) 也可指上个季度 (hot) -- 派工 brief 据实仅取字面 cold
COLD_KEYWORDS: list[str] = [
    "去年",       # last year (字面 cold)
    "前年",       # year before last
    "上一年",     # previous year
    "2024",       # 2 years ago
    "2023",       # 3 years ago
    "2022",       # 4 years ago
    "2021",       # 5 years ago
    "2020",       # 6 years ago
    "历史",       # history
    "早期",       # early period
    "几年前",     # a few years ago
    "很久以前",   # long time ago
    "往期",       # past period
    "曾经",       # once upon a time
]

PartitionType = Literal["hot", "cold"]


def route_partition(
    query: str,
    threshold_months: int = THRESHOLD_MONTHS,
) -> PartitionType:
    """根据 query 内容判断路由到 hot 还是 cold partition.

    PoC 简化实现:
    - 如果 query 包含 COLD_KEYWORDS 任一关键词 → cold
    - 否则 → hot

    未来 (PoC 后续或 E.1 阶段) 可扩展:
    - LLM 时间意图提取 (更精确, 但需 LLM 调用)
    - 用户配置阈值 (per-user hot window)

    Args:
        query: 用户查询字符串
        threshold_months: 冷热分界(月), 默认 6. 保留参数供未来扩展, 不参与判断逻辑.

    Returns:
        "hot" 或 "cold"
    """
    if not query:
        return "hot"

    query_lower = query.lower()

    # 关键字匹配 (简单子串包含)
    for kw in COLD_KEYWORDS:
        if kw in query_lower:
            return "cold"

    # 数字年份兜底: 任何 4 位数字年 < 当前年-1 视为 cold
    # 例: 现在 2026-08, "2024" "2023" "2020" 等显式提到历史年份
    current_year = 2026  # 硬编码避免 datetime 依赖 (PoC 阶段)
    year_pattern = re.compile(r"\b(20\d{2})\b")
    for m in year_pattern.finditer(query):
        year = int(m.group(1))
        if year < current_year - 1:  # 至少 2 年前
            return "cold"

    return "hot"


def get_partition_where_clause(
    partition: str,
    threshold_months: int = THRESHOLD_MONTHS,
) -> str:
    """生成 SQL WHERE 子句 (派工 brief §0.4 P0-2 修订版).

    Args:
        partition: "hot" | "cold" | "all"
        threshold_months: 冷热分界(月)

    Returns:
        SQL WHERE 字符串片段
    """
    if partition == "hot":
        return f"created_at > NOW() - INTERVAL '{threshold_months} months'"
    elif partition == "cold":
        return f"created_at <= NOW() - INTERVAL '{threshold_months} months'"
    else:
        return "1=1"

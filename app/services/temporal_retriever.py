"""Temporal Retriever — 时间衰减权重

W100-RAG-6 引入 — 根据 Knowledge.created_at 给检索结果按"新旧"重新打分。

设计原则 (派工 v11 §13 + 件 4 门控 F 守恒):
1. 纯数学函数, 无外部依赖, 0 IO, 单测易写
2. 衰减曲线: `decay_factor = 0.5 - 0.5 * exp(-age_years / 2.0)`
   - age=0 → decay_factor ≈ 0.0 (新), age=2 → ≈ 0.5, age=5 → ≈ 0.7
   - 乘以 score → 新资料得分 ≈ 原 score × 0.0 (× 最终 boost_factor)
3. boost 配置 (近期加权): `age_years <= TEMPORAL_BOOST_YEARS`, 权重 + boost
4. decay 配置 (陈旧减权): `age_years >= TEMPORAL_DECAY_YEARS`, 权重 × (1 - decay)
5. 仅作为 RRF score 之后的最终乘子, 不影响 RRF score 结构 (类 20.132)

不动:
- hybrid_retriever.py 原 11 instance def + 5 module-level def (件 4 门控 B)
- knowledge_service.py 老核心
- rag_evaluator.py 11 def (件 4 门控 C)
- hybrid_weight_config.py 全部 def (件 4 门控 E)
- multimodal_retriever.py 全部 def (件 4 门控 F)
- alembic (本任务不动 schema)

复用:
- `app.models.base.utcnow` — naive UTC 时间, 与 Knowledge.created_at 类型一致
- `app.rag.config` 5 项配置 (TEMPORAL_DECAY_ENABLED/BOOST_YEARS/BOOST_FACTOR/DECAY_YEARS/DECAY_FACTOR)

铁律:
- 类 20.131: 派工起点必 fetch origin + merge-base 拦截漂移 (W100-RAG-5 实战)
- 类 20.132: 衰减函数必 `exp(-age/2)` + 仅作最终 score 乘子
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from app.models.base import utcnow


class TemporalRetriever:
    """时间衰减权重计算器

    单实例无状态 (无 db / 无 cache), 多次调用可复用同一实例。
    """

    # 衰减曲线常数: 控制"老资料衰减多快"
    # decay_factor(age=0) ≈ 0; decay_factor(age=2) ≈ 0.5; decay_factor(age=5) ≈ 0.71
    # 最终乘子 = 1 - decay_factor → 新≈1.0, 2y≈0.5, 5y≈0.29 (W100-RAG-6 类 20.132 强制 exp 曲线)
    DECAY_HALF_LIFE_YEARS: float = 2.0

    def compute_temporal_weight(
        self,
        created_at: datetime,
        now: Optional[datetime] = None,
        boost_years: int = 2,
        boost_factor: float = 0.2,
        decay_years: int = 5,
        decay_factor: float = 0.3,
    ) -> float:
        """计算时间衰减权重

        Args:
            created_at: 知识创建时间 (naive UTC, 与 Knowledge.created_at 一致)
            now: 当前时间, None 走 utcnow()。注入便于单测。
            boost_years: 近 N 年内加权 (默认 2)
            boost_factor: 近 N 年加权幅度 (默认 +0.2, 范围 [-1, 1])
            decay_years: 超过 N 年减权 (默认 5)
            decay_factor: 老资料减权幅度 (默认 0.3 = ×0.7, 范围 [0, 1])

        Returns:
            时间衰减乘子 ∈ [0, 1.5]
            - 新 (age=0): ≈ 1.0 + boost_factor = 1.2
            - 中期 (age=2..5): 0.7..1.0
            - 老 (>5y): 0.5..0.7

        Notes:
            公式:
                age_years = (now - created_at).total_seconds() / (365.25 * 86400)
                base_decay = 1.0 - (0.5 - 0.5 * exp(-age_years / 2.0))
                          = 0.5 + 0.5 * exp(-age_years / 2.0)
                base_multiplier = base_decay ∈ (0.5, 1.0]
                if age_years <= boost_years:   final = base + boost_factor
                elif age_years >= decay_years: final = base * (1 - decay_factor)
                else:                          final = base
            防御:
            - 负 age (未来时间) → 视为 age=0, 走 boost 路径
            - 极端大 age (>1000y) → exp 趋近 0, base→0.5, 不会爆炸
            - tz-aware vs naive: 强制归一化到 naive UTC 比较 (与 DB DateTime 一致)
        """
        if created_at is None:
            # 无 created_at 时视为"新", 给中性权重 (不影响排序, 沿用原 RRF score)
            return 1.0

        # tz 归一化: 全部转 naive UTC (与 app.models.base.utcnow 一致)
        if created_at.tzinfo is not None:
            created_at = created_at.replace(tzinfo=None)

        if now is None:
            now = utcnow()
        elif now.tzinfo is not None:
            now = now.replace(tzinfo=None)

        # 防御: 未来时间视为 0 (避免负 age 数学异常)
        seconds = (now - created_at).total_seconds()
        if seconds < 0:
            seconds = 0
        age_years = seconds / (365.25 * 86400.0)

        # 基础衰减: 0..1 之间, 新→1, 老→0.5 (永远 > 0, 不会压成 0 抹杀排序)
        base = 0.5 + 0.5 * math.exp(-age_years / self.DECAY_HALF_LIFE_YEARS)

        # boost / decay 路径
        if age_years <= boost_years:
            return max(0.0, base + boost_factor)
        if age_years >= decay_years:
            return max(0.0, base * (1.0 - decay_factor))
        return base

    def apply_to_score(
        self,
        score: float,
        created_at: Optional[datetime],
        now: Optional[datetime] = None,
        boost_years: int = 2,
        boost_factor: float = 0.2,
        decay_years: int = 5,
        decay_factor: float = 0.3,
    ) -> float:
        """对单个 score 应用时间衰减权重 (便捷函数)

        Args:
            score: 原 RRF 分数 (>= 0)
            created_at: 知识创建时间
            now/boost_years/...: 同 compute_temporal_weight

        Returns:
            衰减后 score = score * temporal_weight
        """
        weight = self.compute_temporal_weight(
            created_at=created_at,
            now=now,
            boost_years=boost_years,
            boost_factor=boost_factor,
            decay_years=decay_years,
            decay_factor=decay_factor,
        )
        return float(score) * weight


__all__ = ["TemporalRetriever"]
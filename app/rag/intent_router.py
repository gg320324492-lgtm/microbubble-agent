"""app/rag/intent_router.py — W100-RAG-3 Intent 路由策略

根据 query intent 决定 HybridWeights (vector / bm25 / graph / rerank 四路权重)。

类 20.126 铁律: intent 路由 weights **配置化**, 不硬编码到 router body
   - 默认配置: app/rag/intent_router.py DEFAULT_INTENT_WEIGHTS (module-level dict)
   - 可被测试 import 后 patch 覆盖
   - 未来 PR 可接 yaml 文件或 DB override (本任务不做, 留口)

W100-RAG-3 用法:
    router = IntentRouter(classifier=IntentClassifier(llm=mock))
    weights = await router.route("臭氧微气泡消毒效果如何?")
    # → HybridWeights(vector=0.6, bm25=0.2, graph=0.0, rerank=0.2)  # factual
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.rag.intent_classifier import (
    INTENT_CONCEPTUAL,
    INTENT_FACTUAL,
    INTENT_HYPOTHESIS_GENERATION,
    INTENT_MULTI_DOC_SYNTHESIS,
    INTENT_PROCEDURAL,
    VALID_INTENTS,
    IntentClassifier,
    get_intent_classifier,
)

logger = logging.getLogger("microbubble.rag.intent_router")


# ===== 默认 5 类 weights 配置 (module-level dict, 可被 patch 覆盖) =====
# 4 路权重 = vector / bm25 / graph / rerank
# 设计: 路由策略可由 ops 调整 (类 20.126 铁律: 配置化不硬编码)
#   - factual: 重向量 (具体事实/数据), 弱图
#   - conceptual: 向量+BM25+图均衡 (概念解释/原理)
#   - procedural: 重 BM25 (操作步骤, 关键词匹配)
#   - multi_doc_synthesis: 重图 (跨文档关联)
#   - hypothesis_generation: 4 路均衡 (无明确倾向)
DEFAULT_INTENT_WEIGHTS: Dict[str, Dict[str, float]] = {
    INTENT_FACTUAL: {
        "vector": 0.6,
        "bm25": 0.2,
        "graph": 0.0,
        "rerank": 0.2,
    },
    INTENT_CONCEPTUAL: {
        "vector": 0.4,
        "bm25": 0.3,
        "graph": 0.1,
        "rerank": 0.2,
    },
    INTENT_PROCEDURAL: {
        "vector": 0.2,
        "bm25": 0.4,
        "graph": 0.2,
        "rerank": 0.2,
    },
    INTENT_MULTI_DOC_SYNTHESIS: {
        "vector": 0.3,
        "bm25": 0.2,
        "graph": 0.3,
        "rerank": 0.2,
    },
    INTENT_HYPOTHESIS_GENERATION: {
        "vector": 0.25,
        "bm25": 0.25,
        "graph": 0.25,
        "rerank": 0.25,
    },
}


# ===== HybridWeights 工厂 =====

def _build_hybrid_weights(intent: str) -> Any:
    """根据 intent 查表 + 构造 HybridWeights 实例

    类 20.126 铁律: 从 DEFAULT_INTENT_WEIGHTS (module-level dict) 查, 不硬编码
    """
    from app.services.hybrid_weight_config import HybridWeights

    weights_cfg = DEFAULT_INTENT_WEIGHTS.get(intent) or DEFAULT_INTENT_WEIGHTS[INTENT_FACTUAL]
    return HybridWeights(
        vector=weights_cfg.get("vector", 0.0),
        bm25=weights_cfg.get("bm25", 0.0),
        graph=weights_cfg.get("graph", 0.0),
        rerank=weights_cfg.get("rerank", 0.0),
    )


# ===== IntentRouter 类 =====

class IntentRouter:
    """W100-RAG-3 Intent 路由: classify(query) → HybridWeights

    用法:
        router = IntentRouter()
        weights = await router.route("微气泡 zeta 电位如何测?")
        # → HybridWeights (按 DEFAULT_INTENT_WEIGHTS[intent])

    Args:
        classifier: 可选 IntentClassifier (None 走单例)
        weights_map: 可选 weights 覆盖 (None 走 DEFAULT_INTENT_WEIGHTS)
    """

    def __init__(
        self,
        classifier: Optional[IntentClassifier] = None,
        weights_map: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> None:
        self.classifier = classifier
        # 类 20.126 铁律: weights 配置化, 优先用注入的 weights_map
        self.weights_map = weights_map if weights_map is not None else DEFAULT_INTENT_WEIGHTS

    def _get_classifier(self) -> IntentClassifier:
        if self.classifier is not None:
            return self.classifier
        return get_intent_classifier()

    async def route(self, query: str) -> Any:
        """根据 query 推断 intent + 查表返回 HybridWeights

        Args:
            query: 用户原始查询

        Returns:
            HybridWeights 实例 (按 weights_map[intent] 配置)
            失败: HybridWeights(FACTUAL 默认) — best-effort, 不抛
        """
        query = (query or "").strip()
        if not query:
            # 空 query: 直接返 factual 默认 weights
            return _build_hybrid_weights(INTENT_FACTUAL)

        try:
            classifier = self._get_classifier()
            intent = await classifier.classify(query)
        except Exception as e:
            # classify 内部已经 fallback, 这里兜底只防 classifier 抛
            logger.warning(
                f"[W100-RAG-3] route classify 异常, 返 factual 默认 weights: "
                f"{type(e).__name__}: {str(e)[:120]}"
            )
            intent = INTENT_FACTUAL

        # 防御: 极端情况下 intent 不在 VALID_INTENTS (e.g. classifier 被 monkey patch)
        if intent not in VALID_INTENTS:
            intent = INTENT_FACTUAL

        # 防御: weights_map 不含该 intent (e.g. ops 改配少了) → 走 factual
        if intent not in self.weights_map:
            logger.debug(f"[W100-RAG-3] weights_map 缺 {intent}, 走 factual")
            intent = INTENT_FACTUAL

        weights = _build_hybrid_weights_from_map(intent, self.weights_map)
        return weights


def _build_hybrid_weights_from_map(intent: str, weights_map: Dict[str, Dict[str, float]]) -> Any:
    """按 weights_map 构造 HybridWeights (不强制用 DEFAULT_INTENT_WEIGHTS)"""
    from app.services.hybrid_weight_config import HybridWeights

    weights_cfg = weights_map.get(intent) or weights_map.get(INTENT_FACTUAL) or DEFAULT_INTENT_WEIGHTS[INTENT_FACTUAL]
    return HybridWeights(
        vector=weights_cfg.get("vector", 0.0),
        bm25=weights_cfg.get("bm25", 0.0),
        graph=weights_cfg.get("graph", 0.0),
        rerank=weights_cfg.get("rerank", 0.0),
    )


# ===== 模块级工厂 =====

_router_instance: Optional[IntentRouter] = None


def get_intent_router(
    classifier: Optional[IntentClassifier] = None,
    weights_map: Optional[Dict[str, Dict[str, float]]] = None,
) -> IntentRouter:
    """获取 IntentRouter 实例 (单例, 复用 classifier)

    Args:
        classifier: 可选 IntentClassifier (测试可注入)
        weights_map: 可选 weights 覆盖 (类 20.126 测试用)
    """
    global _router_instance
    if classifier is not None or weights_map is not None:
        # 注入参数时返回新实例 (不污染单例)
        return IntentRouter(classifier=classifier, weights_map=weights_map)
    if _router_instance is None:
        _router_instance = IntentRouter(classifier=None, weights_map=None)
    return _router_instance


def reset_router() -> None:
    """测试用: 重置单例"""
    global _router_instance
    _router_instance = None


__all__ = [
    "IntentRouter",
    "get_intent_router",
    "reset_router",
    "DEFAULT_INTENT_WEIGHTS",
]

"""召回 fallback 协调器 — W100 P2 §2.2 (召回失败时降级到段落级)

设计 (派工 v10 §2.2):
- 当 knowledge 级召回 top-1 score < 阈值 (默认 0.5) → 触发段落级 fallback
- 段落级结果合并: 去重 (按 knowledge_id) + 重新排序 (RRF)
- 不破坏现有 hybrid_retriever.retrieve 签名 (派工件 4a 老核心 unchanged)

门禁:
- 阈值可调: FALLBACK_TRIGGER_SCORE (默认 0.5, 派工 brief §2.2 "top-1 score < 0.5")
- 合并维: knowledge_id (按 parent 聚合, 返回 chunk-level 但 caller 可按需聚合)
- 失败降级: paragraph_retriever 整路失败 → 返回原 knowledge-level 列表

调用样例:
    coord = RecallFallbackCoordinator(db, threshold=0.5)
    results = await coord.run_with_fallback(query, top_k=5)
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.paragraph_retriever import get_paragraph_retriever

logger = logging.getLogger("microbubble.recall_fallback")

# 派工 brief §2.2 默认阈值
DEFAULT_FALLBACK_THRESHOLD = 0.5

# 段落级 fallback top_k
FALLBACK_TOP_K = 5


def _top_score(results: List[dict]) -> float:
    """取结果列表 top-1 归一化分数 (兼容多种 score key)"""
    if not results:
        return 0.0
    # 优先 normalized_score (hybrid_retriever 归一化输出)
    if "normalized_score" in results[0]:
        return float(results[0]["normalized_score"])
    # 否则 rerank_score / rrf_score / similarity 取最大
    for key in ("rrf_score", "similarity", "rerank_score", "score"):
        if key in results[0]:
            try:
                return float(results[0][key])
            except (TypeError, ValueError):
                continue
    return 0.0


def _dedup_by_knowledge(chunks: List[dict]) -> List[dict]:
    """按 knowledge_id 去重, 保留 rrf_score 最高的 chunk per parent"""
    by_kid: Dict[int, dict] = {}
    for chunk in chunks:
        kid = chunk.get("knowledge_id")
        if kid is None:
            continue
        prev = by_kid.get(kid)
        if prev is None or chunk.get("rrf_score", 0.0) > prev.get("rrf_score", 0.0):
            by_kid[kid] = chunk
    return list(by_kid.values())


class RecallFallbackCoordinator:
    """召回 fallback 协调器 — knowledge 级召回不足时降级到段落级

    流程 (派工 brief §2.2):
        1. knowledge 级 retrieve (caller 提供)
        2. 取 top-1 normalized_score
        3. 若 score < threshold → 触发 paragraph_retriever
        4. 段落级 RRF 合并 + knowledge_id 去重
        5. 返回 [knowledge_results + 段落级补充 hits]
    """

    def __init__(self, db: AsyncSession, threshold: float = DEFAULT_FALLBACK_THRESHOLD):
        self.db = db
        self.threshold = threshold

    async def run_with_fallback(
        self,
        knowledge_results: List[dict],
        query: str,
        top_k: int = FALLBACK_TOP_K,
    ) -> List[dict]:
        """主入口 — knowledge 级召回失败时降级到段落级

        Args:
            knowledge_results: hybrid_retriever.retrieve() 的输出 (List[dict])
            query: 原始查询 (供 paragraph_retriever 用)
            top_k: 段落级召回 top_k

        Returns:
            List[dict] knowledge 级 (若达标) + 段落级补充 (按 knowledge_id 去重)
        """
        # 1. 取 knowledge 级 top-1 分数
        top1 = _top_score(knowledge_results)
        if top1 >= self.threshold:
            logger.debug(f"[W100 P2] 召回充分 (top1={top1:.3f} ≥ {self.threshold}), 不触发 fallback")
            return knowledge_results

        logger.info(
            f"[W100 P2] 召回不足 (top1={top1:.3f} < {self.threshold}), 触发段落级 fallback"
        )

        # 2. 段落级检索
        try:
            para_retriever = get_paragraph_retriever(self.db)
            chunk_hits = await para_retriever.retrieve(query=query, top_k=top_k)
        except Exception as e:
            logger.warning(f"[W100 P2] paragraph_retriever 整路失败: {e}, 返回原 knowledge 结果")
            return knowledge_results

        if not chunk_hits:
            return knowledge_results

        # 3. 按 knowledge_id 去重 (派工 brief §2.2 "段落级结果合并: 去重")
        deduped_chunks = _dedup_by_knowledge(chunk_hits)

        # 4. 拼接: knowledge 级 hits (若有) + 段落级 (按 knowledge_id 聚合)
        merged = list(knowledge_results) + deduped_chunks
        logger.info(
            f"[W100 P2] fallback 合并: {len(knowledge_results)} knowledge + "
            f"{len(deduped_chunks)} paragraph = {len(merged)} total"
        )
        return merged


def get_recall_fallback_coordinator(
    db: AsyncSession, threshold: Optional[float] = None,
) -> RecallFallbackCoordinator:
    """获取召回 fallback 协调器实例"""
    if threshold is None:
        threshold = DEFAULT_FALLBACK_THRESHOLD
    return RecallFallbackCoordinator(db, threshold=threshold)

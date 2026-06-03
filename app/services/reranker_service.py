"""Cross-encoder 重排序服务

对检索候选集使用 Cross-encoder 模型精排。
Cross-encoder 比 bi-encoder（向量检索用的）更准确，但更慢，
所以只对候选集做精排（top_k * 3），不做全库扫描。

模型：cross-encoder/ms-marco-MiniLM-L-6-v2（轻量，CPU 可跑，约 80MB）
"""

import logging
from typing import List, Optional

logger = logging.getLogger("microbubble.reranker")

# 模型名称（轻量 Cross-encoder）
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class RerankerService:
    """Cross-encoder 重排序服务"""

    def __init__(self):
        self._model = None

    def _load_model(self):
        """惰性加载 Cross-encoder 模型"""
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"加载 Cross-encoder 模型: {RERANKER_MODEL}")
            self._model = CrossEncoder(RERANKER_MODEL, max_length=512)
            logger.info("Cross-encoder 模型加载完成")
        except Exception as e:
            logger.error(f"Cross-encoder 模型加载失败: {e}（重排序将不可用，直接返回原序）")
            self._model = None

    def rerank(
        self,
        query: str,
        candidates: List[dict],
        top_k: int = 5,
    ) -> List[dict]:
        """对候选集重排序

        Args:
            query: 原始查询
            candidates: 候选文档列表，每条需包含 content 字段
            top_k: 返回条数

        Returns:
            按 Cross-encoder 分数重排序的结果列表
        """
        if not candidates:
            return []

        self._load_model()

        # 模型加载失败时降级：按原始分数排序
        if self._model is None:
            logger.warning("Cross-encoder 不可用，按原始分数排序")
            sorted_candidates = sorted(
                candidates, key=lambda x: x.get("score", 0), reverse=True
            )
            for c in sorted_candidates:
                c["rerank_score"] = c.get("score", 0)
            return sorted_candidates[:top_k]

        # 构建 query-document 对
        pairs = [(query, f"{c.get('title', '')} {c.get('content', '')}") for c in candidates]

        # Cross-encoder 打分
        try:
            scores = self._model.predict(pairs)
        except Exception as e:
            logger.error(f"Cross-encoder 预测失败: {e}")
            sorted_candidates = sorted(
                candidates, key=lambda x: x.get("score", 0), reverse=True
            )
            for c in sorted_candidates:
                c["rerank_score"] = c.get("score", 0)
            return sorted_candidates[:top_k]

        # 将分数附加到候选文档
        for i, candidate in enumerate(candidates):
            candidate["rerank_score"] = round(float(scores[i]), 4)

        # 按重排序分数排序
        reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

        return reranked[:top_k]


# 全局单例
_reranker_service: Optional[RerankerService] = None


def get_reranker_service() -> RerankerService:
    """获取重排序服务单例"""
    global _reranker_service
    if _reranker_service is None:
        _reranker_service = RerankerService()
    return _reranker_service

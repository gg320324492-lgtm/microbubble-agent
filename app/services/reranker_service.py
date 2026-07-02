"""Cross-encoder 重排序服务

对检索候选集使用 Cross-encoder 模型精排。
Cross-encoder 比 bi-encoder（向量检索用的）更准确，但更慢，
所以只对候选集做精排（top_k * 5），不做全库扫描。

# 2026-07-01 升级 v77 → BAAI/bge-reranker-v2-m3 (568M 多语言)
- 模型: BAAI/bge-reranker-v2-m3 (默认) / cross-encoder/ms-marco-MiniLM-L-6-v2 (兼容 fallback)
- 设备: cuda (RTX 5090, ~1.1GB VRAM FP16) — 替代之前的 CPU-only
- env: RERANKER_MODEL_NAME / RERANKER_DEVICE / RERANKER_MAX_LENGTH / RERANKER_BATCH_SIZE
- async: rerank_async 用 run_in_executor 包装 sync predict, 不阻塞 event loop
- warmup: 显式加载避免首次 rerank 时 8-10s 冷启动
- graceful degradation: 模型加载失败/预测失败时, 按原始 score 排序返回（兼容旧行为）

选择 BGE m3 的理由 (2026-07-01 user decision):
- MTEB Reranking 榜 #1 (60.9, 2026-06)
- 中文 MIRACL 榜 #1 (BGE 训练含 arXiv 学术论文)
- 568M 参数 / 1.1GB VRAM FP16 / ~30ms latency / 2.3GB 下载
- 项目知识库 288 条 (195 KB 论文 + 93 drive) 平均 2605 bytes, 需要中文 + 学术能力
"""

import asyncio
import logging
import os
from typing import List, Optional

logger = logging.getLogger("microbubble.reranker")

# 配置 (env var with sensible defaults)
RERANKER_MODEL = os.getenv("RERANKER_MODEL_NAME", "BAAI/bge-reranker-v2-m3")
RERANKER_DEVICE = os.getenv("RERANKER_DEVICE", "auto")  # auto/cuda/cpu
RERANKER_MAX_LENGTH = int(os.getenv("RERANKER_MAX_LENGTH", "512"))
RERANKER_BATCH_SIZE = int(os.getenv("RERANKER_BATCH_SIZE", "32"))


class RerankerService:
    """Cross-encoder 重排序服务

    Singleton via get_reranker_service(). Lazy model load on first use.
    失败 graceful degradation: 模型不可用时按原始 score 排序返回.
    """

    def __init__(self):
        self._model = None
        self._device = None
        self._model_name = None

    def _detect_device(self) -> str:
        """设备检测 (mirror embedding_service.py 模式)

        Returns:
            "cuda" / "cpu"
        """
        if RERANKER_DEVICE != "auto":
            return RERANKER_DEVICE
        try:
            import torch
            if torch.cuda.is_available():
                # smoke test (避免 CUDA lazy init 假阳性)
                torch.zeros(1).cuda()
                return "cuda"
        except Exception as e:
            logger.debug(f"CUDA 不可用, 降级到 CPU: {e}")
        return "cpu"

    def _load_model(self):
        """惰性加载 Cross-encoder 模型 (lazy + thread-safe via _model_name guard)"""
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder
            # 2026-07-02 Phase I 修复: 强制 local_files_only 避免在容器内访问 hf-mirror.com
            # 之前 HF_HUB_OFFLINE=1 没生效, sentence-transformers 默认还尝试网络
            # 加 local_files_only=True 强制从本地 cache 加载
            cache_folder = "/root/.cache/huggingface/hub"

            self._device = self._detect_device()
            self._model_name = RERANKER_MODEL
            logger.info(
                f"加载 Cross-encoder 模型: {self._model_name} on {self._device} "
                f"(max_length={RERANKER_MAX_LENGTH}, batch_size={RERANKER_BATCH_SIZE}, "
                f"cache_folder={cache_folder})"
            )
            self._model = CrossEncoder(
                self._model_name,
                max_length=RERANKER_MAX_LENGTH,
                device=self._device,
                cache_folder=cache_folder,
                local_files_only=True,  # 强制本地加载, 不走网络
            )
            logger.info(
                f"Cross-encoder 模型加载完成 ({self._model_name} on {self._device})"
            )
        except Exception as e:
            logger.error(
                f"Cross-encoder 模型加载失败: {e}（重排序将不可用, 按原始 score 排序返回）"
            )
            self._model = None
            self._model_name = None
            self._device = None

    def rerank(
        self,
        query: str,
        candidates: List[dict],
        top_k: int = 5,
    ) -> List[dict]:
        """对候选集重排序 (sync, 阻塞调用方)

        Args:
            query: 原始查询
            candidates: 候选文档列表, 每条需含 title + content 字段
            top_k: 返回条数

        Returns:
            按 Cross-encoder 分数重排序的 top_k 列表, 每条带 rerank_score 字段
        """
        if not candidates:
            return []

        self._load_model()

        # 模型加载失败时降级: 按原始 score 排序
        if self._model is None:
            logger.warning("Cross-encoder 不可用, 按原始 score 排序返回")
            return self._fallback_sort(candidates, top_k)

        # 构建 query-document 对 (title + content 拼接)
        pairs = [
            (query, f"{c.get('title', '')} {c.get('content', '')}") for c in candidates
        ]

        # Cross-encoder 打分 (GPU 30ms for 25 candidates)
        try:
            scores = self._model.predict(
                pairs,
                batch_size=RERANKER_BATCH_SIZE,
                show_progress_bar=False,
            )
        except Exception as e:
            logger.error(f"Cross-encoder 预测失败: {e}（降级按原始 score 排序）")
            return self._fallback_sort(candidates, top_k)

        # 将分数附加到候选文档
        for i, candidate in enumerate(candidates):
            candidate["rerank_score"] = round(float(scores[i]), 4)

        # 按重排序分数排序
        reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
        return reranked[:top_k]

    async def rerank_async(
        self,
        query: str,
        candidates: List[dict],
        top_k: int = 5,
    ) -> List[dict]:
        """async rerank - for use in async contexts (hybrid_retriever)

        用 run_in_executor 包装 sync predict, 不阻塞 event loop.
        """
        if not candidates:
            return []
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.rerank, query, candidates, top_k)

    async def warmup(self):
        """显式预加载模型 (避免首次 rerank 时 8-10s 冷启动延迟)

        在 app lifespan startup 阶段调一次:
            await get_reranker_service().warmup()
        """
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_model)
        if self.is_loaded:
            logger.info(f"Reranker 预热完成: {self._model_name} on {self._device}")
        else:
            logger.warning("Reranker 预热失败, 首次 rerank 会有冷启动延迟")

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def model_name(self) -> str:
        return self._model_name or RERANKER_MODEL

    @property
    def device(self) -> str:
        return self._device or "unknown"

    def _fallback_sort(self, candidates: List[dict], top_k: int) -> List[dict]:
        """Graceful degradation: 按原始 score 排序返回 (与旧 RerankerService 行为一致)"""
        sorted_candidates = sorted(
            candidates, key=lambda x: x.get("score", 0), reverse=True
        )
        for c in sorted_candidates:
            c["rerank_score"] = c.get("score", 0)
        return sorted_candidates[:top_k]


# 全局单例
_reranker_service: Optional[RerankerService] = None


def get_reranker_service() -> RerankerService:
    """获取重排序服务单例

    Returns:
        RerankerService 实例 (process-local singleton)
    """
    global _reranker_service
    if _reranker_service is None:
        _reranker_service = RerankerService()
    return _reranker_service


def reset_reranker_service() -> None:
    """重置单例 (测试用, 允许重新初始化)"""
    global _reranker_service
    _reranker_service = None

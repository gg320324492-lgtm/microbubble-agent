"""app/rag/dense_sparse_routing.py — Dense/Sparse/Hybrid 一层切换

LlamaIndex VectorStoreIndex + BM25Retriever 组合:
- dense-only: VectorStoreIndex (pgvector HNSW 复用现有 knowledge.embedding)
- sparse-only: BM25Retriever (复用 bm25_service)
- hybrid: 两者融合

切换从改代码 → 改配置 (env: RAG_RETRIEVAL_MODE=dense|sparse|hybrid)

设计约束 (RAG-FW-08, W98):
- 只读复用: PGVectorStore perform_setup=False — 不建表/不建索引/不 UPSERT,
  复用现有 knowledge 表 + embedding 列 (HNSW), 不新建 alembic 迁移
- 0 改老文件: 仅 import app/services/hybrid_retriever.py + bm25_service.py, 不改动
- 失败回退: llama_index 未安装 / 老表列结构不匹配 (缺 node_id/text/metadata 列)
  / embedding 模型不可用 → 自动回退手写 hybrid_retriever.retrieve() (框架门控哲学,
  RAG-FW-01 gate.py)
- 开关关闭 (DENSE_SPARSE_ROUTING_ENABLED=0) → retrieve() 返回 None (fallback_fn=None)
"""

import asyncio
import logging
import os
from typing import Any, Callable, Dict, List, Optional

from app.rag.config import DENSE_SPARSE_ROUTING_ENABLED
from app.rag.gate import framework_gate

logger = logging.getLogger("microbubble.rag.dense_sparse")

# env 切换: dense | sparse | hybrid (默认 hybrid)
RETRIEVAL_MODE = os.getenv("RAG_RETRIEVAL_MODE", "hybrid")


class _EmbeddingFnAdapter:
    """桥接: 现有 async embedding 函数 → llama_index embed_model (鸭子类型)

    llama_index 检索器 async 路径调用 aget_query_embedding; 鸭子类型足够,
    不继承 BaseEmbedding (避免抽象方法样板 + 简化测试 mock).
    默认 fn = app.services.embedding_service.generate_embedding (Qwen3-Embedding 1024 维).
    自定义 fn 的同步变体不可用 → 抛错触发框架门控回退 (不静默返回坏向量).
    """

    def __init__(self, fn: Optional[Callable[[str], Any]], embed_dim: int):
        self._fn = fn
        self.embed_dim = embed_dim

    # --- async 路径 (llama_index async retriever 用) ---
    async def aget_query_embedding(self, query: str) -> List[float]:
        if self._fn is None:
            from app.services.embedding_service import generate_embedding

            embedding = await generate_embedding(query)
        else:
            embedding = await self._fn(query)
        if not embedding:
            raise RuntimeError("embedding 生成失败 (模型不可用)")
        return embedding

    async def aget_text_embedding(self, text: str) -> List[float]:
        return await self.aget_query_embedding(text)

    # --- sync 路径 (仅默认 embedding_service 可用) ---
    def get_query_embedding(self, query: str) -> List[float]:
        if self._fn is not None:
            raise RuntimeError("自定义 embedding_fn 仅支持 async 路径 (aget_query_embedding)")
        from app.services.embedding_service import generate_embedding_sync

        embedding = generate_embedding_sync(query)
        if not embedding:
            raise RuntimeError("embedding 生成失败 (模型不可用)")
        return embedding

    def get_text_embedding(self, text: str) -> List[float]:
        return self.get_query_embedding(text)


class DenseSparseRouter:
    """一层切换路由器 — LlamaIndex 组合"""

    def __init__(self, db=None, embedding_fn: Optional[Callable[[str], Any]] = None):
        self.db = db
        self._embedding_fn = embedding_fn
        self._vector_index = None  # lazy init
        self._bm25_retriever = None  # lazy init

    async def _init_vector_index(self):
        """初始化 LlamaIndex VectorStoreIndex

        - 复用现有 knowledge.embedding HNSW 索引 (pgvector)
        - 显式 embedding_dim=1024 (Qwen3-Embedding, LLAMAINDEX_EMBEDDING_DIM 可覆盖)
        - 只读模式: perform_setup=False (SELECT only, 不建表/不建索引/不 UPSERT)
        - 失败 (llama_index 未装 / 老表列结构不匹配) → 抛异常 → retrieve() 回退手写
        """
        if self._vector_index is not None:
            return self._vector_index
        from llama_index.core import VectorStoreIndex
        from llama_index.vector_stores.postgres import PGVectorStore

        from app.config import settings
        from app.rag.config import LLAMAINDEX_EMBEDDING_DIM, LLAMAINDEX_PGVECTOR_SCHEMA

        vector_store = PGVectorStore(
            connection_string=settings.DATABASE_URL,
            table_name="knowledge",
            schema_name=LLAMAINDEX_PGVECTOR_SCHEMA,
            embed_dim=LLAMAINDEX_EMBEDDING_DIM,
            perform_setup=False,  # 只读 — 复用现有表, 不建表/不建索引
            cache_ok=True,
        )
        embed_model = _EmbeddingFnAdapter(self._embedding_fn, LLAMAINDEX_EMBEDDING_DIM)
        self._vector_index = VectorStoreIndex.from_vector_store(
            vector_store, embed_model=embed_model
        )
        return self._vector_index

    async def _init_bm25_retriever(self):
        """初始化 BM25Retriever (复用 bm25_service 数据, 只读)

        - 从 get_bm25_service() 内存语料 (_documents) 构建 TextNode
        - 语料为空 → 返回 None (sparse-only 返空, 不抛错)
        """
        if self._bm25_retriever is not None:
            return self._bm25_retriever
        from app.services.bm25_service import get_bm25_service

        bm25 = get_bm25_service()
        docs = list(getattr(bm25, "_documents", []) or [])
        if not docs:
            logger.warning("bm25_service 语料为空, BM25Retriever 无数据 — sparse-only 返空")
            return None

        from llama_index.core.retrievers import BM25Retriever
        from llama_index.core.schema import TextNode

        nodes = [
            TextNode(
                id_=str(doc.get("id")),
                text=f"{doc.get('title', '')}\n{doc.get('content', '')}",
                metadata={
                    k: v for k, v in doc.items() if k not in ("id", "title", "content")
                },
            )
            for doc in docs
        ]
        # similarity_top_k 取大值兜底, 调用时按 top_k 动态覆盖
        self._bm25_retriever = BM25Retriever.from_defaults(
            nodes=nodes, similarity_top_k=10
        )
        return self._bm25_retriever

    @framework_gate(feature_flag=DENSE_SPARSE_ROUTING_ENABLED, fallback_fn=None)
    async def retrieve(
        self, query: str, top_k: int = 5, mode: Optional[str] = None
    ) -> List[Dict]:
        """按 mode 检索 — 失败回退手写 hybrid_retriever

        mode: dense | sparse | hybrid (默认取 env RAG_RETRIEVAL_MODE)
        开关关闭 (DENSE_SPARSE_ROUTING_ENABLED=0) → 返回 None
        """
        mode = mode or RETRIEVAL_MODE
        try:
            if mode == "dense":
                return await self._dense_only(query, top_k)
            elif mode == "sparse":
                return await self._sparse_only(query, top_k)
            return await self._hybrid(query, top_k)
        except Exception as e:
            logger.error(f"Dense/Sparse 路由失败, 回退手写 hybrid: {e}", exc_info=True)
            return await self._fallback_hybrid(query, top_k)

    async def _dense_only(self, query: str, top_k: int) -> List[Dict]:
        """向量检索 only (pgvector HNSW via LlamaIndex VectorStoreIndex)"""
        index = await self._init_vector_index()
        retriever = index.as_retriever(similarity_top_k=top_k)
        nodes = await retriever.aretrieve(query)
        return [self._node_to_dict(n, method="dense_vector") for n in nodes]

    async def _sparse_only(self, query: str, top_k: int) -> List[Dict]:
        """BM25 检索 only"""
        retriever = await self._init_bm25_retriever()
        if retriever is None:
            return []
        retriever.similarity_top_k = top_k
        nodes = await retriever.aretrieve(query)
        return [self._node_to_dict(n, method="bm25") for n in nodes]

    async def _hybrid(self, query: str, top_k: int) -> List[Dict]:
        """dense + sparse 融合 — 并发检索 + 按 id 去重保留最高分

        单路失败容忍 (gather return_exceptions), 两路全失败 → 抛异常 → retrieve() 回退手写
        """
        candidate_k = max(top_k * 2, 1)
        results = await asyncio.gather(
            self._dense_only(query, candidate_k),
            self._sparse_only(query, candidate_k),
            return_exceptions=True,
        )
        failed = 0
        merged: Dict[Any, Dict] = {}
        for r in results:
            if isinstance(r, Exception):
                failed += 1
                logger.warning(f"hybrid 单路失败: {r}")
                continue
            for item in r:
                doc_id = item.get("id")
                if doc_id is None:
                    continue
                if doc_id not in merged or item.get("score", 0) > merged[doc_id].get(
                    "score", 0
                ):
                    merged[doc_id] = item
        if not merged and failed > 0 and failed == len(results):
            raise RuntimeError(f"hybrid 两路全失败 ({failed}/{len(results)} 路异常)")
        out = sorted(merged.values(), key=lambda x: x.get("score", 0), reverse=True)
        return out[:top_k]

    async def _fallback_hybrid(self, query: str, top_k: int) -> List[Dict]:
        """回退: 现有手写 hybrid_retriever.retrieve() 4 路并发"""
        from app.services.hybrid_retriever import HybridRetriever

        svc = HybridRetriever(self.db)
        return await svc.retrieve(query, top_k=top_k)

    @staticmethod
    def _node_to_dict(node: Any, method: str) -> Dict:
        """LlamaIndex NodeWithScore → 手写检索结果格式 (id/title/content/score/...)"""
        node_id = getattr(node, "node_id", None) or getattr(node, "id_", None)
        try:
            node_id = int(node_id)
        except (TypeError, ValueError):
            node_id = node_id
        text = getattr(node, "text", "") or ""
        meta = getattr(node, "metadata", None) or {}
        title = meta.get("title")
        if not title and text:
            title = text.split("\n", 1)[0][:80]
        return {
            "id": node_id,
            "title": title or "",
            "content": text,
            "category": meta.get("category"),
            "tags": meta.get("tags"),
            "source": meta.get("source"),
            "score": round(float(getattr(node, "score", 0) or 0), 4),
            "retrieval_method": method,
        }

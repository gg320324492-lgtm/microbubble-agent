"""app/rag/multi_hop_engine.py — Multi-hop / 多文档多轮合成

LlamaIndex SubQuestionQueryEngine:
- 自动分解复杂问题为子问题
- 逐跳检索 (复用现有 pgvector 表, 不建新表)
- 逐层聚合子结果合成最终答案

失败自动降级: knowledge_qa_service.answer_question() 单轮检索。
"""

import logging
from typing import Dict, List, Optional

from app.rag.config import MULTI_HOP_ENABLED
from app.rag.gate import framework_gate

logger = logging.getLogger("microbubble.rag.multi_hop")


class MultiHopEngine:
    """LlamaIndex SubQuestionQueryEngine 包装

    复用现有 knowledge.embedding HNSW 索引 (pgvector),
    不创建 LlamaIndex 新表。
    """

    def __init__(self, db=None, llm=None):
        self.db = db
        self.llm = llm
        self._engine = None  # lazy init

    async def _init_engine(self):
        """初始化 LlamaIndex SubQuestionQueryEngine

        - 用 llama_index.core.query_engine.SubQuestionQueryEngine
        - 用 llama_index.vector_stores.pgvector 指向现有 knowledge 表
        - embedding 用 langchain 桥接 (llama_index.embeddings.langchain)

        幂等: 重复调用返回同一引擎实例。
        """
        if self._engine is not None:
            return self._engine

        from llama_index.core import Settings
        from llama_index.core.indices.vector_store import VectorStoreIndex
        from llama_index.core.query_engine import SubQuestionQueryEngine
        from llama_index.core.tools import QueryEngineTool, ToolMetadata
        from llama_index.embeddings.langchain import LangchainEmbedding
        from llama_index.vector_stores.pgvector import PGVectorStore
        from sqlalchemy import make_url

        from app.rag.config import (
            LLAMAINDEX_EMBEDDING_DIM,
            LLAMAINDEX_PGVECTOR_SCHEMA,
        )

        # LLM: 优先注入, 否则复用 app.core.llm 客户端
        llm = self.llm
        if llm is None:
            from app.core.llm import get_anthropic_client
            llm = get_anthropic_client()
        self.llm = llm

        # 解析现有连接串, pgvector store 指向现有 knowledge 表 (不建新表)
        url = make_url(str(self.db.bind.url))
        vector_store = PGVectorStore.from_params(
            host=url.host or "localhost",
            port=url.port or 5432,
            database=url.database or "microbubble",
            user=url.username or "postgres",
            password=url.password or "",
            table_name="knowledge",
            embed_dim=LLAMAINDEX_EMBEDDING_DIM,
            schema_name=LLAMAINDEX_PGVECTOR_SCHEMA,
            perform_setup=False,  # 复用现有 HNSW 索引, 不做任何建表
        )

        # Embedding: langchain 桥接, 复用现有 embedding_service (同模型同向量空间)
        Settings.llm = llm
        Settings.embed_model = LangchainEmbedding(self._embed_fn())

        # 逐跳检索工具: 现有 knowledge 表 → VectorStoreIndex → query engine
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
        query_engine = index.as_query_engine(similarity_top_k=10)

        tool = QueryEngineTool(
            query_engine=query_engine,
            metadata=ToolMetadata(
                name="knowledge_retriever",
                description=(
                    "从课题组知识库检索与子问题相关的知识条目。"
                    "输入应为单一事实类子问题, 输出为匹配的知识片段。"
                ),
            ),
        )

        self._engine = SubQuestionQueryEngine.from_defaults(
            query_engine_tools=[tool],
            llm=llm,
            verbose=False,
        )
        return self._engine

    def _embed_fn(self):
        """langchain embedding 桥接: 复用现有 embedding_service

        LangchainEmbedding 包装 HuggingFaceEmbeddings (不加载新模型),
        embed_query/embed_documents 委托给 app.services.embedding_service,
        与手写层同模型同向量空间。
        """
        from langchain_community.embeddings import HuggingFaceEmbeddings

        class _Bridge(HuggingFaceEmbeddings):
            """只复用类名/接口, 不加载任何模型

            父类 __init__ 会实例化 SentenceTransformer (下载模型), 这里整体跳过;
            embed_query / embed_documents 全部委托现有 embedding_service,
            与手写层同模型同向量空间。
            """

            def __init__(self):
                pass  # 跳过模型加载

            def embed_documents(self, texts: List[str]) -> List[List[float]]:
                from app.services.embedding_service import embed_texts
                return embed_texts(texts)

            def embed_query(self, text: str) -> List[float]:
                from app.services.embedding_service import embed_text
                return embed_text(text)

        return _Bridge()

    @framework_gate(
        feature_flag=MULTI_HOP_ENABLED,
        fallback_fn=None,
    )
    async def query(self, question: str, top_k: int = 6, **kwargs) -> Dict:
        """多跳查询 — 失败自动降级到单轮

        Returns:
            {
                "answer": str,
                "sub_questions": List[str],
                "source_nodes": List[Dict],
                "confidence": "high" | "low",
                "used_framework": bool,
            }
        """
        try:
            if self._engine is None:
                self._engine = await self._init_engine()
            response = await self._engine.aquery(question)
            return {
                "answer": response.response,
                "sub_questions": [q.sub_query.sub_query for q in response.source_nodes],
                "source_nodes": [n.dict() for n in response.source_nodes],
                "confidence": "high" if response.source_nodes else "low",
                "used_framework": True,
            }
        except Exception as e:
            logger.error(f"Multi-hop 失败, 降级单轮: {e}", exc_info=True)
            # 降级: 单轮检索 + LLM 合成
            return await self._fallback_single_hop(question, top_k, **kwargs)

    async def _fallback_single_hop(self, question: str, top_k: int, **kwargs) -> Dict:
        """降级: 复用现有手写 knowledge_qa_service 单轮检索"""
        from app.services.knowledge_qa_service import KnowledgeQAService
        svc = KnowledgeQAService(self.db)
        result = await svc.answer_question(question, top_k=top_k, auto_research=False)
        return {
            "answer": result.get("answer", ""),
            "sub_questions": [],
            "source_nodes": result.get("sources", []),
            "confidence": "medium",
            "used_framework": False,
        }

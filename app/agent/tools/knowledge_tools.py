"""知识库域工具（v2 架构）— 迁移最高频的 search_knowledge

未迁移（仍走 dispatch_legacy，使用频率低或复杂）：
- explore_knowledge_graph / find_knowledge_gaps / auto_research
- compare_knowledge / summarize_topic / suggest_research
- save_conversation_knowledge
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.knowledge")


class SearchKnowledgeInput(BaseModel):
    query: str = Field(..., min_length=1, description="搜索关键词或问题")
    category: Optional[str] = Field(None, description="分类筛选：文献/实验/方法/FAQ")
    top_k: int = Field(5, ge=1, le=20, description="返回数量（默认 5）")


class SearchKnowledgeOutput(BaseModel):
    status: str
    count: int
    results: list[dict]
    rich_block_type: str = "knowledge_ref"


@tool(
    name="search_knowledge",
    description="搜索知识库。当用户询问专业问题、查找文献、查询实验方法等时使用。",
    input_model=SearchKnowledgeInput,
    output_model=SearchKnowledgeOutput,
)
async def search_knowledge(input: SearchKnowledgeInput, ctx: ToolContext) -> dict:
    """知识库四路混合检索（向量 + BM25 + Graph + Rerank）"""
    from app.services.hybrid_retriever import get_hybrid_retriever

    retriever = get_hybrid_retriever(ctx.db)
    results = await retriever.retrieve(
        query=input.query,
        top_k=input.top_k,
        enable_vector=True,
        enable_bm25=True,
        enable_graph=True,
        enable_rerank=True,
    )
    return {
        "status": "success",
        "count": len(results),
        "results": results,
        "rich_block_type": "knowledge_ref",
    }

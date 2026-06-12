"""知识图谱域工具（v3 迁移）

迁移自 core.py._execute_tool：
- explore_knowledge_graph (line 1058)
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.graph")


class ExploreKnowledgeGraphInput(BaseModel):
    entity_name: str = Field(..., min_length=1, description="实体名称（如'微纳米气泡'、'zeta电位'）")
    hops: int = Field(1, ge=1, le=3, description="遍历跳数（默认 1，最大 3）")


class ExploreKnowledgeGraphOutput(BaseModel):
    status: str
    entity: Optional[str] = None
    nodes: list[dict] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)
    rich_block_type: Optional[str] = None


@tool(
    name="explore_knowledge_graph",
    description="探索知识图谱。当用户询问实体之间的关系、某个概念的关联知识、多跳推理等时使用。",
    input_model=ExploreKnowledgeGraphInput,
    output_model=ExploreKnowledgeGraphOutput,
)
async def explore_knowledge_graph(input: ExploreKnowledgeGraphInput, ctx: ToolContext) -> dict:
    """知识图谱多跳遍历（Neo4j）"""
    from app.services.graph_retriever import get_graph_retriever

    graph = get_graph_retriever()
    result = await graph.multi_hop_retrieve(
        entity_name=input.entity_name,
        hops=min(input.hops, 3),
    )
    return {
        "status": "success",
        "entity": input.entity_name,
        "nodes": result.get("nodes", []),
        "edges": result.get("edges", []),
    }

"""研究 / 知识图谱域工具（v3 迁移）

迁移自 core.py._execute_tool：
- compare_knowledge (line 1091)
- find_knowledge_gaps (line 1068)
- summarize_topic (line 1111)
- suggest_research (line 1128)
- auto_research (line 1082) — 高复杂度（LLM + 联网 + 入库）
"""

import logging
from typing import List, Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.research")


# ============================================================================
# 1. compare_knowledge（低复杂度，纯查询循环）
# ============================================================================


class CompareKnowledgeInput(BaseModel):
    items: list[str] = Field(..., min_length=2, description="要对比的知识条目名称列表")
    criteria: Optional[str] = Field(None, description="对比维度（可选）")


class ComparisonItem(BaseModel):
    name: str
    title: str
    content: str
    score: float


class CompareKnowledgeOutput(BaseModel):
    status: str
    comparisons: list[ComparisonItem]
    criteria: Optional[str] = None
    rich_block_type: Optional[str] = None


@tool(
    name="compare_knowledge",
    description="对比分析多个知识条目。当用户询问「A和B哪个好」「对比XX和YY」时使用。",
    input_model=CompareKnowledgeInput,
    output_model=CompareKnowledgeOutput,
)
async def compare_knowledge(input: CompareKnowledgeInput, ctx: ToolContext) -> dict:
    """对比多个知识条目"""
    from app.services.knowledge_service import KnowledgeService

    kb_svc = KnowledgeService(ctx.db)
    comparisons = []
    for item in input.items:
        results = await kb_svc.search_semantic(query=item, top_k=1)
        if results:
            comparisons.append({
                "name": item,
                "title": results[0]["title"],
                "content": results[0]["content"][:300],
                "score": results[0]["score"],
            })
        else:
            comparisons.append({
                "name": item, "title": "未找到", "content": "", "score": 0.0,
            })
    return {
        "status": "success",
        "comparisons": comparisons,
        "criteria": input.criteria,
        "rich_block_type": None,
    }


# ============================================================================
# 2. find_knowledge_gaps
# ============================================================================


class FindKnowledgeGapsInput(BaseModel):
    topic: Optional[str] = Field(None, description="要检查空白的主题（可选，不填则全局检查）")


class KnowledgeGapItem(BaseModel):
    topic: str
    severity: str  # high/medium/low
    description: str


class FindKnowledgeGapsOutput(BaseModel):
    status: str
    gaps: list[KnowledgeGapItem]
    stats: Optional[dict] = None
    rich_block_type: Optional[str] = None


@tool(
    name="find_knowledge_gaps",
    description="发现知识库中的空白领域。当用户询问「我们还缺什么知识」「哪些方面需要补充」时使用。",
    input_model=FindKnowledgeGapsInput,
    output_model=FindKnowledgeGapsOutput,
)
async def find_knowledge_gaps(input: FindKnowledgeGapsInput, ctx: ToolContext) -> dict:
    """知识空白检测"""
    from app.services.auto_research_service import AutoResearchService

    svc = AutoResearchService(ctx.db)
    if input.topic:
        results = await svc._analyze_gaps(f"研究主题: {input.topic}")
        return {
            "status": "success",
            "gaps": results if isinstance(results, list) else results.get("gaps", []),
            "stats": None,
        }
    stats = await svc._collect_stats()
    gaps = await svc._analyze_gaps(stats)
    return {
        "status": "success",
        "gaps": gaps if isinstance(gaps, list) else gaps.get("gaps", []),
        "stats": stats,
    }


# ============================================================================
# 3. summarize_topic
# ============================================================================


class SummarizeTopicInput(BaseModel):
    topic: str = Field(..., min_length=1, description="要总结的主题")


class SummarizeTopicOutput(BaseModel):
    status: str
    topic: str
    communities: Optional[list] = None
    knowledge_count: int
    top_items: list[dict]
    rich_block_type: Optional[str] = None


@tool(
    name="summarize_topic",
    description="总结某个主题的知识。当用户询问「课题组研究方向有哪些」「总结一下XX领域」时使用。",
    input_model=SummarizeTopicInput,
    output_model=SummarizeTopicOutput,
)
async def summarize_topic(input: SummarizeTopicInput, ctx: ToolContext) -> dict:
    """主题总结（图谱 + 语义）"""
    from app.services.graph_retriever import get_graph_retriever
    from app.services.knowledge_service import KnowledgeService

    graph = get_graph_retriever()
    communities = await graph.get_community_overview(limit=5)
    kb_svc = KnowledgeService(ctx.db)
    results = await kb_svc.search_semantic(query=input.topic, top_k=10)
    return {
        "status": "success",
        "topic": input.topic,
        "communities": communities,
        "knowledge_count": len(results),
        "top_items": [{"title": r["title"], "category": r.get("category")} for r in results[:5]],
    }


# ============================================================================
# 4. suggest_research
# ============================================================================


class SuggestResearchInput(BaseModel):
    area: Optional[str] = Field(None, description="研究领域（可选）")


class SuggestResearchOutput(BaseModel):
    status: str
    area: Optional[str] = None
    gaps: list[dict] = Field(default_factory=list)
    suggestion: str
    rich_block_type: Optional[str] = None


@tool(
    name="suggest_research",
    description="基于知识图谱和假设生成研究建议。当用户询问「下一步该研究什么」「有什么研究方向」时使用。",
    input_model=SuggestResearchInput,
    output_model=SuggestResearchOutput,
)
async def suggest_research(input: SuggestResearchInput, ctx: ToolContext) -> dict:
    """研究建议（基于知识空白）"""
    from app.services.hypothesis_service import HypothesisService
    from app.services.auto_research_service import AutoResearchService

    hypothesis_svc = HypothesisService(ctx.db)
    gaps_svc = AutoResearchService(ctx.db)
    stats = await gaps_svc._collect_stats()
    gaps = await gaps_svc._analyze_gaps(stats)
    return {
        "status": "success",
        "area": input.area,
        "gaps": gaps.get("gaps", [])[:5] if isinstance(gaps, dict) else [],
        "suggestion": "基于知识空白分析，建议重点关注以下研究方向" if gaps else "知识库较为完善，可探索交叉领域",
    }


# ============================================================================
# 5. auto_research（高复杂度 — LLM + 联网 + 入库）
# ============================================================================


class AutoResearchInput(BaseModel):
    topic: str = Field(..., min_length=1, description="要研究的主题")
    max_results: int = Field(5, ge=1, le=20, description="最大搜索结果数（默认 5）")


class AutoResearchOutput(BaseModel):
    status: str
    topic: str
    queries: list[str] = Field(default_factory=list)
    results: list[dict] = Field(default_factory=list)
    ingested: int = 0
    rich_block_type: Optional[str] = None


@tool(
    name="auto_research",
    description="自主研究某个主题。当用户要求研究某个主题、补充知识空白时使用。会联网搜索并自动入库。",
    input_model=AutoResearchInput,
    output_model=AutoResearchOutput,
)
async def auto_research(input: AutoResearchInput, ctx: ToolContext) -> dict:
    """自主研究（LLM + 联网 + 入库）"""
    from app.services.auto_research_service import AutoResearchService

    svc = AutoResearchService(ctx.db)
    result = await svc.research_topic(
        queries=[input.topic],
        max_results_per_query=input.max_results,
    )
    return {
        "status": "success",
        "topic": input.topic,
        "queries": [input.topic],
        "results": result.get("results", []),
        "ingested": result.get("ingested", 0),
    }

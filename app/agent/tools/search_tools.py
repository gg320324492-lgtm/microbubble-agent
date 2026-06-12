"""联网搜索域工具（v2 架构）— 迁移 web_search
"""

import logging
from typing import Optional
from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.search")


class WebSearchInput(BaseModel):
    query: str = Field(..., min_length=1, description="搜索查询关键词")
    max_results: int = Field(5, ge=1, le=20, description="返回结果数量（默认 5）")


class WebSearchOutput(BaseModel):
    status: str
    query: Optional[str] = None
    results: list[dict] = Field(default_factory=list)
    result_count: int = 0
    rich_block_type: Optional[str] = None


@tool(
    name="web_search",
    description="搜索互联网获取最新信息。当用户询问最新新闻、实时信息、天气、网上资料、或知识库中找不到答案的问题时使用。",
    input_model=WebSearchInput,
    output_model=WebSearchOutput,
    requires_db=False,
)
async def web_search(input: WebSearchInput, ctx: ToolContext) -> dict:
    """联网搜索（搜狗 + 必应双引擎）"""
    from app.services.search_service import search_service

    result = await search_service.search(
        query=input.query,
        max_results=input.max_results,
    )
    result["rich_block_type"] = None
    return result

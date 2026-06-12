"""假设域工具（v2 架构）— 新增

- list_hypotheses: 按 status/priority 过滤假设列表
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.hypothesis")


class ListHypothesesInput(BaseModel):
    status: Optional[str] = Field(None, description="按状态筛选：proposed / validated / rejected")
    priority: Optional[str] = Field(None, description="按优先级筛选：high / medium / low")
    topic: Optional[str] = Field(None, description="按主题关键词（暂未实现，留作扩展）")
    limit: int = Field(10, ge=1, le=50, description="返回数量（默认 10）")


class HypothesisItem(BaseModel):
    id: int
    statement: str
    rationale: Optional[str] = None
    status: str
    priority: Optional[str] = None
    confidence: Optional[float] = None
    validation_note: Optional[str] = None
    created_at: Optional[str] = None


class ListHypothesesOutput(BaseModel):
    status: str
    count: int
    total: int
    items: list[HypothesisItem]
    rich_block_type: str = "hypothesis"


@tool(
    name="list_hypotheses",
    description="查询研究假设库（按 status/priority 过滤）。用户问「实验室有哪些研究假设」「有没有已验证的假设」「当前的研究方向是什么」时调用。",
    input_model=ListHypothesesInput,
    output_model=ListHypothesesOutput,
)
async def list_hypotheses(input: ListHypothesesInput, ctx: ToolContext) -> dict:
    """查询假设列表"""
    from app.services.hypothesis_service import HypothesisService

    svc = HypothesisService(ctx.db)
    page_size = input.limit
    result = await svc.list_hypotheses(
        status=input.status,
        priority=input.priority,
        page=1, page_size=page_size,
    )
    items = []
    for h in result.get("items", []):
        items.append({
            "id": h["id"],
            "statement": h.get("statement") or h.get("hypothesis") or "",
            "rationale": h.get("rationale"),
            "status": h.get("status") or "proposed",
            "priority": h.get("priority"),
            "confidence": h.get("confidence"),
            "validation_note": h.get("validation_note"),
            "created_at": h.get("created_at"),
        })
    return {
        "status": "success",
        "count": len(items),
        "total": result.get("total", len(items)),
        "items": items,
        "rich_block_type": "hypothesis",
    }

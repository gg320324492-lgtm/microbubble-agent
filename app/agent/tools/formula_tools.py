"""公式域工具（v2 架构）— 新增

- list_formulas: 按 domain/category/search 过滤公式列表
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.formula")


class ListFormulasInput(BaseModel):
    domain: Optional[str] = Field(None, description="按 domain 筛选（微纳米气泡/流体力学/热力学 等）")
    category: Optional[str] = Field(None, description="按 category 名称筛选（模糊匹配）")
    search: Optional[str] = Field(None, description="按名称/LaTeX 关键词搜索")
    limit: int = Field(20, ge=1, le=100, description="返回数量（默认 20）")


class FormulaItem(BaseModel):
    id: int
    name: str
    expression: str
    latex: Optional[str] = None
    domain: Optional[str] = None
    variables: dict = Field(default_factory=dict)
    source_type: Optional[str] = None
    confidence: Optional[float] = None
    result_unit: Optional[str] = None
    knowledge_id: Optional[int] = None


class ListFormulasOutput(BaseModel):
    status: str
    count: int
    total: int
    formulas: list[FormulaItem]
    rich_block_type: str = "formula"


@tool(
    name="list_formulas",
    description="查询公式库（按 domain / category / 关键词 过滤）。用户问「有哪些公式」「zeta 电位公式」「浮力的公式是什么」时调用。",
    input_model=ListFormulasInput,
    output_model=ListFormulasOutput,
)
async def list_formulas(input: ListFormulasInput, ctx: ToolContext) -> dict:
    """查询公式列表（按 domain/category/search 过滤）"""
    from app.services.formula_service import FormulaService

    svc = FormulaService(ctx.db)
    result = await svc.list_formulas(
        domain=input.domain,
        keyword=input.search,
        page=1, page_size=input.limit,
    )
    items = []
    for f in result.get("items", []):
        items.append({
            "id": f["id"],
            "name": f["name"],
            "expression": f.get("formula_python") or f.get("formula_latex") or "",
            "latex": f.get("formula_latex"),
            "domain": f.get("domain"),
            "variables": f.get("variables") or {},
            "source_type": f.get("source_type"),
            "confidence": f.get("confidence"),
            "result_unit": f.get("result_unit"),
            "knowledge_id": f.get("knowledge_id"),
        })
    return {
        "status": "success",
        "count": len(items),
        "total": result.get("total", len(items)),
        "formulas": items,
        "rich_block_type": "formula",
    }

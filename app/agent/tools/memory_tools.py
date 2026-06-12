"""长期记忆域工具（v2 架构）— 迁移 save/search/forget_memory
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.memory")


# ============================================================================
# save_memory
# ============================================================================


class SaveMemoryInput(BaseModel):
    memory_type: str = Field(..., description="preference(偏好) / summary(摘要) / entity(实体关系)")
    content: str = Field(..., min_length=1, description="记忆内容")
    key: Optional[str] = Field(None, description="记忆键名（preference 类型建议填写）")
    importance: float = Field(0.7, ge=0.0, le=1.0, description="重要性 0.0-1.0")


class SaveMemoryOutput(BaseModel):
    status: str
    memory_id: Optional[int] = None
    type: Optional[str] = None
    rich_block_type: Optional[str] = None


@tool(
    name="save_memory",
    description="保存重要信息到长期记忆。当用户表达偏好、提供重要信息、或你发现值得记住的内容时使用。",
    input_model=SaveMemoryInput,
    output_model=SaveMemoryOutput,
)
async def save_memory(input: SaveMemoryInput, ctx: ToolContext) -> dict:
    """保存一条长期记忆"""
    if not ctx.user_id:
        return {"status": "error", "message": "无法识别用户身份"}
    from app.services.memory_service import MemoryService

    mem_svc = MemoryService(ctx.db)
    m = await mem_svc.save_memory(
        user_id=ctx.user_id,
        memory_type=input.memory_type,
        content=input.content,
        key=input.key,
        importance=input.importance,
    )
    return {
        "status": "success",
        "memory_id": m.id,
        "type": m.memory_type,
        "rich_block_type": None,
    }


# ============================================================================
# search_memory
# ============================================================================


class SearchMemoryInput(BaseModel):
    query: str = Field(..., min_length=1, description="搜索内容")
    memory_type: Optional[str] = Field(None, description="限定记忆类型（preference/summary/entity）")
    top_k: int = Field(5, ge=1, le=20, description="返回数量（默认 5）")


class SearchMemoryOutput(BaseModel):
    status: str
    count: int
    memories: list[dict]
    rich_block_type: Optional[str] = None


@tool(
    name="search_memory",
    description="搜索长期记忆。当需要回忆用户偏好、历史对话信息、实体关系时使用。",
    input_model=SearchMemoryInput,
    output_model=SearchMemoryOutput,
)
async def search_memory(input: SearchMemoryInput, ctx: ToolContext) -> dict:
    """搜索长期记忆"""
    if not ctx.user_id:
        return {"status": "error", "message": "无法识别用户身份", "count": 0, "memories": []}
    from app.services.memory_service import MemoryService

    mem_svc = MemoryService(ctx.db)
    results = await mem_svc.search_memories(
        user_id=ctx.user_id,
        query=input.query,
        top_k=input.top_k,
        memory_type=input.memory_type,
    )
    return {
        "status": "success",
        "count": len(results),
        "memories": results,
        "rich_block_type": None,
    }


# ============================================================================
# forget_memory
# ============================================================================


class ForgetMemoryInput(BaseModel):
    memory_id: int = Field(..., description="记忆ID")


class ForgetMemoryOutput(BaseModel):
    status: str
    message: str
    rich_block_type: Optional[str] = None


@tool(
    name="forget_memory",
    description="遗忘特定记忆。当用户要求删除或纠正某条记忆时使用。",
    input_model=ForgetMemoryInput,
    output_model=ForgetMemoryOutput,
)
async def forget_memory(input: ForgetMemoryInput, ctx: ToolContext) -> dict:
    """遗忘一条记忆"""
    if not ctx.user_id:
        return {"status": "error", "message": "无法识别用户身份"}
    from app.services.memory_service import MemoryService

    mem_svc = MemoryService(ctx.db)
    success = await mem_svc.forget_memory(user_id=ctx.user_id, memory_id=input.memory_id)
    return {
        "status": "success" if success else "error",
        "message": "记忆已遗忘" if success else "记忆不存在或无权操作",
        "rich_block_type": None,
    }

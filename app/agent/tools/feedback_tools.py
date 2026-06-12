"""反馈 / 知识库保存域工具（v3 迁移）

迁移自 core.py._execute_tool：
- submit_feedback (line 1259)
- save_conversation_knowledge (line 1186)
"""

import logging
from typing import Optional

from pydantic import BaseModel, Field

from app.agent.tool_registry import ToolContext, tool

logger = logging.getLogger("microbubble.agent.tools.feedback")


# ============================================================================
# 1. submit_feedback
# ============================================================================


class SubmitFeedbackInput(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="评分：1=很差 2=较差 3=一般 4=较好 5=很好")
    comment: Optional[str] = Field(None, description="用户的反馈内容（可选）")
    agent_reply: Optional[str] = Field(None, description="被评价的 agent 回复（自动截断 500 字）")
    session_id: Optional[str] = Field(None, description="会话 ID（可选）")


class SubmitFeedbackOutput(BaseModel):
    status: str
    message: str
    feedback_id: Optional[int] = None
    rich_block_type: Optional[str] = None


@tool(
    name="submit_feedback",
    description="记录用户对回复的反馈。当用户说「没用」「不对」「很好」「太棒了」等评价性内容时使用。",
    input_model=SubmitFeedbackInput,
    output_model=SubmitFeedbackOutput,
)
async def submit_feedback(input: SubmitFeedbackInput, ctx: ToolContext) -> dict:
    """保存一条 Feedback"""
    from app.models.feedback import Feedback

    fb = Feedback(
        user_id=ctx.user_id or 0,
        session_id=input.session_id,
        rating=input.rating,
        comment=input.comment,
        agent_reply=(input.agent_reply or "")[:500],
    )
    ctx.db.add(fb)
    await ctx.db.commit()
    return {
        "status": "success",
        "message": "感谢你的反馈！",
        "feedback_id": fb.id,
        "rich_block_type": None,
    }


# ============================================================================
# 2. save_conversation_knowledge
# ============================================================================


class SaveConversationKnowledgeInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="知识标题，简洁概括")
    content: str = Field(..., min_length=1, description="整理后的完整知识内容")
    category: Optional[str] = Field(None, description="分类：基础/方法/文献/FAQ")
    tags: Optional[list[str]] = Field(default_factory=list, description="标签列表")


class SaveConversationKnowledgeOutput(BaseModel):
    status: str
    knowledge_id: Optional[int] = None
    title: Optional[str] = None
    rich_block_type: Optional[str] = None


@tool(
    name="save_conversation_knowledge",
    description="将对话中的重要知识保存到知识库。当对话中讨论了有价值的实验方法、研究发现、技术方案、经验总结等内容时使用。",
    input_model=SaveConversationKnowledgeInput,
    output_model=SaveConversationKnowledgeOutput,
)
async def save_conversation_knowledge(input: SaveConversationKnowledgeInput, ctx: ToolContext) -> dict:
    """从对话中保存一条知识"""
    from app.services.knowledge_service import KnowledgeService

    svc = KnowledgeService(ctx.db)
    knowledge = await svc.create_from_conversation(
        title=input.title,
        content=input.content,
        category=input.category,
        tags=input.tags,
        created_by=ctx.user_id,
    )
    return {
        "status": "success",
        "knowledge_id": knowledge.id,
        "title": knowledge.title,
        "rich_block_type": None,
    }

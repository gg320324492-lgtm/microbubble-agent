"""Chat Feedback API (W98 CHAT-P1-D3 +0)

端点:
- POST /api/v1/chat/feedback  用户对 AI 回复的评价 (👍/👎 + 可选评语)

职责:
- 落 Feedback 表 (复用 app/agent/tools/feedback_tools.py submit_feedback 持久化模式)
- 同步写 search_logs.answer_rating (POST /analytics/search-event 异步写, 供分析)
- 可选校验 message_id 存在 + 归属 (避免越权)

W98 CHAT-P1-D3 派工 v3 沿用:
- 复用 feedback_tools 持久化逻辑 (不重复实现)
- 简化 rating 1-5 → 2 档 (-1=👎 / 1=👍), 与前端按钮组件对齐
- 2-3 行 dispatch 即可, 不破坏 chat.py 路由风格
"""
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_optional
from app.models.feedback import Feedback
from app.models.member import Member

logger = logging.getLogger("microbubble.api.chat_feedback")

router = APIRouter(prefix="/chat", tags=["chat-feedback"])


# ============================================================================
# Pydantic Schemas
# ============================================================================


class ChatFeedbackRequest(BaseModel):
    """POST /chat/feedback 请求体

    字段说明:
    - message_id: AI 回复 chat_messages.id (W98 SSE message_id 注入后新前端必填)
      old 反馈无 message_id 可置 0/None
    - rating: 评价 (-1=👎 / 1=👍)
    - comment: 可选评语 (最多 1000 字, 防止滥用)
    - session_id: 可选 (兼容历史会话级反馈; message_id 与 session_id 二选一)
    - agent_reply: 可选 AI 回复内容快照 (前端为加速埋点直接传)
    """
    message_id: Optional[int] = Field(None, ge=1, description="被评价的 AI 回复 chat_messages.id")
    rating: Literal[-1, 1] = Field(..., description="-1=👎 / 1=👍")
    comment: Optional[str] = Field(None, max_length=1000)
    session_id: Optional[str] = Field(None, max_length=100)
    agent_reply: Optional[str] = Field(None, max_length=2000)


class ChatFeedbackResponse(BaseModel):
    """POST /chat/feedback 响应"""
    ok: bool = True
    feedback_id: int
    rating: int


# ============================================================================
# Endpoint: POST /chat/feedback
# ============================================================================


@router.post(
    "/feedback",
    response_model=ChatFeedbackResponse,
    summary="用户对 AI 回复的评价 (👍/👎 + 可选评语)",
)
async def submit_chat_feedback(
    payload: ChatFeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[Member] = Depends(get_current_user_optional),
):
    """W98 CHAT-P1-D3:

    1. 复用 feedback_tools 持久化模式 (不重写)
    2. user_id 从 current_user 取 (匿名降级 0)
    3. message_id (Optional) — 通过则校验存在
    4. 返回 feedback_id 供前端去重 (幂等用)

    P1 简化决策:
    - rating 仅接 -1 / 1 (前端 FeedbackButtons 设计), 其它值 422
    - chat_history 同步落库 (持久化优先于 analytics 双写)
    """
    if payload.rating not in (-1, 1):
        raise HTTPException(
            status_code=422,
            detail="rating must be -1 (👎) or 1 (👍)",
        )

    # 0. 校验 message_id 存在 (前端可能重复点击 / 旧消息无 message_id)
    if payload.message_id is not None:
        from app.models.chat_history import ChatMessage  # 局部 import 避免循环
        check = await db.execute(
            select(ChatMessage.id).where(ChatMessage.id == payload.message_id)
        )
        if check.scalar_one_or_none() is None:
            raise HTTPException(
                status_code=404,
                detail=f"chat_messages.id={payload.message_id} not found",
            )

    # 1. 落 feedback 表 (复用 feedback_tools 持久化模式)
    user_id = current_user.id if current_user else 0
    fb = Feedback(
        user_id=user_id,
        session_id=payload.session_id,
        rating=payload.rating,
        comment=payload.comment,
        agent_reply=(payload.agent_reply or "")[:500],  # 与老模型一致 (500 字截断)
        message_id=payload.message_id,
    )
    db.add(fb)
    await db.commit()
    await db.refresh(fb)

    logger.info(
        f"chat-feedback id={fb.id} user={user_id} rating={payload.rating} "
        f"message_id={payload.message_id} session_id={payload.session_id}"
    )

    # 2. (可选) 同步写 search_logs.answer_rating 维度
    #    策略: 同 user_id + 同 session 最新的 search_log 行 UPDATE answer_rating
    #    失败不回滚 (best-effort, 不阻塞主路径)
    if payload.message_id is not None and user_id > 0:
        try:
            from app.models.search_log import SearchLog
            # 同 session 取最近一条 (无 session 时为 None)
            target_q = (
                select(SearchLog)
                .where(SearchLog.user_id == user_id)
                .order_by(SearchLog.created_at.desc())
                .limit(1)
            )
            if payload.session_id:
                target_q = target_q.where(SearchLog.session_id == payload.session_id)
            target = (await db.execute(target_q)).scalar_one_or_none()
            if target is not None:
                target.answer_rating = payload.rating
                await db.commit()
        except Exception as e:
            logger.warning(
                f"search_logs.answer_rating 同步写入失败 (best-effort): {e}"
            )

    return ChatFeedbackResponse(
        ok=True,
        feedback_id=fb.id if fb.id is not None else 0,
        rating=payload.rating,
    )

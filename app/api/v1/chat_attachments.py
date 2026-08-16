"""#P5 聊天附加文档 API — 用户级全局 (跨 session 复用)

设计:
- 用户手动附加的知识库文档作为"本对话参考文档", 跨 session 持久
- 类似 ChatGPT Project Memory
- chat_stream 自动从 DB 读取用户全局附加, 注入 system prompt

端点:
- GET    /api/v1/chat/attached-documents           列出当前用户所有附加
- POST   /api/v1/chat/attached-documents/{id}     附加一个文档 (幂等)
- DELETE /api/v1/chat/attached-documents/{id}     移除一个文档
- DELETE /api/v1/chat/attached-documents           清空所有附加

约束:
- knowledge 必须 storage_mode='kb' (避免网盘文件泄露)
- 用户级硬上限 8 条 (与 _build_attached_knowledge_block 一致)
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundException
from app.core.security import get_current_user
from app.models.chat_session_attached_document import ChatSessionAttachedDocument
from app.models.knowledge import Knowledge
from app.models.member import Member


router = APIRouter(prefix="/chat/attached-documents", tags=["chat-attachments"])


# 用户级硬上限 — 与 _build_attached_knowledge_block MAX_ATTACHED = 8 一致
MAX_ATTACHED_PER_USER = 8


class AttachedDocumentItem(BaseModel):
    """返回给前端的附加文档项"""
    id: int
    title: str
    category: Optional[str] = None
    snippet: Optional[str] = None
    attached_at: datetime

    class Config:
        from_attributes = True


@router.get("", response_model=List[AttachedDocumentItem])
async def list_attached_documents(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出当前用户所有附加的文档 (按 attached_at 倒序)"""
    # JOIN knowledge 拿 title/category/snippet (避免前端另发请求)
    stmt = (
        select(
            ChatSessionAttachedDocument.knowledge_id,
            ChatSessionAttachedDocument.attached_at,
            Knowledge.title,
            Knowledge.category,
            Knowledge.content,
        )
        .join(Knowledge, Knowledge.id == ChatSessionAttachedDocument.knowledge_id)
        .where(
            ChatSessionAttachedDocument.user_id == current_user.id,
            Knowledge.deleted_at.is_(None),
            Knowledge.storage_mode == "kb",
        )
        .order_by(ChatSessionAttachedDocument.attached_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        AttachedDocumentItem(
            id=row.knowledge_id,
            title=row.title,
            category=row.category,
            snippet=(row.content or "")[:200] if row.content else None,
            attached_at=row.attached_at,
        )
        for row in rows
    ]


@router.post("/{knowledge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def attach_document(
    knowledge_id: int = Path(..., description="知识库文档 ID"),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """附加一个文档到用户的全局上下文 (幂等: 重复附加返回 204 不报错)"""
    # 1. 校验 knowledge 存在 + storage_mode='kb' (避免网盘文件泄露)
    kb_row = (await db.execute(
        select(Knowledge).where(
            Knowledge.id == knowledge_id,
            Knowledge.deleted_at.is_(None),
            Knowledge.storage_mode == "kb",
        )
    )).scalar_one_or_none()
    if not kb_row:
        raise NotFoundException(f"知识库文档 {knowledge_id} 不存在或不可访问")

    # 2. 硬上限 8 条校验
    count_row = (await db.execute(
        select(ChatSessionAttachedDocument).where(
            ChatSessionAttachedDocument.user_id == current_user.id,
        )
    )).scalars().all()
    if len(count_row) >= MAX_ATTACHED_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"最多附加 {MAX_ATTACHED_PER_USER} 个文档, 请先移除一些",
        )

    # 3. INSERT (唯一约束保证幂等)
    record = ChatSessionAttachedDocument(
        user_id=current_user.id,
        knowledge_id=knowledge_id,
    )
    db.add(record)
    try:
        await db.commit()
    except IntegrityError:
        # 唯一约束冲突 → 静默忽略 (已附加)
        await db.rollback()
        return None

    return None


@router.delete("/{knowledge_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_document(
    knowledge_id: int = Path(...),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """从全局上下文移除一个文档"""
    result = await db.execute(
        delete(ChatSessionAttachedDocument).where(
            ChatSessionAttachedDocument.user_id == current_user.id,
            ChatSessionAttachedDocument.knowledge_id == knowledge_id,
        )
    )
    await db.commit()
    # result.rowcount 是删除的行数, 0 = 没附加过 (幂等)
    return None


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_attached_documents(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """清空当前用户所有附加的文档"""
    await db.execute(
        delete(ChatSessionAttachedDocument).where(
            ChatSessionAttachedDocument.user_id == current_user.id,
        )
    )
    await db.commit()
    return None
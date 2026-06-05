"""长期记忆管理 API"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.exceptions import NotFoundException
from app.models.member import Member
from app.services.memory_service import MemoryService

router = APIRouter()


class MemoryResponse(BaseModel):
    """记忆响应"""
    id: int
    memory_type: str
    key: Optional[str] = None
    content: str
    importance: float
    access_count: int
    source_session: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class MemoryList(BaseModel):
    """记忆列表"""
    items: List[MemoryResponse]
    total: int


class MemoryUpdate(BaseModel):
    """更新记忆"""
    content: str


@router.get("/memories", response_model=MemoryList)
async def list_memories(
    memory_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """查询用户记忆列表"""
    service = MemoryService(db)
    items, total = await service.list_memories(
        user_id=current_user.id,
        memory_type=memory_type,
        page=page,
        page_size=page_size
    )
    return MemoryList(items=items, total=total)


@router.put("/memories/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: int,
    data: MemoryUpdate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改记忆内容"""
    service = MemoryService(db)
    memory = await service.update_memory(
        user_id=current_user.id,
        memory_id=memory_id,
        content=data.content
    )
    if not memory:
        raise NotFoundException("记忆")
    return memory


@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(
    memory_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """遗忘记忆"""
    service = MemoryService(db)
    success = await service.forget_memory(
        user_id=current_user.id,
        memory_id=memory_id
    )
    if not success:
        raise NotFoundException("记忆")

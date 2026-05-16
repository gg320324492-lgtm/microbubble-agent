from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.models.knowledge import Knowledge
from app.schemas.knowledge import (
    KnowledgeCreate, KnowledgeUpdate, KnowledgeResponse, KnowledgeList
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter()


@router.post("/knowledge", response_model=KnowledgeResponse, status_code=201)
async def create_knowledge(
    knowledge_data: KnowledgeCreate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """添加知识"""
    service = KnowledgeService(db)
    knowledge = await service.create_knowledge(
        title=knowledge_data.title,
        content=knowledge_data.content,
        category=knowledge_data.category,
        tags=knowledge_data.tags,
        source=knowledge_data.source,
        source_type=knowledge_data.source_type,
        created_by=current_user.id
    )
    return knowledge


@router.get("/knowledge", response_model=KnowledgeList)
async def list_knowledge(
    category: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """查询知识库"""
    query = select(Knowledge)

    if category:
        query = query.where(Knowledge.category == category)
    if keyword:
        query = query.where(
            Knowledge.title.contains(keyword) |
            Knowledge.content.contains(keyword)
        )

    query = query.order_by(Knowledge.created_at.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    items = result.scalars().all()

    return KnowledgeList(items=items, total=len(items))


@router.get("/knowledge/{knowledge_id}", response_model=KnowledgeResponse)
async def get_knowledge(
    knowledge_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取知识详情"""
    result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
    knowledge = result.scalar_one_or_none()

    if not knowledge:
        raise HTTPException(status_code=404, detail="知识不存在")

    return knowledge


@router.put("/knowledge/{knowledge_id}", response_model=KnowledgeResponse)
async def update_knowledge(
    knowledge_id: int,
    knowledge_data: KnowledgeUpdate,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新知识"""
    service = KnowledgeService(db)
    update_data = knowledge_data.model_dump(exclude_unset=True)
    knowledge = await service.update_knowledge(knowledge_id, **update_data)

    if not knowledge:
        raise HTTPException(status_code=404, detail="知识不存在")

    return knowledge


@router.delete("/knowledge/{knowledge_id}", status_code=204)
async def delete_knowledge(
    knowledge_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除知识"""
    result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
    knowledge = result.scalar_one_or_none()

    if not knowledge:
        raise HTTPException(status_code=404, detail="知识不存在")

    await db.delete(knowledge)
    await db.commit()


@router.get("/knowledge/search/semantic")
async def semantic_search(
    query: str,
    category: Optional[str] = None,
    top_k: int = Query(5, ge=1, le=20),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """语义搜索（RAG）"""
    service = KnowledgeService(db)
    results = await service.search_semantic(query=query, top_k=top_k, category=category)
    return results

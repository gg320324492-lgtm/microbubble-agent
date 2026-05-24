from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List

from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.models.knowledge import Knowledge
from app.schemas.knowledge import (
    KnowledgeCreate, KnowledgeUpdate, KnowledgeResponse, KnowledgeList,
    KnowledgeSearchResult
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
    # 构建过滤条件
    filters = []
    if category:
        filters.append(Knowledge.category == category)
    if keyword:
        filters.append(
            Knowledge.title.ilike(f"%{keyword}%") |
            Knowledge.content.ilike(f"%{keyword}%")
        )

    # 总数查询
    count_query = select(func.count()).select_from(Knowledge)
    if filters:
        count_query = count_query.where(*filters)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页查询
    query = select(Knowledge)
    if filters:
        query = query.where(*filters)
    query = query.order_by(Knowledge.created_at.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    items = result.scalars().all()

    return KnowledgeList(items=items, total=total)


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


@router.get("/knowledge/search/semantic", response_model=List[KnowledgeSearchResult])
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


@router.post("/knowledge/upload", response_model=KnowledgeResponse, status_code=201)
async def upload_knowledge_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """上传文件到知识库，自动提取文本、分类、标签"""
    # 验证文件类型
    allowed_exts = {'.pdf', '.docx', '.doc', '.xlsx', '.xls', '.txt', '.md'}
    filename = file.filename or ""
    ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in allowed_exts:
        raise HTTPException(400, f"不支持的文件类型: {ext}")

    # 读取文件
    file_data = await file.read()
    if len(file_data) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(400, f"文件过大（最大 {settings.MAX_UPLOAD_SIZE_MB}MB）")

    # 提取文本
    from app.services.file_parser_service import file_parser_service
    try:
        content = await file_parser_service.extract_text(
            file_data, filename, file.content_type or ""
        )
    except Exception as e:
        raise HTTPException(400, f"文本提取失败: {str(e)}")

    if not content.strip():
        raise HTTPException(400, "未能从文件中提取到文本内容")

    # 上传文件到 MinIO
    from app.services.file_service import file_service
    upload_result = await file_service.upload_file(
        file_data=file_data,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        prefix="knowledge"
    )

    # 创建知识条目（后台自动分析）
    service = KnowledgeService(db)
    knowledge = await service.create_from_file(
        title=title or filename,
        content=content,
        file_path=upload_result["object_name"],
        file_name=filename,
        file_type=file.content_type or "application/octet-stream",
        created_by=current_user.id
    )
    return knowledge


@router.post("/knowledge/from-chat", status_code=201)
async def create_from_chat(
    title: str = Body(...),
    content: str = Body(...),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """从聊天内容创建知识条目（不涉及文件上传）"""
    service = KnowledgeService(db)
    knowledge = await service.create_knowledge(
        title=title,
        content=content,
        source="chat",
        source_type="chat",
        created_by=current_user.id
    )
    return knowledge


@router.get("/knowledge/stats")
async def knowledge_stats(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """知识库分类统计"""
    result = await db.execute(
        select(
            Knowledge.category,
            func.count(Knowledge.id)
        ).group_by(Knowledge.category)
    )
    rows = result.all()
    categories = {row[0] or "未分类": row[1] for row in rows}
    total = sum(categories.values())
    return {"total": total, "categories": categories}

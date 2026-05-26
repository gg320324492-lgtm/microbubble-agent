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
    KnowledgeSearchResult, RelatedKnowledge, KnowledgeGraph,
    DynamicCategory, TagCloudItem, KnowledgeStats,
    QAResponse, ResearchResponse,
    ReasonRequest, ReasonResponse, ReviewQueueItem, ReviewQueueResponse,
)
from app.services.knowledge_service import KnowledgeService
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.knowledge_qa_service import KnowledgeQAService
from app.services.auto_research_service import AutoResearchService
from app.services.dynamic_taxonomy_service import DynamicTaxonomyService

import logging
logger = logging.getLogger("microbubble.knowledge")


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


@router.get("/knowledge/categories", response_model=List[DynamicCategory])
async def get_categories(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取动态分类列表（从实际数据自动聚合）"""
    svc = KnowledgeGraphService(db)
    return await svc.get_dynamic_categories()


@router.get("/knowledge/tags", response_model=List[TagCloudItem])
async def get_tag_cloud(
    min_freq: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取标签云（频率排序）"""
    svc = KnowledgeGraphService(db)
    return await svc.get_tag_cloud(min_freq=min_freq, limit=limit)


@router.get("/knowledge/graph", response_model=KnowledgeGraph)
async def get_knowledge_graph(
    center_id: Optional[int] = Query(None),
    depth: int = Query(2, ge=1, le=5),
    limit: int = Query(50, ge=1, le=200),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取知识图谱数据（用于前端可视化）"""
    svc = KnowledgeGraphService(db)
    return await svc.get_knowledge_graph(center_id=center_id, depth=depth, limit=limit)


@router.get("/knowledge/stats/rich", response_model=KnowledgeStats)
async def rich_knowledge_stats(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """知识库增强统计"""
    svc = KnowledgeGraphService(db)
    return await svc.get_knowledge_stats()


@router.get("/knowledge/{knowledge_id}/related", response_model=List[RelatedKnowledge])
async def get_related_knowledge(
    knowledge_id: int,
    relation_type: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取与指定知识关联的其他条目"""
    svc = KnowledgeGraphService(db)
    types = [relation_type] if relation_type else None
    return await svc.get_related(knowledge_id, relation_types=types, limit=limit)


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
    allowed_exts = {'.pdf', '.docx', '.xlsx', '.txt', '.md'}
    filename = file.filename or ""
    ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in allowed_exts:
        raise HTTPException(400, f"不支持的文件类型: {ext}")

    # 先检查 Content-Length 头，避免读取超大文件
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content_length = file.headers.get("content-length")
    if content_length and int(content_length) > max_bytes:
        raise HTTPException(400, f"文件过大（最大 {settings.MAX_UPLOAD_SIZE_MB}MB）")

    # 读取文件
    file_data = await file.read()

    # 二次校验实际大小
    if len(file_data) > max_bytes:
        raise HTTPException(400, f"文件过大（最大 {settings.MAX_UPLOAD_SIZE_MB}MB）")

    # 提取文本
    from app.services.file_parser_service import file_parser_service
    try:
        content = await file_parser_service.extract_text(
            file_data, filename, file.content_type or "application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(400, f"文本提取失败: {str(e)}")

    if not content.strip():
        raise HTTPException(400, "未能从文件中提取到文本内容")

    # 上传文件到 MinIO
    from app.services.file_service import file_service
    try:
        upload_result = await file_service.upload_file(
            file_data=file_data,
            filename=filename,
            content_type=file.content_type or "application/octet-stream",
            prefix="knowledge"
        )
    except Exception as e:
        logger.exception(f"MinIO 上传失败: {filename}")
        raise HTTPException(500, "文件存储服务暂时不可用，请稍后重试")

    # 创建知识条目（后台自动分析）
    service = KnowledgeService(db)
    try:
        raw_type = file.content_type or "application/octet-stream"
        safe_file_type = raw_type[:200]
        knowledge = await service.create_from_file(
            title=title or filename,
            content=content,
            file_path=upload_result["object_name"],
            file_name=filename,
            file_type=safe_file_type,
            created_by=current_user.id
        )
    except Exception as e:
        logger.exception(f"知识条目创建失败: {filename}")
        # 清理 MinIO 中的孤立文件
        try:
            file_service.delete_file(upload_result["object_name"])
        except Exception:
            logger.warning(f"清理孤立文件失败: {upload_result['object_name']}")
        raise HTTPException(500, "知识条目创建失败，请稍后重试")

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


@router.get("/knowledge/review-queue", response_model=ReviewQueueResponse)
async def get_review_queue(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取待审阅的知识条目（矛盾检测标记）"""
    result = await db.execute(
        select(Knowledge).where(Knowledge.needs_review == True)
    )
    items = result.scalars().all()
    return ReviewQueueResponse(
        items=[
            ReviewQueueItem(
                id=k.id, title=k.title, category=k.category,
                needs_review=k.needs_review, analysis_status=k.analysis_status
            )
            for k in items
        ],
        total=len(items),
    )


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


@router.get("/knowledge/taxonomy/emerging")
async def get_emerging_categories(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取涌现分类体系（从实际数据中聚合）"""
    svc = DynamicTaxonomyService(db)
    return await svc.get_emerging_categories()


@router.get("/knowledge/taxonomy/network")
async def get_theme_network(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取主题关联网络（基于共享概念的分类间关联）"""
    svc = DynamicTaxonomyService(db)
    return await svc.get_theme_network()


@router.post("/knowledge/qa", response_model=QAResponse)
async def ask_knowledge(
    question: str = Body(..., min_length=1, max_length=500),
    top_k: int = Body(8, ge=3, le=20),
    auto_research: bool = Body(True),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """RAG 知识问答 — 基于知识库合成答案，附带来源引用"""
    svc = KnowledgeQAService(db)
    result = await svc.answer_question(
        question=question,
        top_k=top_k,
        auto_research=auto_research,
    )

    # 获取推荐阅读的知识条目 ID
    related = await svc.get_related_knowledge_ids(question)

    return {
        **result,
        "related_knowledge": related,
    }


@router.post("/knowledge/research", response_model=ResearchResponse)
async def trigger_research(
    queries: List[str] = Body(..., min_length=1, max_length=10),
    max_results_per_query: int = Body(3, ge=1, le=5),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """触发自主研究 — 搜索网络知识并自动入库"""
    svc = AutoResearchService(db)
    result = await svc.research_topic(
        queries=queries,
        max_results_per_query=max_results_per_query,
    )
    return result


@router.post("/knowledge/research/gaps")
async def fill_knowledge_gaps(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """分析知识库薄弱领域并自动补充"""
    svc = AutoResearchService(db)
    result = await svc.fill_knowledge_gaps()
    return result


@router.get("/knowledge/health/contradictions")
async def detect_contradictions(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """检测知识库中的矛盾条目"""
    svc = AutoResearchService(db)
    result = await svc.detect_and_handle_contradictions()
    return {"contradictions": result, "count": len(result)}


@router.get("/knowledge/health/duplicates")
async def detect_duplicates(
    threshold: float = Query(0.92, ge=0.5, le=1.0),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """检测重复条目"""
    svc = AutoResearchService(db)
    result = await svc.detect_duplicates(threshold=threshold)
    return {"duplicates": result, "count": len(result)}


@router.get("/knowledge/health/staleness")
async def detect_staleness(
    days: int = Query(365, ge=30, le=730),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """检测可能过期的条目"""
    svc = AutoResearchService(db)
    result = await svc.detect_staleness(days=days)
    return {"stale_entries": result, "count": len(result)}


@router.post("/knowledge/{knowledge_id}/reanalyze", response_model=KnowledgeResponse)
async def reanalyze_knowledge(
    knowledge_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """重新分析指定知识条目（嵌入 + LLM 分析 + 关联），用于分析失败或卡住时重试"""
    service = KnowledgeService(db)
    knowledge = await service.reanalyze(knowledge_id)
    if not knowledge:
        raise HTTPException(status_code=404, detail="知识不存在")
    return knowledge


@router.post("/knowledge/reason", response_model=ReasonResponse)
async def reason_knowledge(
    body: ReasonRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """多跳推理问答 — 遍历知识图谱关联链进行推理"""
    from app.schemas.knowledge import ReasonRequest, ReasonResponse
    qa = KnowledgeQAService(db)
    result = await qa.reason(question=body.question, max_hops=body.max_hops, top_k=body.top_k)
    return result




@router.post("/knowledge/{knowledge_id}/review")
async def mark_reviewed(
    knowledge_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """标记知识条目为已审阅"""
    result = await db.execute(
        select(Knowledge).where(Knowledge.id == knowledge_id)
    )
    knowledge = result.scalar_one_or_none()
    if not knowledge:
        raise HTTPException(status_code=404, detail="知识不存在")
    knowledge.needs_review = False
    await db.commit()
    return {"message": "已标记为已审阅", "id": knowledge_id}

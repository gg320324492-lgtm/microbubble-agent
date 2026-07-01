import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List

from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.core.exceptions import NotFoundException, ValidationException
from app.models.member import Member
from app.models.knowledge import Knowledge
from app.schemas.knowledge import (
    KnowledgeCreate, KnowledgeUpdate, KnowledgeResponse, KnowledgeList,
    KnowledgeSearchResult, RelatedKnowledge, KnowledgeGraph,
    DynamicCategory, TagCloudItem, KnowledgeStats,
    QAResponse, ResearchResponse,
    ReasonRequest, ReasonResponse, ReviewQueueItem, ReviewQueueResponse,
    KnowledgeImageItem, KnowledgeImageList, ExtractionItem, ExtractionList,
    MultimodalExtractResponse,
    AutoExpansionIngestRequest, AutoExpansionIngestResponse,  # #043
)
from app.services.knowledge_service import KnowledgeService
from app.services.knowledge_graph_service import KnowledgeGraphService
from app.services.knowledge_qa_service import KnowledgeQAService
from app.services.auto_research_service import AutoResearchService
from app.services.dynamic_taxonomy_service import DynamicTaxonomyService

import logging
logger = logging.getLogger("microbubble.knowledge")


router = APIRouter()


async def _upload_knowledge_images(knowledge_id: int, images: dict, source_filename: str):
    """后台任务：上传 PDF 提取的图片到 MinIO，更新知识条目的图片 URL"""
    from app.core.database import async_session
    from app.services.file_service import file_service

    image_urls = {}
    for placeholder, img_data in images.items():
        try:
            fig_idx = placeholder.strip().replace("[FIGURE:", "").replace("]", "")
            result = await file_service.upload_file(
                file_data=img_data["bytes"],
                filename=f"fig_{fig_idx}.{img_data['ext']}",
                content_type=f"image/{img_data['ext']}",
                prefix=f"knowledge/{knowledge_id}",
            )
            image_urls[placeholder] = result["url"]
        except Exception as e:
            logger.warning(f"图片上传失败(knowledge_id={knowledge_id}, {placeholder}): {e}")

    if image_urls:
        try:
            async with async_session() as db:
                result = await db.execute(
                    select(Knowledge).where(Knowledge.id == knowledge_id)
                )
                knowledge = result.scalar_one_or_none()
                if knowledge:
                    content = knowledge.content
                    for placeholder, url in image_urls.items():
                        fig_num = placeholder.strip().replace("[FIGURE:", "").replace("]", "")
                        content = content.replace(
                            placeholder,
                            f"\n![图片 {fig_num}]({url})\n",
                        )
                    knowledge.content = content
                    await db.commit()
                    logger.info(f"图片 URL 已嵌入(knowledge_id={knowledge_id}, {len(image_urls)} 张)")
        except Exception as e:
            logger.error(f"图片 URL 嵌入失败(knowledge_id={knowledge_id}): {e}")


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
    has_file: Optional[bool] = Query(None, description="v28 step 69: 只返回有上传文件的条目（file_type 非空）"),
    source_type: Optional[str] = Query(None, description="#043: 按 source_type 过滤（auto_expansion / auto_research / conversation / paper / chat）"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """查询知识库（列表不含 content 字段，详情请调 /knowledge/{id}）

    v28 step 69: 加 has_file=true 严格过滤
    - has_file=true: 只返回 file_type 非空（即真实上传的 PDF/Word/PPT）
    - has_file 不传或 false: 返回全部（含 LLM 自动入库的 [拓展-XXX]）

    #043: 加 source_type 过滤（用于自动拓展分类 chip）
    - source_type=auto_expansion: 只返回 qa-bench 自动入库条目
    - 与 category 互斥（前者过滤 source_type，后者过滤 category）
    """
    # 构建过滤条件
    filters = []
    if category:
        from sqlalchemy import any_
        filters.append(
            (Knowledge.category == category) |
            (Knowledge.tags.any(category))
        )
    if keyword:
        filters.append(
            Knowledge.title.ilike(f"%{keyword}%") |
            Knowledge.content.ilike(f"%{keyword}%")
        )
    # v28 step 69: has_file 过滤
    if has_file:
        filters.append(Knowledge.file_type.isnot(None))
        filters.append(Knowledge.file_type != '')
    # #043: source_type 过滤
    if source_type:
        filters.append(Knowledge.source_type == source_type)

    # 总数查询
    count_query = select(func.count()).select_from(Knowledge)
    if filters:
        count_query = count_query.where(*filters)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # 分页查询 — content 字段只取前 200 字符作为 snippet，不返回完整内容
    # 2026-07-01 课题组网盘 PR1: 加 deleted_at IS NULL 过滤, 软删除条目不显示
    query = select(Knowledge).where(Knowledge.deleted_at.is_(None))
    if filters:
        query = query.where(*filters)
    query = query.order_by(Knowledge.created_at.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    result = await db.execute(query)
    items = result.scalars().all()

    # 列表不含完整 content，只生成 snippet 供卡片预览
    # 2026-06-19 修复: 不要直接 mutate ORM item.content=None（SQLAlchemy autoflush 会
    # 触发 UPDATE knowledge SET content=NULL → NOT NULL 违反）
    # 改为：转 dict 时直接不放 content/formatted_content 字段

    # 2026-06-19 Phase 7: 批量拿缩略图 + 图片数（避免 N+1）
    from app.models.knowledge_multimodal import KnowledgeImage
    from sqlalchemy import func as sql_func
    kb_ids = [it.id for it in items]
    img_map: dict = {}
    if kb_ids:
        img_agg = await db.execute(
            select(
                KnowledgeImage.knowledge_id,
                sql_func.count(KnowledgeImage.id).label("cnt"),
                sql_func.min(KnowledgeImage.id).label("first_id"),
            )
            .where(KnowledgeImage.knowledge_id.in_(kb_ids))
            .group_by(KnowledgeImage.knowledge_id)
        )
        img_map = {row.knowledge_id: (row.cnt, row.first_id) for row in img_agg.all()}
        # 取首图 URL
        first_ids = [v[1] for v in img_map.values() if v[1] is not None]
        first_imgs = {}
        if first_ids:
            first_res = await db.execute(
                select(KnowledgeImage.id, KnowledgeImage.image_url)
                .where(KnowledgeImage.id.in_(first_ids))
            )
            first_imgs = {r.id: r.image_url for r in first_res.all()}

    # 转 dict 形态（避免 mutate ORM 触发 autoflush）
    list_items = []
    for it in items:
        snippet = it.snippet if hasattr(it, "snippet") and it.snippet else None
        if not snippet and not it.summary and it.content:
            snippet = it.content[:200]
        cnt, first_id = img_map.get(it.id, (0, None))
        list_items.append({
            "id": it.id, "title": it.title,
            "category": it.category, "tags": it.tags,
            "key_concepts": it.key_concepts, "related_topics": it.related_topics,
            "knowledge_type": it.knowledge_type, "source": it.source,
            "source_type": it.source_type, "summary": it.summary,
            "snippet": snippet, "analysis_status": it.analysis_status,
            "quality_score": it.quality_score, "needs_review": it.needs_review,
            "topic": it.topic, "created_by": it.created_by,
            "created_at": it.created_at, "updated_at": it.updated_at,
            "thumbnail_url": first_imgs.get(first_id) if first_id else None,
            "image_count": cnt,
            "file_path": it.file_path,
            "file_name": it.file_name,
            "file_type": it.file_type,
            "meta": it.meta,  # #043: 自动拓展条目的 RichBlock 数据
        })
    return KnowledgeList(items=list_items, total=total)


@router.get("/knowledge/stats")
async def knowledge_stats(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """知识库分类统计

    #043: 加 source_types 分布 (用于 Dashboard 自动拓展 chip 计数)
    """
    result = await db.execute(
        select(
            Knowledge.category,
            func.count(Knowledge.id)
        ).group_by(Knowledge.category)
    )
    rows = result.all()
    categories = {row[0] or "未分类": row[1] for row in rows}
    total = sum(categories.values())

    # #043: source_type 分布
    # 2026-06-30 修复: GROUP BY 不返回 count=0 的 group, 导致 auto_expansion
    # 清空时 chip 上没数字 → 用户视觉看到"自动拓展是空白的".
    # 显式补 0 防止前端 chip "v-if count > 0" 直接不渲染数字
    st_result = await db.execute(
        select(
            Knowledge.source_type,
            func.count(Knowledge.id)
        ).where(Knowledge.source_type.isnot(None))
        .group_by(Knowledge.source_type)
    )
    source_types = {row[0]: row[1] for row in st_result.all()}
    # 显式补 count=0 的 source_type (Dashboard chip 必须能拿到值才能渲染)
    for st in ("auto_expansion", "auto_research", "conversation", "meeting", "paper", "chat"):
        source_types.setdefault(st, 0)

    return {
        "total": total,
        "categories": categories,
        "source_types": source_types,
    }


@router.get("/knowledge/auto-intake-summary")
async def auto_intake_summary(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """W5 T5.4 + W6 D5: KB 自动入库监控 summary

    给 ProjectStatsView 第 3 个 tab (KB 入库监控) 提供数据源.
    字段:
      - today_intake: 今日入库条数
      - weekly_intake: 7日入库趋势 (list of 7 ints)
      - hit_rate: KB 命中率 (0-1)
      - negative_feedback_rate: 负反馈率 (0-1)
      - rollback_count: 7 天内 rollback 次数
      - last_update: summary 文件最后更新 timestamp
      - gray_scale_enabled: 灰度开关状态 (0/5/25/100)

    数据源:
      - data/auto_intake_summary.json (save_to_kb.py 写入)
      - DB 实时聚合: 今日 / 7 日 入库量
      - data/auto_intake_rollback_*.json (rollback 任务写入)
    """
    from datetime import datetime, timedelta
    from pathlib import Path

    result = {
        "today_intake": 0,
        "weekly_intake": [0] * 7,
        "hit_rate": 0.0,
        "negative_feedback_rate": 0.0,
        "rollback_count": 0,
        "last_update": None,
        "gray_scale_enabled": 0,
        "total_in_db": 0,
    }

    # 1. 读 save_to_kb.py 输出的 summary 文件
    summary_path = Path("data/auto_intake_summary.json")
    if summary_path.exists():
        try:
            import json
            summary_data = json.loads(summary_path.read_text(encoding="utf-8"))
            result["last_update"] = summary_data.get("timestamp")
            result["gray_scale_enabled"] = 100 if summary_data.get("gray_flag_enabled") else 0
        except Exception:
            pass

    # 2. DB 聚合: 今日 + 7 日入库量 (source_type='auto_expansion')
    today = datetime.now().date()
    week_ago = today - timedelta(days=6)

    today_count_result = await db.execute(
        select(func.count(Knowledge.id))
        .where(Knowledge.source_type == "auto_expansion")
        .where(func.date(Knowledge.created_at) == today)
    )
    result["today_intake"] = today_count_result.scalar() or 0

    weekly_counts = []
    for d_offset in range(6, -1, -1):
        d = today - timedelta(days=d_offset)
        c_result = await db.execute(
            select(func.count(Knowledge.id))
            .where(Knowledge.source_type == "auto_expansion")
            .where(func.date(Knowledge.created_at) == d)
        )
        weekly_counts.append(c_result.scalar() or 0)
    result["weekly_intake"] = weekly_counts

    # 3. DB 总数
    total_result = await db.execute(
        select(func.count(Knowledge.id))
        .where(Knowledge.source_type == "auto_expansion")
    )
    result["total_in_db"] = total_result.scalar() or 0

    # 4. 读 rollback 报告 (7 天内)
    rollback_dir = Path("data")
    if rollback_dir.exists():
        for rb_path in sorted(rollback_dir.glob("auto_intake_rollback_*.json"), reverse=True):
            try:
                rb_data = json.loads(rb_path.read_text(encoding="utf-8"))
                rb_ts = datetime.fromisoformat(rb_data.get("timestamp", "1970-01-01"))
                if (datetime.now() - rb_ts).days <= 7:
                    result["rollback_count"] += rb_data.get("deleted_count", 0)
            except Exception:
                pass

    # 5. 命中率 / 负反馈率 (留 0 待 W6 T6.4 反馈模块接入)
    # 暂用 stub 0.0, 后续 W6 T6.4 接入 feedback 表后填充
    return result


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


@router.get("/knowledge/entities/graph", response_model=dict)
async def get_entity_graph(
    entity_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取实体图谱（节点=实体，边=共现关系）

    v69 P1b fix: 必须放在 /knowledge/{knowledge_id}/graph 之前注册——
    FastAPI 按注册顺序匹配路径，否则 /knowledge/entities/graph 会被
    /knowledge/{knowledge_id}/graph 拦截（knowledge_id="entities" 解析失败 → 422）
    """
    from app.services.entity_service import EntityService
    svc = EntityService(db)
    return await svc.get_entity_graph(entity_id=entity_id, limit=limit)


@router.get("/knowledge/{knowledge_id}/graph", response_model=KnowledgeGraph)
async def get_knowledge_graph_by_id(
    knowledge_id: int,
    depth: int = Query(2, ge=1, le=5),
    limit: int = Query(50, ge=1, le=200),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """v28 step 109.18: per-id 图谱端点别名（前端 KnowledgeDetailView 调用此 URL）

    与 /knowledge/graph?center_id=X 行为一致，仅 URL 形式不同。
    """
    svc = KnowledgeGraphService(db)
    return await svc.get_knowledge_graph(center_id=knowledge_id, depth=depth, limit=limit)


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

    # v31 埋点: 异步写入 (不阻塞响应)
    if results:
        import asyncio
        from app.models.search_log import SearchLog
        from app.core.database import async_session
        import os
        top_ids = [r["id"] for r in results if isinstance(r, dict) and "id" in r]
        if top_ids:
            embedding_model = os.getenv("EMBEDDING_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B")

            async def _log_search():
                try:
                    async with async_session() as log_db:
                        log = SearchLog(
                            query=query,
                            top_ids=top_ids,
                            embedding_model=embedding_model,
                            source="knowledge_search_semantic",
                            session_id=None,
                            # v31.2: 登录用户绑 user_id (匿名写 NULL)
                            user_id=current_user.id if current_user else None,
                        )
                        log_db.add(log)
                        await log_db.commit()
                except Exception:
                    pass  # 埋点失败静默

            asyncio.create_task(_log_search())

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
    allowed_exts = {'.pdf', '.docx', '.xlsx', '.pptx', '.txt', '.md'}
    filename = file.filename or ""
    ext = '.' + filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in allowed_exts:
        raise ValidationException(f"不支持的文件类型: {ext}")

    # 先检查 Content-Length 头，避免读取超大文件
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content_length = file.headers.get("content-length")
    if content_length and int(content_length) > max_bytes:
        raise ValidationException(f"文件过大（最大 {settings.MAX_UPLOAD_SIZE_MB}MB）")

    # 读取文件
    file_data = await file.read()

    # 二次校验实际大小
    if len(file_data) > max_bytes:
        raise ValidationException(f"文件过大（最大 {settings.MAX_UPLOAD_SIZE_MB}MB）")

    # 提取文本和图片
    from app.services.file_parser_service import file_parser_service
    try:
        extracted = await file_parser_service.extract_content(
            file_data, filename, file.content_type or "application/octet-stream"
        )
        content = extracted["text"]
        images = extracted["images"]
    except ValueError as e:
        raise ValidationException(str(e))
    except Exception as e:
        logger.exception(f"文本提取异常: {filename}")
        raise ValidationException(f"文本提取失败: {str(e)}")

    if not content.strip():
        raise ValidationException("未能从文件中提取到文本内容")

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

    # 创建知识条目（暂不 commit，等图片上传完一起）
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
        try:
            file_service.delete_file(upload_result["object_name"])
        except Exception:
            logger.warning(f"清理孤立文件失败: {upload_result['object_name']}")
        raise HTTPException(500, "知识条目创建失败，请稍后重试")

    # 上传提取的图片到 MinIO（后台执行，不影响响应）
    if images:
        asyncio.create_task(
            _upload_knowledge_images(knowledge.id, images, filename)
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


@router.post(
    "/knowledge/from-auto-expansion",
    response_model=AutoExpansionIngestResponse,
    status_code=201,
)
async def create_from_auto_expansion(
    req: AutoExpansionIngestRequest,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """#043 批量接收 qa-bench 高分问答, 写入知识库 (source_type='auto_expansion')

    质量门 (用户决策: 多条件组合):
      - score >= req.min_score (默认 4/5)
      - content 长度 >= req.min_content_length (默认 200)
      - intent ∈ req.allowed_intents (默认 [explain_concept, search_info])

    客户端: tests/qa-bench/save_to_kb.py 改造后调用
    服务端: 按 source='qa-bench:qa_id' 幂等查重 (重复 qa_id 不会创建新行)
    """
    service = KnowledgeService(db)
    saved = 0
    skipped = 0
    errors: list[str] = []
    knowledge_ids: list[int] = []
    for it in req.items:
        try:
            # 质量门 1: 分数
            if (it.score or 0) < req.min_score:
                skipped += 1
                continue
            # 质量门 2: content 长度
            if not it.content or len(it.content) < req.min_content_length:
                skipped += 1
                continue
            # 质量门 3: intent 白名单
            if req.allowed_intents and it.intent not in req.allowed_intents:
                skipped += 1
                continue
            # 入库 (含幂等)
            result = await service.create_from_auto_expansion(
                qa_id=it.qa_id,
                question=it.question,
                content=it.content,
                scope=it.scope,
                score=it.score,
                intent=it.intent,
                tool_calls=it.tool_calls,
                rich_blocks=it.rich_blocks,
            )
            if result:
                saved += 1
                if result.id not in knowledge_ids:
                    knowledge_ids.append(result.id)
        except Exception as e:
            errors.append(f"{it.qa_id}: {str(e)[:200]}")
            logger.exception(f"[#043] 自动拓展入库失败 (qa_id={it.qa_id})")
    return AutoExpansionIngestResponse(
        saved=saved,
        skipped=skipped,
        errors=errors,
        knowledge_ids=knowledge_ids,
    )


# ── P0: Entity-Level Knowledge Graph ──


@router.get("/knowledge/entities", response_model=dict)
async def search_entities(
    subject: Optional[str] = Query(None),
    predicate: Optional[str] = Query(None),
    object_q: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """搜索实体（跨文档合并后的知识三元组）"""
    from app.services.entity_service import EntityService
    svc = EntityService(db)
    return await svc.search_entities(
        subject=subject, predicate=predicate, object_q=object_q,
        keyword=keyword, page=page, page_size=page_size,
    )


@router.get("/knowledge/entities/{entity_id}", response_model=dict)
async def get_entity_detail(
    entity_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取实体详情（含来源文档列表）"""
    from app.services.entity_service import EntityService
    svc = EntityService(db)
    result = await svc.get_entity_detail(entity_id)
    if not result:
        raise NotFoundException("实体")
    return result


# ── P2: Formula / Quantitative Reasoning ──


@router.get("/knowledge/formulas", response_model=dict)
async def list_formulas(
    domain: Optional[str] = Query(None),
    knowledge_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    category_id: Optional[int] = Query(None),
    source_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出公式（支持按分类、来源类型筛选）"""
    from app.services.formula_service import FormulaService
    svc = FormulaService(db)
    return await svc.list_formulas(
        domain=domain, knowledge_id=knowledge_id,
        keyword=keyword, category_id=category_id,
        source_type=source_type, page=page, page_size=page_size,
    )


@router.get("/knowledge/formulas/domains", response_model=List[dict])
async def get_formula_domains(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取公式领域分类"""
    from app.services.formula_service import FormulaService
    svc = FormulaService(db)
    return await svc.get_domains()


@router.post("/knowledge/formulas/calculate", response_model=dict)
async def calculate_formula(
    body: dict = Body(...),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """计算公式 — {formula_id: int, variables: {name: value, ...}}"""
    formula_id = body.get("formula_id")
    variables = body.get("variables", {})
    if not formula_id:
        raise ValidationException("formula_id 必填")
    from app.services.formula_service import FormulaService
    svc = FormulaService(db)
    result = await svc.calculate(formula_id, variables)
    if "error" in result:
        raise ValidationException(result["error"])
    return result


@router.get("/knowledge/formulas/categories", response_model=List[dict])
async def get_formula_categories(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取公式分类树"""
    from app.services.formula_service import FormulaService
    svc = FormulaService(db)
    return await svc.get_categories()


# ── P1: Hypothesis Generation ──


@router.post("/knowledge/hypotheses", response_model=List[dict])
async def generate_hypotheses(
    topic: Optional[str] = Body(None),
    count: int = Body(3, ge=1, le=10),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """生成假设（基于实体+关系+空白）"""
    from app.services.hypothesis_service import HypothesisService
    svc = HypothesisService(db)
    return await svc.generate_hypotheses(topic=topic, count=count)


@router.get("/knowledge/hypotheses", response_model=dict)
async def list_hypotheses(
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """列出假设"""
    from app.services.hypothesis_service import HypothesisService
    svc = HypothesisService(db)
    return await svc.list_hypotheses(status=status, priority=priority,
                                     page=page, page_size=page_size)


@router.get("/knowledge/hypotheses/{hypothesis_id}", response_model=dict)
async def get_hypothesis_detail(
    hypothesis_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取假设详情（含关联实体）"""
    from app.services.hypothesis_service import HypothesisService
    svc = HypothesisService(db)
    result = await svc.get_hypothesis_detail(hypothesis_id)
    if not result:
        raise NotFoundException("假设")
    return result


@router.post("/knowledge/hypotheses/{hypothesis_id}/validate", response_model=dict)
async def validate_hypothesis(
    hypothesis_id: int,
    status: str = Body(...),
    validation_note: Optional[str] = Body(None),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """标记假设验证结果"""
    if status not in ("validated", "rejected"):
        raise ValidationException("status 必须为 validated 或 rejected")
    from app.services.hypothesis_service import HypothesisService
    svc = HypothesisService(db)
    result = await svc.validate_hypothesis(hypothesis_id, status, validation_note)
    if not result:
        raise NotFoundException("假设")
    return result


@router.get("/knowledge/review-queue", response_model=ReviewQueueResponse)
async def get_review_queue(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取待审阅的知识条目（矛盾检测标记）"""
    # 2026-07-01 课题组网盘 PR1: 加 deleted_at IS NULL 过滤
    result = await db.execute(
        select(Knowledge).where(
            Knowledge.deleted_at.is_(None),
            Knowledge.needs_review == True,
        )
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
        raise NotFoundException("知识")

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
        raise NotFoundException("知识")

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
        raise NotFoundException("知识")

    await db.delete(knowledge)
    await db.commit()


@router.get("/knowledge/{knowledge_id}/download")
async def download_knowledge_file(
    knowledge_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """下载知识条目文件"""
    result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
    knowledge = result.scalar_one_or_none()

    if not knowledge:
        raise NotFoundException("知识")
    if not knowledge.file_path:
        raise NotFoundException("文件")

    from app.services.file_service import file_service

    # MinIO SDK 同步调用，放到线程中执行
    minio_response = await asyncio.to_thread(
        file_service.client.get_object, file_service.bucket, knowledge.file_path
    )

    def iter_chunks():
        try:
            for chunk in minio_response.stream(amt=64 * 1024):
                yield chunk
        finally:
            minio_response.close()
            minio_response.release_conn()

    safe_filename = knowledge.file_name.replace('"', "'") if knowledge.file_name else "download"
    return StreamingResponse(
        iter_chunks(),
        media_type=knowledge.file_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'}
    )


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
        raise NotFoundException("知识")
    return knowledge


@router.post("/knowledge/{knowledge_id}/reformat", response_model=KnowledgeResponse)
async def reformat_knowledge(
    knowledge_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """AI 排版整理知识条目内容，后台执行，立即返回"""
    service = KnowledgeService(db)
    knowledge = await service.reformat_content(knowledge_id)
    if not knowledge:
        raise NotFoundException("知识")
    return knowledge


# v28 step 105: vision 看整篇论文输出 page layout
@router.post("/knowledge/{knowledge_id}/scan-layout")
async def scan_paper_layout(
    knowledge_id: int,
    current_user: Member = Depends(get_current_user),
):
    """触发 vision model 扫描整篇论文，输出 page_layout（异步 Celery）"""
    from app.services.paper_layout_service import scan_paper_layout_task
    task = scan_paper_layout_task.delay(knowledge_id)
    return {
        "status": "queued",
        "task_id": task.id,
        "knowledge_id": knowledge_id,
        "message": "vision model 正在扫描整篇论文，扫描完成后会写入 knowledge_layouts 表",
    }


@router.get("/knowledge/{knowledge_id}/layout")
async def get_paper_layout(
    knowledge_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取 vision 扫描的论文 layout（如有）"""
    from app.models import KnowledgeLayout
    from sqlalchemy import select

    result = await db.execute(
        select(KnowledgeLayout).where(KnowledgeLayout.knowledge_id == knowledge_id)
    )
    layout_row = result.scalar_one_or_none()
    if not layout_row:
        return {"knowledge_id": knowledge_id, "has_layout": False, "page_layout": None}

    return {
        "knowledge_id": knowledge_id,
        "has_layout": True,
        "total_pages": layout_row.total_pages,
        "total_blocks": layout_row.total_blocks,
        "vision_model_used": layout_row.vision_model_used,
        "vision_analyzed_at": str(layout_row.vision_analyzed_at) if layout_row.vision_analyzed_at else None,
        "page_layout": layout_row.page_layout,
    }


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
        raise NotFoundException("知识")
    knowledge.needs_review = False
    await db.commit()
    return {"message": "已标记为已审阅", "id": knowledge_id}


# ── Phase 7: 多模态提取（图片/公式/表格） ─────────────────────


@router.get("/knowledge/{knowledge_id}/images", response_model=KnowledgeImageList)
async def list_knowledge_images(
    knowledge_id: int,
    ocr_status: Optional[str] = Query(None, description="过滤 OCR 状态：pending/done/failed/skipped"),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取知识条目提取的图片列表（含 OCR 结果）"""
    from app.models.knowledge_multimodal import KnowledgeImage

    # 校验 knowledge 存在
    k_result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
    if not k_result.scalar_one_or_none():
        raise NotFoundException("知识")

    filters = [KnowledgeImage.knowledge_id == knowledge_id]
    if ocr_status:
        filters.append(KnowledgeImage.ocr_status == ocr_status)

    items_result = await db.execute(
        select(KnowledgeImage)
        .where(*filters)
        .order_by(KnowledgeImage.page_number.nulls_last(), KnowledgeImage.id)
    )
    items = items_result.scalars().all()

    # 统计
    status_count = {"done": 0, "failed": 0, "pending": 0, "skipped": 0}
    for img in items:
        status_count[img.ocr_status] = status_count.get(img.ocr_status, 0) + 1

    def _to_dict(img: KnowledgeImage) -> dict:
        return {
            "id": img.id, "knowledge_id": img.knowledge_id,
            "page_number": img.page_number, "width": img.width, "height": img.height,
            "image_url": img.image_url, "mime_type": img.mime_type,
            "file_size": img.file_size, "ocr_text": img.ocr_text,
            "ocr_status": img.ocr_status, "ocr_error": img.ocr_error,
            "ocr_model": img.ocr_model,
            "ocr_at": str(img.ocr_at) if img.ocr_at else None,
            "created_at": str(img.created_at) if img.created_at else None,
            # ── v28 step 4: vision 模型输出的 12 个结构化字段 ──
            "figure_no": img.figure_no,
            "figure_type": img.figure_type,
            "is_core_figure": img.is_core_figure,
            "is_publisher_image": img.is_publisher_image,
            "is_supporting_figure": img.is_supporting_figure,
            "section_hint": img.section_hint,
            "visual_summary": img.visual_summary,
            "anchor_paragraph_index": img.anchor_paragraph_index,
            "anchor_text": img.anchor_text,
            "vision_confidence": img.vision_confidence,
            "vision_model_used": img.vision_model_used,
            "vision_analyzed_at": str(img.vision_analyzed_at) if img.vision_analyzed_at else None,
        }

    return KnowledgeImageList(
        items=[_to_dict(i) for i in items],
        total=len(items),
        ocr_done=status_count["done"],
        ocr_failed=status_count["failed"],
        ocr_pending=status_count["pending"],
    )


@router.get("/knowledge/{knowledge_id}/extractions", response_model=ExtractionList)
async def list_knowledge_extractions(
    knowledge_id: int,
    kind: Optional[str] = Query(None, description="过滤类型：formula/table/chart/image_block"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取知识条目的提取物列表（公式/表格/图表/OCR 块）"""
    from app.models.knowledge_multimodal import KnowledgeExtraction

    k_result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
    if not k_result.scalar_one_or_none():
        raise NotFoundException("知识")

    base_filter = [
        KnowledgeExtraction.knowledge_id == knowledge_id,
        KnowledgeExtraction.is_active == True,
    ]
    if kind:
        base_filter.append(KnowledgeExtraction.kind == kind)

    # 全部统计（不分页）
    all_result = await db.execute(
        select(KnowledgeExtraction.kind).where(*base_filter)
    )
    by_kind = {"formula": 0, "table": 0, "chart": 0, "image_block": 0}
    for row in all_result.all():
        by_kind[row[0]] = by_kind.get(row[0], 0) + 1

    # 分页
    items_result = await db.execute(
        select(KnowledgeExtraction)
        .where(*base_filter)
        .order_by(KnowledgeExtraction.kind, KnowledgeExtraction.id)
        .offset((page - 1) * page_size).limit(page_size)
    )
    items = items_result.scalars().all()

    def _to_dict(e: KnowledgeExtraction) -> dict:
        return {
            "id": e.id, "knowledge_id": e.knowledge_id,
            "source_image_id": e.source_image_id, "kind": e.kind,
            "page_number": e.page_number, "data": e.data,
            "content_text": e.content_text, "confidence": e.confidence,
            "model_used": e.model_used, "source": e.source,
            "is_active": e.is_active,
            "created_at": str(e.created_at) if e.created_at else None,
        }

    return ExtractionList(
        items=[_to_dict(e) for e in items],
        total=sum(by_kind.values()),
        by_kind=by_kind,
    )


@router.post(
    "/knowledge/{knowledge_id}/extract-multimodal",
    response_model=MultimodalExtractResponse,
)
async def trigger_multimodal_extraction(
    knowledge_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """手动触发多模态提取（PDF/PPTX 重新解析图片+OCR+公式/表格）

    适用场景：
    - 老 PDF 文档在 Phase 7 之前入库，没有提取过图片
    - 之前 OCR 失败想重试
    - 切换 OCR 后端后想重提
    """
    from app.services.multimodal_extraction_service import multimodal_extraction_service

    k_result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
    knowledge = k_result.scalar_one_or_none()
    if not knowledge:
        raise NotFoundException("知识")

    try:
        # 2026-06-30 修复: manual UI 调用传 reset_status=True 翻 'analyzing'
        # 给用户反馈"重新提取中"，与 pipeline Step 7 行为区分
        result = await multimodal_extraction_service.extract_for_knowledge(
            knowledge_id, reset_status=True
        )
        return MultimodalExtractResponse(**result)
    except Exception as e:
        logger.exception(f"多模态提取失败(knowledge_id={knowledge_id})")
        return MultimodalExtractResponse(
            ok=False, error=str(e), knowledge_id=knowledge_id,
        )


class InlineExtractionsResponse(BaseModel):
    """Inline 多模态提取物到原排版响应"""
    ok: bool
    knowledge_id: Optional[int] = None
    matches_total: Optional[int] = None  # 成功 inline 到正文的项数
    unmatched_total: Optional[int] = None  # 退回末尾的项数
    new_content_length: Optional[int] = None
    reason: Optional[str] = None
    error: Optional[str] = None


@router.post(
    "/knowledge/{knowledge_id}/inline-extractions",
    response_model=InlineExtractionsResponse,
)
async def inline_extractions(
    knowledge_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """把多模态提取物（图片/公式/表格/图表）inline 嵌入原排版

    解决用户痛点「所有图都在底下，正文只看到 Fig.5 文字」：
    - 用页码匹配：根据图片/公式/表格的 page_number 找 [PAGE:N] 标记位置
    - 在该位置插入 markdown（图片/LaTeX/表格/引用块）
    - 找不到 page marker（老 PDF 无标记）→ 退回末尾"未匹配" section
    - 幂等（检查 INLINE_MARKER）

    适用场景：
    - extract-multimodal 后没自动跑 inline（默认 step 7b 跑过一次）
    - 想重新调整 inline 位置

    前置条件：knowledge.content 必须有 [PAGE:N] 标记（Phase 7 v2 后新上传自动有）
    老知识先调 POST /knowledge/{id}/reparse-pdf 重解析
    """
    from app.services.multimodal_extraction_service import multimodal_extraction_service

    k_result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
    knowledge = k_result.scalar_one_or_none()
    if not knowledge:
        raise NotFoundException("知识")

    try:
        result = await multimodal_extraction_service.inline_extractions_to_content(knowledge_id)
        return InlineExtractionsResponse(**result)
    except Exception as e:
        logger.exception(f"inline_extractions 失败(knowledge_id={knowledge_id})")
        return InlineExtractionsResponse(
            ok=False, knowledge_id=knowledge_id, error=str(e),
        )


class ReparsePdfResponse(BaseModel):
    """重解析 PDF 加 page markers 响应"""
    ok: bool
    new_content_length: Optional[int] = None
    page_markers: Optional[int] = None
    reason: Optional[str] = None
    error: Optional[str] = None


@router.post(
    "/knowledge/{knowledge_id}/reparse-pdf",
    response_model=ReparsePdfResponse,
)
async def reparse_pdf(
    knowledge_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重新解析 PDF 加 [PAGE:N] 标记（仅 Phase 7 v2 之前入库的 PDF 需要）

    - 从 MinIO 下载原 PDF
    - 调 file_parser_service 重新提取（v2 版本会插入 [PAGE:N] 标记）
    - 更新 knowledge.content（formatted_content 不动，保留 AI 排版）
    """
    from app.services.multimodal_extraction_service import multimodal_extraction_service

    k_result = await db.execute(select(Knowledge).where(Knowledge.id == knowledge_id))
    knowledge = k_result.scalar_one_or_none()
    if not knowledge:
        raise NotFoundException("知识")

    try:
        result = await multimodal_extraction_service.reparse_pdf_with_page_markers(knowledge_id)
        return ReparsePdfResponse(**result)
    except Exception as e:
        logger.exception(f"reparse_pdf 失败(knowledge_id={knowledge_id})")
        return ReparsePdfResponse(ok=False, error=str(e))


# ── 全量重跑端点（admin 专用） ─────────────────────────────


async def _require_admin(current_user: Member):
    """检查当前用户是否 admin（system_admin / admin / wangtianzhi 等）"""
    admin_usernames = {"admin", "wangtianzhi"}
    if current_user.username not in admin_usernames and current_user.role not in ("admin", "system_admin"):
        raise HTTPException(status_code=403, detail="需要 admin 权限")


class ReprocessAllResponse(BaseModel):
    """全量重跑多模态 inline 响应"""
    ok: bool
    total: int
    succeeded: int
    failed: int
    skipped: int
    results: list  # [{knowledge_id, title, status, detail}]
    task_id: Optional[str] = None  # 异步模式时返回
    status_url: Optional[str] = None  # 客户端轮询状态


# 简易 in-memory task state（admin 重跑用，进程重启清空无影响）
_reprocess_state: dict = {}


@router.post(
    "/knowledge/reprocess-all-multimodal",
    response_model=ReprocessAllResponse,
)
async def reprocess_all_multimodal(
    file_type: Optional[str] = Query("pdf", description="文件类型过滤：pdf/pptx/docx/全部(空)"),
    limit: int = Query(100, ge=1, le=500),
    sync: bool = Query(False, description="True=同步等待完成（开发用），False=异步后台跑（生产用，避免 nginx 504）"),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """全量重跑所有有文件知识的 inline 排版

    流程（对每个 knowledge）：
    1. reparse-pdf → 给 content 加 [PAGE:N] 标记
    2. extract-multimodal → 提取图片/公式/表格（如果还没提取过）
    3. inline-extractions → 按页码 inline 嵌入正文

    适用：Phase 7 v2 升级后，老数据迁移 / 重新排版
    异步模式（默认）：立即返回 task_id，结果写到 _reprocess_state[task_id]
    """
    import asyncio as _asyncio
    import uuid
    await _require_admin(current_user)
    from app.services.multimodal_extraction_service import multimodal_extraction_service

    # 1. 找出所有有 file_path 的知识
    # 2026-07-01 课题组网盘 PR1: 加 deleted_at IS NULL 过滤
    file_type_filter = f"%{file_type}%" if file_type else "%"
    q = select(Knowledge).where(
        Knowledge.deleted_at.is_(None),
        Knowledge.file_path.isnot(None),
        Knowledge.file_type.ilike(file_type_filter),
    ).order_by(Knowledge.id).limit(limit)
    rows = (await db.execute(q)).scalars().all()

    async def _run_task(knowledge_rows):
        results = []
        succeeded = 0
        failed = 0
        skipped = 0
        for k in knowledge_rows:
            entry = {
                "knowledge_id": k.id,
                "title": k.title,
                "file_name": k.file_name,
                "status": None,
                "detail": None,
            }
            try:
                reparse_result = await multimodal_extraction_service.reparse_pdf_with_page_markers(k.id)
                if not reparse_result.get("ok"):
                    entry["status"] = "reparse_failed"
                    entry["detail"] = reparse_result.get("reason") or reparse_result.get("error")
                    failed += 1
                    results.append(entry)
                    continue

                is_multimodal_type = (
                    "application/pdf" in (k.file_type or "")
                    or "presentationml" in (k.file_type or "")
                )
                if not is_multimodal_type:
                    entry["status"] = "skipped_non_pdf_pptx"
                    entry["detail"] = f"file_type={k.file_type}"
                    skipped += 1
                    results.append(entry)
                    continue

                extract_result = await multimodal_extraction_service.extract_for_knowledge(
                    k.id, reset_status=True  # 2026-06-30: admin 批量重处理是 manual 操作，翻 'analyzing'
                )
                extract_ok = extract_result.get("ok") and not extract_result.get("skipped")
                images_count = extract_result.get("images_total", 0) if extract_ok else 0

                inline_result = await multimodal_extraction_service.inline_extractions_to_content(k.id)
                if not inline_result.get("ok"):
                    entry["status"] = "inline_failed"
                    entry["detail"] = inline_result.get("reason") or inline_result.get("error")
                    failed += 1
                    results.append(entry)
                    continue

                entry["status"] = "ok"
                entry["detail"] = (
                    f"images={images_count}, "
                    f"inline_matched={inline_result.get('matches_total', 0)}, "
                    f"inline_unmatched={inline_result.get('unmatched_total', 0)}"
                )
                succeeded += 1
                results.append(entry)
            except Exception as e:
                logger.exception(f"reprocess failed for knowledge_id={k.id}")
                entry["status"] = "exception"
                entry["detail"] = str(e)[:300]
                failed += 1
                results.append(entry)
        return {
            "ok": failed == 0,
            "total": len(knowledge_rows),
            "succeeded": succeeded,
            "failed": failed,
            "skipped": skipped,
            "results": results,
        }

    if sync:
        # 同步模式：开发测试用，可能 nginx 504
        return ReprocessAllResponse(**(await _run_task(rows)))

    # 异步模式：立即返回 task_id，后台跑
    task_id = str(uuid.uuid4())[:8]
    _reprocess_state[task_id] = {
        "status": "running",
        "total": len(rows),
        "knowledge_ids": [k.id for k in rows],
        "started_at": datetime.utcnow().isoformat(),
    }

    async def _bg_run():
        try:
            result = await _run_task(rows)
            _reprocess_state[task_id] = {
                "status": "completed",
                **result,
                "finished_at": datetime.utcnow().isoformat(),
            }
            logger.info(f"reprocess task {task_id} done: {result['succeeded']}/{result['total']}")
        except Exception as e:
            logger.exception(f"reprocess task {task_id} failed")
            _reprocess_state[task_id] = {"status": "failed", "error": str(e)}

    # 启动后台任务（fire-and-forget）
    _asyncio.create_task(_bg_run())

    return ReprocessAllResponse(
        ok=True,
        total=len(rows),
        succeeded=0,
        failed=0,
        skipped=0,
        results=[],
        task_id=task_id,
        status_url=f"/api/v1/knowledge/reprocess-status/{task_id}",
    )


@router.get("/knowledge/reprocess-status/{task_id}")
async def get_reprocess_status(
    task_id: str,
    current_user: Member = Depends(get_current_user),
):
    """查询异步批量重跑任务状态"""
    await _require_admin(current_user)
    return _reprocess_state.get(task_id, {"status": "not_found"})

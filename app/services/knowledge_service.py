from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, text
from typing import List, Optional
import asyncio
import logging
import re

from app.models.knowledge import Knowledge

logger = logging.getLogger("microbubble.knowledge")


class KnowledgeService:
    """知识库服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_knowledge(self, knowledge_id: int) -> Optional[Knowledge]:
        """获取单条知识"""
        result = await self.db.execute(
            select(Knowledge).where(Knowledge.id == knowledge_id)
        )
        return result.scalar_one_or_none()

    async def get_knowledge_list(
        self,
        category: Optional[str] = None,
        keyword: Optional[str] = None
    ) -> List[Knowledge]:
        """查询知识列表"""
        query = select(Knowledge)
        filters = []

        if category:
            filters.append(Knowledge.category == category)
        if keyword:
            filters.append(or_(
                Knowledge.title.ilike(f"%{keyword}%"),
                Knowledge.content.ilike(f"%{keyword}%")
            ))

        if filters:
            query = query.where(and_(*filters))

        query = query.order_by(Knowledge.created_at.desc())
        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_knowledge(
        self,
        title: str,
        content: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        source: Optional[str] = None,
        source_type: Optional[str] = None,
        created_by: Optional[int] = None
    ) -> Knowledge:
        """创建知识条目"""
        knowledge = Knowledge(
            title=title,
            content=content,
            category=category,
            tags=tags,
            source=source,
            source_type=source_type,
            created_by=created_by,
        )
        self.db.add(knowledge)
        await self.db.commit()
        await self.db.refresh(knowledge)
        # 后台：生成嵌入 + LLM 分析 + 关联
        asyncio.create_task(
            self._analyze_and_embed(knowledge.id, title, content)
        )
        # 刷新 BM25 索引
        try:
            from app.services.bm25_service import get_bm25_service
            bm25 = get_bm25_service()
            bm25.add_document({
                "id": knowledge.id,
                "title": knowledge.title,
                "content": knowledge.content,
                "category": knowledge.category,
                "tags": knowledge.tags,
                "source": knowledge.source,
            })
        except Exception as e:
            logger.debug(f"BM25 索引增量更新失败: {e}")
        return knowledge

    async def _generate_embedding(self, knowledge: Knowledge, content: str):
        """尝试生成向量嵌入，失败不阻塞"""
        from app.services.embedding_service import generate_embedding
        embedding = await generate_embedding(content)
        if embedding is not None:
            knowledge.embedding = embedding
            await self.db.commit()
            await self.db.refresh(knowledge)

    async def update_knowledge(self, knowledge_id: int, **kwargs) -> Optional[Knowledge]:
        """更新知识条目"""
        knowledge = await self.get_knowledge(knowledge_id)
        if not knowledge:
            return None

        content_changed = False
        for key, value in kwargs.items():
            if hasattr(knowledge, key) and value is not None:
                setattr(knowledge, key, value)
                if key == "content":
                    content_changed = True

        await self.db.commit()
        await self.db.refresh(knowledge)
        # 内容变更时重新生成嵌入
        if content_changed:
            await self._generate_embedding(knowledge, knowledge.content)
        return knowledge

    async def delete_knowledge(self, knowledge_id: int) -> bool:
        """删除知识条目"""
        knowledge = await self.get_knowledge(knowledge_id)
        if not knowledge:
            return False

        await self.db.delete(knowledge)
        await self.db.commit()
        return True

    async def create_from_file(
        self,
        title: str,
        content: str,
        file_path: str,
        file_name: str,
        file_type: str,
        created_by: Optional[int] = None
    ) -> Knowledge:
        """从上传文件创建知识条目，后台自动分析"""
        knowledge = Knowledge(
            title=title,
            content=content,
            file_path=file_path,
            file_name=file_name,
            file_type=file_type,
            created_by=created_by,
        )
        self.db.add(knowledge)
        await self.db.commit()
        await self.db.refresh(knowledge)
        # 后台：生成嵌入 + LLM 分析
        asyncio.create_task(
            self._analyze_and_embed(knowledge.id, title, content)
        )
        return knowledge

    async def _analyze_and_embed(self, knowledge_id: int, title: str, content: str):
        """后台任务：独立步骤执行 embedding + LLM 分析 + 知识关联"""
        from app.core.database import async_session

        # Step 0: 立即标记 analyzing
        try:
            async with async_session() as db:
                result = await db.execute(
                    select(Knowledge).where(Knowledge.id == knowledge_id)
                )
                knowledge = result.scalar_one_or_none()
                if not knowledge:
                    return
                knowledge.analysis_status = "analyzing"
                await db.commit()
        except Exception as e:
            logger.error(f"分析状态更新失败(knowledge_id={knowledge_id}): {e}")
            return

        embedding_ok = False
        analysis_ok = False

        # Step 1: Embedding 生成（独立容错）
        try:
            from app.services.embedding_service import generate_embedding
            embedding = await generate_embedding(content)
            if embedding is not None:
                async with async_session() as db:
                    result = await db.execute(
                        select(Knowledge).where(Knowledge.id == knowledge_id)
                    )
                    knowledge = result.scalar_one_or_none()
                    if knowledge:
                        knowledge.embedding = embedding
                        await db.commit()
                        embedding_ok = True
        except Exception as e:
            logger.warning(f"Embedding 生成失败(knowledge_id={knowledge_id}): {e}")

        # Step 2: LLM 分析（独立容错）
        try:
            from app.services.llm_analysis_service import llm_analysis_service
            analysis = await llm_analysis_service.analyze_content(title, content)
            if analysis.get("summary") or analysis.get("category") or analysis.get("tags"):
                async with async_session() as db:
                    result = await db.execute(
                        select(Knowledge).where(Knowledge.id == knowledge_id)
                    )
                    knowledge = result.scalar_one_or_none()
                    if knowledge:
                        if analysis.get("summary"):
                            knowledge.summary = analysis["summary"]
                        if analysis.get("category"):
                            knowledge.category = analysis["category"]
                        if analysis.get("topic"):
                            knowledge.topic = analysis["topic"]
                        if analysis.get("tags"):
                            knowledge.tags = analysis["tags"]
                        if analysis.get("key_concepts"):
                            knowledge.key_concepts = analysis["key_concepts"]
                        if analysis.get("entities"):
                            knowledge.entities = analysis["entities"]
                        if analysis.get("related_topics"):
                            knowledge.related_topics = analysis["related_topics"]
                        if analysis.get("knowledge_type"):
                            knowledge.knowledge_type = analysis["knowledge_type"]
                        await db.commit()
                        analysis_ok = True

                # Step 2.5: 保存公式（独立容错）
                if analysis.get("formulas"):
                    try:
                        from app.services.formula_service import FormulaService
                        async with async_session() as db_f:
                            formula_svc = FormulaService(db_f)
                            await formula_svc.save_formulas_from_analysis(
                                knowledge_id, analysis["formulas"]
                            )
                    except Exception as e:
                        logger.warning(f"公式保存失败(knowledge_id={knowledge_id}): {e}")

                # Step 2.6: 自动生成假设（独立容错，异步执行）
                if analysis.get("entities") and len(analysis["entities"]) >= 2:
                    try:
                        from app.services.hypothesis_service import HypothesisService
                        async with async_session() as db_h:
                            hypothesis_svc = HypothesisService(db_h)
                            topic = analysis.get("topic") or analysis.get("category")
                            hypotheses = await hypothesis_svc.generate_hypotheses(topic=topic, count=2)
                            if hypotheses:
                                logger.info(f"自动生成 {len(hypotheses)} 条假设(knowledge_id={knowledge_id}, topic={topic})")
                    except Exception as e:
                        logger.warning(f"假设自动生成失败(knowledge_id={knowledge_id}): {e}")

        except Exception as e:
            logger.warning(f"LLM 分析失败(knowledge_id={knowledge_id}): {e}")

        # Step 2.6: AI 内容排版（独立容错，仅对 PDF 文件执行）
        try:
            from app.services.content_formatter_service import content_formatter_service
            formatted = await content_formatter_service.format_content(title, content)
            if formatted:
                async with async_session() as db:
                    result = await db.execute(
                        select(Knowledge).where(Knowledge.id == knowledge_id)
                    )
                    knowledge = result.scalar_one_or_none()
                    if knowledge:
                        formatted = await self._resolve_figure_placeholders(knowledge_id, formatted)
                        knowledge.formatted_content = formatted
                        await db.commit()
                        logger.info(f"内容排版已保存(knowledge_id={knowledge_id})")
        except Exception as e:
            logger.warning(f"内容排版失败(knowledge_id={knowledge_id}): {e}")

        # Step 3: 确定最终状态（任一成功即为 done）
        final_status = "done" if (embedding_ok or analysis_ok) else "failed"
        async with async_session() as db:
            result = await db.execute(
                select(Knowledge).where(Knowledge.id == knowledge_id)
            )
            knowledge = result.scalar_one_or_none()
            if knowledge:
                knowledge.analysis_status = final_status
                await db.commit()

        # Step 4: 知识关联（独立容错，不影响分析状态）
        if final_status == "done":
            try:
                from app.services.knowledge_graph_service import KnowledgeGraphService
                async with async_session() as db:
                    graph_svc = KnowledgeGraphService(db)
                    await graph_svc.build_relations_for(knowledge_id)
            except Exception as e:
                logger.warning(f"知识关联建立失败(knowledge_id={knowledge_id}): {e}")

        # Step 5: 实体融合（独立容错）
        try:
            from app.services.entity_service import EntityService
            async with async_session() as db:
                entity_svc = EntityService(db)
                await entity_svc.merge_entities_from_document(knowledge_id)
        except Exception as e:
            logger.warning(f"实体融合失败(knowledge_id={knowledge_id}): {e}")

        # Step 6: Neo4j 知识图谱构建（独立容错）
        try:
            from app.services.knowledge_graph_builder import get_kg_builder
            kg_builder = get_kg_builder()
            result = await kg_builder.build_graph_for_knowledge(knowledge_id, title, content)
            if result["entities_created"] > 0:
                logger.info(
                    f"Neo4j 图谱构建完成(knowledge_id={knowledge_id}): "
                    f"{result['entities_created']} 实体, {result['relations_created']} 关系"
                )
        except Exception as e:
            logger.warning(f"Neo4j 图谱构建失败(knowledge_id={knowledge_id}): {e}")

        # Step 7: 多模态提取（图片 OCR / 公式 / 表格） — Phase 7
        # 仅当文件是 PDF/PPTX 且有 file_path 时触发
        try:
            from app.services.multimodal_extraction_service import multimodal_extraction_service
            extraction_result = await multimodal_extraction_service.extract_for_knowledge(knowledge_id)
            if extraction_result.get("ok") and not extraction_result.get("skipped"):
                logger.info(
                    f"多模态提取完成(knowledge_id={knowledge_id}): "
                    f"images={extraction_result.get('images_total', 0)}, "
                    f"extractions={extraction_result.get('extractions', {})}"
                )
        except Exception as e:
            logger.warning(f"多模态提取失败(knowledge_id={knowledge_id}): {e}", exc_info=True)

        # Step 7b: 把图/表/公式 inline 嵌入原文位置 — 2026-06-19 v2
        # LLM 找 anchor + markdown 内联
        try:
            from app.services.multimodal_extraction_service import multimodal_extraction_service
            inline_result = await multimodal_extraction_service.inline_extractions_to_content(knowledge_id)
            if inline_result.get("ok") and not inline_result.get("skipped"):
                logger.info(
                    f"多模态 inline 嵌入完成(knowledge_id={knowledge_id}): "
                    f"matches={inline_result.get('matches_total', 0)}, "
                    f"unmatched={inline_result.get('unmatched_total', 0)}"
                )
        except Exception as e:
            logger.warning(f"多模态 inline 失败(knowledge_id={knowledge_id}): {e}", exc_info=True)

    async def create_from_conversation(
        self,
        title: str,
        content: str,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        created_by: Optional[int] = None,
        session_id: Optional[str] = None
    ) -> Knowledge:
        """从对话中创建知识条目"""
        knowledge = Knowledge(
            title=title,
            content=content,
            category=category,
            tags=tags or [],
            source=f"对话记录#{session_id}" if session_id else "对话记录",
            source_type="conversation",
            created_by=created_by,
        )
        self.db.add(knowledge)
        await self.db.commit()
        await self.db.refresh(knowledge)
        # 后台生成嵌入（如果未提供分类则由 LLM 分析）
        asyncio.create_task(
            self._analyze_and_embed(knowledge.id, title, content)
        )
        return knowledge

    async def search_semantic(self, query: str, top_k: int = 5, category: Optional[str] = None) -> List[dict]:
        """语义搜索 - 使用pgvector余弦距离（如果可用）"""
        try:
            # 检查 pgvector 扩展是否可用
            check = await self.db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
            if not check.scalar():
                # pgvector 不可用，回退到关键词搜索
                return await self._search_keyword_fallback(query, top_k, category)

            from app.services.embedding_service import generate_embedding
            query_embedding = await generate_embedding(query)
            if query_embedding is None:
                return await self._search_keyword_fallback(query, top_k, category)

            stmt = select(
                Knowledge,
                Knowledge.embedding.cosine_distance(query_embedding).label("distance")
            )

            if category:
                stmt = stmt.where(Knowledge.category == category)

            stmt = stmt.order_by(Knowledge.embedding.cosine_distance(query_embedding))
            stmt = stmt.limit(top_k)

            result = await self.db.execute(stmt)
            rows = result.all()

            return [
                {
                    "id": row.Knowledge.id,
                    "title": row.Knowledge.title,
                    "content": row.Knowledge.content[:500],
                    "category": row.Knowledge.category,
                    "tags": row.Knowledge.tags,
                    "source": row.Knowledge.source,
                    "score": round(1.0 - row.distance, 4)
                }
                for row in rows
            ]
        except Exception:
            # pgvector 不可用，回退到关键词搜索
            return await self._search_keyword_fallback(query, top_k, category)

    async def _search_keyword_fallback(self, query: str, top_k: int = 5, category: Optional[str] = None) -> List[dict]:
        """关键词搜索回退"""
        stmt = select(Knowledge).where(or_(
            Knowledge.title.ilike(f"%{query}%"),
            Knowledge.content.ilike(f"%{query}%")
        ))
        if category:
            stmt = stmt.where(Knowledge.category == category)
        stmt = stmt.limit(top_k)
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "title": r.title,
                "content": r.content[:500],
                "category": r.category,
                "tags": r.tags,
                "source": r.source,
                "score": 0.5
            }
            for r in rows
        ]

    async def reanalyze(self, knowledge_id: int):
        """重新分析指定知识条目（嵌入 + LLM 分析 + 关联）"""
        knowledge = await self.get_knowledge(knowledge_id)
        if not knowledge:
            return None

        # 重启后台分析（会覆盖现有状态和数据）
        asyncio.create_task(
            self._analyze_and_embed(knowledge_id, knowledge.title, knowledge.content)
        )
        return knowledge

    async def reformat_content(self, knowledge_id: int):
        """AI 排版整理指定知识条目的内容"""
        knowledge = await self.get_knowledge(knowledge_id)
        if not knowledge:
            return None

        asyncio.create_task(self._reformat_task(knowledge_id, knowledge.title, knowledge.content))
        return knowledge

    async def _reformat_task(self, knowledge_id: int, title: str, content: str):
        """后台任务：AI 排版"""
        from app.core.database import async_session
        from app.services.content_formatter_service import content_formatter_service

        try:
            formatted = await content_formatter_service.format_content(title, content)
            if formatted:
                async with async_session() as db:
                    result = await db.execute(
                        select(Knowledge).where(Knowledge.id == knowledge_id)
                    )
                    knowledge = result.scalar_one_or_none()
                    if knowledge:
                        formatted = await self._resolve_figure_placeholders(knowledge_id, formatted)
                        knowledge.formatted_content = formatted
                        await db.commit()
                        logger.info(f"手动排版已保存(knowledge_id={knowledge_id})")
        except Exception as e:
            logger.error(f"手动排版失败(knowledge_id={knowledge_id}): {e}")

    async def _resolve_figure_placeholders(self, knowledge_id: int, text: str) -> str:
        """将 [FIGURE:N] 占位符替换为 MinIO 中的实际图片 URL"""
        placeholders = re.findall(r'\[FIGURE:([\d.]+)\]', text)
        if not placeholders:
            return text

        from app.services.file_service import file_service
        prefix = f"knowledge/{knowledge_id}/"
        try:
            objects = await file_service.list_objects(prefix)
            # 构建 fig_N → url 映射
            url_map = {}
            for obj in objects:
                name = obj.get("object_name", "")
                url = obj.get("url", "")
                # 从文件名提取 fig 编号: fig_1.png, fig_2.jpg 等
                m = re.search(r'fig_(\d+)\.', name)
                if m:
                    fig_n = m.group(1)
                    url_map[fig_n] = url

            for fig_n in placeholders:
                placeholder = f"[FIGURE:{fig_n}]"
                if fig_n in url_map:
                    text = text.replace(placeholder, f"\n![图片 {fig_n}]({url_map[fig_n]})\n")
                else:
                    text = text.replace(placeholder, "")
                    logger.debug(f"图片占位符无匹配文件: {placeholder} (knowledge_id={knowledge_id})")
        except Exception as e:
            logger.warning(f"图片占位符解析失败(knowledge_id={knowledge_id}): {e}")
            # 移除所有未解析的占位符
            text = re.sub(r'\[FIGURE:[\d.]+\]', '', text)

        return text

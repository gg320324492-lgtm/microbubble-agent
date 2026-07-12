from sqlalchemy import select, and_, or_, text
from typing import List, Optional
import logging
import re

from app.core.celery_db import create_celery_engine_and_session
from app.core.celery import celery_app
from app.models.knowledge import Knowledge
from app.services.name_aliases import clean_text as clean_person_names

logger = logging.getLogger("microbubble.knowledge")


# ============================================================
# 2026-06-29 修复 #257 教训：_analyze_and_embed 改 Celery
# ============================================================
# 之前用 asyncio.create_task() 启动 _analyze_and_embed（fire-and-forget），
# 4 个调用点 + Step 3 (写 final_status) 无 try/except 包裹，
# 任何 DB 抖动会让 task 静默死亡，analysis_status 永远卡 'analyzing'。
# 修复：提取为模块函数 + Celery 任务 + 顶层 try/except + Step 3 兜底。
# 镜像 reminder_service.process_reminders_task (NullPool + asyncio.run)。
# ============================================================


async def _resolve_figure_placeholders(knowledge_id: int, text: str) -> str:
    """将 [FIGURE:N] 占位符替换为 MinIO 中的实际图片 URL（模块级，无 self 依赖）"""
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


async def _run_analyze_and_embed(
    knowledge_id: int,
    title: str,
    content: str,
    session_factory,
):
    """后台分析流程的模块级实现（替代 _analyze_and_embed 方法体）。

    Args:
        knowledge_id: 知识条目 ID
        title: 标题
        content: 正文
        session_factory: async_sessionmaker 实例，Celery 任务用 NullPool 新 engine，
            API 路由复用全局 async_session（back-compat）
    """
    # Step 0: 立即标记 analyzing
    try:
        async with session_factory() as db:
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
            async with session_factory() as db:
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
            async with session_factory() as db:
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
                    async with session_factory() as db_f:
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
                    async with session_factory() as db_h:
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
            async with session_factory() as db:
                result = await db.execute(
                    select(Knowledge).where(Knowledge.id == knowledge_id)
                )
                knowledge = result.scalar_one_or_none()
                if knowledge:
                    formatted = await _resolve_figure_placeholders(knowledge_id, formatted)
                    knowledge.formatted_content = formatted
                    await db.commit()
                    logger.info(f"内容排版已保存(knowledge_id={knowledge_id})")
    except Exception as e:
        logger.warning(f"内容排版失败(knowledge_id={knowledge_id}): {e}")

    # Step 3: 确定最终状态（防御：任何异常都不能让 status 卡 'analyzing'）
    # v28 step 32 修复: 之前 final_status = "done" if (embedding_ok or analysis_ok) else "failed"
    #   后果: embedding 生成成功但 LLM 分析失败 → status='done' 但 summary/tags 全空
    #   用户看到"已完成"标签，实际什么也没分析，体验差
    # 2026-06-29 修复: 整个 Step 3 包裹 try/except + 兜底 status='failed'，
    #   防止 #257 复发（之前 Step 3 抛未捕获异常 → task 静默死亡 → status 永卡）
    if analysis_ok:
        final_status = "done"
    elif embedding_ok:
        # LLM 失败但 embedding 成功 → 半完成状态，但不要"骗"用户是 done
        final_status = "partial"
    else:
        final_status = "failed"
    logger.info(
        f"[_run_analyze_and_embed] knowledge_id={knowledge_id} final_status={final_status} "
        f"embedding_ok={embedding_ok} analysis_ok={analysis_ok}"
    )
    try:
        async with session_factory() as db:
            result = await db.execute(
                select(Knowledge).where(Knowledge.id == knowledge_id)
            )
            knowledge = result.scalar_one_or_none()
            if knowledge:
                knowledge.analysis_status = final_status
                await db.commit()
    except Exception as e:
        # 兜底：哪怕这段也炸了，也要把 status 置为 failed
        logger.error(
            f"[Step3] final_status 写入失败(knowledge_id={knowledge_id}): {e}",
            exc_info=True,
        )
        try:
            async with session_factory() as db:
                result = await db.execute(
                    select(Knowledge).where(Knowledge.id == knowledge_id)
                )
                knowledge = result.scalar_one_or_none()
                if knowledge:
                    knowledge.analysis_status = "failed"
                    await db.commit()
        except Exception as e2:
            logger.error(
                f"[Step3] 兜底 failed 写入也失败(knowledge_id={knowledge_id}): {e2}"
            )
        # 抛回让 Celery 顶层 try 处理 retry
        raise

    # Step 4: 知识关联（独立容错，不影响分析状态）
    if final_status == "done":
        try:
            from app.services.knowledge_graph_service import KnowledgeGraphService
            async with session_factory() as db:
                graph_svc = KnowledgeGraphService(db)
                await graph_svc.build_relations_for(knowledge_id)
        except Exception as e:
            logger.warning(f"知识关联建立失败(knowledge_id={knowledge_id}): {e}")

    # Step 5: 实体融合（独立容错）
    try:
        from app.services.entity_service import EntityService
        async with session_factory() as db:
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
    # 2026-06-30 修复: pipeline 调用显式传 reset_status=False, 保留 Step 3 已写终态
    try:
        from app.services.multimodal_extraction_service import multimodal_extraction_service
        extraction_result = await multimodal_extraction_service.extract_for_knowledge(
            knowledge_id, reset_status=False
        )
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

    # Step 8 (2026-06-30 修复): 最终终态写入防御
    # 即使 Step 7 multimodal reset 覆盖了 status (虽然已加 reset_status=False 但仍
    # 可能因 race condition / 旧版本 cache 覆盖), 这里再次写回 final_status.
    # 保证: 不管 pipeline 中间状态如何翻转, 最终用户看到的就是 final_status (done/partial/failed).
    try:
        async with session_factory() as db:
            result = await db.execute(
                select(Knowledge).where(Knowledge.id == knowledge_id)
            )
            k = result.scalar_one_or_none()
            if k and k.analysis_status != final_status:
                logger.warning(
                    f"[_run_analyze_and_embed] Step 7/7b 覆盖了 status, "
                    f"恢复 final_status={final_status} (was={k.analysis_status})"
                )
                k.analysis_status = final_status
                await db.commit()
    except Exception as e:
        logger.error(
            f"[_run_analyze_and_embed] Step 8 最终终态写入失败: {e}",
            exc_info=True,
        )


@celery_app.task(
    name="app.services.knowledge_service.analyze_knowledge_task",
    bind=True,
    max_retries=2,
)
def analyze_knowledge_task(self, knowledge_id: int, title: str, content: str):
    """Celery 任务：生成嵌入 + LLM 分析 + 知识关联。

    替代 asyncio.create_task 启动方式（2026-06-29 修复 #257）：
    - 独立 NullPool 引擎（不绑定 FastAPI app 的 event loop）
    - 顶层 try/except 任何异常 → status='failed' + self.retry
    - Step 3 final_status 写入独立 try/except 兜底（防 #257 复发）
    - 抗 FastAPI/celery-worker 进程重启
    """
    import asyncio
    from app.config import settings

    async def _run():
        try:
            try:
                await _run_analyze_and_embed(knowledge_id, title, content, session_factory)
            except Exception as e:
                logger.error(
                    f"[analyze_knowledge_task] 未捕获异常 knowledge_id={knowledge_id}: {e}",
                    exc_info=True,
                )
                # 防御性兜底：哪怕 _run_analyze_and_embed 抛了，status 也要落到 'failed'
                try:
                    async with session_factory() as db:
                        result = await db.execute(
                            select(Knowledge).where(Knowledge.id == knowledge_id)
                        )
                        k = result.scalar_one_or_none()
                        if k and k.analysis_status == "analyzing":
                            k.analysis_status = "failed"
                            await db.commit()
                except Exception as e2:
                    logger.error(
                        f"[analyze_knowledge_task] 兜底 failed 写入也失败(knowledge_id={knowledge_id}): {e2}"
                    )
                raise
        finally:
            await engine.dispose()

    try:
        asyncio.run(_run())
    except Exception as e:
        raise self.retry(exc=e, countdown=60)


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
        # 2026-07-01 课题组网盘 PR1: 加 deleted_at IS NULL 过滤, 软删除条目不返回
        query = select(Knowledge).where(Knowledge.deleted_at.is_(None))
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
        """创建知识条目

        v28 step 60: 入库前清洗谐音人名（"洪辉"→"张宏魁" 等）
        """
        title = clean_person_names(title)
        content = clean_person_names(content)
        if category:
            category = clean_person_names(category)
        if tags:
            tags = [clean_person_names(t) for t in tags]

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
        # 后台：生成嵌入 + LLM 分析 + 关联（Celery 任务，2026-06-29 修复 #257）
        try:
            analyze_knowledge_task.delay(knowledge.id, title, content)
        except Exception as e:
            logger.warning(f"[knowledge_service] Celery 任务入队失败(knowledge_id={knowledge.id}): {e}")
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

    # =========================================================================
    # #043 自动拓展 (2026-06-29 chat agent 知识闭环)
    # =========================================================================

    SCOPE_TO_CATEGORY: dict = {
        "core": "基础知识",
        "method": "实验方法",
        "industry": "行业应用",
        "application": "应用案例",
        "academic": "学术研究",
        "policy": "政策法规",
        "theory": "理论基础",
        "emerging": "新兴方向",
    }

    async def create_from_auto_expansion(
        self,
        qa_id: str,
        question: str,
        content: str,
        scope: Optional[str] = None,
        score: Optional[int] = None,
        intent: Optional[str] = None,
        tool_calls: Optional[list] = None,
        rich_blocks: Optional[list] = None,
    ) -> Optional[Knowledge]:
        """#043 自动拓展：从 qa-bench 高分问答创建知识卡片 (source_type='auto_expansion')

        设计要点:
          1. 幂等: 通过 (source='qa-bench:qa_id' AND source_type='auto_expansion') 查重
          2. 绕过 LLM 重分析 (qa-bench 已评估) → analysis_status='done'
          3. created_by=None 表示系统自动创建 (与 auto_research 一致)
          4. quality_score = score/5.0; knowledge_type = scope (用于过滤)
          5. RichBlock 模式: tool_calls + rich_blocks 存到 knowledge.meta JSONB

        Returns: 已存在时返回旧行 (调用方跳过计数), 新建时返回新行
        """
        # 1. 幂等查重
        source_tag = f"qa-bench:{qa_id}"
        result = await self.db.execute(
            select(Knowledge).where(
                (Knowledge.source == source_tag)
                & (Knowledge.source_type == "auto_expansion")
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info(
                f"[#043] 自动拓展已存在 (qa_id={qa_id}, knowledge_id={existing.id}), 跳过"
            )
            return existing

        # 2. 构造标题与内容
        title = f"[自动拓展-{qa_id}] {question[:60]}"
        rich_blocks_section = self._build_rich_blocks_section(
            question=question,
            content=content,
            tool_calls=tool_calls or [],
            rich_blocks=rich_blocks or [],
        )
        full_content = (
            f"## 问题\n{question}\n\n"
            f"## 回答\n{content}\n\n"
            f"## 工具调用\n{rich_blocks_section}"
        )

        # 3. 构造 meta (RichBlock 数据 + qa-bench 元信息)
        meta = {
            "qa_id": qa_id,
            "intent": intent,
            "scope": scope,
            "score": score,
            "tool_calls": tool_calls or [],
            "rich_blocks": rich_blocks or [],
        }

        # 4. 入库
        category = self.SCOPE_TO_CATEGORY.get(scope or "", "基础知识")
        tags = ["自动拓展"]
        if intent:
            tags.append(f"intent:{intent}")
        if scope:
            tags.append(f"scope:{scope}")

        knowledge = Knowledge(
            title=title,
            content=full_content,
            category=category,
            tags=tags,
            source=source_tag,
            source_type="auto_expansion",
            created_by=None,  # 系统自动创建 (与 auto_research 一致)
            auto_researched=False,
            analysis_status="done",  # qa-bench 已评估, 跳过 LLM 重分析
            quality_score=score / 5.0 if score else None,
            knowledge_type=scope,
            meta=meta,
        )
        self.db.add(knowledge)
        await self.db.commit()
        await self.db.refresh(knowledge)

        # 5. 异步: 仅生成 embedding (跳过 LLM analyze + 关系构建)
        import asyncio
        try:
            asyncio.create_task(self._embed_only(knowledge.id, title, full_content))
        except RuntimeError:
            # 无 event loop (sync 上下文) — 同步执行
            await self._embed_only(knowledge.id, title, full_content)

        # 6. BM25 索引增量更新
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
            logger.debug(f"自动拓展 BM25 索引增量更新失败: {e}")

        return knowledge

    @staticmethod
    def _build_rich_blocks_section(
        question: str,
        content: str,
        tool_calls: list,
        rich_blocks: list,
    ) -> str:
        """构造 RichBlock 模式内容 (Markdown 风格, 供前端 KnowledgeCard 渲染)

        输出示例:
          ### 🔧 工具调用
          - **search_knowledge** (query="zeta 电位")
          ### 📊 Rich Blocks
          - KnowledgeRefBlock × 2
          - FormulaBlock × 1
        """
        if not tool_calls and not rich_blocks:
            return "_(无工具调用)_"
        parts = []
        if tool_calls:
            parts.append("### 🔧 工具调用")
            for tc in tool_calls:
                name = tc.get("name", "?")
                inp = tc.get("input", {}) if isinstance(tc, dict) else {}
                inp_str = ", ".join(
                    f'{k}="{v}"' for k, v in list(inp.items())[:3]
                )
                parts.append(f"- **{name}** ({inp_str})")
        if rich_blocks:
            parts.append("\n### 📊 Rich Blocks")
            from collections import Counter
            block_counts = Counter(
                rb.get("type", "?") if isinstance(rb, dict) else "?"
                for rb in rich_blocks
            )
            for btype, count in block_counts.most_common():
                parts.append(f"- {btype} × {count}")
        return "\n".join(parts)

    async def _embed_only(self, knowledge_id: int, title: str, content: str):
        """#043: 仅生成 embedding (自动拓展跳过 LLM analyze + 关系构建)"""
        try:
            from app.services.embedding_service import generate_embedding
            embedding = await generate_embedding(content)
            if embedding is not None:
                result = await self.db.execute(
                    select(Knowledge).where(Knowledge.id == knowledge_id)
                )
                k = result.scalar_one_or_none()
                if k:
                    k.embedding = embedding
                    await self.db.commit()
        except Exception as e:
            logger.warning(
                f"[#043] 自动拓展 embedding 失败 (knowledge_id={knowledge_id}): {e}"
            )

    async def _generate_embedding(self, knowledge: Knowledge, content: str):
        """尝试生成向量嵌入，失败不阻塞"""
        from app.services.embedding_service import generate_embedding
        embedding = await generate_embedding(content)
        if embedding is not None:
            knowledge.embedding = embedding
            await self.db.commit()
            await self.db.refresh(knowledge)

    async def update_knowledge(self, knowledge_id: int, **kwargs) -> Optional[Knowledge]:
        """更新知识条目

        v28 step 60: 更新时也清洗谐音人名
        """
        # 入参清洗
        cleaned_kwargs = {}
        for key, value in kwargs.items():
            if isinstance(value, str):
                cleaned_kwargs[key] = clean_person_names(value)
            elif isinstance(value, list):
                cleaned_kwargs[key] = [
                    clean_person_names(v) if isinstance(v, str) else v
                    for v in value
                ]
            else:
                cleaned_kwargs[key] = value

        knowledge = await self.get_knowledge(knowledge_id)
        if not knowledge:
            return None

        content_changed = False
        for key, value in cleaned_kwargs.items():
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
        # 后台：生成嵌入 + LLM 分析（Celery 任务，2026-06-29 修复 #257）
        try:
            analyze_knowledge_task.delay(knowledge.id, title, content)
        except Exception as e:
            logger.warning(f"[knowledge_service] Celery 任务入队失败(knowledge_id={knowledge.id}): {e}")
        return knowledge

    async def _analyze_and_embed(self, knowledge_id: int, title: str, content: str):
        """向后兼容薄壳（2026-06-29 修复 #257 改为 Celery 任务）。

        新代码请用 `analyze_knowledge_task.delay(knowledge_id, title, content)`。
        保留本方法仅为兼容旧测试 / 旧调用方（如 `await service._analyze_and_embed(...)`）。
        复用全局 async_session（在 FastAPI event loop 上跑，安全）。
        """
        from app.core.database import async_session
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        factory = async_sessionmaker(async_session().bind, class_=AsyncSession, expire_on_commit=False)
        await _run_analyze_and_embed(knowledge_id, title, content, factory)

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
        # 后台生成嵌入（如果未提供分类则由 LLM 分析，Celery 任务，2026-06-29 修复 #257）
        try:
            analyze_knowledge_task.delay(knowledge.id, title, content)
        except Exception as e:
            logger.warning(f"[knowledge_service] Celery 任务入队失败(knowledge_id={knowledge.id}): {e}")
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

            # 2026-07-01 课题组网盘 PR1: 加 deleted_at IS NULL + storage_mode='kb' 过滤
            # drive 模式不入 embedding 索引, 软删除条目不可检索
            # PR2.10 课题组网盘: 加 visibility IN ('team','public') 过滤
            # private 文件即使 owner 也不通过 search_knowledge 看到 (走 search_my_files 工具)
            stmt = select(
                Knowledge,
                Knowledge.embedding.cosine_distance(query_embedding).label("distance")
            ).where(
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "kb",
                Knowledge.visibility.in_(["team", "public"]),
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
        # 2026-07-01 课题组网盘 PR1: 加 deleted_at IS NULL + storage_mode='kb' 过滤
        # PR2.10: 加 visibility IN ('team','public') 过滤 (硬边界)
        stmt = select(Knowledge).where(
            Knowledge.deleted_at.is_(None),
            Knowledge.storage_mode == "kb",
            Knowledge.visibility.in_(["team", "public"]),
            or_(
                Knowledge.title.ilike(f"%{query}%"),
                Knowledge.content.ilike(f"%{query}%")
            )
        )
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

        # 重启后台分析（会覆盖现有状态和数据，Celery 任务，2026-06-29 修复 #257）
        try:
            analyze_knowledge_task.delay(knowledge_id, knowledge.title, knowledge.content)
        except Exception as e:
            logger.warning(f"[knowledge_service] Celery 任务入队失败(knowledge_id={knowledge_id}): {e}")
        return knowledge

    async def reformat_content(self, knowledge_id: int):
        """AI 排版整理指定知识条目的内容（v28 step 18: 用 Celery 抗重启）

        之前用 asyncio.create_task() 在 FastAPI 进程内 spawn 任务，
        进程重启任务丢失 → formatted_content 永远不更新。
        改用 Celery delay() 把任务扔到 Redis broker，worker 进程重启后仍能 resume。
        """
        knowledge = await self.get_knowledge(knowledge_id)
        if not knowledge:
            return None

        # 触发 Celery 任务（不等结果，立即返回）
        from app.services.content_formatter_service import reformat_knowledge_task
        reformat_knowledge_task.delay(knowledge_id)
        logger.info(f"reformat_content: knowledge_id={knowledge_id} Celery 任务已派发")
        return knowledge

    async def _reformat_task(self, knowledge_id: int, title: str, content: str):
        """v28 step 18 兼容保留：FastAPI 进程内的重排（已废弃，由 Celery task 替代）

        保留仅为兼容旧测试 / 旧调用方。新代码应走 reformat_content() -> Celery delay()。
        """
        logger.warning("_reformat_task 已废弃，请用 Celery 任务")

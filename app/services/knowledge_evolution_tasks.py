"""Celery 定时任务 — 知识库自主进化与健康监控"""

import asyncio
import logging

from app.core.celery import celery_app
from app.core.database import async_session

logger = logging.getLogger("microbubble.knowledge_evolution")


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def evolve_knowledge_base(self):
    """每周知识进化 — 检测空白并补充"""
    logger.info("开始每周知识进化任务")

    async def _run():
        async with async_session() as db:
            from app.services.auto_research_service import AutoResearchService
            svc = AutoResearchService(db)
            result = await svc.fill_knowledge_gaps()
            logger.info(
                f"知识进化完成: 新增 {result['new_knowledge_count']} 条知识, "
                f"薄弱领域 {len(result.get('weak_areas', []))} 个"
            )
            return result

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run())
        loop.close()
        return result
    except Exception as e:
        logger.error(f"每周知识进化失败: {e}")
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=1)
def process_pending_gaps(self):
    """处理待填补的知识空白 — 每6小时检查 knowledge_gaps 表并触发研究"""
    logger.info("开始处理待填补的知识空白")

    async def _run():
        async with async_session() as db:
            from sqlalchemy import select
            from app.models.knowledge import KnowledgeGap
            from app.services.auto_research_service import AutoResearchService

            result = await db.execute(
                select(KnowledgeGap).where(KnowledgeGap.filled == False).limit(5)
            )
            gaps = result.scalars().all()

            if not gaps:
                logger.info("无待填补的知识空白")
                return {"processed": 0}

            svc = AutoResearchService(db)
            filled_count = 0
            for gap in gaps:
                try:
                    research = await svc.research_topic(
                        queries=[gap.query], max_results_per_query=2
                    )
                    if research["new_knowledge_count"] > 0:
                        gap.filled = True
                        gap.filled_at = str(__import__('datetime').datetime.utcnow())
                        gap.knowledge_ids = []
                        gap.filled_count = research["new_knowledge_count"]
                        filled_count += 1
                    await db.commit()
                except Exception as e:
                    logger.warning(f"填补空白失败(gap_id={gap.id}): {e}")

            logger.info(f"知识空白处理完成: 填补 {filled_count}/{len(gaps)} 个")
            return {"processed": len(gaps), "filled": filled_count}

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run())
        loop.close()
        return result
    except Exception as e:
        logger.error(f"知识空白处理失败: {e}")
        return {"error": str(e)}


@celery_app.task(bind=True, max_retries=1)
def health_check_knowledge_base(self):
    """知识健康检查 — 矛盾/重复/过期检测"""
    logger.info("开始知识健康检查")

    async def _run():
        async with async_session() as db:
            from app.services.auto_research_service import AutoResearchService
            svc = AutoResearchService(db)

            contradictions = await svc.detect_and_handle_contradictions()
            duplicates = await svc.detect_duplicates()
            stale = await svc.detect_staleness()

            report = {
                "contradictions": len(contradictions),
                "duplicates": len(duplicates),
                "stale_entries": len(stale),
            }
            logger.info(f"知识健康检查完成: {report}")
            return report

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run())
        loop.close()
        return result
    except Exception as e:
        logger.error(f"知识健康检查失败: {e}")
        return {"error": str(e)}


@celery_app.task(bind=True, max_retries=1)
def fuse_entities_task(self):
    """每日实体融合 — 跨文档合并相似知识三元组"""
    logger.info("开始每日实体融合")

    async def _run():
        async with async_session() as db:
            from app.services.entity_service import EntityService
            svc = EntityService(db)
            return await svc.bulk_fuse_entities()

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run())
        loop.close()
        return result
    except Exception as e:
        logger.error(f"实体融合任务失败: {e}")
        return {"error": str(e)}

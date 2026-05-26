"""Celery 定时任务 — 知识库自主进化与健康监控"""

import asyncio
import logging

from app.core.celery import celery_app
from app.core.database import async_session

logger = logging.getLogger("microbubble.knowledge_evolution")


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def evolve_knowledge_base(self):
    """每日知识进化 — 检测空白并补充"""
    logger.info("开始每日知识进化任务")

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
        logger.error(f"每日知识进化失败: {e}")
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=1)
def detect_knowledge_gaps(self):
    """知识空白检测 — 每6小时"""
    logger.info("开始知识空白检测")

    async def _run():
        async with async_session() as db:
            from app.services.auto_research_service import AutoResearchService
            svc = AutoResearchService(db)
            result = await svc.fill_knowledge_gaps()
            return {
                "weak_areas": len(result.get("weak_areas", [])),
                "new_knowledge": result["new_knowledge_count"],
            }

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run())
        loop.close()
        return result
    except Exception as e:
        logger.error(f"知识空白检测失败: {e}")
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

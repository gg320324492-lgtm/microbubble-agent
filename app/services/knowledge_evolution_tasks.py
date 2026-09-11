"""Celery 定时任务 — 知识库自主进化与健康监控

2026-09-11 根治 (agent_traces 饿死事故顺带挖出):
- 本文件曾是 celery_db 迁移的漏网之鱼 (celery_db.py docstring 点名已抽取 18+ 文件,
  唯独这里仍用模块级 app.core.database.async_session)。全局连接池的 connection
  绑定首个 loop, 而每任务 new_event_loop+close 后池里全是 stale conn →
  间歇 "greenlet_spawn has not been called" / 挂死小时级 (fuse_entities 实锤)。
  统一改 create_celery_engine_and_session() (NullPool + expire_on_commit=False + dispose)。
- fuse_entities_task 加 Redis SETNX 锁 (TTL 30min): 防历史积压消息在新 pool 下并发重跑
  导致双合并竞态。redis 不可用时 fail-open (宁重跑不卡死调度)。
"""

import asyncio
import logging
import time

from app.config import settings
from app.core.celery import celery_app
from app.core.celery_db import create_celery_engine_and_session

logger = logging.getLogger("microbubble.knowledge_evolution")


def _run_in_fresh_loop(coro_fn):
    """per-task 新 loop 跑协程 (Celery 线程/进程上下文通用), 返回协程结果。

    协程内部自管 engine dispose (见各任务 _run)。
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro_fn())
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        loop.close()


@celery_app.task(bind=True, max_retries=2, default_retry_delay=300)
def evolve_knowledge_base(self):
    """每周知识进化 — 检测空白并补充"""
    logger.info("开始每周知识进化任务")

    async def _run():
        engine, SessionFactory = create_celery_engine_and_session()
        try:
            async with SessionFactory() as db:
                from app.services.auto_research_service import AutoResearchService
                svc = AutoResearchService(db)
                result = await svc.fill_knowledge_gaps()
                logger.info(
                    f"知识进化完成: 新增 {result['new_knowledge_count']} 条知识, "
                    f"薄弱领域 {len(result.get('weak_areas', []))} 个"
                )
                return result
        finally:
            await engine.dispose()

    try:
        return _run_in_fresh_loop(_run)
    except Exception as e:
        logger.error(f"每周知识进化失败: {e}")
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=1)
def process_pending_gaps(self):
    """处理待填补的知识空白 — 每6小时检查 knowledge_gaps 表并触发研究"""
    logger.info("开始处理待填补的知识空白")

    async def _run():
        engine, SessionFactory = create_celery_engine_and_session()
        try:
            async with SessionFactory() as db:
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
        finally:
            await engine.dispose()

    try:
        return _run_in_fresh_loop(_run)
    except Exception as e:
        logger.error(f"知识空白处理失败: {e}")
        return {"error": str(e)}


@celery_app.task(bind=True, max_retries=1)
def health_check_knowledge_base(self):
    """知识健康检查 — 矛盾/重复/过期检测"""
    logger.info("开始知识健康检查")

    async def _run():
        engine, SessionFactory = create_celery_engine_and_session()
        try:
            async with SessionFactory() as db:
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
        finally:
            await engine.dispose()

    try:
        return _run_in_fresh_loop(_run)
    except Exception as e:
        logger.error(f"知识健康检查失败: {e}")
        return {"error": str(e)}


@celery_app.task(bind=True, max_retries=1)
def fuse_entities_task(self):
    """每日实体融合 — embedding 预筛候选 + LLM 只判相似对 (2026-09-11 重做)

    旧版三病: ①全局 async_session 跨 loop → greenlet 炸/挂死; ②n² 全对 LLM
    (最坏 ~2.45 万调用, 数小时); ③积压重投并发双合并。修 = celery_db 独立
    NullPool engine + bulk_fuse_entities 预筛/预算 + Redis SETNX 锁。
    """
    logger.info("开始每日实体融合")

    # 防重入锁: 覆盖最长预算 (wall-clock 900s) + 余量; redis 挂 → fail-open
    lock_key = "celery:lock:fuse_entities"
    lock_acquired = False
    r = None
    try:
        import redis as redis_sync
        r = redis_sync.from_url(settings.REDIS_URL, socket_timeout=3)
        lock_acquired = bool(r.set(lock_key, str(time.time()), nx=True, ex=1200))
        if not lock_acquired:
            logger.info("fuse_entities: 已有实例在跑 (锁持有), 跳过本轮")
            return {"skipped": "another run holds the lock"}
    except Exception as e:
        logger.warning(f"fuse_entities: redis 锁不可用, fail-open 直跑: {e}")

    async def _run():
        engine, SessionFactory = create_celery_engine_and_session()
        try:
            async with SessionFactory() as db:
                from app.services.entity_service import EntityService
                svc = EntityService(db)
                return await svc.bulk_fuse_entities()
        finally:
            await engine.dispose()

    try:
        return _run_in_fresh_loop(_run)
    except Exception as e:
        logger.error(f"实体融合任务失败: {e}")
        return {"error": str(e)}
    finally:
        if lock_acquired and r is not None:
            try:
                r.delete(lock_key)
            except Exception:
                pass  # TTL 兜底自解

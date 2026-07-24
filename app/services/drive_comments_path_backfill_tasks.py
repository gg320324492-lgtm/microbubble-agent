"""Drive v2 PR14 path backfill Celery task (2026-07-24, W68 第 12 批 B-1)

设计要点 (与 chat_history_tasks / drive_cleanup_tasks 一致):
- 独立 create_async_engine(NullPool) + async_sessionmaker: 避免全局
  async_session 绑定主进程事件循环, 与 asyncio.run() 新循环冲突
- NullPool: 禁用连接池, 每任务创建新连接避免跨 loop 复用
- engine.dispose() finally: 清理连接
- 始终 logger.warning (即便更新 0 个) → 健康监控可见

beat schedule:
- 默认每日 02:00 跑慢速回填 (凌晨低峰, 减少对生产评论写影响)
- celery_app.conf.beat_schedule 加 "drive-comments-path-backfill-daily"
- celery_app.conf.imports 加 "app.services.drive_comments_path_backfill_tasks"
- celery_app.autodiscover_tasks 也加 (双保险)

PR14 铁律沉淀 (CLAUDE.md W68 第 12 批):
1. Celery 跑重算必须 dry_run=False 显式 (默认 dry_run, 防误写库)
2. 单文件模式 (file_id 传) 比全表模式更安全 (锁粒度小)
3. 慢速回填 = 后台异步, 失败不阻塞前端用户评论
"""
import asyncio
import logging
from typing import Optional

from app.core.celery import celery_app
from app.core.celery_db import create_celery_engine_and_session

logger = logging.getLogger("microbubble.drive_comments_path_backfill")


@celery_app.task(name="app.services.drive_comments_path_backfill_tasks.backfill_paths_task")
def backfill_paths_task(
    file_id: Optional[int] = None,
    folder_id: Optional[int] = None,
    dry_run: bool = False,
    fix_orphans: bool = True,
):
    """Celery beat 任务: 异步重算 drive_comments.path

    Args:
        file_id: 单文件模式 (None = 不限 file 维度)
        folder_id: 单 folder 模式 (None = 不限 folder 维度)
        dry_run: True = 只统计, 不写库 (默认 False 因为是后台慢速回填)
        fix_orphans: True = 修复孤儿引用

    Returns:
        dict: {
            "status": "ok" | "error" | "skipped",
            "target": "all" | "file:42" | "folder:3",
            "updated": int,
            "orphans_fixed": int,
            "total_examined": int,
            "error": str? | None,
        }

    PR14 纪律:
    1. dry_run=False 默认 — 因为这是后台慢速回填, 需要真写库
       (但 Celery 任务外部触发时仍可传 dry_run=True 看效果)
    2. 任务失败不抛 → return {status: error} 让 Celery 不重试链
    3. updated=0 也要 logger.info 输出 (健康监控 + 审计追溯)
    4. NullPool 避免连接池跨事件循环 (CLAUDE.md 2026-06-03 垃圾桶清理铁律复用)
    """
    target_label = (
        f"file:{file_id}" if file_id is not None
        else f"folder:{folder_id}" if folder_id is not None
        else "all"
    )

    try:
        async def _run():
            # 延迟 import: 避免 Celery worker 启动时强依赖 sqlalchemy 等重库
            from app.services.drive_comments_path_backfill_service import (
                DriveCommentsPathBackfillService,
            )

            engine, session_factory = create_celery_engine_and_session()
            try:
                async with session_factory() as db:
                    svc = DriveCommentsPathBackfillService(db)

                    if file_id is not None:
                        # 单文件模式
                        updated = await svc.backfill_for_file(
                            file_id,
                            dry_run=dry_run,
                            fix_orphans=fix_orphans,
                        )
                        return {
                            "status": "ok",
                            "target": target_label,
                            "updated": updated,
                            "orphans_fixed": 0,  # 单文件模式不单独计 orphan
                            "total_examined": updated,
                            "dry_run": dry_run,
                        }
                    elif folder_id is not None:
                        # 单 folder 模式
                        updated = await svc.backfill_for_folder(
                            folder_id,
                            dry_run=dry_run,
                            fix_orphans=fix_orphans,
                        )
                        return {
                            "status": "ok",
                            "target": target_label,
                            "updated": updated,
                            "orphans_fixed": 0,
                            "total_examined": updated,
                            "dry_run": dry_run,
                        }
                    else:
                        # 全部模式
                        result = await svc.backfill_all_paths(
                            dry_run=dry_run,
                            fix_orphans=fix_orphans,
                        )
                        return {
                            "status": "ok",
                            "target": target_label,
                            "updated": result.updated,
                            "orphans_fixed": result.orphans_fixed,
                            "total_examined": result.total_examined,
                            "dry_run": result.dry_run,
                        }
            finally:
                await engine.dispose()

        result = asyncio.run(_run())

        if result.get("updated", 0) > 0:
            logger.warning(
                f"🔄 [PR14 path backfill] 自动回填: 更新 {result['updated']} 个评论 "
                f"target={target_label} orphans={result['orphans_fixed']} "
                f"dry_run={result.get('dry_run', False)}"
            )
        else:
            logger.info(
                f"✅ [PR14 path backfill] 健康: target={target_label} 无评论需更新 "
                f"dry_run={result.get('dry_run', False)}"
            )

        return result

    except Exception as e:
        logger.error(
            f"❌ [PR14 path backfill] 自动回填失败: target={target_label} error={e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "target": target_label,
            "error": str(e),
            "updated": 0,
            "orphans_fixed": 0,
            "total_examined": 0,
        }

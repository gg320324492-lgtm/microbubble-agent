"""课题组网盘 (Lab Group Drive) — Celery beat 软删除清理任务
2026-07-01

设计要点（与 chat_history_tasks.py / task_service.auto_purge_trash_task 一致）：
- 独立 create_async_engine(NullPool) + async_sessionmaker：避免全局
  async_session 绑定主进程事件循环，与 asyncio.run() 新循环冲突
- NullPool：禁用连接池，每任务创建新连接避免跨 loop 复用
- engine.dispose() finally：清理连接
- 始终 logger.warning (即便删除 0 个) → 健康监控可见

**2026-07-02 PR6-P12+ 增量 — service 函数拆出**:
原版所有 SQL + 物理删除 + MinIO 清理逻辑都在 task 顶层 (235 行),
现拆成:
- `app/services/drive_cleanup_service.py:clean_old_drive_files()` (NEW)
  - 物理清理逻辑 (Knowledge + Folder + MinIO)
  - 接受 db + cutoff_date, 返回 dict {deleted_files, deleted_folders, ...}
  - 与 chat_history_service.cleanup_soft_deleted_sessions 范式一致
- 本 task 文件: thin Celery wrapper (~80 行)
  - NullPool engine + 二次确认守卫 + asyncio.run + logger.warning 输出

清理范围:
- Knowledge 表: storage_mode='drive' AND deleted_at < cutoff 的记录
- Folder 表: deleted_at < cutoff 的孤儿 folder (无子文件 + 无子 folder)
- MinIO: 物理删除 Knowledge.file_path 对应对象

调度频率: 1h (与 task/chat 清理对齐)
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.celery_db import create_celery_engine_and_session
from app.core.celery import celery_app
from app.config import settings
from app.services.cleanup_safety import confirm_retention_param_auto
from app.services.drive_cleanup_service import clean_old_drive_files

logger = logging.getLogger("microbubble.drive_cleanup")


@celery_app.task(name="app.services.drive_cleanup_tasks.cleanup_expired_drive_files_task")
def cleanup_expired_drive_files_task(retention_days: Optional[int] = None):
    """Celery beat 任务：物理清除 retention_days 天前软删除的 drive 文件 + 孤儿 folder。

    Args:
        retention_days: 保留天数 (None 时使用 settings.DRIVE_RETENTION_DAYS, 默认 3)

    Returns:
        dict: {"status": "ok"|"skipped"|"error", "deleted_files": int, "deleted_folders": int,
               "skipped_folders": int, "minio_cleanup_failures": int, "cutoff": iso, "error": str?}

    关键铁律：
    1. 任务失败不抛 → return {status: error} 让 Celery 不重试链
    2. deleted_count = 0 也要 logger.info 输出 (健康监控 + 审计追溯)
    3. NullPool 避免连接池跨事件循环 (CLAUDE.md 2026-06-03 垃圾桶清理铁律复用)
    4. cutoff 计算后转 tz-naive (CLAUDE.md 2026-06-05 tz-aware vs naive 教训)
       — Knowledge.deleted_at 是 TIMESTAMP WITHOUT TIME ZONE, asyncpg 不能直接比较
    5. PR6-P11+ 二次确认守卫: confirm_retention_param_auto 自动选严格/友好模式
    6. **PR6-P12+ service 拆分**: 物理删除逻辑在 clean_old_drive_files() (可 mock 测试),
       本 task 只做 Celery wrapper (NullPool + asyncio.run + logger)
    """
    days = retention_days if retention_days is not None else getattr(
        settings, "DRIVE_RETENTION_DAYS", 3
    )

    # PR6-P11 + PR6-P12 二次确认守卫: retention_days != settings 默认值时延迟 + warn
    # 事故防复发: PR6-P9 误传 retention_days=0 删 31 条 (drive_cleanup 同模式风险)
    # PR6-P12: 用统一入口 confirm_retention_param_auto, 根据 settings.CLEANUP_CRITICAL_GUARDED_TASKS
    #          自动选择友好模式 (延迟 + warn) 或严格模式 (or_skip 直接拒绝)
    guard = confirm_retention_param_auto(
        retention_days=retention_days,
        default=getattr(settings, "DRIVE_RETENTION_DAYS", 3),
        task_name="app.services.drive_cleanup_tasks.cleanup_expired_drive_files_task",
    )
    if not guard["proceed"]:
        return {
            "status": "skipped",
            "reason": guard["reason"],
            "retention_days": guard["effective_days"],
            "deleted_files": 0,
            "deleted_folders": 0,
            "skipped_folders": 0,
        }
    try:
        async def _run():
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            try:
                # 计算 cutoff: UTC-aware → service 内部 _to_naive_datetime 统一
                cutoff_aware = datetime.now(timezone.utc) - timedelta(days=days)

                async with session_factory() as db:
                    # PR6-P12+ 增量: 物理删除逻辑全部在 service 函数 (可单测 + 可复用)
                    result = await clean_old_drive_files(db, cutoff_aware)

                    # 日志输出 (drive 多表统计, 与 chat_history 单表不同)
                    if result["deleted_files"] > 0 or result["deleted_folders"] > 0:
                        logger.warning(
                            f"🗑️ [drive_cleanup] 自动清理: 删除 {result['deleted_files']} 个 drive 文件, "
                            f"{result['deleted_folders']} 个孤儿 folder (跳过 {result['skipped_folders']} 个非空 folder, "
                            f"MinIO 失败 {result['minio_cleanup_failures']} 个) "
                            f"(cutoff={cutoff_aware.isoformat()}, retention={days}天)"
                        )
                    else:
                        logger.info(
                            f"✅ [drive_cleanup] 健康: 当前无超过 {days} 天的过期 drive 文件/folder "
                            f"(cutoff={cutoff_aware.isoformat()})"
                        )

                    return {
                        "status": "ok",
                        "deleted_files": result["deleted_files"],
                        "deleted_folders": result["deleted_folders"],
                        "skipped_folders": result["skipped_folders"],
                        "minio_cleanup_failures": result["minio_cleanup_failures"],
                        "cutoff": cutoff_aware.isoformat(),
                    }
            finally:
                await engine.dispose()

        result = asyncio.run(_run())
        return result
    except Exception as e:
        logger.error(f"❌ [drive_cleanup] 自动清理失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "deleted_files": 0,
            "deleted_folders": 0,
            "skipped_folders": 0,
            "minio_cleanup_failures": 0,
        }
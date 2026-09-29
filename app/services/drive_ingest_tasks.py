"""app/services/drive_ingest_tasks.py — 网盘文件自动入库 Celery 任务 (2026-09-05)

"网盘文件默认入库" 的异步执行体: 上传/版本更新入口 fire-and-forget 调
auto_ingest_drive_file_task.delay(file_id)，本任务在 celery-worker 里跑
完整 drive → kb 管线 (下载 → 分级提取 → 建/刷 kb 行 → analyze_knowledge_task)。

设计要点 (CLAUDE.md 铁律):
- 独立 NullPool engine (不能复用 FastAPI 的 async_session / 事件循环)
- 顶层 try/except 兜底: 任务内任何异常都不允许静默逃逸
- 幂等: ingest_drive_file 对同 file_id 天然幂等, 重试安全
- 开关: settings.DRIVE_AUTO_INGEST_KB=False 可整体停用 (入口侧判)
"""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.core.celery import celery_app

logger = logging.getLogger("microbubble.drive_ingest")

# ZB-2 备份产物形态 — 零感托管备份的容器与解密钥匙 (桌面端 cloud-backup.service
# 同目录同命名: <name>.mnbbak + <name>.mnbbak.key.json)。这类文件的 content 是
# 密钥信封明文, 绝不入知识库/向量索引 (跳过 drive→kb 抽取与 drive 内容索引)。
BACKUP_ARTIFACT_SUFFIXES: tuple = (".mnbbak", ".key.json")


def is_backup_artifact_name(file_name) -> bool:
    """文件名是否为备份产物形态 (纯函数, 单测用; 大小写不敏感后缀匹配)。"""
    n = (str(file_name) if file_name is not None else "").strip().lower()
    return n.endswith(BACKUP_ARTIFACT_SUFFIXES)


@celery_app.task(
    name="app.services.drive_ingest_tasks.auto_ingest_drive_file_task",
    bind=True,
    max_retries=2,
    priority=9,  # 高优先级: 上传入库不能排在 analyze 积压后面 (Redis transport 支持)
)
def auto_ingest_drive_file_task(self, drive_file_id: int, reingest: bool = False):
    """网盘文件 → 知识库自动入库 (上传/版本更新后异步执行)"""

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _run():
        from app.services.drive_to_kb_service import DriveToKBService

        async with session_factory() as db:
            # ZB-2: 备份产物形态在入口即跳过 (早于建 kb 孪生行, 「先跑后删」不算数)——
            # key.json 的 content 是密钥信封明文, 抽取入库 = 全组可见+可检索+向量化
            row_name = (
                await db.execute(
                    text("SELECT file_name FROM knowledge WHERE id = :i"),
                    {"i": drive_file_id},
                )
            ).scalar()
            if is_backup_artifact_name(row_name):
                logger.info(
                    f"[drive_auto_ingest] file_id={drive_file_id} "
                    f"file_name={row_name} 为备份产物形态, 跳过知识库抽取 (ZB-2)"
                )
                return {
                    "knowledge_id": None,
                    "skipped": "backup-artifact",
                    "ingest_mode": "skipped",
                    "reingested": reingest,
                    "content_length": 0,
                }
            result = await DriveToKBService(db).ingest_drive_file(
                drive_file_id, reingest=reingest
            )
            logger.info(
                f"[drive_auto_ingest] file_id={drive_file_id} → "
                f"knowledge_id={result['knowledge_id']} "
                f"mode={result.get('ingest_mode')} "
                f"reingested={result.get('reingested')} "
                f"content={result.get('content_length')} chars"
            )
            return result

    try:
        return asyncio.run(_run())
    except Exception as e:
        # 文件被删/不存在等永久性失败不重试; 其余 (MinIO 抖动/DB) 有限重试
        from app.services.drive_to_kb_service import DriveToKBError

        if isinstance(e, DriveToKBError) and e.status_code == 404:
            logger.warning(
                f"[drive_auto_ingest] file_id={drive_file_id} 已不存在, 放弃: {e.message}"
            )
            return None
        logger.error(
            f"[drive_auto_ingest] file_id={drive_file_id} 入库失败 (attempt "
            f"{self.request.retries + 1}/{self.max_retries + 1}): {e}",
            exc_info=True,
        )
        raise self.retry(exc=e, countdown=120)
    finally:
        # NullPool: asyncio.run 结束后 loop 已关, dispose 只清池配置不涉及活跃连接
        asyncio.run(engine.dispose())

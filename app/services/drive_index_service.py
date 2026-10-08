"""Drive 文件内容索引服务 (WP2, 2026-09-02)

审计缺口: drive 模式文件 (277 个) 只有 title/file_name 可搜, 原文躺在 MinIO。
本服务在上传/回填时解析原文 → 分块 → embedding → 写 knowledge_chunks
(drive 行本就是 knowledge 行, 复用 chunk 表)。

语料域隔离 (关键契约):
- kb 检索路全部带 storage_mode='kb' 过滤 — drive chunk 绝不混入知识库语料
- drive 内容只在 hybrid_retriever 新 drive 路 (storage_mode='drive' +
  可见性过滤) 出现
- 可见性口径: visibility != 'private' OR created_by = user (对齐
  drive_service.visibility_see_cond); user_id=None 时仅非 private

幂等: 先 DELETE 该 drive 行的全部 chunk 再 INSERT。
"""
from __future__ import annotations

import logging
import mimetypes
from typing import Any, Dict

from sqlalchemy import delete, select

logger = logging.getLogger("microbubble.drive_index_service")

# FIN-1 A2: 任务引擎 URL 可注入 (生产恒 None → create_celery_engine_and_session,
# 行为逐字不变); 测试注入测试库 URL 使任务不连生产库
_index_db_url_override = None

# drive 内容索引放行的扩展名。
#
# 注意: 这不是 file_parser_service.SUPPORTED_EXTENSIONS (那份只有 6 项结构化文档,
# 仅被 drive_to_kb_service 引用), 而是 drive 索引路自己的闸门。真正的解析能力
# 由 file_parser_service.extract_content 的分派决定 —— 它认 .pdf/.docx/.xlsx/
# .pptx 的专用解析器, 以及 TEXT_EXTENSIONS 里的整族纯文本。本表此前与那份 6 项
# 列表重复, 导致 parser 已支持的格式在 drive 索引路上被误挡 (占位 chunk 永不替换)。
#
# 2026-10-09 补 .csv / .log (见下方逐项理由)。
SUPPORTED_EXTS = {
    ".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md",
    # .csv: file_parser 有专用 _parse_csv (file_parser_service.py:79-80) —— 不是
    # 裸文本读! 它走 csv.reader 逐行解析、单元格去空后空格拼接, 输出风格与
    # _parse_xlsx 一致。实测 2 个网盘 CSV (52B / 1690B) 均解析为**单 chunk**,
    # 表头 (时间/转化率/温度/催化剂批次) 随正文保留, 搜"转化率"能命中且带列名上下文。
    # 注: 大 CSV (>6000 字符) 会 fallback 到 window 策略切成数字碎片, 这是 .xlsx
    # 既有的同款行为, 不是 csv 引入的新风险; 网盘现存 CSV 均远小于该阈值。
    ".csv",
    # .log: 已在 file_parser_service.TEXT_EXTENSIONS 内 (file_parser_service.py:50),
    # 走 _decode_text 的 utf-8 → utf-8-sig → gb18030 编码探测链。实测 2 个网盘
    # 日志解析出结构化中文运维记录 (自检/标定/丢帧/探头超时), 检索价值高。
    ".log",
}
# 为什么**不加** .json (ZB-2 安全边界, 勿扩):
# 1) .json 同样有专用 _parse_json 解析器, 技术上能解析, 但 key.json 这类密钥信封
#    的正文会被 pretty-print 后**明文写进 knowledge_chunks**, 而 embedding 表与
#    chunk 表都会随之落到备份/导出里 —— 泄密面从 MinIO 单文件扩大到可检索语料。
# 2) 现有守卫在**任务层**: index_drive_content_task 调 is_backup_artifact_name()
#    拦截备份产物 (drive_index_service.py:219)。若本表放开 .json, 就多出一条绕过
#    该守卫的**脚本侧**入口 (backfill_drive_content.py:68 直接 import 本表过滤),
#    守卫从"唯一收口"退化为"任选其一", 风险大于收益。
#    ⇒ 真要索引普通 .json, 必须先把 is_backup_artifact_name 下沉为共用谓词,
#      任务侧与脚本侧同时调用, 而不是在这里加一个字符串。


def _ext_of(filename: str) -> str:
    name = (filename or "").lower().strip()
    dot = name.rfind(".")
    return name[dot:] if dot >= 0 else ""


async def index_drive_content(
    knowledge_id: int,
    session_factory,
) -> Dict[str, Any]:
    """解析 drive 文件原文 → 分块 → embedding → 写 knowledge_chunks (幂等)

    Returns:
        {"chunks": 写入行数, "embedded": 回填数, "skipped": 0/1, "reason": str}
    """
    from app.models.knowledge import Knowledge
    from app.models.knowledge_chunk import KnowledgeChunk
    from app.services.chunking_service import chunk_text
    from app.services.embedding_service import generate_embeddings
    from app.services.embedding_truncation_policy import truncate_for_embedding
    from app.services.file_parser_service import file_parser_service
    from app.services.file_service import file_service

    stats: Dict[str, Any] = {"chunks": 0, "embedded": 0, "skipped": 0, "reason": ""}

    # 1. 读 drive 行 + 校验
    async with session_factory() as db:
        k = await db.get(Knowledge, knowledge_id)
        if k is None or k.storage_mode != "drive":
            stats["skipped"] = 1
            stats["reason"] = "not a drive row"
            return stats
        if k.deleted_at is not None:
            stats["skipped"] = 1
            stats["reason"] = "deleted"
            return stats

        ext = _ext_of(k.file_name or k.file_type or "")
        if ext not in SUPPORTED_EXTS:
            stats["skipped"] = 1
            stats["reason"] = f"unsupported ext {ext}"
            return stats
        if not k.file_path:
            stats["skipped"] = 1
            stats["reason"] = "no file_path"
            return stats

        file_name = k.file_name or f"file{ext}"
        file_path = k.file_path

    # 2. MinIO 下载原文
    try:
        data = await file_service.download_file(file_path)
    except Exception as e:
        stats["skipped"] = 1
        stats["reason"] = f"download failed: {e}"
        logger.warning("drive 内容下载失败(knowledge_id=%s): %s", knowledge_id, e)
        return stats

    # 3. 解析 (parser 抛错 → skipped)
    try:
        extracted = await file_parser_service.extract_content(
            data, file_name, mimetypes.guess_type(file_name)[0] or ""
        )
        text = (extracted.get("text") or "").strip()
    except Exception as e:
        stats["skipped"] = 1
        stats["reason"] = f"parse failed: {e}"
        logger.warning("drive 内容解析失败(knowledge_id=%s): %s", knowledge_id, e)
        return stats

    if not text:
        stats["skipped"] = 1
        stats["reason"] = "empty parse"
        return stats

    # 4. 分块 + 幂等落表
    chunks = chunk_text(text)
    if not chunks:
        stats["skipped"] = 1
        stats["reason"] = "no chunks"
        return stats

    async with session_factory() as db:
        await db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.knowledge_id == knowledge_id)
        )
        db.add_all(
            KnowledgeChunk(
                knowledge_id=knowledge_id,
                chunk_index=idx,
                content=c.content,
                char_start=c.char_start,
                char_end=c.char_end,
                char_count=c.char_count,
                strategy=c.strategy,
                chunk_metadata=c.chunk_metadata,
            )
            for idx, c in enumerate(chunks)
        )
        await db.commit()
    stats["chunks"] = len(chunks)

    # 5. embedding 批量回填 (失败 warning, 可由脚本/回填补)
    try:
        texts = [truncate_for_embedding(c.content) for c in chunks]
        embeddings = await generate_embeddings(texts, for_query=False)
        if embeddings and len(embeddings) == len(chunks):
            async with session_factory() as db:
                rows = (
                    await db.execute(
                        select(KnowledgeChunk).where(
                            KnowledgeChunk.knowledge_id == knowledge_id
                        )
                    )
                ).scalars().all()
                by_index = {r.chunk_index: r for r in rows}
                for idx, emb in enumerate(embeddings):
                    target = by_index.get(idx)
                    if target is not None and emb is not None:
                        target.embedding = emb
                        stats["embedded"] += 1
                await db.commit()
    except Exception as e:
        logger.warning(
            "drive chunk embedding 回填失败(knowledge_id=%s): %s", knowledge_id, e
        )

    logger.info(
        "drive 内容索引完成(knowledge_id=%s): chunks=%d embedded=%d",
        knowledge_id, stats["chunks"], stats["embedded"],
    )
    return stats


# ===== Celery 任务包装 =====
try:
    from app.core.celery import celery_app  # noqa: E402
    _HAS_CELERY = True
except ImportError:  # pragma: no cover
    _HAS_CELERY = False

if _HAS_CELERY:
    from app.core.celery_db import create_celery_engine_and_session  # noqa: E402

    @celery_app.task(
        name="app.services.drive_index_service.index_drive_content_task",
        bind=True,
        max_retries=2,
        default_retry_delay=30,
    )
    def index_drive_content_task(self, knowledge_id: int) -> Dict[str, Any]:
        """drive 文件内容索引任务 — 上传完成后 dispatch"""
        import asyncio

        async def _run():
            from app.services.drive_index_service import index_drive_content
            from app.core.celery_db import create_celery_engine_and_session as _mk

            # FIN-1 A2: 测试可注入引擎 URL (生产恒 None → 既有 celery_db 通道, 行为逐字不变)
            override = globals().get("_index_db_url_override")
            if override:
                from sqlalchemy.ext.asyncio import (
                    AsyncSession,
                    async_sessionmaker,
                    create_async_engine,
                )
                from sqlalchemy.pool import NullPool

                engine = create_async_engine(override, poolclass=NullPool)
                session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            else:
                engine, session_factory = _mk()
            try:
                # ZB-2: 备份产物形态 (.mnbbak / .key.json) 跳过内容索引——
                # key.json 的 chunk 会把密钥信封明文写进 knowledge_chunks
                from app.models.knowledge import Knowledge
                from app.services.drive_ingest_tasks import is_backup_artifact_name

                async with session_factory() as _db:
                    row_name = (
                        await _db.execute(
                            select(Knowledge.file_name).where(Knowledge.id == knowledge_id)
                        )
                    ).scalar()
                if is_backup_artifact_name(row_name):
                    logger.info(
                        f"[wp2] knowledge_id={knowledge_id} file_name={row_name} "
                        f"为备份产物形态, 跳过内容索引 (ZB-2)"
                    )
                    return {"knowledge_id": knowledge_id, "skipped": "backup-artifact"}
                return await index_drive_content(knowledge_id, session_factory)
            finally:
                await engine.dispose()

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.error(f"index_drive_content_task failed knowledge_id={knowledge_id}: {e}")
            try:
                raise self.retry(exc=e)
            except self.MaxRetriesExceededError:
                return {"knowledge_id": knowledge_id, "error": str(e)}

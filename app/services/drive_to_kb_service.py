"""app/services/drive_to_kb_service.py — 网盘文件入库 RAG (drive → kb)

把 storage_mode='drive' 的网盘文件转化为 storage_mode='kb' 的知识条目,
复用完整 RAG 管线 (file_parser → content 落库 → analyze_knowledge_task:
embedding + chunking + tsvector + BM25 + LLM 分析 + KG)。

关键复用 (只 import 不改):
- file_parser_service.extract_content   (app/services/file_parser_service.py)
- file_service.download_file            (app/services/file_service.py)
- analyze_knowledge_task               (app/services/knowledge_service.py)
- _incremental_add_document            (app/services/bm25_service.py, PR3 增量钩子)

转化语义:
- 新建一条 Knowledge 行 storage_mode='kb', 保留 original_path/original_parent_id/
  meta.drive_source_file_id 关联回网盘 (0 alembic 迁移, 复用现有字段)
- 原 drive 行不动 (文件管理/预览/版本/评论仍走 drive 域)
- 幂等: 同 drive file_id 重复调用返回既有 kb 行, 不重复建
- 权限: 与 drive_service.get_file 同口径 (owner 或 visibility != private)

与老 extract_to_kb 的关系 (DriveService.extract_to_kb, v2 PR1 简化版):
- 老方法: 原地改 storage_mode drive→kb (同一行), 不解析内容, PR3 说明"异步 LLM 提取留后"。
  该方法在 W98 派工前已被前端"📚 加入公共知识库"入口使用。
- 本服务: 新建 kb 行 + 完整解析 + 完整 RAG 管线, 原 drive 行保留。两者互不干扰。
"""

import logging
from typing import List, Optional

from sqlalchemy import select

from app.models.knowledge import Knowledge

logger = logging.getLogger("microbubble.drive_to_kb")

# 解析器不支持的扩展名 (image/video/archive 等) 直接不可入库
UNSUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp",
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a",
    ".mp4", ".avi", ".mov", ".mkv", ".webm",
    ".zip", ".rar", ".7z", ".gz", ".tar",
    ".exe", ".dll", ".bin", ".iso",
}


class DriveToKBError(Exception):
    """drive → kb 转化错误"""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class DriveToKBService:
    """网盘文件入库服务"""

    def __init__(self, db):
        self.db = db

    # ------------------------------------------------------------------
    # 单文件入库
    # ------------------------------------------------------------------

    async def ingest_drive_file(self, file_id: int, auto_research: bool = False) -> dict:
        """单文件入库: drive 文件 → kb 条目

        流程:
          1. 查 drive 行 (storage_mode='drive' + deleted_at IS NULL)
          2. 幂等检查: 同 drive file_id 是否已转化 (meta->>'drive_source_file_id')
          3. MinIO 下载原文件
          4. FileParserService.extract_content 解析
          5. 新建 Knowledge 行 storage_mode='kb' + original_path/original_parent_id 关联
          6. analyze_knowledge_task.delay (异步: embedding + chunking + tsvector +
             BM25 + LLM 分析 + KG + 多模态), 失败降级同步 best-effort

        Returns:
            {
              "knowledge_id": 新 kb 行 id,
              "already_ingested": bool,   # True = 幂等命中, 返回既有行
              "title": ..., "content_length": ..., "source_file_id": ...,
            }

        Raises:
            DriveToKBError: 文件不存在 / 不可入库 / 解析失败
        """
        drive_row = await self._get_drive_row(file_id)
        if drive_row is None:
            raise DriveToKBError("drive 文件不存在或已删除", 404)

        # 幂等: 同 file_id 已转化过 → 返回既有 kb 行
        existing = await self._find_existing_kb(drive_row.id)
        if existing is not None:
            logger.info(
                f"[drive_to_kb] 幂等命中 drive_file_id={drive_row.id} "
                f"→ knowledge_id={existing.id}, 跳过"
            )
            return {
                "knowledge_id": existing.id,
                "already_ingested": True,
                "title": existing.title,
                "content_length": len(existing.content or ""),
                "source_file_id": drive_row.id,
            }

        ext = self._extension_of(drive_row)
        if not ext or ext in UNSUPPORTED_EXTENSIONS:
            raise DriveToKBError(
                f"文件类型 {ext or '未知'} 不支持入库 (仅支持 PDF/Word/Excel/PPT/文本)",
                422,
            )

        # 1. MinIO 下载
        try:
            from app.services.file_service import file_service
            raw = await file_service.download_file(drive_row.file_path)
        except Exception as e:
            logger.warning(
                f"[drive_to_kb] MinIO 下载失败 file_id={drive_row.id} "
                f"path={drive_row.file_path}: {e}"
            )
            raise DriveToKBError(
                f"从网盘存储下载文件失败 (MinIO): {str(e)[:120]}", 502
            )
        if not raw:
            raise DriveToKBError("下载的文件内容为空", 422)

        # 2. 文件解析
        try:
            from app.services.file_parser_service import file_parser_service
            parsed = await file_parser_service.extract_content(
                raw, drive_row.file_name or "", drive_row.file_type or ""
            )
        except Exception as e:
            logger.warning(
                f"[drive_to_kb] 解析失败 file_id={drive_row.id} "
                f"name={drive_row.file_name}: {e}"
            )
            raise DriveToKBError(
                f"文件解析失败: {str(e)[:120]}", 422
            )

        text = (parsed or {}).get("text") or ""
        text = text.strip()
        # PostgreSQL text 类型拒绝 NUL 字节 (U+0000 是合法 UTF-8, errors='replace'
        # 不会清掉它)。坏文件/二进制伪装 .txt 可能带 NUL → 插入前必清, 否则 500。
        text = text.replace("\x00", "")
        if not text:
            raise DriveToKBError(
                "解析结果为空 (文件可能是扫描件/纯图片, 无文字内容)", 422
            )

        # 3. 新建 kb 行 (原 drive 行不动)
        # 注意: drive 侧 title/file_name 上限 500 (DriveFileUpdate schema),
        # kb 侧 Knowledge.title String(200) + ck_knowledge_file_name_length <= 200
        # (Agent 7 5th-wave CHECK 约束)。超长直抄会 500 → 截断到 200。
        title = (drive_row.title or drive_row.file_name or f"网盘文件 {drive_row.id}")[:200]
        visibility = drive_row.visibility if drive_row.visibility != "private" else "team"
        knowledge = Knowledge(
            title=title,
            content=text,
            source_type="drive_extracted",
            source=f"drive://file/{drive_row.id}",
            file_path=drive_row.file_path,      # 复用 MinIO 对象 (drive 行仍管理对象生命周期)
            file_name=(drive_row.file_name or "")[:200],
            file_type=drive_row.file_type,
            file_size=drive_row.file_size,
            file_hash=drive_row.file_hash,
            created_by=drive_row.created_by,
            storage_mode="kb",
            visibility=visibility,
            folder_id=None,                     # kb 条目不入 drive 目录树
            original_parent_id=drive_row.folder_id,
            original_path=drive_row.file_path,  # 关联回网盘 MinIO object_name
            analysis_status="pending",
            meta={"drive_source_file_id": drive_row.id},
        )
        self.db.add(knowledge)
        await self.db.commit()
        await self.db.refresh(knowledge)

        # 4. 触发完整 RAG 管线 (Celery, 失败降级同步 best-effort)
        self._enqueue_analysis(knowledge.id, title, text)

        logger.info(
            f"[drive_to_kb] 入库完成 drive_file_id={drive_row.id} "
            f"→ knowledge_id={knowledge.id} (content={len(text)} chars, "
            f"visibility={visibility})"
        )
        return {
            "knowledge_id": knowledge.id,
            "already_ingested": False,
            "title": title,
            "content_length": len(text),
            "source_file_id": drive_row.id,
        }

    # ------------------------------------------------------------------
    # 文件夹批量入库
    # ------------------------------------------------------------------

    async def ingest_folder(self, folder_id: int, dry_run: bool = False) -> dict:
        """文件夹批量入库: 该文件夹下所有 drive 文件

        权限: folder 不存在或非团队可见 → 404/403。
        逐文件 best-effort (单个失败记录 error, 不中断整批)。
        """
        from app.services.folder_service import FolderService

        folder = await FolderService(self.db).get_folder(folder_id)
        if folder is None:
            raise DriveToKBError("文件夹不存在或已删除", 404)
        if folder.visibility == "private":
            raise DriveToKBError("private 文件夹不可批量入库", 403)

        stmt = self._iter_folder_files(folder_id)
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())
        return await self._ingest_many(rows, dry_run=dry_run)

    # ------------------------------------------------------------------
    # 团队可见文件批量入库
    # ------------------------------------------------------------------

    async def ingest_team_files(self, dry_run: bool = False) -> dict:
        """团队可见文件批量入库 (visibility IN team/public 且未转化)"""
        stmt = self._iter_team_files()
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())
        return await self._ingest_many(rows, dry_run=dry_run)

    # ------------------------------------------------------------------
    # 可入库清单
    # ------------------------------------------------------------------

    async def list_ingestable(self, folder_id: Optional[int] = None) -> List[dict]:
        """列出可入库的 drive 文件 (未转化 + 解析器支持)"""
        if folder_id is not None:
            from app.services.folder_service import FolderService

            folder = await FolderService(self.db).get_folder(folder_id)
            if folder is None:
                raise DriveToKBError("文件夹不存在或已删除", 404)
            if folder.visibility == "private":
                raise DriveToKBError("private 文件夹不可批量入库", 403)
            stmt = self._iter_folder_files(folder_id)
        else:
            stmt = self._iter_team_files()

        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        # 已转化 file_id 集合 (单次查询, 避免 N+1 — W86-mini-4 实体图 N+1 教训)
        converted_ids = set()
        if rows:
            res = await self.db.execute(
                select(Knowledge.meta["drive_source_file_id"].astext).where(
                    Knowledge.storage_mode == "kb",
                    Knowledge.deleted_at.is_(None),
                    Knowledge.meta["drive_source_file_id"].astext.in_(
                        [str(r.id) for r in rows]
                    ),
                )
            )
            converted_ids = {int(v) for v in res.scalars().all() if v}

        items = []
        for row in rows:
            if row.id in converted_ids:
                continue
            ext = self._extension_of(row)
            ingestable = bool(ext and ext not in UNSUPPORTED_EXTENSIONS)
            items.append({
                "file_id": row.id,
                "title": row.title,
                "file_name": row.file_name,
                "file_type": row.file_type,
                "file_size": row.file_size,
                "visibility": row.visibility,
                "folder_id": row.folder_id,
                "ingestable": ingestable,
            })
        return items

    # ------------------------------------------------------------------
    # 内部 helpers
    # ------------------------------------------------------------------

    async def _get_drive_row(self, file_id: int) -> Optional[Knowledge]:
        result = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.storage_mode == "drive",
                Knowledge.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def _find_existing_kb(self, drive_file_id: int) -> Optional[Knowledge]:
        """幂等查重: 找已由该 drive 文件转化的 kb 行

        主键: meta->>'drive_source_file_id' == drive_file_id (W98 新增写入)。
        兜底: original_path == drive 行 file_path 且 storage_mode='kb' 且
        source_type='drive_extracted' (兼容历史手动升级条目)。
        """
        result = await self.db.execute(
            select(Knowledge).where(
                Knowledge.storage_mode == "kb",
                Knowledge.deleted_at.is_(None),
                Knowledge.meta["drive_source_file_id"].astext == str(drive_file_id),
            ).limit(1)
        )
        k = result.scalar_one_or_none()
        if k is not None:
            return k

        drive_row = await self._get_drive_row(drive_file_id)
        if drive_row is not None and drive_row.file_path:
            result2 = await self.db.execute(
                select(Knowledge).where(
                    Knowledge.storage_mode == "kb",
                    Knowledge.deleted_at.is_(None),
                    Knowledge.source_type == "drive_extracted",
                    Knowledge.original_path == drive_row.file_path,
                ).limit(1)
            )
            return result2.scalar_one_or_none()
        return None

    def _extension_of(self, row: Knowledge) -> str:
        name = row.file_name or ""
        ext = ""
        if "." in name:
            ext = "." + name.rsplit(".", 1)[-1].lower()
        if not ext and row.file_type:
            ft = (row.file_type or "").lower()
            if ft.startswith("."):
                ext = ft
        return ext

    def _iter_folder_files(self, folder_id: int):
        return (
            select(Knowledge)
            .where(
                Knowledge.storage_mode == "drive",
                Knowledge.deleted_at.is_(None),
                Knowledge.folder_id == folder_id,
                Knowledge.is_latest.is_(True),
            )
            .order_by(Knowledge.id)
        )

    def _iter_team_files(self):
        return (
            select(Knowledge)
            .where(
                Knowledge.storage_mode == "drive",
                Knowledge.deleted_at.is_(None),
                Knowledge.visibility.in_(["team", "public"]),
                Knowledge.is_latest.is_(True),
            )
            .order_by(Knowledge.id)
        )

    async def _ingest_many(self, rows, *, dry_run: bool) -> dict:
        """批量入库公共实现

        Args:
            rows: 已执行查询的 Knowledge 行列表 (调用方负责执行 Select)
        """

        if dry_run:
            return {
                "dry_run": True,
                "total": len(rows),
                "ingested": 0,
                "already_ingested": 0,
                "failed": 0,
                "errors": [],
                "knowledge_ids": [],
            }

        ingested = 0
        already = 0
        failed = 0
        errors = []
        knowledge_ids = []
        for row in rows:
            try:
                res = await self.ingest_drive_file(row.id)
                if res["already_ingested"]:
                    already += 1
                else:
                    ingested += 1
                knowledge_ids.append(res["knowledge_id"])
            except DriveToKBError as e:
                failed += 1
                errors.append({"file_id": row.id, "error": e.message})
            except Exception as e:  # noqa: BLE001 — best-effort 批量, 单个异常不中断
                failed += 1
                errors.append({"file_id": row.id, "error": str(e)[:160]})
                logger.exception(f"[drive_to_kb] 批量入库失败 file_id={row.id}")

        return {
            "dry_run": False,
            "total": len(rows),
            "ingested": ingested,
            "already_ingested": already,
            "failed": failed,
            "errors": errors,
            "knowledge_ids": knowledge_ids,
        }

    def _enqueue_analysis(self, knowledge_id: int, title: str, content: str) -> None:
        """触发 analyze_knowledge_task (Celery), 失败降级同步 best-effort。

        analyze_knowledge_task 是模块级函数 (Celery 任务装饰器),
        _run_analyze_and_embed 在内部用独立 NullPool engine 跑, 跨 loop 安全。
        """
        try:
            from app.services.knowledge_service import analyze_knowledge_task
            analyze_knowledge_task.delay(knowledge_id, title, content)
            return
        except Exception as e:
            logger.warning(
                f"[drive_to_kb] Celery 入队失败 knowledge_id={knowledge_id}, "
                f"降级同步执行: {e}"
            )
        try:
            from app.core.database import async_session
            from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

            factory = async_sessionmaker(
                async_session().bind, class_=AsyncSession, expire_on_commit=False
            )
            import asyncio

            from app.services.knowledge_service import _run_analyze_and_embed

            async def _sync_run():
                await _run_analyze_and_embed(knowledge_id, title, content, factory)

            try:
                asyncio.get_running_loop()
                asyncio.create_task(_sync_run())
            except RuntimeError:
                asyncio.run(_sync_run())
        except Exception as e:
            logger.warning(
                f"[drive_to_kb] 同步降级分析也失败 knowledge_id={knowledge_id}: {e}"
            )

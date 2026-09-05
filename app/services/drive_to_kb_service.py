"""app/services/drive_to_kb_service.py — 网盘文件入库 RAG (drive → kb)

把 storage_mode='drive' 的网盘文件转化为 storage_mode='kb' 的知识条目,
复用完整 RAG 管线 (file_parser → content 落库 → analyze_knowledge_task:
embedding + chunking + tsvector + BM25 + LLM 分析 + KG + 多模态)。

2026-09-05 全格式默认入库改造 (废除手动"入库知识库"按钮):
- 上传即自动入库 (drive_ingest_tasks.auto_ingest_drive_file_task 挂上传入口)
- 不再有"不支持类型 422 拒绝": 任何格式都会产生 kb 条目, 按扩展名分级提取:
    document  → file_parser (pdf/office + 40+ 纯文本族, 见 file_parser_service)
    image     → ocr_service.classify_and_extract (LLM vision OCR)
    av        → SpeechRecognizer.transcribe (SenseVoice ASR, 音视频皆可)
    archive   → zip/tar 内嵌文本成员提取 (硬上限防爆)
    binary    → 元数据兜底 (文件名/类型/大小入向量, 文件本体留在网盘)
  任何提取失败都降级元数据兜底, 保证"默认入库"永不失败。
- reingest=True 支持版本更新后原 kb 行原地刷新 (内容重提取 + 重新分析)。

关键复用 (只 import 不改):
- file_parser_service.extract_content   (app/services/file_parser_service.py)
- ocr_service.classify_and_extract      (app/services/ocr_service.py)
- SpeechRecognizer.transcribe           (app/voice/asr.py)
- file_service.download_file            (app/services/file_service.py)
- analyze_knowledge_task               (app/services/knowledge_service.py)

转化语义:
- 新建一条 Knowledge 行 storage_mode='kb', 保留 original_path/original_parent_id/
  meta.drive_source_file_id 关联回网盘 (0 alembic 迁移, 复用现有字段)
- 原 drive 行不动 (文件管理/预览/版本/评论仍走 drive 域)
- 幂等: 同 drive file_id 重复调用返回既有 kb 行, 不重复建 (reingest=True 例外)
"""

import logging
import mimetypes
import tarfile
import zipfile
from io import BytesIO
from typing import Optional

from sqlalchemy import select

from app.models.knowledge import Knowledge

logger = logging.getLogger("microbubble.drive_to_kb")

# ---------------------------------------------------------------------
# 按扩展名分级的提取策略 (2026-09-05 全格式入库)
# ---------------------------------------------------------------------

# LLM vision OCR (.svg 是 XML 文本, 归 document 走文本提取, 不进 OCR)
IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff",
}
# SenseVoice ASR (音频直接支持; 视频走 ffmpeg 解封装, 失败自动降级元数据)
AV_EXTENSIONS = {
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".oga", ".m4a", ".wma", ".opus",
    ".mp4", ".avi", ".mov", ".mkv", ".webm", ".flv", ".wmv", ".m4v",
}
# 压缩包内嵌文本提取 (rar/7z 无标准库 → 元数据兜底)
ARCHIVE_EXTENSIONS = {".zip", ".tar", ".gz", ".tgz"}

# ASR 输入上限 (SenseVoice 服务端 10min 超时 + ffmpeg 转码内存; 超限元数据兜底)
AV_MAX_BYTES = 300 * 1024 * 1024
# 压缩包提取硬上限 (zip-bomb / 超大包防御)
ARCHIVE_MAX_MEMBERS = 30
ARCHIVE_MAX_MEMBER_BYTES = 20 * 1024 * 1024
ARCHIVE_MAX_TOTAL_CHARS = 200_000


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

    async def ingest_drive_file(
        self, file_id: int, auto_research: bool = False, reingest: bool = False
    ) -> dict:
        """单文件入库: drive 文件 → kb 条目 (全格式, 失败降级元数据兜底)

        流程:
          1. 查 drive 行 (storage_mode='drive' + deleted_at IS NULL)
          2. 幂等检查: 已转化 → reingest=False 时直接返回既有 kb 行;
             reingest=True (版本更新) 时原地刷新既有 kb 行
          3. 按扩展名分级提取文本 (document/image/av/archive/binary)
          4. 新建或更新 Knowledge 行 storage_mode='kb'
          5. analyze_knowledge_task.delay (异步: embedding + chunking +
             tsvector + BM25 + LLM 分析 + KG), 失败降级同步 best-effort

        Returns:
            {
              "knowledge_id": kb 行 id,
              "already_ingested": bool,   # True = 幂等命中 (reingest=False)
              "reingested": bool,         # True = 版本更新刷新
              "ingest_mode": document|image_ocr|asr|archive|metadata,
              "title": ..., "content_length": ..., "source_file_id": ...,
            }

        Raises:
            DriveToKBError: 文件不存在 (404); 其余提取失败一律元数据兜底不抛
        """
        drive_row = await self._get_drive_row(file_id)
        if drive_row is None:
            raise DriveToKBError("drive 文件不存在或已删除", 404)

        # 幂等: 同 file_id 已转化过
        existing = await self._find_existing_kb(drive_row.id)
        if existing is not None and not reingest:
            logger.info(
                f"[drive_to_kb] 幂等命中 drive_file_id={drive_row.id} "
                f"→ knowledge_id={existing.id}, 跳过"
            )
            return {
                "knowledge_id": existing.id,
                "already_ingested": True,
                "reingested": False,
                "ingest_mode": (existing.meta or {}).get("drive_ingest_mode", "unknown"),
                "title": existing.title,
                "content_length": len(existing.content or ""),
                "source_file_id": drive_row.id,
            }

        ext = self._extension_of(drive_row)
        text, ingest_mode = await self._extract_text(drive_row, ext)

        if existing is not None:
            knowledge = await self._update_kb_row(existing, drive_row, text, ingest_mode)
            reingested = True
        else:
            knowledge = await self._create_kb_row(drive_row, text, ingest_mode)
            reingested = False

        # 触发完整 RAG 管线 (Celery, 失败降级同步 best-effort)
        title = knowledge.title or ""
        self._enqueue_analysis(knowledge.id, title, knowledge.content or "")

        logger.info(
            f"[drive_to_kb] 入库完成 drive_file_id={drive_row.id} "
            f"→ knowledge_id={knowledge.id} (mode={ingest_mode}, "
            f"content={len(knowledge.content or '')} chars, reingested={reingested})"
        )
        return {
            "knowledge_id": knowledge.id,
            "already_ingested": False,
            "reingested": reingested,
            "ingest_mode": ingest_mode,
            "title": title,
            "content_length": len(knowledge.content or ""),
            "source_file_id": drive_row.id,
        }

    # ------------------------------------------------------------------
    # 分级文本提取 (任何失败都降级元数据, 不抛)
    # ------------------------------------------------------------------

    async def _extract_text(self, row: Knowledge, ext: str) -> tuple:
        """按扩展名提取文本。

        Returns:
            (text, ingest_mode); text 可能为 "" (元数据兜底内容另行构造)
        """
        if ext in IMAGE_EXTENSIONS:
            return await self._extract_image_ocr(row), "image_ocr"
        if ext in AV_EXTENSIONS:
            return await self._extract_av_asr(row), "asr"
        if ext in ARCHIVE_EXTENSIONS:
            return await self._extract_archive_text(row, ext), "archive"
        if self._is_document(ext):
            return await self._extract_document(row), "document"
        # binary / 未知 → 纯元数据 (不下载文件)
        return "", "metadata"

    @staticmethod
    def _is_document(ext: str) -> bool:
        from app.services.file_parser_service import file_parser_service

        return (
            ext in file_parser_service.SUPPORTED_EXTENSIONS
            or ext in file_parser_service.TEXT_EXTENSIONS
        )

    async def _download(self, row: Knowledge):
        from app.services.file_service import file_service

        return await file_service.download_file(row.file_path)

    async def _extract_document(self, row: Knowledge) -> str:
        """pdf/office/文本族 → file_parser; 失败/空返回 "" (调用方元数据兜底)"""
        try:
            raw = await self._download(row)
            if not raw:
                return ""
            from app.services.file_parser_service import file_parser_service

            parsed = await file_parser_service.extract_content(
                raw, row.file_name or "", row.file_type or ""
            )
            text = ((parsed or {}).get("text") or "").strip()
            # NUL 字节清零 (PostgreSQL text 拒绝 U+0000)
            return text.replace("\x00", "")
        except Exception as e:
            logger.warning(
                f"[drive_to_kb] 文档解析失败 file_id={row.id} "
                f"name={row.file_name}: {e}"
            )
            return ""

    async def _extract_image_ocr(self, row: Knowledge) -> str:
        """图片 → LLM vision OCR (classify_and_extract); 失败返回 """""
        try:
            raw = await self._download(row)
            if not raw:
                return ""
            from app.services.ocr_service import ocr_service

            mime = (
                mimetypes.guess_type(row.file_name or "")[0]
                or row.file_type
                or "image/png"
            )
            result = await ocr_service.classify_and_extract(raw, mime)
            parts = []
            ocr_text = (result.get("text") or "").strip()
            if ocr_text:
                parts.append(ocr_text)
            if result.get("latex"):
                parts.append(f"公式 LaTeX:\n{result['latex']}")
            if result.get("table_md"):
                parts.append(f"表格:\n{result['table_md']}")
            if result.get("chart_description"):
                parts.append(f"图表说明:\n{result['chart_description']}")
            if result.get("caption"):
                parts.append(f"图注: {result['caption']}")
            return "\n\n".join(parts).replace("\x00", "")
        except Exception as e:
            logger.warning(f"[drive_to_kb] 图片 OCR 失败 file_id={row.id}: {e}")
            return ""

    async def _extract_av_asr(self, row: Knowledge) -> str:
        """音视频 → SenseVoice ASR; 服务不可用/超限/失败返回 """""
        try:
            if (row.file_size or 0) > AV_MAX_BYTES:
                logger.warning(
                    f"[drive_to_kb] 音视频超限跳过 ASR file_id={row.id} "
                    f"size={row.file_size}"
                )
                return ""
            raw = await self._download(row)
            if not raw:
                return ""
            from app.voice.asr import asr_service

            result = await asr_service.transcribe(raw)
            return ((result or {}).get("text") or "").strip().replace("\x00", "")
        except Exception as e:
            logger.warning(f"[drive_to_kb] 音视频 ASR 失败 file_id={row.id}: {e}")
            return ""

    async def _extract_archive_text(self, row: Knowledge, ext: str) -> str:
        """压缩包 → 提取内嵌文本成员 (zip/tar*, 硬上限防 zip-bomb); 失败返回 """""
        def _extract_sync(data: bytes) -> str:
            from app.services.file_parser_service import (
                file_parser_service as fps,
            )

            text_ok_exts = fps.TEXT_EXTENSIONS | fps.SUPPORTED_EXTENSIONS
            parts = []
            total_chars = 0

            def _member_ok(name: str) -> bool:
                low = (name or "").lower()
                return any(low.endswith(e) for e in text_ok_exts)

            def _add_member(name: str, data: bytes):
                nonlocal total_chars
                if len(parts) >= ARCHIVE_MAX_MEMBERS:
                    return
                if len(data) > ARCHIVE_MAX_MEMBER_BYTES:
                    return
                text = fps._decode_text(data)[: 400_000].replace("\x00", "")
                if not text.strip():
                    return
                parts.append(f"--- {name} ---\n{text}")
                total_chars += len(text)

            if ext == ".zip":
                with zipfile.ZipFile(BytesIO(data)) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        if not _member_ok(info.filename):
                            continue
                        _add_member(info.filename, zf.read(info))
                        if total_chars >= ARCHIVE_MAX_TOTAL_CHARS:
                            break
            else:  # .tar / .gz / .tgz (tarfile r:* 自动识别 gzip)
                with tarfile.open(fileobj=BytesIO(data), mode="r:*") as tf:
                    for member in tf.getmembers():
                        if not member.isfile():
                            continue
                        if not _member_ok(member.name):
                            continue
                        fobj = tf.extractfile(member)
                        if fobj is not None:
                            _add_member(member.name, fobj.read())
                        if total_chars >= ARCHIVE_MAX_TOTAL_CHARS:
                            break
            return "\n\n".join(parts)

        try:
            raw = await self._download(row)
            if not raw:
                return ""
            text = await self._to_thread(_extract_sync, raw)
            return text[:ARCHIVE_MAX_TOTAL_CHARS]
        except Exception as e:
            logger.warning(
                f"[drive_to_kb] 压缩包提取失败 file_id={row.id}: {e}"
            )
            return ""

    @staticmethod
    async def _to_thread(func, *args):
        import asyncio

        return await asyncio.to_thread(func, *args)

    # ------------------------------------------------------------------
    # 元数据兜底内容
    # ------------------------------------------------------------------

    def _metadata_content(self, row: Knowledge, ingest_mode: str) -> str:
        """无文本可提取时的兜底正文 (文件元数据入向量, 可按文件名检索)"""
        ext = self._extension_of(row) or "未知"
        size = row.file_size or 0
        if size >= 1024 * 1024 * 1024:
            size_str = f"{size / 1024 / 1024 / 1024:.1f} GB"
        elif size >= 1024 * 1024:
            size_str = f"{size / 1024 / 1024:.1f} MB"
        else:
            size_str = f"{size / 1024:.1f} KB"

        if ingest_mode == "image_ocr":
            note = "图片文件 (OCR 未识别到文字内容)"
        elif ingest_mode == "asr":
            note = "音视频文件 (语音转写不可用或结果为空)"
        elif ingest_mode == "archive":
            note = "压缩包 (未提取到文本内容)"
        elif ingest_mode == "document":
            note = "文档 (解析结果为空, 可能是扫描件或无文字层)"
        else:
            note = "二进制/程序文件, 暂无可提取的文本内容"

        created = ""
        if row.created_at:
            try:
                created = row.created_at.strftime("%Y-%m-%d %H:%M")
            except Exception:
                created = str(row.created_at)

        lines = [
            "【网盘文件 · 自动归档】",
            f"文件名: {row.file_name or row.title or ''}",
            f"格式: {ext}",
            f"大小: {size_str}",
        ]
        if created:
            lines.append(f"入库时间: {created}")
        lines.append(f"说明: {note}。已按文件元数据入库, 可按文件名检索; 文件本体保留在团队网盘。")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # kb 行创建 / 更新
    # ------------------------------------------------------------------

    async def _create_kb_row(self, row: Knowledge, text: str, ingest_mode: str) -> Knowledge:
        content = text or self._metadata_content(row, ingest_mode)
        # drive 侧 title/file_name 上限 500, kb 侧 Knowledge.title String(200)
        # + CHECK 约束 → 截断到 200 防直抄 500
        title = (row.title or row.file_name or f"网盘文件 {row.id}")[:200]
        visibility = row.visibility if row.visibility != "private" else "team"
        knowledge = Knowledge(
            title=title,
            content=content,
            source_type="drive_extracted",
            source=f"drive://file/{row.id}",
            file_path=row.file_path,      # 复用 MinIO 对象 (drive 行仍管理对象生命周期)
            file_name=(row.file_name or "")[:200],
            file_type=row.file_type,
            file_size=row.file_size,
            file_hash=row.file_hash,
            created_by=row.created_by,
            storage_mode="kb",
            visibility=visibility,
            folder_id=None,                     # kb 条目不入 drive 目录树
            original_parent_id=row.folder_id,
            original_path=row.file_path,        # 关联回网盘 MinIO object_name
            analysis_status="pending",
            meta={
                "drive_source_file_id": row.id,
                "drive_ingest_mode": ingest_mode,
            },
        )
        self.db.add(knowledge)
        await self.db.commit()
        await self.db.refresh(knowledge)
        return knowledge

    async def _update_kb_row(self, kb: Knowledge, row: Knowledge, text: str, ingest_mode: str) -> Knowledge:
        """版本更新 (reingest=True): 原地刷新 kb 行内容 + 元数据, 重新进分析管线"""
        content = text or self._metadata_content(row, ingest_mode)
        kb.title = (row.title or row.file_name or f"网盘文件 {row.id}")[:200]
        kb.content = content
        kb.file_path = row.file_path
        kb.file_name = (row.file_name or "")[:200]
        kb.file_type = row.file_type
        kb.file_size = row.file_size
        kb.file_hash = row.file_hash
        kb.original_path = row.file_path
        kb.original_parent_id = row.folder_id
        # JSONB mutable 协议 (W66 教训): 改 dict 后必须重新赋值
        base = dict(kb.meta or {})
        base["drive_source_file_id"] = row.id
        base["drive_ingest_mode"] = ingest_mode
        base.pop("ingest_last_error", None)
        kb.meta = base
        kb.analysis_status = "pending"
        await self.db.commit()
        await self.db.refresh(kb)
        return kb

    # ------------------------------------------------------------------
    # 文件夹批量入库
    # ------------------------------------------------------------------

    async def ingest_folder(self, folder_id: int, dry_run: bool = False) -> dict:
        """文件夹批量入库: 该文件夹下所有 drive 文件

        逐文件 best-effort (单个失败记录 error, 不中断整批)。
        """
        from app.services.folder_service import FolderService

        folder = await FolderService(self.db).get_folder(folder_id)
        if folder is None:
            raise DriveToKBError("文件夹不存在或已删除", 404)

        stmt = self._iter_folder_files(folder_id)
        result = await self.db.execute(stmt)
        rows = list(result.scalars().all())
        return await self._ingest_many(rows, dry_run=dry_run)

    # ------------------------------------------------------------------
    # 团队可见文件批量入库 (存量回填入口)
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

    async def list_ingestable(self, folder_id: Optional[int] = None) -> list:
        """列出未入库的 drive 文件 (全格式默认入库, ingestable 恒 True)"""
        if folder_id is not None:
            from app.services.folder_service import FolderService

            folder = await FolderService(self.db).get_folder(folder_id)
            if folder is None:
                raise DriveToKBError("文件夹不存在或已删除", 404)
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
            items.append({
                "file_id": row.id,
                "title": row.title,
                "file_name": row.file_name,
                "file_type": row.file_type,
                "file_size": row.file_size,
                "visibility": row.visibility,
                "folder_id": row.folder_id,
                "ingestable": True,  # 全格式默认入库 (2026-09-05)
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

        主键: meta->>'drive_source_file_id' == drive_file_id。
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

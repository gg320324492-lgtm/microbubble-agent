"""Drive v2 PR9 — File Version Diff Service (2026-07-24)

功能: 文件版本对比 (diff)

设计:
- 与 PR9 versions (W68 第 3 批 F-2) 互补: upload/list/download/rollback/delete 已有,
  本模块提供 **版本对比** —— 看 v3 vs v1 都改了啥
- 文本文件 (.txt .md .py .js .ts .json .yaml .yml .csv .html .css .sql .sh 等):
  用 difflib.SequenceMatcher 计算行级 + 字符级 diff
- 二进制文件 (PDF/image/zip/exe 等): 只返回 metadata diff (size/uploader/timestamp),
  **不解析内容** (解析二进制 = 高 CPU + 易内存爆, 留 PR11+ 评估)
- VersionDiff dataclass: 统一响应结构

为什么不用 external lib:
- difflib 是 stdlib (Python 内置, 0 依赖)
- SequenceMatcher 用 Ratcliff-Obershelp 算法, 最长公共子序列
- 对小文件 (< 1MB) 性能足够, 平均 50-200ms

调用方 (API 层):
- app/api/v1/drive_version_diff.py
"""
from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_file_version import DriveFileVersion
from app.models.knowledge import Knowledge

logger = logging.getLogger(__name__)


# ============================================================
# 常量: 文本文件扩展名白名单 (用于决定走文本 diff 还是 metadata diff)
# ============================================================

TEXT_EXTENSIONS = frozenset({
    # 纯文本
    ".txt", ".md", ".markdown", ".rst",
    # 代码
    ".py", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
    ".java", ".kt", ".swift", ".go", ".rs", ".c", ".cpp", ".cc", ".cxx", ".h", ".hpp",
    ".rb", ".php", ".lua", ".pl", ".sh", ".bash", ".zsh", ".ps1",
    ".html", ".htm", ".css", ".scss", ".less", ".sass",
    ".xml", ".xsl", ".xslt", ".vue", ".svelte",
    # 数据 / 配置
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".csv", ".tsv", ".sql",
    # 日志 (常 plain text)
    ".log",
    # 其它经常性的 plain text 容器
    ".gitignore", ".dockerignore", ".env",
})


# ============================================================
# 自定义异常
# ============================================================


class DriveVersionDiffServiceError(Exception):
    """Drive v2 PR9 版本对比服务错误

    - message: 错误消息
    - status_code: HTTP 状态码 (默认 400)
    """
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


# ============================================================
# 响应数据模型 (dataclass, 由 API 层转 Pydantic)
# ============================================================


@dataclass
class VersionDiff:
    """两个版本之间的对比结果

    字段语义:
    - file_id: 主文件 Knowledge.id
    - file_name: 当前文件名 (取自 Knowledge 主表)
    - from_version_number / from_version_id: 起始版本 (默认旧)
    - to_version_number / to_version_id: 目标版本 (默认新)
    - is_text: 是否走文本 diff (True) 还是 metadata diff (False)
    - unified_diff: unified diff 字符串 (仅 is_text=True 有值)
    - changed_lines: 变更行号列表 (仅 is_text=True 有值, 行号 in `to` 视角)
    - additions / deletions: 增加/删除行数 (仅 is_text=True)
    - size_delta: to.size - from.size (字节, 二进制 diff 也有)
    - uploader_delta: from.uploader_id != to.uploader_id 时为 True
    - from_meta / to_meta: 简单 metadata dict (uploader_id/uploader_name/created_at/comment)
    """
    file_id: int
    file_name: str
    from_version_number: int
    from_version_id: int
    to_version_number: int
    to_version_id: int
    is_text: bool
    unified_diff: Optional[str]
    changed_lines: Optional[List[int]]
    additions: Optional[int] = None
    deletions: Optional[int] = None
    size_delta: int = 0
    uploader_delta: bool = False
    from_meta: dict = field(default_factory=dict)
    to_meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """序列化为 dict (供 Pydantic 转 JSON)"""
        return asdict(self)


# ============================================================
# Service 类
# ============================================================


class DriveVersionDiffService:
    """Drive v2 PR9 版本对比服务

    核心方法:
    - compare_versions(file_id, from_version, to_version, current_user_id):
        主入口, 返回 VersionDiff
    - preview_version(version_id, current_user_id, head_lines):
        取某版本前 N 行 (用于 UI 对比左侧窗)
    """

    # 软上限: 单个版本超过这个字节数 → 拒绝完整文本 diff,
    # 退回 metadata diff + 警告
    TEXT_DIFF_MAX_BYTES = 1 * 1024 * 1024  # 1 MB

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================================================================
    # 权限校验 (复用 DriveVersionService 的可见性逻辑, 简化内联)
    # ==========================================================================

    @staticmethod
    async def _validate_visible(
        db: AsyncSession, file_id: int, user_id: int,
    ) -> Knowledge:
        """验证文件存在 + 可见性 (private 仅 owner 可见), 返回 Knowledge"""
        cur_file = await db.get(Knowledge, file_id)
        if cur_file is None:
            raise DriveVersionDiffServiceError(
                f"文件 id={file_id} 不存在", status_code=404,
            )
        if cur_file.deleted_at is not None:
            raise DriveVersionDiffServiceError(
                f"文件 id={file_id} 已删除", status_code=410,
            )
        if cur_file.created_by != user_id and cur_file.visibility == "private":
            raise DriveVersionDiffServiceError(
                f"无权查看文件 id={file_id} (private)", status_code=403,
            )
        return cur_file

    @staticmethod
    def _is_text_file(file_name: Optional[str]) -> bool:
        """判断文件是否为文本文件 (走 ext 白名单)"""
        if not file_name:
            return False
        if "." not in file_name:
            # 无扩展名, 保守返回 False
            return False
        ext = "." + file_name.rsplit(".", 1)[-1].lower()
        return ext in TEXT_EXTENSIONS

    @staticmethod
    def _meta_dict(v: DriveFileVersion) -> dict:
        """把 DriveFileVersion 序列化为 metadata dict (用于 from_meta / to_meta)"""
        return {
            "version_id": v.id,
            "version_number": v.version_number,
            "size": v.size,
            "uploader_id": v.uploader_id,
            "comment": v.comment,
            "is_current": bool(v.is_current),
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }

    @staticmethod
    def _char_offset_to_line(text: str, offset: int) -> int:
        """把字符偏移映射到 1-indexed 行号 (用 splitlines 累积)"""
        if offset <= 0:
            return 1
        # 防越界
        if offset > len(text):
            offset = len(text)
        # 数 \n 数量 (offset 之前的 \n 把它前面归到 line N, 当前是 line N+1)
        line = text.count("\n", 0, offset) + 1
        return line

    @staticmethod
    def _compute_text_diff(
        *,
        from_text: str,
        to_text: str,
        from_label: str,
        to_label: str,
    ) -> tuple:
        """计算文本 diff, 返回 (unified_diff, changed_lines, additions, deletions)

        Args:
            from_text / to_text: 两个版本的文本内容
            from_label / to_label: unified diff 行前缀标签 (e.g. "v1" / "v2")

        Returns:
            unified_diff: str (unified diff 格式, 含 @@ hunk 标记)
            changed_lines: List[int] (变更行号 in `to` 视角, 1-indexed)
            additions: int (+ 字符段数)
            deletions: int (- 字符段数)
        """
        # splitlines(keepends=True) 保留换行符让 difflib 知道行边界
        from_lines = from_text.splitlines(keepends=True)
        to_lines = to_text.splitlines(keepends=True)

        diff_lines = list(difflib.unified_diff(
            from_lines,
            to_lines,
            fromfile=from_label,
            tofile=to_label,
            lineterm="",
            n=3,  # context lines
        ))
        unified = "".join(diff_lines)

        # 用 SequenceMatcher 算 changed_lines (to 视角) + 增减统计
        matcher = difflib.SequenceMatcher(a=from_text, b=to_text, autojunk=False)
        changed_lines: List[int] = []
        additions = 0
        deletions = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            # j1 / j2 是 to_text 的字符偏移
            start_line = DriveVersionDiffService._char_offset_to_line(to_text, j1)
            # j2 是区间结尾 (exclusive), 减 1 转 inclusive, 但 clamp >= j1
            end_char = max(j2 - 1, j1)
            end_line = DriveVersionDiffService._char_offset_to_line(to_text, end_char)
            for ln in range(start_line, end_line + 1):
                if ln not in changed_lines:
                    changed_lines.append(ln)
            if tag in ("insert", "replace"):
                additions += (j2 - j1)
            if tag in ("delete", "replace"):
                deletions += (i2 - i1)

        changed_lines.sort()
        return unified, changed_lines, additions, deletions

    # ==========================================================================
    # 核心 API: compare_versions
    # ==========================================================================

    async def compare_versions(
        self,
        *,
        file_id: int,
        from_version_number: int,
        to_version_number: int,
        current_user_id: int,
    ) -> VersionDiff:
        """对比两个版本

        流程:
        1. 校验 file 存在 + 可见性
        2. 查 from_version (DriveFileVersion WHERE file_id=? AND version_number=?)
        3. 查 to_version (同理)
        4. 同 version → 返回空 diff (no change)
        5. 读 MinIO 两个版本 bytes
        6. 判定 is_text (走文本 diff vs metadata diff)
        7. 计算 diff 结果

        Args:
            file_id: 主文件 Knowledge.id
            from_version_number: 起始版本号 (1, 2, 3...)
            to_version_number: 目标版本号
            current_user_id: 当前用户 (JWT 鉴权)

        Returns:
            VersionDiff dataclass

        Raises:
            DriveVersionDiffServiceError: 404 文件不存在, 403 不可见,
              400 跨文件对比 / 参数非法
        """
        # 1. 校验
        cur_file = await self._validate_visible(self.db, file_id, current_user_id)

        if from_version_number < 1 or to_version_number < 1:
            raise DriveVersionDiffServiceError(
                f"version_number 必须 >= 1, 当前 from={from_version_number} "
                f"to={to_version_number}",
                status_code=400,
            )

        # 2. 查 from_version (JOIN Knowledge 一次性拿主表行, 简化)
        from_stmt = (
            select(DriveFileVersion)
            .where(
                and_(
                    DriveFileVersion.file_id == file_id,
                    DriveFileVersion.version_number == from_version_number,
                )
            )
        )
        from_v = (await self.db.execute(from_stmt)).scalars().first()
        if from_v is None:
            raise DriveVersionDiffServiceError(
                f"版本 v{from_version_number} 在文件 id={file_id} 中不存在",
                status_code=404,
            )

        # 3. 查 to_version
        to_stmt = (
            select(DriveFileVersion)
            .where(
                and_(
                    DriveFileVersion.file_id == file_id,
                    DriveFileVersion.version_number == to_version_number,
                )
            )
        )
        to_v = (await self.db.execute(to_stmt)).scalars().first()
        if to_v is None:
            raise DriveVersionDiffServiceError(
                f"版本 v{to_version_number} 在文件 id={file_id} 中不存在",
                status_code=404,
            )

        # 跨 file 错配 (理论上 file_id WHERE 已限制, 这里二次校验保险)
        if from_v.file_id != file_id or to_v.file_id != file_id:
            raise DriveVersionDiffServiceError(
                f"版本与文件 id 错配 (内部错误)", status_code=500,
            )

        # 4. 同版本 → 返回空 diff
        if from_v.version_number == to_v.version_number:
            logger.info(
                f"[DriveVersionDiffService.compare_versions] file_id={file_id} "
                f"same version v{from_v.version_number} → empty diff"
            )
            return VersionDiff(
                file_id=file_id,
                file_name=cur_file.file_name,
                from_version_number=from_v.version_number,
                from_version_id=from_v.id,
                to_version_number=to_v.version_number,
                to_version_id=to_v.id,
                is_text=False,
                unified_diff=None,
                changed_lines=None,
                size_delta=0,
                uploader_delta=False,
                from_meta=DriveVersionDiffService._meta_dict(from_v),
                to_meta=DriveVersionDiffService._meta_dict(to_v),
            )

        # 5. 读 bytes
        from app.services.file_service import file_service
        try:
            from_bytes = await file_service.download_file(from_v.minio_object_key)
        except Exception as e:
            logger.error(
                f"[DriveVersionDiffService] 读 from_version bytes 失败: "
                f"file_id={file_id} v{from_v.version_number} key={from_v.minio_object_key} "
                f"err={e!r}"
            )
            raise DriveVersionDiffServiceError(
                f"读取 from 版本 bytes 失败: {e!r}", status_code=500,
            )
        try:
            to_bytes = await file_service.download_file(to_v.minio_object_key)
        except Exception as e:
            logger.error(
                f"[DriveVersionDiffService] 读 to_version bytes 失败: "
                f"file_id={file_id} v{to_v.version_number} key={to_v.minio_object_key} "
                f"err={e!r}"
            )
            raise DriveVersionDiffServiceError(
                f"读取 to 版本 bytes 失败: {e!r}", status_code=500,
            )

        # 6. 判定 is_text
        is_text = DriveVersionDiffService._is_text_file(cur_file.file_name)

        # 7. 计算 diff
        size_delta = to_v.size - from_v.size
        uploader_delta = from_v.uploader_id != to_v.uploader_id

        from_meta = DriveVersionDiffService._meta_dict(from_v)
        to_meta = DriveVersionDiffService._meta_dict(to_v)

        if not is_text:
            # 二进制: 只返回 metadata diff
            logger.info(
                f"[DriveVersionDiffService.compare_versions] file_id={file_id} "
                f"v{from_v.version_number}→v{to_v.version_number} binary "
                f"size_delta={size_delta} uploader_delta={uploader_delta}"
            )
            return VersionDiff(
                file_id=file_id,
                file_name=cur_file.file_name,
                from_version_number=from_v.version_number,
                from_version_id=from_v.id,
                to_version_number=to_v.version_number,
                to_version_id=to_v.id,
                is_text=False,
                unified_diff=None,
                changed_lines=None,
                size_delta=size_delta,
                uploader_delta=uploader_delta,
                from_meta=from_meta,
                to_meta=to_meta,
            )

        # 文本: 走 SequenceMatcher
        # 超大文件保护: 超过 TEXT_DIFF_MAX_BYTES → 退回 metadata diff + warning
        if len(from_bytes) > self.TEXT_DIFF_MAX_BYTES or len(to_bytes) > self.TEXT_DIFF_MAX_BYTES:
            logger.warning(
                f"[DriveVersionDiffService] 大文件, 触发简化 metadata diff: "
                f"file_id={file_id} from_size={len(from_bytes)} to_size={len(to_bytes)} "
                f"max={self.TEXT_DIFF_MAX_BYTES}"
            )
            return VersionDiff(
                file_id=file_id,
                file_name=cur_file.file_name,
                from_version_number=from_v.version_number,
                from_version_id=from_v.id,
                to_version_number=to_v.version_number,
                to_version_id=to_v.id,
                is_text=False,  # 强制 False (UI 显示 "文件过大, 仅 metadata diff")
                unified_diff=None,
                changed_lines=None,
                size_delta=size_delta,
                uploader_delta=uploader_delta,
                from_meta={
                    **from_meta,
                    "warning": f"文件超过 {self.TEXT_DIFF_MAX_BYTES // 1024}KB, 跳过完整 diff",
                },
                to_meta={
                    **to_meta,
                    "warning": f"文件超过 {self.TEXT_DIFF_MAX_BYTES // 1024}KB, 跳过完整 diff",
                },
            )

        # 文本 diff (errors='replace' 防单字节解码失败整体抛)
        try:
            from_text = from_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            raise DriveVersionDiffServiceError(
                f"from version 文本解码失败: {e!r}", status_code=500,
            )
        try:
            to_text = to_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            raise DriveVersionDiffServiceError(
                f"to version 文本解码失败: {e!r}", status_code=500,
            )

        unified, changed_lines, additions, deletions = (
            DriveVersionDiffService._compute_text_diff(
                from_text=from_text,
                to_text=to_text,
                from_label=f"v{from_v.version_number}",
                to_label=f"v{to_v.version_number}",
            )
        )

        logger.info(
            f"[DriveVersionDiffService.compare_versions] file_id={file_id} "
            f"v{from_v.version_number}→v{to_v.version_number} text "
            f"+{additions}/-{deletions} changed_lines={len(changed_lines)} "
            f"size_delta={size_delta}"
        )

        return VersionDiff(
            file_id=file_id,
            file_name=cur_file.file_name,
            from_version_number=from_v.version_number,
            from_version_id=from_v.id,
            to_version_number=to_v.version_number,
            to_version_id=to_v.id,
            is_text=True,
            unified_diff=unified,
            changed_lines=changed_lines,
            additions=additions,
            deletions=deletions,
            size_delta=size_delta,
            uploader_delta=uploader_delta,
            from_meta=from_meta,
            to_meta=to_meta,
        )

    # ==========================================================================
    # 核心 API: preview_version (取某版本前 N 行)
    # ==========================================================================

    async def preview_version(
        self,
        *,
        version_id: int,
        current_user_id: int,
        head_lines: int = 200,
    ) -> dict:
        """预览某版本前 N 行 (用于对比 UI 左侧窗口)

        Args:
            version_id: DriveFileVersion.id
            current_user_id: 当前用户
            head_lines: 最多取前 N 行 (默认 200, max=2000 防爆内存)

        Returns:
            {
                "version_id": int,
                "file_id": int,
                "version_number": int,
                "file_name": str,
                "head_lines": int,
                "preview_lines": List[str],   # 已 trim 末尾 \n
                "total_lines": int,
                "truncated": bool,            # total_lines > head_lines 时 True
                "is_text": bool,              # 二进制文件返回空 preview_lines
                "size": int,
            }

        Raises:
            DriveVersionDiffServiceError: 404 / 403 / 400
        """
        # 限流 head_lines
        if head_lines < 1:
            head_lines = 1
        if head_lines > 2000:
            head_lines = 2000

        # 查版本
        v = await self.db.get(DriveFileVersion, version_id)
        if v is None:
            raise DriveVersionDiffServiceError(
                f"版本 id={version_id} 不存在", status_code=404,
            )

        # 文件可见性
        cur_file = await self._validate_visible(self.db, v.file_id, current_user_id)

        is_text = DriveVersionDiffService._is_text_file(cur_file.file_name)

        if not is_text:
            # 二进制: 返回 metadata + 提示, 不读内容
            return {
                "version_id": v.id,
                "file_id": v.file_id,
                "version_number": v.version_number,
                "file_name": cur_file.file_name,
                "head_lines": head_lines,
                "preview_lines": [],
                "total_lines": 0,
                "truncated": False,
                "is_text": False,
                "size": v.size,
                "note": "二进制文件, 不支持文本预览",
            }

        # 读 bytes
        from app.services.file_service import file_service
        try:
            content_bytes = await file_service.download_file(v.minio_object_key)
        except Exception as e:
            logger.error(
                f"[DriveVersionDiffService.preview_version] 读 bytes 失败: "
                f"version_id={version_id} err={e!r}"
            )
            raise DriveVersionDiffServiceError(
                f"读取版本 bytes 失败: {e!r}", status_code=500,
            )

        # 软上限: 超大 → 截断前 1MB
        if len(content_bytes) > self.TEXT_DIFF_MAX_BYTES:
            content_bytes = content_bytes[: self.TEXT_DIFF_MAX_BYTES]

        # 解码 (errors='replace' 防单字节损坏炸整体)
        text = content_bytes.decode("utf-8", errors="replace")
        all_lines = text.splitlines()
        total_lines = len(all_lines)
        preview = all_lines[:head_lines]

        logger.info(
            f"[DriveVersionDiffService.preview_version] version_id={version_id} "
            f"file_id={v.file_id} v{v.version_number} total_lines={total_lines} "
            f"preview={len(preview)}"
        )

        return {
            "version_id": v.id,
            "file_id": v.file_id,
            "version_number": v.version_number,
            "file_name": cur_file.file_name,
            "head_lines": head_lines,
            "preview_lines": preview,
            "total_lines": total_lines,
            "truncated": total_lines > head_lines,
            "is_text": True,
            "size": v.size,
        }

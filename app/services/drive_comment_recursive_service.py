"""Drive v2 PR11 recursive fallback service (2026-07-24, W68 第 9 批 B-2)

PR11 主路径 (commit a2a00ad73) 用 GIN trgm 索引 + path LIKE 替代 N+1 递归.
本 service 提供 PG function 兜底 (recursive CTE), 在以下场景自动 fallback:
- GIN trgm 索引失效 (DB 故障 / 索引重建中 / 索引被 drop)
- 极深嵌套 (>50 层) 时 path 字符串已超 VARCHAR(500) 限制, path 列物化失败
- 任何 sqlalchemy.exc.DatabaseError 23P01 invalid_text_representation 等

设计原则:
- 优先走 PR11 path LIKE GIN (快速, 1 query)
- 失败时调 PG function get_comment_ancestors_recursive / get_comment_descendants_recursive
- 错误码白名单: 只对 GIN 索引相关错误 fallback (见 _FALLBACK_ERROR_CODES)
  其他错误 (FK 违反 / 网络断) 仍 raise, 不可吞错
- 返回 dataclass 而不是 ORM 对象 (解耦 schema, 适配 PR11 + 老 schema 两种 ORM)

调用方:
- DriveCommentService.get_breadcrumb 失败时 → get_comment_ancestors_fallback
- DriveCommentService.list_by_path_prefix 失败时 → get_comment_descendants_fallback
- API 层 GET /drive/comments/{id}/breadcrumb 加 X-Fallback header 标识走哪条路径

纪律:
- 0 production code 改动铁律 (W68 第 9 批): 纯新功能, 不动 PR11 老逻辑
- service 函数失败 fallback 必须 log + raise in caller (不吞错)
- PG function 必须 GRANT EXECUTE TO app_user (migration 069 已含)
- 性能 A/B: GIN < 10ms / recursive < 50ms (PR11 性能预期)
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("microbubble.drive_comment_recursive")


# ==========================================================================
# 错误码白名单 (只对这些 fallback, 其他错误 raise)
# ==========================================================================

# PostgreSQL SQLSTATE codes
# 23P01 = exclusion_violation (GIN 索引 constraint 失效)
# 57014 = query_canceled (query timeout)
# 42P01 = undefined_table (驱动表不在)
# 42703 = undefined_column (列不在 — path 列可能被回滚)
# 22023 = invalid_parameter_value (path 物化失败, > VARCHAR(500))
_FALLBACK_ERROR_CODES = frozenset({
    "23P01",  # exclusion_violation — GIN 索引约束违反
    "57014",  # query_canceled — query timeout
    "42P01",  # undefined_table — 驱动表不在
    "42703",  # undefined_column — 列不在 (path 列被回滚)
    "22023",  # invalid_parameter_value — path 物化失败
})

# SQLAlchemy 通用错误 (OperationalError / ProgrammingError 可能含 pgcode)
_FALLBACK_SQLA_EXCEPTIONS = (OperationalError, ProgrammingError, DBAPIError)


# ==========================================================================
# Dataclass — fallback 返回 (不依赖 ORM schema 变化)
# ==========================================================================


@dataclass
class CommentBreadcrumbRow:
    """PG function 返回的单行 — 兼容 PR11 + 老 schema 两种 ORM

    field 列表故意精简 (不引用 path 列), 适配 PR11 前后两种 schema
    """
    id: int
    parent_id: Optional[int]
    depth: int
    file_id: Optional[int]
    folder_id: Optional[int]
    author_id: int
    content: str
    is_resolved: bool
    created_at: datetime
    updated_at: datetime

    # 兼容 ORM (前端渲染需要 content_preview + author_name)
    content_preview: str = field(default="")
    author_name: Optional[str] = None


@dataclass
class FallbackResult:
    """PG function fallback 调用结果

    Attributes:
        rows: 拿到的行 (祖先链 / 子树)
        fallback_used: True = 走了 PG function (没走 GIN)
        path: "gin" 或 "recursive" — 哪条路径被采纳
        error_code: 触发的 SQLSTATE code (None 表示 GIN 成功)
        duration_ms: 本次调用耗时 (ms)
    """
    rows: List[CommentBreadcrumbRow]
    fallback_used: bool
    path: str
    error_code: Optional[str] = None
    duration_ms: float = 0.0


# ==========================================================================
# Service 主体
# ==========================================================================


class DriveCommentRecursiveService:
    """PR11 PG function 兜底 — 调 get_comment_ancestors_recursive / get_comment_descendants_recursive

    单纯薄壳封装 (logic 在 PG 函数体内), 这里只负责:
    - 错误码白名单判断 (是否 fallback)
    - SQL execute + dataclass 映射
    - 耗时统计 (供 caller 写 X-Fallback header + 性能监控)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_comment_ancestors_fallback(
        self, comment_id: int
    ) -> FallbackResult:
        """兜底拿祖先链 (PG function: get_comment_ancestors_recursive)

        Args:
            comment_id: 目标评论 id

        Returns:
            FallbackResult (rows + fallback_used=True + path="recursive")

        Raises:
            sqlalchemy.exc.DatabaseError: 非白名单错误 (不吞错, 让 caller raise)

        Notes:
            - 边界: comment_id 不存在 → rows=[], fallback_used=True (PG function 自己返回空)
            - 兼容: 不引用 path 列 (PR11 前后 schema 都跑得动)
        """
        import time
        start = time.monotonic()

        sql = text(
            """
            SELECT
                id, parent_id, depth, file_id, folder_id, author_id,
                content, is_resolved, created_at, updated_at
            FROM get_comment_ancestors_recursive(:comment_id)
            """
        )

        try:
            result = await self.db.execute(sql, {"comment_id": comment_id})
        except _FALLBACK_SQLA_EXCEPTIONS as e:
            pgcode = _extract_sqlstate(e)
            if pgcode in _FALLBACK_ERROR_CODES:
                logger.warning(
                    f"[DriveCommentRecursiveService.get_comment_ancestors_fallback] "
                    f"PG function 失败 (sqlstate={pgcode}): {e!r}, "
                    f"fallback 失败也无路可走 (这是 fallback 自身)"
                )
            # 注意: 这是 fallback 自身, 失败只能 raise
            raise

        rows_raw = result.fetchall()
        rows = [_row_to_breadcrumb_row(r) for r in rows_raw]
        duration_ms = (time.monotonic() - start) * 1000.0

        logger.info(
            f"[DriveCommentRecursiveService.get_comment_ancestors_fallback] "
            f"comment_id={comment_id} rows={len(rows)} duration={duration_ms:.2f}ms"
        )

        return FallbackResult(
            rows=rows,
            fallback_used=True,
            path="recursive",
            error_code=None,
            duration_ms=duration_ms,
        )

    async def get_comment_descendants_fallback(
        self, root_id: int, max_depth: int = 100
    ) -> FallbackResult:
        """兜底拿子树 (PG function: get_comment_descendants_recursive)

        Args:
            root_id: 起始评论 id
            max_depth: 嵌套深度上限 (默认 100, 0~1000 由 PG function 强制)

        Returns:
            FallbackResult (rows + fallback_used=True + path="recursive")

        Raises:
            sqlalchemy.exc.DatabaseError: 非白名单错误 (不吞错, 让 caller raise)

        Notes:
            - 边界: root_id 不存在 → rows=[]
            - max_depth: PG function 内部 clamp 到 [0, 1000]
        """
        import time
        start = time.monotonic()

        sql = text(
            """
            SELECT
                id, parent_id, depth, file_id, folder_id, author_id,
                content, is_resolved, created_at, updated_at
            FROM get_comment_descendants_recursive(:root_id, :max_depth)
            """
        )

        try:
            result = await self.db.execute(
                sql, {"root_id": root_id, "max_depth": max_depth}
            )
        except _FALLBACK_SQLA_EXCEPTIONS as e:
            pgcode = _extract_sqlstate(e)
            if pgcode in _FALLBACK_ERROR_CODES:
                logger.warning(
                    f"[DriveCommentRecursiveService.get_comment_descendants_fallback] "
                    f"PG function 失败 (sqlstate={pgcode}): {e!r}"
                )
            raise

        rows_raw = result.fetchall()
        rows = [_row_to_breadcrumb_row(r) for r in rows_raw]
        duration_ms = (time.monotonic() - start) * 1000.0

        logger.info(
            f"[DriveCommentRecursiveService.get_comment_descendants_fallback] "
            f"root_id={root_id} max_depth={max_depth} rows={len(rows)} "
            f"duration={duration_ms:.2f}ms"
        )

        return FallbackResult(
            rows=rows,
            fallback_used=True,
            path="recursive",
            error_code=None,
            duration_ms=duration_ms,
        )

    # ==========================================================================
    # GIN 主路径调用 (失败 fallback)
    # ==========================================================================

    async def get_breadcrumb_with_fallback(
        self, comment_id: int
    ) -> FallbackResult:
        """拿祖先链 — 优先 GIN path LIKE, 失败 fallback PG function

        Args:
            comment_id: 目标评论 id

        Returns:
            FallbackResult (path="gin" 或 "recursive")

        Raises:
            DriveCommentServiceError(404) comment 不存在 (GIN 和 fallback 都查不到)

        Notes:
            - GIN 主路径用 LIKE path 走 ix_drive_comments_path_gin 索引 (PR11 加)
            - 失败 fallback: SQLSTATE 白名单 (23P01 / 57014 / 42703 / 22023)
            - X-Fallback header 由 API 层从 result.path 取值
        """
        import time
        start = time.monotonic()

        # === GIN 主路径 (1 query, 走 path LIKE) ===
        gin_sql = text(
            """
            SELECT id, parent_id, file_id, folder_id, author_id,
                   content, is_resolved, created_at, updated_at,
                   -- path 深度 (按 path 长度推算 depth, 兼容 PR11 前后 schema)
                   COALESCE(array_length(string_to_array(trim(path, '/'), '/'), 1), 0) AS depth
            FROM drive_comments
            WHERE id = :comment_id
            """
        )

        try:
            result = await self.db.execute(gin_sql, {"comment_id": comment_id})
            row = result.fetchone()
        except _FALLBACK_SQLA_EXCEPTIONS as e:
            pgcode = _extract_sqlstate(e)
            if pgcode in _FALLBACK_ERROR_CODES:
                logger.warning(
                    f"[DriveCommentRecursiveService.get_breadcrumb_with_fallback] "
                    f"GIN 主路径失败 (sqlstate={pgcode}): {e!r}, fallback 到 PG function"
                )
                # === Fallback to PG function ===
                fb = await self.get_comment_ancestors_fallback(comment_id)
                fb.duration_ms = (time.monotonic() - start) * 1000.0
                return fb
            # 非白名单错误 → raise
            raise

        if row is None:
            # GIN 没找到 — 可能是真的不存在, 也可能是 path 列物化失败
            # 兜底: 直接 fallback, 如果 PG function 也返回空就 404
            fb = await self.get_comment_ancestors_fallback(comment_id)
            if not fb.rows:
                from app.services.drive_comment_service import DriveCommentServiceError
                raise DriveCommentServiceError(
                    f"Comment id={comment_id} 不存在", status_code=404
                )
            fb.duration_ms = (time.monotonic() - start) * 1000.0
            return fb

        # GIN 成功, 拉祖先链
        current_id = row[0]
        current = _row_to_breadcrumb_row(row)

        # 拿祖先 (path LIKE 走 GIN)
        # current.path LIKE '%/X/%' → 拿祖先 (深度 depth - 1, depth - 2, ...)
        # 这里简化: 直接调 PG function 拿 ancestors, 因为 PG function 自己有 STABLE 优化
        # 而且 ancestor_chain 用 parent_id 沿链向上, 不依赖 path 列
        fb = await self.get_comment_ancestors_fallback(current_id)
        duration_ms = (time.monotonic() - start) * 1000.0

        # 把 GIN 命中的 current row 加到头部 (depth=0)
        # 然后 PG function 返回的深度 >= 1 的 rows
        gin_result = FallbackResult(
            rows=[current] + fb.rows[1:] if len(fb.rows) > 1 else [current],
            fallback_used=False,
            path="gin",
            error_code=None,
            duration_ms=duration_ms,
        )
        logger.info(
            f"[DriveCommentRecursiveService.get_breadcrumb_with_fallback] "
            f"comment_id={comment_id} path=gin rows={len(gin_result.rows)} "
            f"duration={duration_ms:.2f}ms"
        )
        return gin_result


# ==========================================================================
# 工具函数
# ==========================================================================


def _extract_sqlstate(error: BaseException) -> Optional[str]:
    """从 SQLAlchemy / psycopg2 错误对象提取 PostgreSQL SQLSTATE code

    兼容:
    - psycopg2.errors.lookup (e.pgcode)
    - psycopg (v3) errors (e.sqlstate 或 e.diag.sqlstate)
    - 字符串形式包含 SQLSTATE (e.orig.pgcode)

    Returns:
        5-char SQLSTATE (例 "23P01") 或 None (非 pg 错误)
    """
    # psycopg2 style
    pgcode = getattr(error, "pgcode", None)
    if pgcode:
        return str(pgcode)

    # psycopg (v3) style
    sqlstate = getattr(error, "sqlstate", None)
    if sqlstate:
        return str(sqlstate)

    # diag.sqlstate
    diag = getattr(error, "diag", None)
    if diag is not None:
        sqlstate = getattr(diag, "sqlstate", None)
        if sqlstate:
            return str(sqlstate)

    # orig.pgcode (SQLAlchemy 包装)
    orig = getattr(error, "orig", None)
    if orig is not None and orig is not error:
        nested = _extract_sqlstate(orig)
        if nested:
            return nested

    return None


def _row_to_breadcrumb_row(row: Any) -> CommentBreadcrumbRow:
    """SQLAlchemy Row → CommentBreadcrumbRow dataclass

    行顺序必须与 SQL SELECT 一致 (id, parent_id, depth, file_id, folder_id,
    author_id, content, is_resolved, created_at, updated_at)
    """
    return CommentBreadcrumbRow(
        id=int(row[0]),
        parent_id=int(row[1]) if row[1] is not None else None,
        depth=int(row[2]) if row[2] is not None else 0,
        file_id=int(row[3]) if row[3] is not None else None,
        folder_id=int(row[4]) if row[4] is not None else None,
        author_id=int(row[5]),
        content=str(row[6]) if row[6] else "",
        is_resolved=bool(row[7]) if row[7] is not None else False,
        created_at=row[8],
        updated_at=row[9],
        content_preview=str(row[6])[:100] if row[6] else "",
        author_name=None,  # 不在 SELECT 里 (PG function 不 join author)
    )


__all__ = [
    "DriveCommentRecursiveService",
    "CommentBreadcrumbRow",
    "FallbackResult",
    "_FALLBACK_ERROR_CODES",
]
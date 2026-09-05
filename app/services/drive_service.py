"""Drive 文件服务 (PR2.1 + v2 升级)

负责 drive_storage_mode='drive' 文件元数据的 CRUD 操作。

# 2026-08-17 #Step2-重做: drive_service.py 2430 行结构性文档 (Plan v1 Step 2)
# 实际拆分调研: 0 安全拆点 (所有 50+ 方法都被 drive_files.py 路由直接调用, 删任一方法 → 500).
# Plan v1 路线 Step 2 拆为子服务 已确认不可行 (227 行的真重复代码 vs 1950 行的活代码).
# 现 Step 2 落地: 文档化 9 个 section + 标注子服务迁移路径, 为未来真拆分留 anchor.
# 未来拆分锚点 (主拍决策时启动):
#   - share 4 方法 (L1022-1200) -> 已有 drive_share_service.py 728 行, API 应改用 DriveShareService 直接
#   - version 3 方法 (L1814-1970) -> 已有 drive_version_service.py 768 行
#   - dedupe 2 方法 (L1683-1810) -> 已有 drive_dedupe_service.py 228 行
#   - collab N 方法 -> 已有 drive_collab_service.py 564 行
# 当前: 全部 facade 调用由 drive_files.py 路由直接 svc.method() 触发 (主拍决策前不强行改路由).

核心边界:
- 2026-09 单一团队空间: owner (created_by) 降级为纯溯源, 所有 owner 相等权限门禁已删;
  visibility='private' 概念退役 — create_file/create_instant_upload 收口点强制改写 'team',
  存量由 alembic 133 回填, is_team_shared 服务端恒 True。
- visibility='private' 文件: 仅 created_by (owner) 可见，其他人**完全看不到** (不是 403)
  ↑ 历史语义; 新数据不再产生 private, 该过滤仅存兜底
- visibility='team': 当前活跃成员可见
- visibility='public': 含团队外部分享链接 (本服务暂不展开 share_token, 留 PR2.7)
- 文件 visibility >= 所在文件夹 visibility (文件夹硬上限, plan 决策 2026-07-01)
- drive 文件不入 embedding 索引 (search_semantic 硬过滤 storage_mode='kb', PR1.4 已实现)
- 软删除: deleted_at 标记 → Celery beat 30 天后物理清除 (W72 B-3)

业务规则优先级:
  1. visibility 继承上级文件夹（不可越权）, 见 _validate_visibility_inherits
  2. drive 文件不入 Agent search_knowledge 检索 (隐私边界)
  3. listing 时 SQL hard-filter private → created_by=current_user_id
"""
import hashlib
import asyncio
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, delete, or_, select, func, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.datetime_utils import to_naive_datetime

from app.models.folder import Folder, VISIBILITY_ORDER
from app.models.drive_file_star import DriveFileStar
from app.models.knowledge import Knowledge, KnowledgeVersion, ChunkedUploadSession  # PR5: 断点续传
from app.models.member import Member
from app.services.file_service import file_service
# 批次① B2: 永久删时统一回收 当前对象 + PR9 版本对象 (collect 必须先于 DELETE)
from app.services.drive_object_gc import collect_object_keys, purge_minio_keys
# PR6: activity + notification 集成
from app.services.activity_service import activity_service
from app.services.notification_service import notification_service
from app.services.drive_upload_service import create_initial_version

logger = logging.getLogger("microbubble.drive")


# 默认配额
MAX_DRIVE_FILE_SIZE_MB = 2048  # MinIO multipart 安全上限
MAX_DRIVE_FILE_SIZE_BYTES = MAX_DRIVE_FILE_SIZE_MB * 1024 * 1024


# ===== 分享链接默认值 (v2 PR1) =====
DEFAULT_SHARE_EXPIRES_HOURS = 168   # 7 天 (百度网盘默认 7 天, 我们保持一致)
MAX_SHARE_EXPIRES_HOURS = 8760     # 365 天
MIN_SHARE_PASSWORD_LENGTH = 4
MAX_SHARE_PASSWORD_LENGTH = 8


def _hash_share_password(password: str) -> str:
    """提取码 SHA256 hex 哈希 (64 字符).

    计划文档原话: "提取码 SHA256 哈希存", 所以即使明文是 4 位数字也存 hash.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _validate_share_password(password: Optional[str]) -> None:
    """校验提取码长度 (4-8 位数字). 抛出 DriveServiceError(400) 给上层 API.
    """
    if password is None:
        return  # 公开分享, 无密码
    if not isinstance(password, str) or len(password) < MIN_SHARE_PASSWORD_LENGTH or len(password) > MAX_SHARE_PASSWORD_LENGTH:
        raise DriveServiceError(
            f"提取码长度需在 {MIN_SHARE_PASSWORD_LENGTH}-{MAX_SHARE_PASSWORD_LENGTH} 位之间",
            status_code=400,
        )
    if not password.isdigit():
        raise DriveServiceError("提取码必须为纯数字", status_code=400)


def _validate_share_expires_hours(expires_hours: Optional[int]) -> None:
    """校验分享链接过期时间 (1h - 365d). 0/None = 7 天默认. 负数 = 永久 (-1).
    """
    if expires_hours is None or expires_hours == 0:
        return
    if expires_hours == -1:
        return  # -1 = 永久
    if expires_hours < 1 or expires_hours > MAX_SHARE_EXPIRES_HOURS:
        raise DriveServiceError(
            f"过期时长超出范围 (1 - {MAX_SHARE_EXPIRES_HOURS} 小时), 0 = 默认 7 天, -1 = 永久",
            status_code=400,
        )


# =====================================================================
# v2 代码清理收尾 (2026-07-23): retry 装饰器 + folder filter + query builder
# =====================================================================
# 之前 _stream_concat_chunks + chunked_upload 路径直接裸调 MinIO/DB, 出错时
# 网络瞬断 (RST/timeout/5xx) 不会自动重试, 用户看到 "上传失败" 但其实 0.5s 后
# 重试就能成功. 第三/四/五波多版本迭代后, retry 模式逐渐分散, 这里抽成一个
# 装饰器 + helper, 未来加 retry 只需 `@drive_retry(max_attempts=3)` 一行.

import functools


# 默认重试参数 (针对 MinIO/PG 瞬断场景: 200ms → 400ms → 800ms, 上限 1.6s)
DRIVE_RETRY_DEFAULT_MAX_ATTEMPTS = 3
DRIVE_RETRY_DEFAULT_BACKOFF_BASE = 0.2  # seconds
DRIVE_RETRY_DEFAULT_BACKOFF_MAX = 1.6   # seconds

# DriveServiceError 不重试 (业务级错误, 重试也 4xx)
# OperationalError / IOError / OSError / asyncio.TimeoutError 走重试
import sqlalchemy.exc as _sa_exc


def drive_retry(
    max_attempts: int = DRIVE_RETRY_DEFAULT_MAX_ATTEMPTS,
    backoff_base: float = DRIVE_RETRY_DEFAULT_BACKOFF_BASE,
    backoff_max: float = DRIVE_RETRY_DEFAULT_BACKOFF_MAX,
    retry_on: tuple = (_sa_exc.OperationalError, OSError, IOError, asyncio.TimeoutError),
):
    """Drive 服务共享 retry 装饰器 (替代分散的 try/except 重试模式)

    设计要点:
    - 仅重试 transient 错误 (OperationalError / OSError / IOError / asyncio.TimeoutError)
    - 业务错误 (DriveServiceError, ValueError) 不重试 — 重试也是 4xx
    - 指数退避 + jitter: sleep = min(base * 2^(attempt-1), max) + random(0, 0.05)
    - 最后一次失败抛原异常 (不包 DriveServiceError, 让上游 try/except 正常处理)
    - async 函数专用 (装饰器内部 await sleep)

    使用范式:
        @drive_retry(max_attempts=3)
        async def upload_chunk(...):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            import random
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except retry_on as exc:
                    last_exc = exc
                    if attempt >= max_attempts:
                        # 最后一次失败: 抛原异常, 让上游处理
                        logger.warning(
                            f"[drive_retry] {func.__name__} attempt {attempt}/{max_attempts} "
                            f"failed (final): {type(exc).__name__}: {exc}"
                        )
                        raise
                    # 退避: base * 2^(attempt-1), capped at max
                    sleep_sec = min(backoff_base * (2 ** (attempt - 1)), backoff_max)
                    sleep_sec += random.uniform(0, 0.05)  # jitter 防 thundering herd
                    logger.debug(
                        f"[drive_retry] {func.__name__} attempt {attempt}/{max_attempts} "
                        f"failed ({type(exc).__name__}), retry in {sleep_sec:.2f}s"
                    )
                    await asyncio.sleep(sleep_sec)
            # 理论不会到这里, 但保险
            raise last_exc
        return wrapper
    return decorator


def _build_folder_filter_clause(
    folder_id: Optional[int],
    include_subfolders: bool = False,
):
    """v2.21 (2026-07-11) + v2.22 (2026-07-11) 共享 folder filter 逻辑.

    三种场景:
    1. folder_id 显式 (e.g. 5) → `Knowledge.folder_id == 5` (只看该 folder)
    2. folder_id=None + include_subfolders=False → `Knowledge.folder_id.is_(None)` (顶级, 个人 view)
    3. folder_id=None + include_subfolders=True → 跳过 filter (团队共享盘顶级, 含 root + 所有 sub)

    Returns:
        SQLAlchemy 谓词 (用于 filters.append), 或 None 表示"不过滤".

    v2.22 重构说明:
    之前 3 种场景分散在 _list_files_impl 的 if/elif 分支里 (line 427-436), 混在
    6 种其他 filter 中 (deleted, visibility, starred, file_type, is_team_shared, see_cond).
    抽成 helper 后: 单测可独立覆盖 + 新增场景 (e.g. include_subfolders=True + folder_id=5
    的混合) 只改 1 处.
    """
    if folder_id is not None:
        # 显式 folder → 只看该 folder (不论 include_subfolders, 子文件夹遍历留给调用方)
        return Knowledge.folder_id == folder_id
    if include_subfolders:
        # 团队共享盘顶级 view → 不过滤 (root + 所有 sub folder 都要)
        return None
    # 个人 view 顶级 → 只看 folder_id IS NULL (即"根目录", 不含子文件夹)
    return Knowledge.folder_id.is_(None)


def _escape_ilike(term: str) -> str:
    """批次① B6: ILIKE 通配符转义 (\\ % _) — 用户输入的 %/_ 必须按字面量匹配.

    转义顺序: 先转义反斜杠本身, 再转 % _ (否则会把刚插进去的 \\ 二次转义)。
    配合 ilike(..., escape="\\\\") 编译出 `ESCAPE '\\'`。
    """
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _build_list_files_query(
    *,
    storage_mode: str,
    folder_id: Optional[int],
    include_subfolders: bool,
    visibility_filter: Optional[str],
    starred_only: bool,
    file_type: Optional[str],
    is_team_shared_filter: Optional[bool],
    deleted_only: bool,
    include_deleted: bool,
    current_user_id: int,
    search: Optional[str] = None,
):
    """v2.22 (2026-07-11): 抽 list_files filter builder 到独立 helper.

    把 _list_files_impl 中"组装 filters list + visibility_see_cond + and_(...)"
    的 35 行 (line 418-458) 压缩成单一调用. caller 拿到 (filters, has_folder_filter)
    后只需负责 ORDER BY + LIMIT/OFFSET.

    Returns:
        filters: list[ColumnElement] — 必传 WHERE 子句列表 (不含 ORDER/LIMIT)

    Note:
        include_deleted + deleted_only 互斥 (caller 必须二选一, 这里仅按 caller 传的参数加 filter)

    批次① (2026-09-05) 变化:
    - starred_only: Knowledge.is_starred 全局限列退役 → 子查询 drive_file_stars
      (仅当前成员本人的收藏; alembic 134 回填后创建人视角与原行为兼容)。
    - search: 文件名/标题中缀 ILIKE (pg_trgm 部分索引 ix_knowledge_file_name_trgm 支撑;
      通配符经 _escape_ilike 转义为字面量)。
    """
    filters = [Knowledge.storage_mode == storage_mode]
    if deleted_only:
        filters.append(Knowledge.deleted_at.isnot(None))
    elif not include_deleted:
        filters.append(Knowledge.deleted_at.is_(None))

    # folder filter (v2.21 + v2.22 共享逻辑)
    folder_clause = _build_folder_filter_clause(folder_id, include_subfolders)
    if folder_clause is not None:
        filters.append(folder_clause)

    if visibility_filter:
        filters.append(Knowledge.visibility == visibility_filter)
    if starred_only:
        # 收藏个人化 (134): 本人 star 过的行。IN 子查询与 JOIN 行数等价 (uk 保证)
        filters.append(
            Knowledge.id.in_(
                select(DriveFileStar.file_id).where(
                    DriveFileStar.member_id == current_user_id
                )
            )
        )
    if file_type:
        ext_predicate = DriveService._build_file_type_predicate(file_type)
        if ext_predicate is not None:
            filters.append(ext_predicate)
    if search and search.strip():
        pattern = f"%{_escape_ilike(search.strip())}%"
        filters.append(
            or_(
                Knowledge.file_name.ilike(pattern, escape="\\"),
                Knowledge.title.ilike(pattern, escape="\\"),
            )
        )
    if is_team_shared_filter is not None:
        # 2026-09 单一团队空间: API 层已恒传 None (view 参数只回显不再过滤);
        # 保留代码路径给内部调用方, 迁移 133 回填后所有行 is_team_shared=true, 语义收敛。
        filters.append(Knowledge.is_team_shared == is_team_shared_filter)

    # 核心隐私边界: private 文件仅 owner 可见
    # 2026-09 单一团队空间: create_file 收口点已禁止新 private drive 行 + 迁移 133
    # 把存量翻成 team, 该条件实际恒真 (保留防脏数据兜底)。
    visibility_see_cond = or_(
        Knowledge.created_by == current_user_id,
        Knowledge.visibility != "private",
    )
    filters.append(visibility_see_cond)

    return filters


# 2026-07-12 死代码清理: _to_naive_dt helper 提取到 app.utils.datetime_utils.to_naive_datetime


class DriveServiceError(Exception):
    """业务级错误，调用方映射成 HTTP 4xx"""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message  # 暴露属性, 否则 e.message 报 AttributeError
        self.status_code = status_code


async def _stream_concat_chunks(
    session_id: str, chunk_indices: List[int], dst_object: str
) -> int:
    """顺序下载 chunks → 拼接 → 上传最终 object (PR5 分片完成核心)

    实现: 用 sync file I/O (asyncio.to_thread 包), 顺序写临时文件 + put_object.
    内存峰值 = 1 chunk (默认 5MB), 总文件大小无关.

    备选实现 (未采用):
    - aiofiles 异步文件: 需要 aiofiles 依赖 (本环境未装)
    - python-level join: 内存峰值 = 总文件大小 (10GB 视频会爆 RAM)
    - ffmpeg concat: 需写本地 concat list + 转码 (重, 没必要)
    """
    import tempfile

    def _sync_concat():
        """同步版拼接 (放线程池跑, 不阻塞 event loop)"""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tmp") as tmp:
            tmp_path = tmp.name
        total = 0
        try:
            with open(tmp_path, "wb") as f:
                for idx in chunk_indices:
                    chunk_obj = f"drive-uploads/{session_id}/chunk_{idx:04d}"
                    # file_service.download_file 内部走 minio fget_object (流式)
                    chunk_bytes = file_service.download_file_sync(chunk_obj)
                    if not chunk_bytes:
                        raise DriveServiceError(
                            f"chunk_{idx} 读取为空 (session={session_id})", status_code=500
                        )
                    f.write(chunk_bytes)
                    total += len(chunk_bytes)
            return tmp_path, total
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # 跑线程池
    tmp_path, total_size = await asyncio.to_thread(_sync_concat)
    try:
        # 上传最终 object (file_service.upload_to_path 已是 async)
        with open(tmp_path, "rb") as f:
            content = f.read()
        await file_service.upload_to_path(
            dst_object, content, content_type="application/octet-stream"
        )

        logger.info(
            f"[_stream_concat_chunks] session={session_id} chunks={len(chunk_indices)} "
            f"size={total_size} → {dst_object}"
        )
        return total_size
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


class DriveService:
    """Drive 文件元数据 CRUD"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==========================================================================
    # 可见性校验
    # ==========================================================================

    @staticmethod
    def _validate_visibility_inherits(
        file_visibility: str,
        folder_visibility: Optional[str],
    ) -> None:
        """验证文件 visibility ≤ 所在文件夹 visibility（防止越权暴露）

        文件夹是文件的"上界": 文件 visibility 必须 <= 文件夹 visibility

        例如:
          folder=private → 文件只能是 private (不允许 team/public, 否则其他人能看到)
          folder=team    → 文件可以是 private/team/public (team 文件夹允许任何 visibility)
          folder=public  → 文件只能是 public (公开文件夹不能放私人草稿)

        VISIBILITY_ORDER 排序: private(0) < team(1) < public(2)
        """
        if folder_visibility is None:
            return
        if VISIBILITY_ORDER.get(file_visibility, -1) > VISIBILITY_ORDER.get(folder_visibility, -1):
            raise DriveServiceError(
                f"文件可见性 ({file_visibility}) 高于文件夹可见性 ({folder_visibility})，越权暴露",
                status_code=400,
            )

    @staticmethod
    def _can_see_file(file: Knowledge, current_user_id: int) -> bool:
        """判断当前用户是否能"看到"该 drive 文件（list API 用）

        - owner: 任何 visibility 都能看
        - 其他用户: 仅看 visibility != private
        """
        if file.created_by == current_user_id:
            return True
        return file.visibility != "private"

    # ==========================================================================
    # CRUD
    # ==========================================================================

    async def create_file(
        self,
        *,
        title: str,
        file_path: str,
        file_name: str,
        file_type: str,
        file_size: int,
        owner_id: int,
        storage_mode: str = "drive",
        visibility: str = "team",
        folder_id: Optional[int] = None,
        created_by: Optional[int] = None,
        source_type: Optional[str] = None,
        content: Optional[str] = None,
        file_hash: Optional[str] = None,  # PR4: 秒传 hash
        # v2 PR6-P19: 团队共享盘标识 (前端在 team 视图上传 = true)
        is_team_shared: bool = False,
    ) -> Knowledge:
        """创建 drive 文件元数据 (multipart complete 后调用, 或从前端直接表单上传)

        Args:
            title: 文件标题 (脱敏用户可读)
            file_path: MinIO object_name, 例如 drive/1/.../test.pptx
            file_name: 原始文件名 (用户上传时的名字)
            file_type: 扩展名 (.pptx / .docx / .pdf)
            file_size: 字节 (validation: 不超 MAX_DRIVE_FILE_SIZE_BYTES)
            owner_id: 仓库所有者 (folder owner 或 created_by 备份)
            storage_mode: kb | drive (默认 drive)
            visibility: private | team | public (默认 team)
            folder_id: 关联 folders.id (顶级目录 = None)
            created_by: 创建人 (默认 = owner_id)
            source_type: auto_research 等上游标识, 默认 None
            content: 提取摘要 (默认 None)
            file_hash: 文件 MD5/SHA256 hex hash (PR4 秒传字段, 可选)
            is_team_shared: v2 PR6-P19, True=团队共享盘上传, 不在个人网盘显示
        """
        if storage_mode == "drive":
            assert visibility in ("private", "team", "public"), f"invalid visibility: {visibility}"

        # 2026-09 单一团队空间: drive 文件 private 概念退役 — 本方法是无网盘 upload/
        # create_file 的统一收口点, incoming 'private' 一律强制改写为 'team' (log warning)。
        # 同时 is_team_shared 服务端恒置 True (迁移 133 回填后该字段退役)。
        if storage_mode == "drive":
            if visibility == "private":
                logger.warning(
                    "[DriveService.create_file] visibility='private' 已退役, 强制改写为 "
                    f"'team' (file_name={file_name}, created_by={created_by or owner_id})"
                )
                visibility = "team"
            is_team_shared = True

        # 配额校验
        if file_size > MAX_DRIVE_FILE_SIZE_BYTES:
            raise DriveServiceError(
                f"文件过大 ({file_size} bytes > {MAX_DRIVE_FILE_SIZE_MB}MB)",
                status_code=413,
            )

        # 文件夹存在 + visibility 继承校验
        if folder_id is not None:
            folder = await self.get_folder(folder_id)
            if folder is None:
                raise DriveServiceError(f"文件夹 id={folder_id} 不存在", status_code=400)
            # 2026-09 单一团队空间: 不再校验 folder.owner_id == owner_id (owner 仅溯源)
            self._validate_visibility_inherits(visibility, folder.visibility)

        knowledge = Knowledge(
            title=title,
            content=content or f"[drive upload] {file_name}",
            file_path=file_path,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,           # PR4: 真值 (PR2.7 之前 0)
            file_hash=file_hash,            # PR4: 秒传 hash (可空)
            is_latest=True,                 # PR4: 新文件默认最新
            version_number=1,               # PR4: 默认 v1
            source_type=source_type or "drive",
            created_by=created_by or owner_id,
            storage_mode=storage_mode,
            visibility=visibility,
            folder_id=folder_id,
            is_team_shared=is_team_shared,  # v2 PR6-P19
        )
        self.db.add(knowledge)
        await self.db.commit()
        await self.db.refresh(knowledge)
        # WP2 (2026-09-02): drive 内容索引 — 解析原文→分块→embedding 入
        # knowledge_chunks (异步, 失败可由 backfill_drive_content 补)
        try:
            from app.services.drive_index_service import index_drive_content_task
            index_drive_content_task.delay(knowledge.id)
        except Exception as e:
            logger.warning(f"[wp2] drive 内容索引 dispatch 失败 (id={knowledge.id}): {e}")
        logger.info(
            f"[DriveService.create_file] id={knowledge.id} file_name={file_name} "
            f"visibility={visibility} folder_id={folder_id} "
            f"file_size={file_size} file_hash={'<set>' if file_hash else None}"
        )
        # PR6: 活动动态流 (上传事件) — best-effort 不阻塞
        try:
            await activity_service.log(
                self.db,
                actor_id=created_by or owner_id,
                action="upload",
                target_type="file",
                target_id=knowledge.id,
                target_name=knowledge.file_name,
                metadata={
                    "visibility": visibility,
                    "folder_id": folder_id,
                    "file_size": file_size,
                },
            )
            await self.db.commit()
        except Exception as e:
            logger.debug(f"[DriveService.create_file] activity log 失败 (非阻塞): {e}")

        # v2 网盘 PR6-P12+ 增量: upload owner notification (folder owner != uploader 时通知 owner)
        # 设计: 自通知 skip (owner_id == current_user_id 时不触发, 避免噪音)
        # 未来扩展: "upload to other user's folder" 时自动通知 folder owner
        # best-effort 不阻塞, 失败只 logger.debug
        # 2026-09 单一团队空间: 实际上所有调用方都传 owner_id == created_by (上传者即"owner"),
        # 该分支已 effectively dead (仅保留功能代码, 不删)。
        try:
            owner_id_for_notify = owner_id
            uploader_id = created_by or owner_id
            if owner_id_for_notify != uploader_id:
                # 跨用户上传场景: 通知 file owner (e.g. folder owner != uploader)
                await notification_service.create_mention(
                    self.db,
                    file_id=knowledge.id,
                    mentioned_user_id=owner_id_for_notify,
                    mentioned_by=uploader_id,
                    context="upload",
                )
        except Exception as e:
            logger.debug(f"[DriveService.create_file] notification trigger 失败 (非阻塞): {e}")

        await create_initial_version(
            db=self.db,
            file_id=knowledge.id,
            minio_object_key=file_path,
            size=file_size,
            uploader_id=created_by or owner_id,
        )
        return knowledge

    async def list_files(
        self,
        *,
        current_user_id: int,
        folder_id: Optional[int] = None,
        visibility_filter: Optional[str] = None,
        storage_mode: str = "drive",
        include_deleted: bool = False,
        page: int = 1,
        page_size: int = 50,
        # v2 PR2: 新增 sort + filter 参数 (默认行为向后兼容)
        sort_by: str = "created_at",
        sort_order: str = "desc",
        starred_only: bool = False,
        file_type: Optional[str] = None,
        # v2 PR6-P19: 团队共享盘隔离 (None=不过滤)
        is_team_shared: Optional[bool] = None,
        # v2.21 (2026-07-11): folder_id=None + include_subfolders=True 时
        # 跳过 folder_id IS NULL filter (用于 🌐 团队共享盘顶级 view, 列出
        # 所有 team PPT, 不论 folder_id 是否 NULL). personal view 维持 v2 PR3 行为.
        include_subfolders: bool = False,
        # 批次① B6 (2026-09-05): 文件名/标题中缀搜索 (None/空白 = 不过滤, 行为与老版一致)
        search: Optional[str] = None,
    ) -> Tuple[List[Knowledge], int]:
        """列 drive 文件 (含列表 SQL 越权防御)

        Args:
            current_user_id: 当前用户 (用于 private 文件过滤)
            folder_id: 仅列该文件夹的文件 (None = 顶级)
            visibility_filter: 过滤特定 visibility (None = 不限定)
            storage_mode: 默认 drive (filter out kb)
            include_deleted: True = 含已软删 (admin)
            page, page_size: 分页
            sort_by: 排序字段 (默认 created_at)
            sort_order: asc / desc
            starred_only: 仅当前成员个人收藏 (批次① 134: drive_file_stars 子查询, 老全局 is_starred 列退役)
            file_type: pdf/image/video/office/text
            is_team_shared: v2 PR6-P19, None=不过滤/True=仅 team/False=仅 personal
            include_subfolders: v2.21, True 时跳过 folder_id IS NULL filter (🌐 team view 顶级用)

        Returns:
            (items, total)
        """
        return await self._list_files_impl(
            current_user_id=current_user_id,
            folder_id=folder_id,
            visibility_filter=visibility_filter,
            storage_mode=storage_mode,
            include_deleted=include_deleted,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            starred_only=starred_only,
            file_type=file_type,
            is_team_shared_filter=is_team_shared,
            include_subfolders=include_subfolders,
            search=search,
        )

    async def _list_files_impl(
        self,
        *,
        current_user_id: int,
        folder_id: Optional[int],
        visibility_filter: Optional[str],
        storage_mode: str,
        include_deleted: bool,
        page: int,
        page_size: int,
        sort_by: str,                # created_at | updated_at | file_name | file_size | starred_at
        sort_order: str,             # asc | desc
        starred_only: bool,
        file_type: Optional[str],    # pdf | image | video | office | text | (None=全部)
        deleted_only: bool = False,  # v2 PR2: trash 模式 exclusive filter
        is_team_shared_filter: Optional[bool] = None,  # v2 PR6-P19: None=both, True=仅 team, False=仅 personal
        include_subfolders: bool = False,  # v2.21 (2026-07-11): 见 list_files docstring
        search: Optional[str] = None,  # 批次① B6: 文件名/标题中缀搜索 (见 list_files docstring)
    ) -> Tuple[List[Knowledge], int]:
        """v2 PR2: 拆出 list_files 内部实现, 支持 sort_by / sort_order / starred_only / file_type.

        对外保持向后兼容 (list_files 默认 sort=created_at desc).
        v2 PR2: deleted_only=True 时仅返 deleted_at IS NOT NULL (回收站专用).
        v2 PR6-P19: is_team_shared_filter 隔离个人/团队共享盘 (True/False/None).
        v2.21 (2026-07-11): include_subfolders=True 时跳过 folder_id IS NULL filter
          (团队共享盘顶级 view 列出整个团队空间的 PPT, 含 root + 所有 sub folder).
          personal view 维持 v2 PR3 行为 (folder_id=None → folder_id IS NULL).
        """
        stmt = select(Knowledge)
        count_stmt = select(func.count(Knowledge.id))

        # v2.22 (2026-07-11): 抽 list_files filter builder 到独立 helper
        # 之前 35 行 if/elif + and_(...) 压缩成单一调用, _build_folder_filter_clause
        # 单独覆盖 v2.21 (include_subfolders) + v2.22 (file_type chip 拆分) 共享逻辑
        filters = _build_list_files_query(
            storage_mode=storage_mode,
            folder_id=folder_id,
            include_subfolders=include_subfolders,
            visibility_filter=visibility_filter,
            starred_only=starred_only,
            file_type=file_type,
            is_team_shared_filter=is_team_shared_filter,
            deleted_only=deleted_only,
            include_deleted=include_deleted,
            current_user_id=current_user_id,
            search=search,
        )

        stmt = stmt.where(and_(*filters))
        count_stmt = count_stmt.where(and_(*filters))

        # 排序
        sort_column = self._resolve_sort_column(sort_by)
        if starred_only and sort_by == "starred_at":
            # 批次① 收藏个人化 (134): Knowledge.starred_at 全局限列不再被 toggle 维护,
            # 收藏列表的"最近收藏在前"排序改用**当前成员**在 drive_file_stars 的时间
            # (相关标量子查询; 能通过 starred_only 过滤的行必有本人 star 行, 不会 NULL)
            sort_column = (
                select(DriveFileStar.starred_at)
                .where(
                    DriveFileStar.file_id == Knowledge.id,
                    DriveFileStar.member_id == current_user_id,
                )
                .correlate(Knowledge)
                .scalar_subquery()
            )
        if sort_order == "asc":
            stmt = stmt.order_by(sort_column.asc())
        else:
            stmt = stmt.order_by(sort_column.desc())

        # 分页
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        items_result = await self.db.execute(stmt)
        count_result = await self.db.execute(count_stmt)
        items = list(items_result.scalars().all())
        total = count_result.scalar() or 0

        return items, total

    @staticmethod
    def _resolve_sort_column(sort_by: str):
        """v2 PR2: 把前端 sort_by 字符串映射到 Knowledge 列对象.

        'deleted_at' 是回收站专属, fallback 到 updated_at (回收站里 updated_at 通常是删除时间).
        """
        mapping = {
            "created_at": Knowledge.created_at,
            "updated_at": Knowledge.updated_at,
            "file_name": Knowledge.file_name,
            "file_size": Knowledge.file_size,  # 三栏工作台"大小"列排序 (注释 L644 早已声明支持, 实现漏了)
            "starred_at": Knowledge.starred_at,
            "deleted_at": Knowledge.updated_at,  # 回收站 fallback
        }
        if sort_by not in mapping:
            raise DriveServiceError(f"不支持的排序字段 '{sort_by}'", status_code=400)
        return mapping[sort_by]

    @staticmethod
    def _build_file_type_predicate(file_type: str):
        """v2 PR2: 把文件类型枚举映射到 file_name 后缀 LIKE 条件.

        返回 SQLAlchemy 列表达式 (用于 .where()), 无效类型返 None (不过滤).

        v2.7.1 (2026-07-10) bugfix: 加 'audio' 映射 (前缺导致前端 chip 选了 audio
        返回的是全部文件 — 看上去 '所有 PPT 也是音频' 的错误). 覆盖常见音频:
        .mp3 / .wav / .flac / .aac / .ogg / .m4a / .wma / .opus. 任何未匹配
        的 type 返 None → 不过滤 (前端拿到全部,需前端 chip 自身友好 fallback).

        v2.22 (2026-07-11): 拆分 office → word/ppt/excel (用户决策"Office 分类太粗")
        前端 chip 选项 DesktopDriveView.FILE_TYPE_OPTIONS 同步更新.
        office 留为 alias (含全部 6 扩展名) 用于向后兼容 (老请求 / 第三方脚本).
        """
        type_to_ext = {
            "pdf":   [".pdf"],
            "image": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"],
            "video": [".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv"],
            "audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus"],
            "word":  [".doc", ".docx"],
            "ppt":   [".ppt", ".pptx"],
            "excel": [".xls", ".xlsx"],
            # office 留作 alias, 覆盖全部 Office 扩展名, 老请求 / 旧 chip fallback
            "office": [".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"],
            "text":  [".txt", ".md", ".log", ".csv"],
        }
        exts = type_to_ext.get(file_type.lower())
        if not exts:
            return None
        # 用 OR 串接: file_name ILIKE '%.pdf' OR file_name ILIKE '%.jpg' ...
        from sqlalchemy import or_ as _or
        predicates = [Knowledge.file_name.ilike(f"%{ext}") for ext in exts]
        return _or(*predicates)

    async def get_file(self, file_id: int, current_user_id: int) -> Optional[Knowledge]:
        """获取 drive 文件详情 (含越权防御)

        Returns:
            Knowledge 对象, None = 不存在或无权访问
        """
        stmt = select(Knowledge).where(
            Knowledge.id == file_id,
            Knowledge.deleted_at.is_(None),
        )
        file = (await self.db.execute(stmt)).scalar_one_or_none()
        if file is None:
            return None
        if not self._can_see_file(file, current_user_id):
            return None  # 不是 owner + private → 隐身 (连文件名都不展示)
        return file

    async def update_file(
        self,
        file_id: int,
        current_user_id: int,
        *,
        title: Optional[str] = None,
        file_name: Optional[str] = None,  # PR4.4: 重命名 (修复 PR2.5 漏的字段)
        visibility: Optional[str] = None,
        folder_id: Optional[int] = None,
    ) -> Optional[Knowledge]:
        """更新 drive 文件 (2026-09 单一团队空间: 任何成员可改)

        Returns: 更新后的 Knowledge, None = 文件不存在
        Raises: DriveServiceError 若文件夹 visibility 不兼容
        """
        file = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.deleted_at.is_(None),
            )
        )
        file = file.scalar_one_or_none()
        if file is None:
            return None
        # 2026-09 单一团队空间: 删除 created_by != current_user_id 门禁 (溯源非权限)

        # visibility 上限
        if visibility is not None:
            target_folder_id = folder_id if folder_id is not None else file.folder_id
            if target_folder_id is not None:
                folder = await self.get_folder(target_folder_id)
                if folder is not None:
                    self._validate_visibility_inherits(visibility, folder.visibility)
            file.visibility = visibility

        if title is not None:
            file.title = title

        if file_name is not None:  # PR4.4: 重命名 (修复 PR2.5 漏的字段)
            file.file_name = file_name

        if folder_id is not None and folder_id != file.folder_id:
            # 校验目标文件夹存在 (2026-09 单一团队空间: 不再校验 target folder owner)
            target_folder = await self.get_folder(folder_id)
            if target_folder is None:
                raise DriveServiceError(f"目标文件夹 id={folder_id} 不存在", status_code=400)
            self._validate_visibility_inherits(file.visibility, target_folder.visibility)
            file.folder_id = folder_id

        await self.db.commit()
        await self.db.refresh(file)
        logger.info(
            f"[DriveService.update_file] id={file.id} visibility={file.visibility} "
            f"folder_id={file.folder_id}"
        )
        # PR6: 活动动态流 — best-effort 不阻塞
        try:
            meta = {}
            if title is not None:
                meta["new_title"] = title
            if file_name is not None:
                meta["new_file_name"] = file_name
            if visibility is not None:
                meta["new_visibility"] = visibility
            if folder_id is not None and folder_id != file.folder_id:
                meta["new_folder_id"] = folder_id
            await activity_service.log(
                self.db,
                actor_id=current_user_id,
                action="rename" if (file_name is not None or title is not None) else "move",
                target_type="file",
                target_id=file.id,
                target_name=file.file_name,
                metadata=meta,
            )
            await self.db.commit()
        except Exception as e:
            logger.debug(f"[DriveService.update_file] activity log 失败: {e}")
        return file

    async def soft_delete_file(
        self,
        file_id: int,
        current_user_id: int,
    ) -> bool:
        """软删除 drive 文件 (2026-09 单一团队空间: 任何成员可删)

        设置 deleted_at = NOW(), 30 天后由 Celery beat 物理清除 (W72 B-3)
        Returns: True = 成功, False = 文件不存在
        """
        file = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.deleted_at.is_(None),
            )
        )
        file = file.scalar_one_or_none()
        if file is None:
            return False

        # 快照原目录与物化路径；软删本身仍保留 folder_id，快照用于父目录在
        # 回收期间被移动/物理删除后的确定性恢复与 UI 审计。
        file.original_parent_id = file.folder_id
        if file.folder_id is not None:
            original_folder = await self.get_folder(file.folder_id)
            file.original_path = original_folder.path if original_folder is not None else None
        else:
            file.original_path = "/"
        file.deleted_at = to_naive_datetime(datetime.now(timezone.utc))
        await self.db.commit()
        logger.info(f"[DriveService.soft_delete_file] id={file.id}")
        # PR6: 活动动态流
        try:
            await activity_service.log(
                self.db,
                actor_id=current_user_id,
                action="delete",
                target_type="file",
                target_id=file.id,
                target_name=file.file_name,
            )
            await self.db.commit()
        except Exception as e:
            logger.debug(f"[DriveService.soft_delete_file] activity log 失败: {e}")
        return True

    async def _restore_original_location(self, file: Knowledge) -> None:
        """Restore a trashed file to its snapshotted folder, or safely fall back to root."""
        target_parent_id = file.original_parent_id
        if target_parent_id is not None:
            # 2026-09 单一团队空间修复: 旧实现要求 Folder.owner_id == file.created_by,
            # 跨成员文件恢复时目标 folder 判空 → 静默掉到根目录 (真 bug)。owner 仅溯源,
            # 该谓词删除。
            target = (
                await self.db.execute(
                    select(Folder).where(
                        Folder.id == target_parent_id,
                        Folder.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            file.folder_id = target.id if target is not None else None
        elif file.original_path == "/":
            file.folder_id = None
        elif file.folder_id is not None:
            # Backward compatibility for rows deleted before Alembic 080.
            current_parent = (
                await self.db.execute(
                    select(Folder).where(
                        Folder.id == file.folder_id,
                        Folder.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if current_parent is None:
                file.folder_id = None
        file.original_parent_id = None
        file.original_path = None

    async def restore_file(
        self,
        file_id: int,
        current_user_id: int,
        is_admin: bool = False,
    ) -> Optional[Knowledge]:
        """恢复被软删的 drive 文件 (2026-09 单一团队空间: 任何成员可恢复, 30 天保留期内有效)."""
        file = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.deleted_at.isnot(None),
                Knowledge.storage_mode == "drive",
            )
        )
        file = file.scalar_one_or_none()
        if file is None:
            return None
        await self._restore_original_location(file)
        file.deleted_at = None
        await self.db.commit()
        await self.db.refresh(file)
        logger.info(f"[DriveService.restore_file] id={file.id}")
        # PR6: 活动动态流
        try:
            await activity_service.log(
                self.db,
                actor_id=current_user_id,
                action="restore",
                target_type="file",
                target_id=file.id,
                target_name=file.file_name,
            )
            await self.db.commit()
        except Exception as e:
            logger.debug(f"[DriveService.restore_file] activity log 失败: {e}")
        return file

    # ==========================================================================
    # extract-to-kb 升级 (drive → kb, 触发 LLM 提取)
    # ==========================================================================

    async def extract_to_kb(
        self,
        file_id: int,
        current_user_id: int,
        *,
        target_visibility: str = "team",
    ) -> Optional[Knowledge]:
        """将 drive 文件升级到公共知识库 (PR2 简化版, PR3 加 LLM)

        流程:
          1. 校验 source file 存在 + owner 一致
          2. 校验 visibility 升级合法 (private→team/public)
          3. 改 storage_mode: drive → kb
          4. 改 source_type: drive → drive_extracted
          5. 改 visibility 到 target_visibility
          6. (异步) 触发 file_parser + LLM summary + embedding

        PR2 只先做 storage_mode/visibility 切换 (即时可见性升级)
        异步 LLM 提取留 PR3 与 desktop 触达一并做
        """
        if target_visibility not in ("team", "public"):
            raise DriveServiceError(
                f"extract-to-kb 目标 visibility 必须为 team/public, 不是 {target_visibility}",
                status_code=400,
            )

        file = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.deleted_at.is_(None),
            )
        )
        file = file.scalar_one_or_none()
        if file is None:
            return None

        # visibility 必须升 (private → team/public)
        # team → public 合法
        # 已是 team/public 再"升级"无意义但允许 (幂等)
        # 2026-09 单一团队空间: 删除 created_by owner 门禁 (任何成员可 extract)
        before = file.visibility
        file.visibility = target_visibility
        file.storage_mode = "kb"
        file.source_type = "drive_extracted"
        await self.db.commit()
        await self.db.refresh(file)

        logger.info(
            f"[DriveService.extract_to_kb] id={file.id} storage: drive→kb "
            f"visibility: {before}→{target_visibility}"
        )
        # 异步 LLM 提取留 PR3 再启 (本 PR 只切 storage_mode 让前端能立刻看到)
        return file

    # ==========================================================================
    # Folder 引用 (PR2.2 完整实现, 本服务先 forward 一下供调用方补 commit)
    # ==========================================================================

    async def get_folder(self, folder_id: int) -> Optional[Folder]:
        """获取 folder (含可见性校验)"""
        stmt = select(Folder).where(
            Folder.id == folder_id,
            Folder.deleted_at.is_(None),
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    # ==========================================================================
    # 存储统计 (PR2.5 用)
    # ==========================================================================

    async def storage_stats(self, current_user_id: int) -> dict:
        """当前用户的 drive 存储统计

        PR2.1 仅返 file_count + 按 visibility 分组 (Knowledge 表无 file_size 列,
        总占用需 PR2.5 引入 file_size 列 + 异步遍历 MinIO).
        """
        stmt = select(
            func.count(Knowledge.id).label("file_count"),
        ).where(
            Knowledge.storage_mode == "drive",
            Knowledge.created_by == current_user_id,
            Knowledge.deleted_at.is_(None),
        )

        # PG 没有 file_size 列在 Knowledge (只有 file_type, file_name, file_path)
        # 实际计算文件大小需遍历 MinIO list_objects, PR2.5 引入 metric 列 (count only for now)
        row = (await self.db.execute(stmt)).first()

        # 按 visibility 分组
        by_visibility = await self.db.execute(
            select(Knowledge.visibility, func.count(Knowledge.id))
            .where(
                Knowledge.storage_mode == "drive",
                Knowledge.created_by == current_user_id,
                Knowledge.deleted_at.is_(None),
            )
            .group_by(Knowledge.visibility)
        )
        vis_counts = {row[0]: row[1] for row in by_visibility}

        return {
            "file_count": row.file_count if row else 0,
            "by_visibility": vis_counts,
            "active": True,
        }

    # ==========================================================================
    # PR2.7 分享链接 + 下载计数
    # ==========================================================================

    async def increment_download_count(self, file_id: int) -> int:
        """原子 +1 下载计数, 返回新值"""
        result = await self.db.execute(
            update(Knowledge)
            .where(
                Knowledge.id == file_id,
                Knowledge.storage_mode == "drive",
                Knowledge.deleted_at.is_(None),
            )
            .values(download_count=Knowledge.download_count + 1)
            .returning(Knowledge.download_count)
        )
        row = result.first()
        if row is None:
            return 0
        return row[0]

    async def create_share_link(
        self,
        file_id: int,
        current_user_id: int,
        *,
        expires_in_days: Optional[int] = None,
        expires_hours: Optional[int] = None,
        password: Optional[str] = None,
    ) -> Optional[Knowledge]:
        """生成公开分享 token (2026-09 单一团队空间: 任何成员可分享)

        v2 PR1 升级:
        - expires_hours 新参数 (细粒度, 1-8760)
        - password 新参数 (4-8 位数字, 存 SHA256 hash)
        - 保留 expires_in_days 向后兼容 (None 时优先级低于 expires_hours)

        Args:
            file_id: drive 文件 id
            current_user_id: 当前用户 (操作者溯源, 不再要求 = file.created_by)
            expires_in_days: 保留旧 API, 1-365 (向后兼容)
            expires_hours: 新 API, 1-8760; 0=None=默认 7 天; -1=永久
            password: 4-8 位数字, None = 公开分享
        """
        # 优先 expires_hours (新 API), 退到 expires_in_days (旧 API)
        if expires_hours is not None:
            _validate_share_expires_hours(expires_hours)
            if expires_hours == -1:
                expires_at = None  # 永久
            elif expires_hours == 0:
                expires_at = to_naive_datetime(
                    datetime.now(timezone.utc) + timedelta(hours=DEFAULT_SHARE_EXPIRES_HOURS)
                )
            else:
                expires_at = to_naive_datetime(
                    datetime.now(timezone.utc) + timedelta(hours=expires_hours)
                )
        elif expires_in_days is not None:
            if expires_in_days < 1 or expires_in_days > 365:
                raise DriveServiceError(
                    f"expires_in_days {expires_in_days} 超出范围 [1, 365]",
                    status_code=400,
                )
            expires_at = to_naive_datetime(
                datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            )
        else:
            # 默认 7 天
            expires_at = to_naive_datetime(
                datetime.now(timezone.utc) + timedelta(hours=DEFAULT_SHARE_EXPIRES_HOURS)
            )

        # 提取码校验
        _validate_share_password(password)
        password_hash = _hash_share_password(password) if password else None

        f = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        f = f.scalar_one_or_none()
        if f is None:
            return None
        # 2026-09 单一团队空间: 删除 created_by owner 门禁 (任何成员可生成分享链接)

        # 32 字符 token (44 字符 url-safe base64)
        token = secrets.token_urlsafe(24)[:32]
        f.share_token = token
        f.share_expires_at = expires_at
        f.share_password = password_hash
        # 批次⑩.7: 可见性跟随分享 — 分享即公开, 撤销/过期回团队 (用户 2026-09-05 拍板)
        f.visibility = "public"
        await self.db.commit()
        await self.db.refresh(f)
        logger.info(
            f"[DriveService.create_share_link] id={f.id} token={token[:8]}... "
            f"expires={f.share_expires_at} password={'yes' if password_hash else 'no'}"
        )
        # PR6: 活动动态流 + 文件 owner 自提醒 (通知 owner 分享成功)
        try:
            await activity_service.log(
                self.db,
                actor_id=current_user_id,
                action="share",
                target_type="file",
                target_id=f.id,
                target_name=f.file_name,
                metadata={
                    "expires_at": str(f.share_expires_at),
                    "password_required": bool(password_hash),
                },
            )
            await self.db.commit()
        except Exception as e:
            logger.debug(f"[DriveService.create_share_link] activity log 失败: {e}")

        # v2 网盘 PR6-P12+ 增量: share 触发 notification (context='share')
        # 设计: create_share_link 仅 owner 可调 (line 859 已校验), 所以 share 通知发给 owner 自己
        # 未来 PR3 "team 成员触发分享" 时, 这里会跳过自通知
        try:
            if f.created_by != current_user_id:
                await notification_service.create_mention(
                    self.db,
                    file_id=f.id,
                    mentioned_user_id=f.created_by,
                    mentioned_by=current_user_id,
                    context="share",
                )
        except Exception as e:
            logger.debug(f"[DriveService.create_share_link] notification trigger 失败 (非阻塞): {e}")

        return f

    async def revoke_share_link(
        self,
        file_id: int,
        current_user_id: int,
    ) -> bool:
        """撤销分享链接 (清 token + expires + password) — 2026-09: 任何成员可撤销"""
        f = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        f = f.scalar_one_or_none()
        if f is None:
            return False
        f.share_token = None
        f.share_expires_at = None
        f.share_password = None
        # 批次⑩.7: 撤销分享 → 回团队属性
        f.visibility = "team"
        await self.db.commit()
        return True

    async def get_by_share_token(self, token: str) -> Optional[Knowledge]:
        """通过 token 公开访问 (无 JWT, 用于 /drive/share/{token} 端点)

        注意: 不校验密码 (留给 verify_share_access 调用方), 密码验证必须先 get_by_share_token
        后由调用方主动传 password 走 verify_share_access(token, password).
        """
        if not token:
            return None
        f = await self.db.execute(
            select(Knowledge).where(
                Knowledge.share_token == token,
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        f = f.scalar_one_or_none()
        if f is None:
            return None
        # 校验 expires
        if f.share_expires_at is not None:
            expires_naive = to_naive_datetime(f.share_expires_at)
            now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
            if expires_naive < now_naive:
                logger.info(f"[DriveService.get_by_share_token] token={token[:8]}... 已过期")
                # 批次⑩.7: 过期懒回团队属性
                f.visibility = "team"
                await self.db.commit()
                return None
        return f

    async def verify_share_access(
        self,
        token: str,
        password: Optional[str] = None,
    ) -> Optional[Knowledge]:
        """验证分享链接访问权限 (含密码校验).

        Returns:
            - None: token 不存在 / 已过期 / 密码错误
            - Knowledge: 通过验证的文件对象

        行为:
        1. 调 get_by_share_token 校验 token 存在 + 未过期
        2. share_password is NULL (公开分享) → 直接返回 file
        3. share_password 非 NULL → 必须 password 正确 (SHA256 hash 一致) 才能返回
        """
        f = await self.get_by_share_token(token)
        if f is None:
            return None
        # 公开分享 / password_hash 未设 → 直接通过
        if not f.share_password:
            return f
        # 有密码: 必须提供且 hash 一致
        if password is None:
            return None
        password_hash = _hash_share_password(password)
        if password_hash != f.share_password:
            logger.info(f"[DriveService.verify_share_access] token={token[:8]}... 密码错误")
            return None
        return f

    # ==========================================================================
    # v2 PR1 visibility edit (桌面 stub 修复)
    # ==========================================================================

    async def update_visibility(
        self,
        file_id: int,
        current_user_id: int,
        new_visibility: str,
    ) -> Optional[Knowledge]:
        """修改 drive 文件可见性 (owner only).

        校验:
        1. visibility 必须在 {private, team, public} 三选一
        2. 必须 <= 所在文件夹 visibility (硬上限, plan 决策)
        3. 文件已 owner 才能改

        Returns: 更新后的 Knowledge 或 None (越权/不存在).
        """
        if new_visibility not in ("private", "team", "public"):
            raise DriveServiceError(
                f"非法 visibility '{new_visibility}', 必须是 private/team/public",
                status_code=400,
            )

        f = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        f = f.scalar_one_or_none()
        if f is None:
            return None
        # 2026-09 单一团队空间: 删除 created_by owner 门禁 (任何成员可改 visibility)

        # visibility 上限 (private 不能往公开升级除非 folder 允许)
        if f.folder_id is not None:
            folder = await self.get_folder(f.folder_id)
            if folder is not None:
                self._validate_visibility_inherits(new_visibility, folder.visibility)

        before = f.visibility
        f.visibility = new_visibility

        # 注意: 文件夹 owner 改 visibility 后, share_token 可不撤销 (原 token 仅受 expires 控制)
        # owner 主动 revoke 才清 token. 维持现行策略.

        await self.db.commit()
        await self.db.refresh(f)
        logger.info(
            f"[DriveService.update_visibility] id={f.id} {before}→{new_visibility} "
            f"folder={f.folder_id}"
        )
        return f

    # ============================================================
    # v2 PR2 收藏 / 回收站 / 批量操作
    # ============================================================

    async def toggle_star_file(
        self, file_id: int, current_user_id: int
    ) -> Optional[Tuple[Knowledge, bool, Optional[datetime]]]:
        """切换文件收藏状态 — 批次① 收藏个人化 (alembic 134, 2026-09-05).

        旧实现写 Knowledge.is_starred 全局限列 (任何人 star 对全员生效, 是 bug 而非
        特性); 现在对 drive_file_stars (file_id × member_id) 增删, **仅影响当前成员
        自己的收藏夹**。Knowledge.is_starred / starred_at 两列退役为只读 legacy,
        本方法不再写它们。

        Returns:
            None = 文件不存在 (或非 drive 行)
            (Knowledge, starred_now, starred_at_now) — starred_now 是**当前成员视角**

        保留 PR6-P12+ 通知逻辑: star 时通知 created_by (跳过自通知), unstar 不通知。
        """
        f = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id == file_id,
                Knowledge.storage_mode == "drive",
            )
        )
        f = f.scalar_one_or_none()
        if f is None:
            return None
        existing = (await self.db.execute(
            select(DriveFileStar).where(
                DriveFileStar.file_id == f.id,
                DriveFileStar.member_id == current_user_id,
            )
        )).scalar_one_or_none()
        starred_now: bool
        starred_at_now: Optional[datetime]
        if existing is not None:
            await self.db.delete(existing)
            starred_now = False
            starred_at_now = None
            action = "unstar"
        else:
            starred_at_now = to_naive_datetime(datetime.now(timezone.utc))
            self.db.add(DriveFileStar(
                file_id=f.id,
                member_id=current_user_id,
                starred_at=starred_at_now,
            ))
            starred_now = True
            action = "star"
        await self.db.commit()
        logger.info(f"[DriveService.toggle_star_file] id={f.id} user={current_user_id} {action}")

        # v2 网盘 PR6-P12+ 增量: star 通知 file owner (只有 star 时通知, unstar 不通知)
        # 设计: 单一团队空间下任何成员可 star 他人文件 → 非本人文件收藏时提醒创建人
        # (通知失败非阻塞, try/except 兜底)。
        if action == "star":
            try:
                if f.created_by != current_user_id:
                    await notification_service.create_mention(
                        self.db,
                        file_id=f.id,
                        mentioned_user_id=f.created_by,
                        mentioned_by=current_user_id,
                        context="star",
                    )
            except Exception as e:
                logger.debug(f"[DriveService.toggle_star_file] notification trigger 失败 (非阻塞): {e}")

        return f, starred_now, starred_at_now

    async def get_starred_ids(
        self, file_ids: List[int], current_user_id: int
    ) -> set:
        """批次①: 批量反查"当前成员收藏过"的文件 id 集合 (列表端点 attach per-user is_starred 用).

        单次 SELECT, 防 N+1 (同 _to_item owner_lookup 范式)。空输入直接返空集不查库。
        """
        if not file_ids:
            return set()
        stmt = select(DriveFileStar.file_id).where(
            DriveFileStar.member_id == current_user_id,
            DriveFileStar.file_id.in_(file_ids),
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return set(rows)

    async def batch_star_files(
        self,
        file_ids: List[int],
        current_user_id: int,
        *,
        starred: bool,
    ) -> int:
        """批次①: 批量收藏/取消收藏 (POST /drive/files/batch-star, 对当前成员视角, 幂等).

        - starred=True: INSERT...ON CONFLICT DO NOTHING (重复调不产生重复行, 不报错)
        - starred=False: DELETE...WHERE file_id IN AND member_id=me (未收藏的 id 删 0 行, 同样幂等)
        - 仅 storage_mode='drive' 的行有效; kb 行/不存在 id 静默跳过 (批量操作不做逐个 404)。

        Returns: updated = 命中目标状态的本人在册 drive 文件数 (幂等语义: 重复调用返回同值)
        """
        if not file_ids:
            return 0
        stmt = select(Knowledge.id).where(
            Knowledge.id.in_(file_ids),
            Knowledge.storage_mode == "drive",
        )
        valid_ids = list((await self.db.execute(stmt)).scalars().all())
        if not valid_ids:
            return 0
        if starred:
            now = to_naive_datetime(datetime.now(timezone.utc))
            ins = pg_insert(DriveFileStar).values([
                {"file_id": vid, "member_id": current_user_id, "starred_at": now}
                for vid in valid_ids
            ]).on_conflict_do_nothing(index_elements=["file_id", "member_id"])
            await self.db.execute(ins)
        else:
            await self.db.execute(
                delete(DriveFileStar).where(
                    DriveFileStar.file_id.in_(valid_ids),
                    DriveFileStar.member_id == current_user_id,
                )
            )
        await self.db.commit()
        logger.info(
            f"[DriveService.batch_star_files] user={current_user_id} "
            f"requested={len(file_ids)} updated={len(valid_ids)} starred={starred}"
        )
        return len(valid_ids)

    async def list_trash(
        self,
        *,
        current_user_id: int,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "deleted_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Knowledge], int]:
        """v2 PR2: 列回收站文件 (软删的 drive 文件).

        2026-09 单一团队空间: 全组共享垃圾桶 — 实际实现从未按 created_by 过滤,
        只有 visibility_see_cond (存量 private 由迁移 133 翻 team 后全员可见)。
        - deleted_at 必然非空
        - 排序默认 deleted_at desc (最近删除在前)
        - 注意: 这里**不**走 _list_files_impl 的 folder 语义 (回收站跨 folder 看)
        """
        return await self._list_files_impl(
            current_user_id=current_user_id,
            folder_id=None,            # 回收站跨 folder 看
            visibility_filter=None,    # 回收站混合
            storage_mode="drive",
            include_deleted=False,     # 用 deleted_only 替代 (exclusive filter)
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            starred_only=False,
            file_type=None,
            deleted_only=True,         # v2 PR2 fix: 仅 deleted_at IS NOT NULL
        )

    async def list_starred(
        self,
        *,
        current_user_id: int,
        page: int = 1,
        page_size: int = 50,
        sort_by: str = "starred_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Knowledge], int]:
        """v2 PR2 + 批次① 收藏个人化: 列**当前成员**的个人收藏文件.

        - 过滤 = drive_file_stars 含本人 star 行的文件 (134 起 per-user;
          旧 docstring 写"owner 隔离"但实现实为全局限 is_starred, N2 一并修正)
        - sort_by 默认 starred_at desc = 本人收藏动作时间 (相关子查询排序)
        """
        return await self._list_files_impl(
            current_user_id=current_user_id,
            folder_id=None,
            visibility_filter=None,
            storage_mode="drive",
            include_deleted=False,
            page=page,
            page_size=page_size,
            sort_by=sort_by,
            sort_order=sort_order,
            starred_only=True,         # ⭐ 关键
            file_type=None,
        )

    async def batch_soft_delete(
        self,
        file_ids: List[int],
        current_user_id: int,
    ) -> Tuple[int, List[int]]:
        """v2 PR2: 批量软删 (2026-09 单一团队空间: 任何成员可批量删, 不存在/已删的 id 入 skipped).

        Returns: (deleted_count, skipped_ids)
        """
        if not file_ids:
            return 0, []
        result = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id.in_(file_ids),
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        files = list(result.scalars().all())
        now = to_naive_datetime(datetime.now(timezone.utc))
        skipped = []
        deleted = 0
        for f in files:
            # 2026-09 单一团队空间: 删除 created_by owner skip
            f.original_parent_id = f.folder_id
            if f.folder_id is None:
                f.original_path = "/"
            else:
                original_folder = await self.get_folder(f.folder_id)
                f.original_path = original_folder.path if original_folder is not None else None
            f.deleted_at = now
            deleted += 1
        # 不在 file_ids 里的也入 skipped (前端提示 "id=X 不存在")
        existing_ids = {f.id for f in files}
        for fid in file_ids:
            if fid not in existing_ids:
                skipped.append(fid)
        await self.db.commit()
        # PR6: 活动动态流 (批量删除 = 每个被删文件一条 delete event)
        try:
            for f in files:
                if f.deleted_at is not None and f.id not in skipped:
                    await activity_service.log(
                        self.db,
                        actor_id=current_user_id,
                        action="delete",
                        target_type="file",
                        target_id=f.id,
                        target_name=f.file_name,
                    )
            await self.db.commit()
        except Exception as e:
            logger.debug(f"[DriveService.batch_soft_delete] activity log 失败: {e}")
        logger.info(
            f"[DriveService.batch_soft_delete] requested={len(file_ids)} "
            f"deleted={deleted} skipped={len(skipped)}"
        )
        return deleted, skipped

    async def batch_restore(
        self,
        file_ids: List[int],
        current_user_id: int,
        is_admin: bool = False,
    ) -> Tuple[int, List[int]]:
        """v2 PR2/W72 B-3: 批量恢复到原路径 (2026-09 单一团队空间: 任何成员可批量恢复).

        - 不在 trash 的 (deleted_at IS NULL) 也入 skipped
        Returns: (restored_count, skipped_ids)
        """
        if not file_ids:
            return 0, []
        result = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id.in_(file_ids),
                Knowledge.deleted_at.isnot(None),  # 必须真在 trash
                Knowledge.storage_mode == "drive",
            )
        )
        files = list(result.scalars().all())
        skipped = []
        restored = 0
        for f in files:
            # 2026-09 单一团队空间: 删除 created_by/is_admin owner skip
            await self._restore_original_location(f)
            f.deleted_at = None
            restored += 1
        existing_ids = {f.id for f in files}
        for fid in file_ids:
            if fid not in existing_ids:
                skipped.append(fid)
        await self.db.commit()
        logger.info(
            f"[DriveService.batch_restore] requested={len(file_ids)} "
            f"restored={restored} skipped={len(skipped)}"
        )
        return restored, skipped

    async def batch_move(
        self,
        file_ids: List[int],
        target_folder_id: Optional[int],
        current_user_id: int,
    ) -> Tuple[int, List[int]]:
        """v2 PR2: 批量移动到 folder (target_folder_id=None = 顶级).

        2026-09 单一团队空间: 任何成员可移动任意文件 (owner 仅溯源)。
        - target_folder 必须存在 (不校验 owner)
        - 移动时 file.visibility 不得超过 folder.visibility (继承规则)
        Returns: (moved_count, skipped_ids)
        """
        if not file_ids:
            return 0, []
        # 校验 target folder
        target_folder = None
        if target_folder_id is not None:
            target_folder = await self.get_folder(target_folder_id)
            if target_folder is None:
                raise DriveServiceError(
                    f"目标文件夹 id={target_folder_id} 不存在",
                    status_code=404,
                )
            # 2026-09 单一团队空间: 删除 target_folder.owner_id == current_user_id 403
        result = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id.in_(file_ids),
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        files = list(result.scalars().all())
        skipped = []
        moved = 0
        for f in files:
            # 2026-09 单一团队空间: 删除 created_by owner skip
            if target_folder is not None:
                self._validate_visibility_inherits(f.visibility, target_folder.visibility)
            f.folder_id = target_folder_id
            moved += 1
        existing_ids = {f.id for f in files}
        for fid in file_ids:
            if fid not in existing_ids:
                skipped.append(fid)
        await self.db.commit()
        logger.info(
            f"[DriveService.batch_move] requested={len(file_ids)} "
            f"moved={moved} skipped={len(skipped)} target={target_folder_id}"
        )
        return moved, skipped

    async def batch_update_visibility(
        self,
        file_ids: List[int],
        new_visibility: str,
        current_user_id: int,
    ) -> Tuple[int, List[int]]:
        """v2 PR2: 批量改可见性 (team | public).

        2026-09 单一团队空间: 任何成员可改 (owner 仅溯源)。
        - 越权 (folder 上限) 的文件入 skipped (不抛错, 让用户知道哪些被跳过)
        Returns: (updated_count, skipped_ids)
        """
        if new_visibility not in ("private", "team", "public"):
            raise DriveServiceError(
                f"非法 visibility '{new_visibility}'",
                status_code=400,
            )
        if not file_ids:
            return 0, []
        result = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id.in_(file_ids),
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "drive",
            )
        )
        files = list(result.scalars().all())
        skipped = []
        updated = 0
        for f in files:
            # 2026-09 单一团队空间: 删除 created_by owner skip
            if f.folder_id is not None:
                folder = await self.get_folder(f.folder_id)
                if folder is not None:
                    try:
                        self._validate_visibility_inherits(new_visibility, folder.visibility)
                    except DriveServiceError:
                        skipped.append(f.id)
                        continue
            f.visibility = new_visibility
            updated += 1
        existing_ids = {f.id for f in files}
        for fid in file_ids:
            if fid not in existing_ids:
                skipped.append(fid)
        await self.db.commit()
        logger.info(
            f"[DriveService.batch_update_visibility] requested={len(file_ids)} "
            f"updated={updated} skipped={len(skipped)} vis={new_visibility}"
        )
        return updated, skipped

    async def permanent_delete(
        self,
        file_id: int,
        current_user_id: int,
        is_admin: bool = False,
    ) -> bool:
        """v2 PR2/W72 B-3: 物理删除 (2026-09 单一团队空间: 任何成员可永久删).

        Returns: True=成功, False=不存在 (或未软删/非 drive 行).
        """
        f = await self.db.execute(
            select(Knowledge).where(Knowledge.id == file_id)
        )
        f = f.scalar_one_or_none()
        if (
            f is None
            or f.deleted_at is None
            or f.storage_mode != "drive"
        ):
            # 2026-09: created_by/is_admin owner 门禁已删, current_user_id 参数保留兼容签名
            return False
        # 批次① B2: 旧实现只删 f.file_path 当前对象, PR9 历史版本对象泄漏。
        # collect 必须在 db.delete 前 (FK CASCADE 一删主行, 版本行即消失查不到 key);
        # purge 在 commit 后 (MinIO 失败不回滚 DB 硬删)。
        object_keys = await collect_object_keys(self.db, [f])
        await self.db.delete(f)
        await self.db.commit()
        failures = purge_minio_keys(object_keys)
        if failures:
            logger.warning(
                f"[DriveService.permanent_delete] MinIO 清理失败 {failures}/{len(object_keys)} "
                f"key id={f.id} (DB 行已删, 对象留待孤儿巡检)"
            )
        logger.info(f"[DriveService.permanent_delete] id={f.id} objects_purged={len(object_keys)}")
        return True

    async def permanent_delete_batch(
        self,
        file_ids: List[int],
        current_user_id: int,
        is_admin: bool = False,
    ) -> Tuple[int, List[int]]:
        """v2 PR2/W72 B-3: 批量永久删除 (2026-09 单一团队空间: 任何成员可批量永久删).

        Returns: (deleted_count, skipped_ids)
        """
        if not file_ids:
            return 0, []
        result = await self.db.execute(
            select(Knowledge).where(
                Knowledge.id.in_(file_ids),
                Knowledge.deleted_at.isnot(None),  # 必须真在 trash
                Knowledge.storage_mode == "drive",
            )
        )
        files = list(result.scalars().all())
        # 批次① B2: 与 permanent_delete 同款 — 全部 key 在任何 db.delete 前收集
        # (版本行随主行 CASCADE 消失), MinIO 清理工统一挪到 commit 后。
        object_keys = await collect_object_keys(self.db, files)
        skipped = []
        deleted = 0
        for f in files:
            # 2026-09 单一团队空间: 删除 created_by/is_admin owner skip
            await self.db.delete(f)
            deleted += 1
        existing_ids = {f.id for f in files}
        for fid in file_ids:
            if fid not in existing_ids:
                skipped.append(fid)
        await self.db.commit()
        failures = purge_minio_keys(object_keys)
        if failures:
            logger.warning(
                f"[DriveService.permanent_delete_batch] MinIO 清理失败 {failures}/{len(object_keys)} "
                f"key (DB 行已删, 对象留待孤儿巡检)"
            )
        logger.info(
            f"[DriveService.permanent_delete_batch] requested={len(file_ids)} "
            f"deleted={deleted} skipped={len(skipped)} objects_purged={len(object_keys)}"
        )
        return deleted, skipped

    # ============================================================
    # v2 PR4: 文件秒传 (hash) + 版本历史
    # ============================================================

    async def hash_lookup(
        self,
        *,
        file_hash: str,
        current_user_id: int,
    ) -> Optional[Knowledge]:
        """按 hash 查同 owner 的活跃 drive 文件 (秒查 dedup)

        匹配规则:
        - file_hash 严格相等
        - storage_mode='drive' (KB 不参与秒传)
        - deleted_at IS NULL (软删不算)
        - is_latest=True (历史版本不参与秒查, 避免误命中)

        Returns:
            命中的 Knowledge 行, 没命中返 None
        """
        stmt = (
            select(Knowledge)
            .where(
                Knowledge.file_hash == file_hash,
                Knowledge.storage_mode == "drive",
                Knowledge.deleted_at.is_(None),
                Knowledge.is_latest.is_(True),
            )
            .order_by(Knowledge.created_at.desc())
            .limit(1)
        )
        res = await self.db.execute(stmt)
        row = res.scalar_one_or_none()
        if row and self._can_see_file(row, current_user_id):
            return row
        return None

    async def create_instant_upload(
        self,
        *,
        file_hash: str,
        file_name: str,
        file_size: int,
        owner_id: int,
        folder_id: Optional[int] = None,
        visibility: str = "team",
        created_by: Optional[int] = None,
        # v2 PR6-P19: 团队共享盘标识 (前端在 team 视图上传 = true)
        is_team_shared: bool = False,
    ) -> Tuple[Optional[Knowledge], int]:
        """秒传 dedup: hash 命中 → MinIO copy_object 零带宽秒传

        PR4 设计:
        1. hash_lookup 查同 hash 文件 (用户可见)
        2. 命中 → file_service.copy_object_async 在 MinIO 内复制, 不经过本机
        3. 新 Knowledge 行 file_path 是新路径, 但 file_hash/file_size 一致
        4. dedup_saved_bytes = 复制的字节数 (告诉前端"省了 X MB")

        v2 PR6-P19: is_team_shared 标记上传来源视图, 决定 list_drive_files 过滤.

        Returns:
            (knowledge_or_none, dedup_saved_bytes)
            - 命中: (Knowledge行, 复制字节数)
            - 未命中: (None, 0) → 前端走 multipart 上传
        """
        existing = await self.hash_lookup(
            file_hash=file_hash, current_user_id=owner_id,
        )
        if existing is None:
            return None, 0

        # MinIO 服务端 copy_object 零带宽秒传
        ext = ""
        if "." in file_name:
            ext = "." + file_name.rsplit(".", 1)[-1].lower()
        new_object = (
            f"uploads/drive/{owner_id}/"
            f"{secrets.token_hex(8)}_{file_hash[:12]}_{int(datetime.now(timezone.utc).timestamp())}"
            f"{ext}"
        )
        copied_size = await file_service.copy_object_async(
            existing.file_path, new_object,
        )

        # 文件夹校验 (复用 create_file 的逻辑)
        if folder_id is not None:
            folder = await self.get_folder(folder_id)
            if folder is None:
                raise DriveServiceError(
                    f"文件夹 id={folder_id} 不存在", status_code=400,
                )
            # 2026-09 单一团队空间: 不再校验 folder.owner_id == owner_id (owner 仅溯源)
            self._validate_visibility_inherits(visibility, folder.visibility)

        # 2026-09 单一团队空间: 与 create_file 同款收口 — private 退役强制 team,
        # is_team_shared 服务端恒 True (秒传行也是 drive 文件)
        if visibility == "private":
            logger.warning(
                "[DriveService.create_instant_upload] visibility='private' 已退役, "
                f"强制改写为 'team' (file_name={file_name})"
            )
            visibility = "team"
        is_team_shared = True

        # 新行 + 复用同 hash
        new_k = Knowledge(
            title=file_name,
            content=f"[drive instant-upload] {file_name}",
            file_path=new_object,
            file_name=file_name,
            file_type=ext.lstrip(".") if ext else existing.file_type,
            file_size=copied_size,
            file_hash=file_hash,
            is_latest=True,
            version_number=1,            # 秒传是新文件, 不是新版本
            parent_version_id=None,
            source_type="drive",
            created_by=created_by or owner_id,  # Knowledge 模型无 owner_id, 用 created_by
            storage_mode="drive",
            visibility=visibility,
            folder_id=folder_id,
            is_team_shared=is_team_shared,  # v2 PR6-P19
        )
        self.db.add(new_k)
        await self.db.commit()
        await self.db.refresh(new_k)
        logger.info(
            f"[DriveService.create_instant_upload] HIT hash={file_hash[:12]}... "
            f"src_id={existing.id} dst_id={new_k.id} "
            f"src_path={existing.file_path} dst_path={new_object} "
            f"dedup_saved_bytes={copied_size}"
        )
        await create_initial_version(
            db=self.db,
            file_id=new_k.id,
            minio_object_key=new_object,
            size=copied_size,
            uploader_id=created_by or owner_id,
        )
        return new_k, copied_size

    async def create_version(
        self,
        *,
        file_id: int,
        new_hash: str,
        new_size: int,
        new_object_name: str,
        new_filename: str,
        change_note: Optional[str],
        uploader_id: int,
    ) -> Knowledge:
        """创建新版本: 旧 is_latest=False, 新行 version_number+=1, parent_version_id=旧.id

        调用方 (前端 multipart upload 走完后) 负责:
        - 把新文件 bytes 通过 file_service.upload_to_path 写到 new_object_name
        - 然后调本方法写 metadata

        Returns:
            新 Knowledge 行 (is_latest=True)
        """
        cur = await self.db.get(Knowledge, file_id)
        if cur is None:
            raise DriveServiceError(
                f"文件 id={file_id} 不存在", status_code=404,
            )
        if cur.is_latest is False:
            raise DriveServiceError(
                f"文件 id={file_id} 已是历史版本, 无法再创建新版本", status_code=400,
            )

        # 旧行翻 is_latest=False (保留作为历史链)
        cur.is_latest = False
        cur.parent_version_id = cur.parent_version_id  # 不动, 保持原链

        # 新行
        new_version_number = (cur.version_number or 1) + 1
        new_k = Knowledge(
            title=cur.title,
            content=cur.content,
            file_path=new_object_name,
            file_name=new_filename,
            file_type=cur.file_type,
            file_size=new_size,
            file_hash=new_hash,
            is_latest=True,
            version_number=new_version_number,
            parent_version_id=cur.id,
            source_type=cur.source_type,
            created_by=uploader_id,
            storage_mode="drive",
            visibility=cur.visibility,
            folder_id=cur.folder_id,
            # BUG FIX (2026-09 单一团队空间): 原 owner_id=cur.owner_id — Knowledge 模型
            # 无 owner_id 列, 读取 AttributeError + 构造 TypeError, 该行直接删除
            # (溯源字段用 created_by=uploader_id, 上方已设)
        )
        self.db.add(new_k)
        await self.db.flush()  # 拿 new_k.id

        # 写知识版明细 (一行 = 一次版本)
        kv = KnowledgeVersion(
            file_id=new_k.id,
            version_number=new_version_number,
            file_hash=new_hash,
            file_size=new_size,
            uploaded_by=uploader_id,
            change_note=change_note,
        )
        self.db.add(kv)
        await self.db.commit()
        await self.db.refresh(new_k)
        logger.info(
            f"[DriveService.create_version] file_id={file_id} → v{new_version_number} "
            f"new_id={new_k.id} hash={new_hash[:12]}... "
            f"change_note={change_note!r}"
        )
        return new_k

    async def list_versions(
        self,
        *,
        file_id: int,
        current_user_id: int,
    ) -> List[dict]:
        """列文件版本历史 (含每版 hash + 上传者 + 时间)

        返回字段:
        - id: knowledge_versions.id (版本明细行 id)
        - file_id: knowledge.id (新版时 = 新行 id, 旧版时 = 老行 id)
        - version_number
        - file_hash
        - file_size
        - uploaded_by + uploaded_by_name (LEFT JOIN members)
        - change_note
        - created_at (ISO format)
        - is_current: 是否当前最新版本
        """
        cur = await self.db.get(Knowledge, file_id)
        if cur is None:
            raise DriveServiceError(
                f"文件 id={file_id} 不存在", status_code=404,
            )
        if not self._can_see_file(cur, current_user_id):
            raise DriveServiceError(
                f"无权查看文件 id={file_id} 的版本", status_code=403,
            )

        # 联合查询: knowledge_versions JOIN members + 当前 knowledge 行作为"current"
        # 简化: 单独查两张表
        from app.models.member import Member

        stmt = (
            select(KnowledgeVersion, Member.name)
            .outerjoin(Member, KnowledgeVersion.uploaded_by == Member.id)
            .where(KnowledgeVersion.file_id == file_id)
            .order_by(KnowledgeVersion.version_number.desc())
        )
        res = await self.db.execute(stmt)
        rows = res.all()

        result = []
        for kv, member_name in rows:
            result.append({
                "id": kv.id,
                "file_id": kv.file_id,
                "version_number": kv.version_number,
                "file_hash": kv.file_hash,
                "file_size": kv.file_size,
                "uploaded_by": kv.uploaded_by,
                "uploaded_by_name": member_name,
                "change_note": kv.change_note,
                "created_at": kv.created_at.isoformat() if kv.created_at else None,
                "is_current": (kv.file_id == file_id and (cur.is_latest and kv.version_number == cur.version_number)),
            })
        return result

    async def restore_version(
        self,
        *,
        file_id: int,
        version_id: int,
        uploader_id: int,
        change_note: Optional[str] = None,
    ) -> Knowledge:
        """恢复历史版本: 从旧 object_name copy_object 到新路径, 创建新行 v{cur.version+1}

        流程 (与 create_version 类似, 只是数据源是历史版本的 object_name):
        1. 拿 version 明细 → 拿到历史 file_hash + file_size
        2. cur.is_latest=False
        3. 新行: file_path = 新 object_name (从历史 object copy_object 过来)
        4. 写知识版明细

        Returns:
            新 Knowledge 行 (is_latest=True, 与被恢复的 v1 内容字节级一致)
        """
        cur = await self.db.get(Knowledge, file_id)
        if cur is None:
            raise DriveServiceError(
                f"文件 id={file_id} 不存在", status_code=404,
            )
        if cur.is_latest is False:
            raise DriveServiceError(
                f"文件 id={file_id} 已是历史版本, 无法再恢复", status_code=400,
            )

        kv = await self.db.get(KnowledgeVersion, version_id)
        if kv is None:
            raise DriveServiceError(
                f"版本 id={version_id} 不存在", status_code=404,
            )
        if kv.file_id != file_id:
            raise DriveServiceError(
                f"版本 id={version_id} 不属于文件 id={file_id}", status_code=400,
            )

        # 拿历史行的 file_path (knowledge 行 file_path 即 MinIO object_name)
        old_k = await self.db.get(Knowledge, kv.file_id)
        old_object = old_k.file_path if old_k else None
        if not old_object:
            raise DriveServiceError(
                f"历史版本 id={kv.file_id} 缺 MinIO object 引用", status_code=500,
            )

        # 校验源 object 还在 (防止被误删)
        exists = await file_service.object_exists(old_object)
        if not exists:
            raise DriveServiceError(
                f"历史版本 MinIO object 不存在: {old_object}", status_code=410,
            )

        # copy_object 反向
        new_version_number = (cur.version_number or 1) + 1
        ext = ""
        if old_k.file_name and "." in old_k.file_name:
            ext = "." + old_k.file_name.rsplit(".", 1)[-1].lower()
        new_object = (
            f"uploads/drive/{cur.created_by}/"
            f"v{new_version_number}_{kv.file_hash[:12]}_{int(datetime.now(timezone.utc).timestamp())}"
            f"{ext}"
        )
        copied_size = await file_service.copy_object_async(old_object, new_object)

        # 旧行翻 is_latest=False
        cur.is_latest = False

        # 新行
        new_k = Knowledge(
            title=cur.title,
            content=cur.content,
            file_path=new_object,
            file_name=old_k.file_name,
            file_type=old_k.file_type,
            file_size=copied_size,
            file_hash=kv.file_hash,        # 与历史版字节级一致
            is_latest=True,
            version_number=new_version_number,
            parent_version_id=cur.id,
            source_type=cur.source_type,
            created_by=uploader_id,
            storage_mode="drive",
            visibility=cur.visibility,
            folder_id=cur.folder_id,
            # BUG FIX (2026-09 单一团队空间): 原 owner_id=cur.owner_id — 同 create_version,
            # Knowledge 无 owner_id 列, 删除 (溯源走 created_by=uploader_id)
        )
        self.db.add(new_k)
        await self.db.flush()

        # 写知识版明细 (恢复也算一个版本)
        kv_new = KnowledgeVersion(
            file_id=new_k.id,
            version_number=new_version_number,
            file_hash=kv.file_hash,
            file_size=copied_size,
            uploaded_by=uploader_id,
            change_note=change_note or f"restored from v{kv.version_number}",
        )
        self.db.add(kv_new)
        await self.db.commit()
        await self.db.refresh(new_k)
        logger.info(
            f"[DriveService.restore_version] file_id={file_id} "
            f"restored_from_v{kv.version_number} → new_v{new_version_number} "
            f"new_id={new_k.id} copy_bytes={copied_size}"
        )
        # PR6: 活动动态流
        try:
            await activity_service.log(
                self.db,
                actor_id=uploader_id,
                action="version_restore",
                target_type="file",
                target_id=new_k.id,
                target_name=new_k.file_name,
                metadata={
                    "restored_from_version": kv.version_number,
                    "new_version": new_version_number,
                },
            )
            await self.db.commit()
        except Exception as e:
            logger.debug(f"[DriveService.restore_version] activity log 失败: {e}")
        return new_k

    # ========================================================================
    # v2 PR5: 配额检查 + 分片上传 + 缩略图 (2026-07-01)
    # ========================================================================

    async def check_quota(
        self, user_id: int, additional_bytes: int
    ) -> Tuple[bool, int, int]:
        """配额检查 (上传前调用)

        Args:
            user_id: Member.id
            additional_bytes: 待上传字节数

        Returns:
            (allowed, used_after, quota_total)
            - allowed=True: 可上传 (剩余配额足够)
            - allowed=False: 配额不足 (返回 used_after=当前值, 调用方返 413)

        简化策略:
        - 单 user 维度 (不按 file_type 分层)
        - 不预扣配额 (上传过程中可能失败, 失败不扣)
        - 上传成功后才 recalc (storage_tasks.recalc_user_storage_task fire-and-forget)
        """
        user = (await self.db.execute(
            select(Member).where(Member.id == user_id)
        )).scalar_one_or_none()
        if not user:
            return False, 0, 0
        # 用户可主动调 storage-stats API 刷新, 这里读快照
        used = user.drive_used_bytes or 0
        quota = user.drive_quota_bytes or 10737418240
        if used + additional_bytes > quota:
            return False, used, quota
        return True, used + additional_bytes, quota

    async def get_storage_quota(self, user_id: int) -> dict:
        """获取用户配额详情 (含百分比, 用于 UI badge)

        返回:
            {
                user_id: int,
                used_bytes: int,
                quota_bytes: int,
                percent: float (0.0 ~ 1.0+),
                file_count: int (软删 NULL 计数),
                is_over_quota: bool (used > quota),
                updated_at: ISO datetime
            }
        """
        user = (await self.db.execute(
            select(Member).where(Member.id == user_id)
        )).scalar_one_or_none()
        if not user:
            return {
                "user_id": user_id,
                "used_bytes": 0,
                "quota_bytes": 0,
                "percent": 0.0,
                "file_count": 0,
                "is_over_quota": False,
                "updated_at": None,
            }
        used = user.drive_used_bytes or 0
        quota = user.drive_quota_bytes or 0
        percent = (used / quota) if quota > 0 else 0.0
        # 活跃文件数
        count_stmt = select(func.count(Knowledge.id)).where(
            and_(
                Knowledge.created_by == user_id,
                Knowledge.storage_mode == "drive",
                Knowledge.deleted_at.is_(None),
            )
        )
        file_count = (await self.db.execute(count_stmt)).scalar() or 0

        return {
            "user_id": user_id,
            "used_bytes": used,
            "quota_bytes": quota,
            "percent": round(percent, 4),
            "file_count": file_count,
            "is_over_quota": used > quota,
            "updated_at": user.drive_quota_updated_at.isoformat() if user.drive_quota_updated_at else None,
        }

    # ----- 分片上传 + 断点续传 -----

    async def init_chunked_upload(
        self,
        user_id: int,
        file_name: str,
        file_size: int,
        total_chunks: int,
        file_hash: Optional[str] = None,
        folder_id: Optional[int] = None,
        visibility: str = "team",
    ) -> ChunkedUploadSession:
        """初始化分片上传 session (POST /files/upload/init)

        配额检查: 配额不足时抛 DriveServiceError 413
        24h TTL: expires_at = now + 24h
        status='active': 等 chunks 写入

        v2 PR6-P19: is_team_shared 不在这里传 — 移到 complete 阶段 (前端可在 complete 时
        决定 final 视图归属, init 阶段用户可能还没决定). service 层 complete_chunked_upload
        接 is_team_shared 参数 (Optional, None=默认 personal/false).
        """
        # 配额检查
        allowed, _, quota = await self.check_quota(user_id, file_size)
        if not allowed:
            raise DriveServiceError(
                f"配额不足: 文件 {file_size} 字节, 配额上限 {quota} 字节", status_code=413
            )

        # 文件大小校验
        if file_size > MAX_DRIVE_FILE_SIZE_BYTES:
            raise DriveServiceError(
                f"文件过大: {file_size} > {MAX_DRIVE_FILE_SIZE_BYTES}", status_code=413
            )

        # folder_id 校验 (如提供)
        if folder_id is not None:
            folder = (await self.db.execute(
                select(Folder).where(
                    and_(Folder.id == folder_id, Folder.deleted_at.is_(None))
                )
            )).scalar_one_or_none()
            if not folder:
                raise DriveServiceError(f"Folder {folder_id} 不存在", status_code=404)
            # visibility 继承校验 (函数内 raise, 不需要 if not)
            self._validate_visibility_inherits(visibility, folder.visibility)

        session_id = secrets.token_hex(16)  # 32 chars
        session = ChunkedUploadSession(
            id=session_id,
            user_id=user_id,
            file_name=file_name,
            file_size=file_size,
            file_hash=file_hash,
            folder_id=folder_id,
            visibility=visibility,
            total_chunks=total_chunks,
            uploaded_chunks=[],
            status="active",
            expires_at=datetime.utcnow() + timedelta(hours=24),
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        logger.info(
            f"[DriveService.init_chunked_upload] session={session_id} "
            f"user={user_id} file={file_name} chunks={total_chunks}"
        )
        return session

    async def upload_chunk(
        self,
        session_id: str,
        user_id: int,
        chunk_index: int,
        chunk_data: bytes,
    ) -> ChunkedUploadSession:
        """上传单个 chunk (PUT /files/upload/{id}/chunk/{idx})

        写 MinIO: drive-uploads/{session_id}/chunk_{idx}
        更新 session.uploaded_chunks (append idx)
        """
        session = (await self.db.execute(
            select(ChunkedUploadSession).where(
                and_(
                    ChunkedUploadSession.id == session_id,
                    ChunkedUploadSession.user_id == user_id,  # 越权防御
                    ChunkedUploadSession.status == "active",
                )
            )
        )).scalar_one_or_none()
        if not session:
            raise DriveServiceError("Session 不存在/已过期/无权访问", status_code=404)

        # chunk_index 范围校验
        if chunk_index < 0 or chunk_index >= session.total_chunks:
            raise DriveServiceError(
                f"chunk_index={chunk_index} 越界 [0, {session.total_chunks})",
                status_code=400,
            )

        # 写 MinIO staging
        object_name = f"drive-uploads/{session_id}/chunk_{chunk_index:04d}"
        await file_service.upload_to_path(
            object_name, chunk_data, content_type="application/octet-stream"
        )

        # 追加 uploaded_chunks (去重 + 排序)
        existing = set(session.uploaded_chunks or [])
        existing.add(chunk_index)
        session.uploaded_chunks = sorted(existing)
        await self.db.commit()
        await self.db.refresh(session)

        logger.debug(
            f"[DriveService.upload_chunk] session={session_id} "
            f"chunk={chunk_index} total_uploaded={len(session.uploaded_chunks)}/{session.total_chunks}"
        )
        return session

    async def get_chunked_session(
        self, session_id: str, user_id: int
    ) -> Optional[ChunkedUploadSession]:
        """获取分片 session 状态 (断点续传用)

        返回的 session.uploaded_chunks 列表告诉前端哪些 chunks 已传, 跳到下一索引
        """
        session = (await self.db.execute(
            select(ChunkedUploadSession).where(
                and_(
                    ChunkedUploadSession.id == session_id,
                    ChunkedUploadSession.user_id == user_id,
                )
            )
        )).scalar_one_or_none()
        return session

    async def complete_chunked_upload(
        self,
        session_id: str,
        user_id: int,
        change_note: Optional[str] = None,
        # v2 PR6-P19: 团队共享盘标识 (前端 complete 时传, 决定 Knowledge.is_team_shared)
        is_team_shared: Optional[bool] = None,
    ) -> Knowledge:
        """完成分片上传 (POST /files/upload/{id}/complete)

        流程:
        1. 查 session (active + 全 chunks 已传)
        2. 从 MinIO 按顺序读所有 chunk → 拼接 → 写最终 object_name
        3. 创建 Knowledge 行 (drive 模式)
        4. 标 session.status='completed'
        5. Fire-and-forget: 重算配额 + 生成缩略图
        6. 清 MinIO staging
        """
        session = (await self.db.execute(
            select(ChunkedUploadSession).where(
                and_(
                    ChunkedUploadSession.id == session_id,
                    ChunkedUploadSession.user_id == user_id,
                    ChunkedUploadSession.status == "active",
                )
            )
        )).scalar_one_or_none()
        if not session:
            raise DriveServiceError("Session 不存在/已完成/已过期", status_code=404)

        # 校验所有 chunks 已传
        uploaded = set(session.uploaded_chunks or [])
        expected = set(range(session.total_chunks))
        missing = expected - uploaded
        if missing:
            raise DriveServiceError(
                f"未完成的 chunks: {sorted(missing)[:10]}{'...' if len(missing) > 10 else ''}",
                status_code=400,
            )

        # 拼接 chunks → 最终 object_name
        final_object = (
            f"uploads/drive/{user_id}/"
            f"{session_id[:8]}_{int(datetime.utcnow().timestamp())}"
            f"{os.path.splitext(session.file_name)[1] if session.file_name else ''}"
        )

        # 顺序下载 + 上传 (简化: 不真做拼接, 走 copy_object 链)
        # 真实拼接需 ffmpeg concat 或 pyfilesystem — 这里走 app/services/file_service 的 streaming 拼接
        await _stream_concat_chunks(
            session_id=session_id,
            chunk_indices=sorted(uploaded),
            dst_object=final_object,
        )

        # 2026-09 单一团队空间: is_team_shared 服务端恒 True (迁移 133 回填后该字段退役)
        is_team_shared_resolved = True

        # 创建 Knowledge 行 (复用 create_file 走 drive 路径)
        new_file = await self.create_file(
            title=session.file_name,
            file_path=final_object,
            file_name=session.file_name,
            file_type=os.path.splitext(session.file_name)[1] if session.file_name else None,
            file_size=session.file_size,
            file_hash=session.file_hash,
            owner_id=user_id,
            created_by=user_id,
            folder_id=session.folder_id,
            visibility=session.visibility,
            storage_mode="drive",
            is_team_shared=is_team_shared_resolved,
        )

        # 标 session 完成
        session.status = "completed"
        session.object_name = final_object
        session.completed_at = datetime.utcnow()
        await self.db.commit()

        # Fire-and-forget: 重算配额 + 生成缩略图
        try:
            from app.services.storage_tasks import recalc_user_storage_task
            from app.services.thumbnail_tasks import generate_thumbnail_task
            recalc_user_storage_task.delay(user_id)
            generate_thumbnail_task.delay(new_file.id)
        except Exception as e:
            logger.warning(f"[DriveService.complete_chunked_upload] fire Celery 失败: {e}")

        # 清 MinIO staging (异步)
        try:
            import asyncio
            objects = await file_service.list_objects(f"drive-uploads/{session_id}/")
            for obj in objects:
                await asyncio.to_thread(file_service.delete_file, obj.object_name)
        except Exception as e:
            logger.warning(f"[DriveService.complete_chunked_upload] staging 清理失败: {e}")

        logger.info(
            f"[DriveService.complete_chunked_upload] session={session_id} → file_id={new_file.id}"
        )
        return new_file

    async def abort_chunked_upload(self, session_id: str, user_id: int) -> bool:
        """中止分片上传 (POST /files/upload/{id}/abort)

        标 session.status='aborted' + 清 MinIO staging
        """
        session = (await self.db.execute(
            select(ChunkedUploadSession).where(
                and_(
                    ChunkedUploadSession.id == session_id,
                    ChunkedUploadSession.user_id == user_id,
                    ChunkedUploadSession.status == "active",
                )
            )
        )).scalar_one_or_none()
        if not session:
            return False

        session.status = "aborted"
        await self.db.commit()

        # 清 MinIO staging
        try:
            import asyncio
            objects = await file_service.list_objects(f"drive-uploads/{session_id}/")
            for obj in objects:
                await asyncio.to_thread(file_service.delete_file, obj.object_name)
        except Exception as e:
            logger.warning(f"[DriveService.abort_chunked_upload] staging 清理失败: {e}")

        logger.info(f"[DriveService.abort_chunked_upload] session={session_id} aborted")
        return True

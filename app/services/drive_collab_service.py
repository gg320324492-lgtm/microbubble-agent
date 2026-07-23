"""Drive v2 PR10 — 协同编辑 service 骨架 (2026-07-24, W68 第 5 批)

设计目标 (W68 第 5 批):
- **仅**调研 + 骨架 (本 PR 0 production code 改动铁律)
- 提供 5 个 stub 方法, 留 W69 实施
- 不挂 API 路由, 不创建 Celery task
- 不引入 pycrdt 硬依赖 (用 TYPE_CHECKING 软引用, 部署时不报错)

实施路线:
- W69 (12h): 完整实现, 挂 /api/v1/drive/collab/{file_id} WS 端点
- W70 (16h): Redis pub/sub + op log 压缩
- W71 (14h): y-codemirror 集成 + 协作者光标 + 离线兜底

调用方 (W69):
- WS 端点: 客户端连入 → get_or_create_ydoc_state() → apply_update
- WS 端点: 客户端发 op → apply_remote_op() → 广播给同 room
- Celery beat flush_ydoc_state_task: 30s 周期调 flush_ydoc_state()

注意 (CLAUDE.md 铁律):
- 持久化 best-effort (chat-history-persistent-2026-06-30.md 铁律 5)
- 越权防护: 强制 (db, file_id, user_id) 三元组过滤
- JSONB flag_modified (本表无 JSONB 字段, 不适用)

参考:
- docs/drive-v2-pr10-collab-editing-design.md
- pycrdt 0.14.1 协议 (https://pypi.org/project/pycrdt/)
- Yjs 13.6.x 协议 (字节兼容)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_document import DriveDocument, DriveDocOpLog

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ===== 错误码 =====
class DriveCollabError(Exception):
    """DriveCollab 基础异常"""


class FileNotFoundError(DriveCollabError):
    """file_id 不存在"""


class YDocNotFoundError(DriveCollabError):
    """Y.Doc 状态不存在 (W69 实施时, get_or_create 应自动创建)"""


class InvalidOpError(DriveCollabError):
    """op 字节无法被 Y.Doc 解析"""


# ===== Service 骨架 =====
class DriveCollabService:
    """Drive v2 PR10 — 协同编辑 service (W69 实施)

    5 个核心方法 (本 PR 仅 stub):
    1. get_or_create_ydoc_state(file_id) -> bytes
    2. apply_remote_op(file_id, op_bytes, client_id, user_id) -> bytes (新 state)
    3. get_snapshot(file_id) -> bytes
    4. flush_ydoc_state(file_id, state, version) -> None (Celery beat 调)
    5. export_text(file_id) -> str (供 PR9 save_version 复用)

    内存 Y.Doc 缓存:
    - 本 service 不持有内存 Y.Doc (Celery 进程隔离, 跨进程不共享)
    - W69 实施时由 collab-gateway (FastAPI WS 进程) 持有, 每 file_id 一个 Y.Doc
    - 启动时从 drive_documents.ydoc_state 重建
    - 退出时 flush 到 drive_documents.ydoc_state

    持久化策略:
    - apply_remote_op: 同步写 drive_doc_op_logs (best-effort)
    - flush_ydoc_state: 30s 周期 OR ops_count % 100 == 0 触发
    - compress_op_logs_task: 每天凌晨 3:00 合并 7 天前 op → 写 ydoc_state → 删老 op
    """

    @staticmethod
    async def get_or_create_ydoc_state(
        db: AsyncSession, file_id: int
    ) -> bytes:
        """读 drive_documents.ydoc_state, 不存在则创建空 doc 并初始化行

        W69 实施:
        1. SELECT * FROM drive_documents WHERE file_id = :file_id
        2. 存在 → 返回 ydoc_state
        3. 不存在 → INSERT (ydoc_state=b'', ops_count=0, version_number=0)
        4. 返回 b''

        Args:
            db: AsyncSession
            file_id: Knowledge.id

        Returns:
            Y.Doc 状态字节 (0 字节 = 空 doc)

        Raises:
            FileNotFoundError: file_id 对应 Knowledge 不存在
        """
        # ===== 骨架 (W69 实施) =====
        if db is None:
            # W68 第 5 批 SKIP_DB_SETUP 模式: 不连 DB, 直接返回空 state
            return b""
        result = await db.execute(
            select(DriveDocument).where(DriveDocument.file_id == file_id)
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            logger.debug(
                "DriveCollabService.get_or_create_ydoc_state: no row for file_id=%d, "
                "W69 实施时自动 INSERT 空行",
                file_id,
            )
            # W69: doc = DriveDocument(file_id=file_id, ydoc_state=b""); db.add(doc); await db.commit()
            return b""
        return bytes(doc.ydoc_state) if doc.ydoc_state is not None else b""

    @staticmethod
    async def apply_remote_op(
        db: AsyncSession,
        file_id: int,
        op_bytes: bytes,
        client_id: int,
        user_id: Optional[int] = None,
    ) -> bytes:
        """应用 op 到内存 Y.Doc, 返回新 state, 写 op_logs, 异步刷 ydoc_state

        W69 实施:
        1. collab-gateway 持有内存 Y.Doc per file_id
        2. doc.apply_update(op_bytes) — Yjs 协议自动 merge
        3. INSERT INTO drive_doc_op_logs (op, client_id, user_id, applied_at)
        4. 若 ops_count % 100 == 0 → 立即 flush_ydoc_state
        5. 返回 doc.get_state() 新字节

        Args:
            db: AsyncSession
            file_id: Knowledge.id
            op_bytes: Yjs update 字节 (5-200 字节典型)
            client_id: Yjs client_id (uint32)
            user_id: 操作者 (匿名 / system 时为 None)

        Returns:
            新 ydoc_state 字节 (供客户端 sync 用)

        Raises:
            FileNotFoundError: file_id 不存在
            InvalidOpError: op_bytes 无法被 Y.Doc 解析
        """
        # ===== 骨架 (W69 实施) =====
        if not op_bytes:
            raise InvalidOpError("op_bytes is empty")

        if db is None:
            # W68 第 5 批 SKIP_DB_SETUP 模式: 不连 DB
            return b""

        # W69: collab-gateway 进程持有内存 Y.Doc
        # doc = await self._get_or_load_ydoc(db, file_id)
        # try:
        #     doc.apply_update(op_bytes)
        # except Exception as e:
        #     raise InvalidOpError(f"apply_update failed: {e}") from e
        #
        # # 写 op log (best-effort, CLAUDE.md 铁律 5)
        # try:
        #     log = DriveDocOpLog(
        #         file_id=file_id, op=op_bytes, client_id=client_id, user_id=user_id,
        #     )
        #     db.add(log)
        #     await db.commit()
        # except Exception as e:
        #     logger.error("op log write failed", exc_info=True)
        #
        # # 更新内存 ops_count
        # doc.ops_count += 1
        #
        # # 100 op 触发 flush
        # if doc.ops_count % 100 == 0:
        #     await DriveCollabService.flush_ydoc_state(
        #         db, file_id, doc.get_state(), doc.version_number
        #     )
        #
        # return doc.get_state()

        logger.debug(
            "DriveCollabService.apply_remote_op STUB: "
            "file_id=%d client_id=%d user_id=%s op_len=%d",
            file_id, client_id, user_id, len(op_bytes),
        )
        return b""

    @staticmethod
    async def get_snapshot(
        db: AsyncSession, file_id: int
    ) -> bytes:
        """返回最新 ydoc_state, 用于新客户端连接时 sync

        W69 实施:
        1. 优先从 collab-gateway 内存 Y.Doc 读 (若 room 活跃)
        2. 否则从 drive_documents.ydoc_state 读
        3. 返回

        Args:
            db: AsyncSession
            file_id: Knowledge.id

        Returns:
            最新 ydoc_state 字节
        """
        # ===== 骨架 (W69 实施) =====
        # W69: in-memory 优先
        # doc = collab_gateway.get_room(file_id)
        # if doc is not None:
        #     return doc.get_state()
        return await DriveCollabService.get_or_create_ydoc_state(db, file_id)

    @staticmethod
    async def flush_ydoc_state(
        db: AsyncSession,
        file_id: int,
        state: bytes,
        version: int,
    ) -> None:
        """Celery beat 调, 30s 周期刷盘

        W69 实施:
        1. UPSERT drive_documents SET ydoc_state=:state, version_number=:version, updated_at=NOW()
        2. WHERE file_id = :file_id

        Args:
            db: AsyncSession
            file_id: Knowledge.id
            state: Y.Doc 字节 (从 collab-gateway 内存读)
            version: 当前 version_number
        """
        # ===== 骨架 (W69 实施) =====
        # W69:
        # from sqlalchemy.dialects.postgresql import insert as pg_insert
        # stmt = pg_insert(DriveDocument).values(
        #     file_id=file_id, ydoc_state=state, version_number=version,
        # ).on_conflict_do_update(
        #     index_elements=['file_id'],
        #     set_={'ydoc_state': state, 'version_number': version, 'updated_at': sa.func.now()},
        # )
        # await db.execute(stmt)
        # await db.commit()
        logger.debug(
            "DriveCollabService.flush_ydoc_state STUB: file_id=%d state_len=%d v=%d",
            file_id, len(state), version,
        )

    @staticmethod
    async def export_text(db: AsyncSession, file_id: int) -> str:
        """从 ydoc_state 提取纯文本, 写 MinIO (供 PR9 save_version 复用)

        W69 实施:
        1. 加载 Y.Doc from ydoc_state
        2. 提取 text = doc.get('content', type=Text)
        3. return str(text)

        Args:
            db: AsyncSession
            file_id: Knowledge.id

        Returns:
            纯文本内容
        """
        # ===== 骨架 (W69 实施) =====
        # W69:
        # state = await DriveCollabService.get_or_create_ydoc_state(db, file_id)
        # from pycrdt import Doc, Text
        # doc = Doc()
        # if state:
        #     doc.apply_update(state)
        # text = doc.get('content', type=Text)
        # return str(text)
        return ""

    @staticmethod
    async def get_active_users(db: AsyncSession, file_id: int) -> int:
        """返回实时房间人数 (best-effort, 30s 刷盘)

        W69 实施:
        1. SELECT active_users FROM drive_documents WHERE file_id = :file_id
        2. 返回

        Args:
            db: AsyncSession
            file_id: Knowledge.id

        Returns:
            活跃用户数 (0 表示无活跃 room)
        """
        # ===== 骨架 (W69 实施) =====
        result = await db.execute(
            select(DriveDocument.active_users).where(DriveDocument.file_id == file_id)
        )
        return result.scalar() or 0

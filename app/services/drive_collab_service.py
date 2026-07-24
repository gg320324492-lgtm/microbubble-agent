"""Drive v2 PR10 — 协同编辑 service 实施 (2026-07-24, W68 第 7 批 B-1)

W68 第 5 批仅调研 + 骨架 (305 行 stub). W68 第 7 批 B-1 完整实施 CRDT 协同编辑核心:

核心方法 (真实实现):
1. get_or_create_ydoc_state(db, file_id)      → 读 Y.Doc snapshot, 不存在则 INSERT 空行
2. apply_remote_op(db, file_id, op, client_id) → apply_update + 写 op log + 触发刷盘
3. get_snapshot(db, file_id)                  → 返最新 Y.Doc state (op log 重放兜底)
4. subscribe_to_room(redis, file_id)          → WS Redis pub/sub 订阅其他客户端 op
5. publish_op_to_room(redis, file_id, ...)    → WS Redis pub/sub 广播 op
6. flush_ydoc_state_to_db(db, file_id, ...)   → Celery 30s 周期刷盘
7. recover_from_crash(db, file_id)            → 从 op log 重放重建 Y.Doc
8. export_text(db, file_id)                   → 提取纯文本 (供 PR9 save_version 复用)
9. get_active_users(db, file_id)              → 房间人数

设计要点 (CLAUDE.md 铁律):
- **跨 event loop 安全** (方案 C 铁律 1): 不在模块顶部创建 redis/llm client, 统一参数注入
- **持久化 best-effort** (chat-history-persistent-2026-06-30.md 铁律 5): op log 写失败不阻塞流
- **越权防护** (chat-history 铁律 8): 权限校验由 API 层 DrivePermissionService 完成, service
  层只做 file_id 过滤 (不承担鉴权, 保持 service 纯数据层职责)
- **op log 压缩** (设计 doc §7): 7 天前 op 由 Celery compress task 合并到 ydoc_state 后删

CRDT 语义 (pycrdt 0.14.1 / Yjs 13.6.x 字节兼容):
- Y.Doc.get_update(state_vector) → 增量 update 字节 (state_vector=None 时全量)
- Y.Doc.apply_update(bytes)      → 幂等合并 (CRDT 收敛性, 重复 apply 无副作用)
- Y.Doc.get_state()              → state vector (用于计算增量 diff)
- get_update() (无参)             → 全量 update (用于新客户端 init 同步)

关键: **snapshot 存的是全量 update 字节, 不是 state vector**. 因为 state vector 只是
"我知道哪些 update" 的摘要, 无法重建内容. 客户端 init 需要全量 update.

参考:
- docs/drive-v2-pr10-collab-editing.md
- docs/drive-v2-pr10-collab-editing-design.md
- memory/w68-route-7-b1-drive-pr10-collab-ws-2026-07-24.md
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, AsyncIterator, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_document import DriveDocOpLog, DriveDocument

if TYPE_CHECKING:  # pragma: no cover
    import redis.asyncio as aioredis

logger = logging.getLogger("microbubble.drive_collab")


# ===== 常量 =====
#: Redis pub/sub 频道前缀 (每 file_id 一个房间)
ROOM_CHANNEL_PREFIX = "drive:collab:room:"
#: 每累计 N 个 op 立即触发一次刷盘 (不等 30s Celery beat)
FLUSH_EVERY_N_OPS = 100
#: snapshot 字节软阈值 (超过则告警, 由 W70 compress 强制重建)
SNAPSHOT_SIZE_WARN_BYTES = 50 * 1024


# ===== 错误码 =====
class DriveCollabError(Exception):
    """DriveCollab 基础异常"""


class CollabFileNotFoundError(DriveCollabError):
    """file_id 不存在 (对应 Knowledge 行缺失)

    命名避免与内建 FileNotFoundError 冲突 (W68 第 5 批骨架用了内建同名, 本次修正).
    """


class YDocNotFoundError(DriveCollabError):
    """Y.Doc 状态不存在"""


class InvalidOpError(DriveCollabError):
    """op 字节无法被 Y.Doc 解析"""


def room_channel(file_id: int) -> str:
    """返回 file_id 对应的 Redis pub/sub 频道名"""
    return f"{ROOM_CHANNEL_PREFIX}{file_id}"


class DriveCollabService:
    """Drive v2 PR10 — 协同编辑 service (W68 第 7 批 B-1 完整实施)

    职责边界:
    - **数据层**: 只做 file_id 过滤 + Y.Doc 序列化/反序列化 + op log CRUD
    - **不承担鉴权**: 由 API 层 DrivePermissionService 前置校验 (service 纯数据)
    - **不持有内存 Y.Doc**: 每次调用即时从 snapshot 重建 (Celery / WS 进程隔离,
      内存 Y.Doc 无法跨进程共享). 高频写场景 W70 引入 collab-gateway 内存缓存.

    snapshot 存储约定:
    - drive_documents.ydoc_state 存 **全量 update 字节** (Doc.get_update() 无参)
    - 空 doc → b"" (0 字节)
    - 客户端 init 直接 apply 这个字节即可重建全部内容
    """

    # ------------------------------------------------------------------
    # 1. get_or_create — 读 snapshot, 不存在则 INSERT 空行
    # ------------------------------------------------------------------
    @staticmethod
    async def get_or_create_ydoc_state(db: AsyncSession, file_id: int) -> bytes:
        """读 drive_documents.ydoc_state, 不存在则创建空 doc 行并返回 b""

        Args:
            db: AsyncSession (None 时 SKIP_DB_SETUP 模式返回 b"")
            file_id: Knowledge.id

        Returns:
            全量 Y.Doc update 字节 (0 字节 = 空 doc)
        """
        if db is None:
            # SKIP_DB_SETUP smoke 模式: 不连 DB
            return b""

        result = await db.execute(
            select(DriveDocument).where(DriveDocument.file_id == file_id)
        )
        doc_row = result.scalar_one_or_none()
        if doc_row is None:
            # 自动 INSERT 空行 (best-effort — 写失败不阻塞读)
            try:
                doc_row = DriveDocument(file_id=file_id, ydoc_state=b"")
                db.add(doc_row)
                await db.commit()
                logger.info(
                    "[collab] 初始化空 Y.Doc row file_id=%d", file_id
                )
            except Exception:
                await db.rollback()
                logger.error(
                    "[collab] get_or_create INSERT 失败 file_id=%d", file_id,
                    exc_info=True,
                )
            return b""

        return bytes(doc_row.ydoc_state) if doc_row.ydoc_state is not None else b""

    # ------------------------------------------------------------------
    # 2. apply_remote_op — apply_update + 写 op log + 触发刷盘
    # ------------------------------------------------------------------
    @staticmethod
    async def apply_remote_op(
        db: AsyncSession,
        file_id: int,
        op_bytes: bytes,
        client_id: int,
        user_id: Optional[int] = None,
    ) -> bytes:
        """应用远端 op, 返回新的全量 update 字节

        流程:
        1. 加载现有 snapshot → 重建 Y.Doc
        2. doc.apply_update(op_bytes)  (CRDT 幂等合并)
        3. 写 drive_doc_op_logs (best-effort)
        4. UPSERT drive_documents.ydoc_state = doc.get_update() (新全量)
        5. ops_count % 100 == 0 时 log 提示 (真刷盘由 flush task / 本次已同步写)
        6. 返回 doc.get_update() 供客户端 / 广播用

        Args:
            db: AsyncSession
            file_id: Knowledge.id
            op_bytes: Yjs update 字节
            client_id: Yjs client_id (uint32)
            user_id: 操作者 member.id (匿名/system 为 None)

        Returns:
            新的全量 Y.Doc update 字节

        Raises:
            InvalidOpError: op_bytes 空或无法被 Y.Doc 解析
        """
        if not op_bytes:
            raise InvalidOpError("op_bytes is empty")

        if db is None:
            # SKIP_DB_SETUP smoke 模式
            return b""

        import pycrdt

        # 1) 加载现有 snapshot 重建 doc
        result = await db.execute(
            select(DriveDocument).where(DriveDocument.file_id == file_id)
        )
        doc_row = result.scalar_one_or_none()
        if doc_row is None:
            doc_row = DriveDocument(file_id=file_id, ydoc_state=b"")
            db.add(doc_row)
            await db.flush()  # 拿到 row, 不 commit (下面统一 commit)

        doc = pycrdt.Doc()
        existing = bytes(doc_row.ydoc_state) if doc_row.ydoc_state else b""
        if existing:
            try:
                doc.apply_update(existing)
            except Exception:
                logger.error(
                    "[collab] snapshot 损坏 file_id=%d, 尝试从 op log 重放",
                    file_id, exc_info=True,
                )
                doc = await DriveCollabService._rebuild_doc_from_oplog(db, file_id)

        # 2) 应用新 op (CRDT 幂等)
        try:
            doc.apply_update(op_bytes)
        except Exception as e:
            raise InvalidOpError(f"apply_update failed: {e}") from e

        new_state = doc.get_update()

        # 3) 写 op log (best-effort — 失败不阻塞主流)
        try:
            db.add(
                DriveDocOpLog(
                    file_id=file_id,
                    op=op_bytes,
                    client_id=client_id,
                    user_id=user_id,
                )
            )
        except Exception:
            logger.error("[collab] op log 入队失败 file_id=%d", file_id, exc_info=True)

        # 4) 更新 snapshot + 计数 + 最近编辑者
        doc_row.ydoc_state = new_state
        doc_row.ops_count = (doc_row.ops_count or 0) + 1
        if user_id is not None:
            doc_row.last_edited_by = user_id
            doc_row.last_edited_at = datetime.now(timezone.utc).replace(tzinfo=None)

        try:
            await db.commit()
        except Exception:
            await db.rollback()
            logger.error("[collab] apply_remote_op commit 失败 file_id=%d", file_id, exc_info=True)
            # snapshot 未落库, 但内存 doc 已合并 → 返回 new_state 供广播 (客户端仍收敛)
            return new_state

        if doc_row.ops_count % FLUSH_EVERY_N_OPS == 0:
            logger.info(
                "[collab] file_id=%d 达到 %d op, snapshot 已同步刷盘 (size=%d bytes)",
                file_id, doc_row.ops_count, len(new_state),
            )
        if len(new_state) > SNAPSHOT_SIZE_WARN_BYTES:
            logger.warning(
                "[collab] file_id=%d snapshot 超阈值 %d bytes (>%d), 建议 W70 compress",
                file_id, len(new_state), SNAPSHOT_SIZE_WARN_BYTES,
            )

        return new_state

    # ------------------------------------------------------------------
    # 3. get_snapshot — 返最新 state, op log 兜底
    # ------------------------------------------------------------------
    @staticmethod
    async def get_snapshot(db: AsyncSession, file_id: int) -> bytes:
        """返回最新全量 Y.Doc update 字节 (供新客户端连接 init 同步)

        兜底: snapshot 为空但有 op log → 从 op log 重放重建 (崩溃恢复场景).

        Args:
            db: AsyncSession
            file_id: Knowledge.id

        Returns:
            全量 Y.Doc update 字节
        """
        if db is None:
            return b""

        snapshot = await DriveCollabService.get_or_create_ydoc_state(db, file_id)
        if snapshot:
            return snapshot

        # snapshot 为空: 检查是否有 op log (崩溃后 snapshot 丢失但 op 还在)
        result = await db.execute(
            select(DriveDocOpLog.id)
            .where(DriveDocOpLog.file_id == file_id)
            .limit(1)
        )
        if result.scalar_one_or_none() is None:
            return b""  # 真空 doc

        doc = await DriveCollabService._rebuild_doc_from_oplog(db, file_id)
        return doc.get_update()

    # ------------------------------------------------------------------
    # 4 + 5. Redis pub/sub — subscribe / publish
    # ------------------------------------------------------------------
    @staticmethod
    async def publish_op_to_room(
        redis: "aioredis.Redis",
        file_id: int,
        op_bytes: bytes,
        origin_client_id: int,
    ) -> int:
        """把 op 广播到 file_id 房间 (跨 WS 进程扇出)

        Redis message 编码: <origin_client_id:uint>|<op base64>
        用竖线分隔避免二进制 op 与整数混淆.

        Args:
            redis: aioredis client (由 WS handler 注入, 跨 loop 安全)
            file_id: Knowledge.id
            op_bytes: Yjs update
            origin_client_id: 发起者 client_id (订阅者据此跳过自己的 op)

        Returns:
            收到该消息的订阅者数 (Redis PUBLISH 返回值)
        """
        import base64

        payload = f"{origin_client_id}|{base64.b64encode(op_bytes).decode('ascii')}"
        try:
            return int(await redis.publish(room_channel(file_id), payload))
        except Exception:
            logger.error("[collab] publish_op 失败 file_id=%d", file_id, exc_info=True)
            return 0

    @staticmethod
    async def subscribe_to_room(
        redis: "aioredis.Redis",
        file_id: int,
    ) -> AsyncIterator[Tuple[int, bytes]]:
        """订阅 file_id 房间, 异步 yield (origin_client_id, op_bytes)

        用法 (WS handler):
            async for origin_cid, op in DriveCollabService.subscribe_to_room(redis, fid):
                if origin_cid == my_client_id:
                    continue  # 跳过自己的 op
                await ws.send_bytes(op)

        注意 (方案 C 铁律 1): redis 必须由调用方注入 (WS handler 的 event loop),
        不能在 service 模块顶部创建全局 client.

        Args:
            redis: aioredis client
            file_id: Knowledge.id

        Yields:
            (origin_client_id, op_bytes) 元组
        """
        import base64

        pubsub = redis.pubsub()
        await pubsub.subscribe(room_channel(file_id))
        try:
            async for message in pubsub.listen():
                if message is None or message.get("type") != "message":
                    continue
                data = message.get("data")
                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="ignore")
                if not isinstance(data, str) or "|" not in data:
                    continue
                cid_str, op_b64 = data.split("|", 1)
                try:
                    origin_cid = int(cid_str)
                    op_bytes = base64.b64decode(op_b64)
                except Exception:
                    logger.debug("[collab] 无法解析 pubsub 消息 file_id=%d", file_id)
                    continue
                yield origin_cid, op_bytes
        finally:
            try:
                await pubsub.unsubscribe(room_channel(file_id))
                await pubsub.aclose()
            except Exception:
                logger.debug("[collab] pubsub 清理异常 file_id=%d", file_id, exc_info=True)

    # ------------------------------------------------------------------
    # 6. flush_ydoc_state_to_db — Celery 30s 周期刷盘
    # ------------------------------------------------------------------
    @staticmethod
    async def flush_ydoc_state_to_db(
        db: AsyncSession,
        file_id: int,
        state: Optional[bytes] = None,
        version: Optional[int] = None,
        active_users: Optional[int] = None,
    ) -> bool:
        """把 Y.Doc snapshot 写入 drive_documents (UPSERT)

        调用方:
        - Celery flush_ydoc_state_task: 传 collab-gateway 内存 state
        - state=None 时: 从 op log 重放重建 (无内存 state 的兜底刷盘)

        Args:
            db: AsyncSession
            file_id: Knowledge.id
            state: 全量 Y.Doc update 字节 (None 时从 op log 重建)
            version: version_number (None 保持不变)
            active_users: 房间人数 (None 保持不变)

        Returns:
            True 刷盘成功, False 失败 (best-effort, 不抛)
        """
        if db is None:
            return False

        try:
            result = await db.execute(
                select(DriveDocument).where(DriveDocument.file_id == file_id)
            )
            doc_row = result.scalar_one_or_none()

            if state is None:
                # 无传入 state → 从 op log 重放 (兜底)
                doc = await DriveCollabService._rebuild_doc_from_oplog(db, file_id)
                state = doc.get_update()

            if doc_row is None:
                doc_row = DriveDocument(file_id=file_id, ydoc_state=state)
                db.add(doc_row)
            else:
                doc_row.ydoc_state = state

            if version is not None:
                doc_row.version_number = version
            if active_users is not None:
                doc_row.active_users = active_users

            await db.commit()
            logger.debug(
                "[collab] flush file_id=%d state=%d bytes v=%s users=%s",
                file_id, len(state), version, active_users,
            )
            return True
        except Exception:
            await db.rollback()
            logger.error("[collab] flush_ydoc_state 失败 file_id=%d", file_id, exc_info=True)
            return False

    # ------------------------------------------------------------------
    # 7. recover_from_crash — 从 op log 重放重建
    # ------------------------------------------------------------------
    @staticmethod
    async def recover_from_crash(db: AsyncSession, file_id: int) -> bytes:
        """崩溃恢复: 从 op log 全量重放重建 Y.Doc, 写回 snapshot

        场景: snapshot 损坏 / 进程崩溃丢失内存 state, 但 op log 完整.
        重放 (snapshot + 所有 op log) → 得到最新 doc → 写回 ydoc_state.

        Args:
            db: AsyncSession
            file_id: Knowledge.id

        Returns:
            重建后的全量 update 字节
        """
        if db is None:
            return b""

        doc = await DriveCollabService._rebuild_doc_from_oplog(db, file_id)
        state = doc.get_update()
        await DriveCollabService.flush_ydoc_state_to_db(db, file_id, state=state)
        logger.info(
            "[collab] recover_from_crash file_id=%d 重建 %d bytes", file_id, len(state)
        )
        return state

    # ------------------------------------------------------------------
    # 8. export_text — 提取纯文本 (供 PR9 save_version 复用)
    # ------------------------------------------------------------------
    @staticmethod
    async def export_text(db: AsyncSession, file_id: int) -> str:
        """从 ydoc_state 提取 'content' Text 的纯文本

        Args:
            db: AsyncSession
            file_id: Knowledge.id

        Returns:
            纯文本 (空 doc → "")
        """
        if db is None:
            return ""

        state = await DriveCollabService.get_snapshot(db, file_id)
        if not state:
            return ""

        import pycrdt

        doc = pycrdt.Doc()
        try:
            doc.apply_update(state)
        except Exception:
            logger.error("[collab] export_text apply 失败 file_id=%d", file_id, exc_info=True)
            return ""
        text = doc.get("content", type=pycrdt.Text)
        return str(text)

    # ------------------------------------------------------------------
    # 9. get_active_users — 房间人数
    # ------------------------------------------------------------------
    @staticmethod
    async def get_active_users(db: AsyncSession, file_id: int) -> int:
        """返回实时房间人数 (best-effort, 30s 刷盘)

        Args:
            db: AsyncSession
            file_id: Knowledge.id

        Returns:
            活跃用户数 (0 = 无活跃 room / file 不存在)
        """
        if db is None:
            return 0
        result = await db.execute(
            select(DriveDocument.active_users).where(DriveDocument.file_id == file_id)
        )
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------
    @staticmethod
    async def _rebuild_doc_from_oplog(db: AsyncSession, file_id: int):
        """从 snapshot(若有) + 所有 op log 按时间顺序重放, 返回 pycrdt.Doc

        CRDT 幂等: 即使 snapshot 已含部分 op, 重复 apply 也收敛 (不会重复插入).
        """
        import pycrdt

        doc = pycrdt.Doc()

        # 先 apply 现有 snapshot (可能为空)
        result = await db.execute(
            select(DriveDocument.ydoc_state).where(DriveDocument.file_id == file_id)
        )
        snapshot = result.scalar_one_or_none()
        if snapshot:
            try:
                doc.apply_update(bytes(snapshot))
            except Exception:
                logger.warning(
                    "[collab] _rebuild snapshot 损坏 file_id=%d, 跳过仅用 op log",
                    file_id,
                )

        # 再按时间顺序 apply 所有 op log
        op_result = await db.execute(
            select(DriveDocOpLog.op)
            .where(DriveDocOpLog.file_id == file_id)
            .order_by(DriveDocOpLog.applied_at.asc(), DriveDocOpLog.id.asc())
        )
        applied = 0
        for (op_bytes,) in op_result.all():
            if not op_bytes:
                continue
            try:
                doc.apply_update(bytes(op_bytes))
                applied += 1
            except Exception:
                logger.debug("[collab] _rebuild 单条 op 损坏 file_id=%d 跳过", file_id)
        logger.debug("[collab] _rebuild file_id=%d 重放 %d 条 op", file_id, applied)
        return doc

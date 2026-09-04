"""网盘归属转移助手 (2026-09 单一团队空间 — 决策 2)

删除成员 (硬删) 前, 把挂在该成员名下、FK 指向 members.id 的网盘/知识库归属行
批量转给锚点成员 (settings.DRIVE_WORKSPACE_ANCHOR_ID, 默认 1), 一个事务内让
DELETE FROM members 不再被 RESTRICT/NO ACTION FK 卡死。

背景: 整个网盘树 (组会PPT 等) 历史上挂在单一账号 folders.owner_id /
knowledge.created_by 上, 2026-09-05 之前的删号演练只能手工 SQL 转 owner。
本模块把该操作固化为可复用 service (scripts/reassign_member_rows.py 与
DELETE /members/{id}?reassign_drive=true 共用)。

覆盖表 (与 drive_ownership 语义相关的归属列):
- folders.owner_id               (RESTRICT)
- knowledge.created_by           (NO ACTION)
- knowledge_versions.uploaded_by (NO ACTION)
- drive_file_versions.uploader_id (RESTRICT)
- file_requests.created_by       (RESTRICT)
- agent_traces.user_id           (NO ACTION)
- chat_sessions.user_id          (CASCADE — 转移后 chat_messages 跟着 anchor 走,
                                  避免 CASCADE 连带删会话历史)

注意: activity_events.actor_id / 各 SET NULL / CASCADE 列不需要处理
(FK 行为本身就会在硬删时置空/级联, 不阻塞删除)。

⚠ 语义代价 (plan 决策 2 已锁定): owner_id/created_by 是"创建人溯源", 转移会把
被删成员创建内容的作者归到锚点成员名下。相比丢内容/删号被卡, 这是接受项。
"""
import logging

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("microbubble.drive_ownership")

# (表名, 归属列) — UPDATE <table> SET <col>=:anchor WHERE <col>=:member
REASSIGN_TARGETS: tuple[tuple[str, str], ...] = (
    ("folders", "owner_id"),
    ("knowledge", "created_by"),
    ("knowledge_versions", "uploaded_by"),
    ("drive_file_versions", "uploader_id"),
    ("file_requests", "created_by"),
    ("agent_traces", "user_id"),
    ("chat_sessions", "user_id"),
    # 遗留共享机制表 (0 行, RESTRICT/NO ACTION FK): 一并防御性覆盖, 防未来有行后卡删号
    ("team_folders", "owner_id"),
    ("drive_folder_shares", "created_by"),
    ("drive_folder_members", "invited_by"),
    ("drive_version_tags", "created_by"),
)


async def reassign_member_rows(
    db: AsyncSession,
    *,
    member_id: int,
    anchor_id: int,
) -> dict[str, int]:
    """把 member_id 名下所有网盘/知识库归属行转给 anchor_id (单事务)。

    Args:
        db: AsyncSession (调用方负责 commit — 本函数内 commit, 与 endpoint 事务边界一致)
        member_id: 被删成员 id
        anchor_id: 工作区锚点成员 id (settings.DRIVE_WORKSPACE_ANCHOR_ID)
    Returns: {表名: 受影响行数}
    Raises: ValueError — member_id == anchor_id / 任一成员不存在
    """
    if member_id == anchor_id:
        raise ValueError(
            f"member_id 与 anchor_id 相同 ({member_id}), 转移无意义且会掩盖调用错误"
        )

    # 成员存在性守卫 (表名/列名来自本模块常量, 无注入面)
    member_exists = (await db.execute(
        text("SELECT 1 FROM members WHERE id = :mid"), {"mid": member_id}
    )).scalar()
    if member_exists is None:
        raise ValueError(f"成员 id={member_id} 不存在, 拒绝转移")
    anchor_exists = (await db.execute(
        text("SELECT 1 FROM members WHERE id = :aid"), {"aid": anchor_id}
    )).scalar()
    if anchor_exists is None:
        raise ValueError(f"锚点成员 id={anchor_id} 不在 members 表中, 拒绝转移")

    counts: dict[str, int] = {}
    for table, column in REASSIGN_TARGETS:
        result = await db.execute(
            text(f"UPDATE {table} SET {column} = :anchor WHERE {column} = :member"),
            {"anchor": anchor_id, "member": member_id},
        )
        counts[f"{table}.{column}"] = result.rowcount or 0

    await db.commit()
    logger.info(
        f"[drive_ownership.reassign_member_rows] member={member_id} → anchor={anchor_id} "
        f"counts={counts}"
    )
    return counts

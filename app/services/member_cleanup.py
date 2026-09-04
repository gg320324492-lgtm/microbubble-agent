"""成员删除前的引用普查 (2026-09 单一团队空间)

背景: 2026-09-04 删测试账号被网盘 FK 卡死, 只能手工 SQL 转 owner。本模块提供
只读普查 (READ-ONLY census) — 枚举所有 FK→members.id 的 表.列, 统计该成员名下
行数, 供脚本/端点在硬删前评估影响面。配套转移助手见 app/services/drive_ownership.py。

两个公开函数:
- list_member_referencing_rows(db, member_id) -> {"表.列": 行数}
- blocking_refs(census)          -> 仅 RESTRICT/NO ACTION 且 count>0 的条目
  (这些会真正阻塞 DELETE FROM members; CASCADE/SET NULL 列不阻塞故剔除)

纪律: 本模块 **绝不** UPDATE/DELETE, 只 SELECT COUNT。硬删成员必须走
reassign_member_rows + 人工 --confirm 流程 (purge 铁律)。
"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("microbubble.member_cleanup")

# FK→members.id 全量清单 (2026-09 实测 alembic head 132 的 schema 普查硬编码)。
# 不存在的表 (meeting_templates / research_task 已下架) 由 _count 容错返 0。
MEMBER_FK_COLUMNS: tuple[tuple[str, str], ...] = (
    ("meetings", "created_by"),
    ("projects", "created_by"),
    ("knowledge", "created_by"),
    ("tasks", "assignee_id"),
    ("tasks", "created_by"),
    ("meeting_participants", "member_id"),
    ("reminders", "acknowledged_by"),
    ("memories", "user_id"),
    ("feedback", "user_id"),
    ("prompt_templates", "created_by"),
    ("voiceprint_history", "member_id"),
    ("meeting_templates", "created_by"),
    ("agent_traces", "user_id"),
    ("search_logs", "user_id"),
    ("member_voice_history", "member_id"),
    ("chat_sessions", "user_id"),
    ("chat_shares", "shared_by"),
    ("folders", "owner_id"),
    ("knowledge_versions", "uploaded_by"),
    ("chunked_upload_sessions", "user_id"),
    ("file_mentions", "mentioned_by"),
    ("file_mentions", "mentioned_user_id"),
    ("activity_events", "actor_id"),
    ("file_comments", "user_id"),
    ("file_requests", "created_by"),
    ("audit_log", "user_id"),
    ("drive_folder_shares", "created_by"),
    ("drive_folder_members", "invited_by"),
    ("drive_folder_members", "member_id"),
    ("drive_comments", "author_id"),
    ("drive_comments", "deleted_by"),
    ("drive_comments", "resolved_by"),
    ("drive_file_versions", "uploader_id"),
    ("drive_documents", "last_edited_by"),
    ("drive_doc_op_logs", "user_id"),
    ("push_subscriptions", "user_id"),
    ("drive_reactions", "member_id"),
    ("drive_version_tags", "created_by"),
    ("team_folders", "owner_id"),
    ("team_folder_audit_log", "actor_id"),
    ("drive_chunked_uploads", "user_id"),
    ("dft_jobs", "user_id"),
    ("chat_session_attached_documents", "user_id"),
    ("research_task", "created_by_user_id"),
)

# 真正阻塞 DELETE members 的列 (RESTRICT 或默认 NO ACTION)。
# CASCADE (chat_sessions/memories/feedback/... 连带删) 与 SET NULL
# (activity_events.actor_id/reminders.acknowledged_by/... 置空) 不列入。
_BLOCKING_COLUMNS: frozenset[str] = frozenset({
    # RESTRICT (models 实测)
    "folders.owner_id",
    "drive_file_versions.uploader_id",
    "file_requests.created_by",
    "drive_folder_shares.created_by",
    "drive_folder_members.invited_by",
    "drive_version_tags.created_by",
    "team_folders.owner_id",
    "team_folder_audit_log.actor_id",
    # NO ACTION (裸 ForeignKey, PG 默认 = 阻塞)
    "knowledge.created_by",
    "knowledge_versions.uploaded_by",
    "agent_traces.user_id",
    "meetings.created_by",
    "projects.created_by",
    "tasks.assignee_id",
    "tasks.created_by",
    "prompt_templates.created_by",
    "member_voice_history.member_id",
})


async def _count_rows(db: AsyncSession, table: str, column: str, member_id: int) -> int:
    """单表 COUNT; 表/列不存在 (老库漂移/已下架) 容错返 0, 不炸普查。"""
    try:
        result = await db.execute(
            # table/column 来自本模块常量, 非用户输入, 无注入面
            text(f"SELECT COUNT(*) FROM {table} WHERE {column} = :mid"),
            {"mid": member_id},
        )
        return int(result.scalar() or 0)
    except Exception as e:
        # 表在该库不存在 (如 meeting_templates 已被 alembic 016+038 下架) — 记 0
        await db.rollback()
        logger.debug(f"[member_cleanup] {table}.{column} count 失败 (视为 0): {e}")
        return 0


async def list_member_referencing_rows(
    db: AsyncSession,
    member_id: int,
) -> dict[str, int]:
    """只读普查: 成员 member_id 在每个 FK→members 列上的引用行数。

    Returns: {"表.列": count} — 含 0 行条目 (方便审计全貌)。
    """
    census: dict[str, int] = {}
    for table, column in MEMBER_FK_COLUMNS:
        census[f"{table}.{column}"] = await _count_rows(db, table, column, member_id)
    total_blocking = sum(
        c for k, c in census.items() if k in _BLOCKING_COLUMNS
    )
    logger.info(
        f"[member_cleanup.list_member_referencing_rows] member={member_id} "
        f"blocking_refs_total={total_blocking}"
    )
    return census


def blocking_refs(census: dict[str, int]) -> dict[str, int]:
    """从普查结果筛出会**真正阻塞** DELETE members 的条目 (RESTRICT/NO ACTION 且 count>0)。

    用法 (脚本侧): census = await list_member_referencing_rows(db, mid);
    blockers = blocking_refs(census) → 非空则必须先 reassign_member_rows 再删。
    """
    return {
        key: count
        for key, count in census.items()
        if key in _BLOCKING_COLUMNS and count > 0
    }

"""2026-07-02 v2 PR6-P10 — Celery cleanup task 物理删除前 JSON 备份 helper

事故根因 (PR6-P9): 我误传 cleanup_old_mentions_task(retention_days=0) 删了 31 条
生产 file_mentions 数据, 因为没有 backup_before_delete 机制无法回滚. 用户决策
"接受丢失", 但要求 3 个 Celery cleanup schedule (chat_history/drive/mention)
全加 backup 机制.

设计:
- **统一 SELECT → 备份 → DELETE 模式**: caller 传 (db, model, where_clause, table_name),
  helper 先 SELECT 行 (返回 row_count) → 写 JSON 备份到 /tmp/celery_cleanup_<table>_<ts>.json
  → 返回 (row_count, backup_path) 让 caller 自己 DELETE
- **不是装饰器**: 因为 3 个 cleanup service 的 SQL 拼装不一致 (chat_history 用 .where(and_(...)),
  notification 用 .where(<single condition>), drive_cleanup 内嵌). 装饰器无法
  统一拦截, 用 helper 函数更灵活
- **settings.BACKUP_BEFORE_DELETE_ENABLED = True 默认开启**: 关闭时不写备份, 直接
  返回 (SELECT count, None) — caller 仍可决定要不要 DELETE

铁律沉淀: CLAUDE.md 2026-07-02 v2 PR6-P10 章节
"""
import json
import logging
from datetime import datetime
from typing import Any, List, Optional, Tuple, Type

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logger = logging.getLogger("microbubble.cleanup_backup")


def _row_to_dict(row) -> dict:
    """ORM row → JSON-serializable dict (含 datetime/UUID 转 ISO/str)

    防御性: 不依赖 ORM `__dict__` (会丢 relationship), 用 column 反射取
    """
    result = {}
    for col in row.__table__.columns:
        value = getattr(row, col.name, None)
        if isinstance(value, datetime):
            value = value.isoformat()
        elif value is not None and not isinstance(value, (str, int, float, bool, list, dict)):
            value = str(value)
        result[col.name] = value
    return result


async def backup_rows_to_json(
    db: AsyncSession,
    *,
    model: Type,
    where_clause: Any,
    table_name: str,
    extra_metadata: Optional[dict] = None,
) -> Tuple[int, Optional[str]]:
    """先 SELECT 满足 where_clause 的行 → 写 JSON 备份 → 返回 (row_count, backup_path)

    Args:
        db: AsyncSession
        model: ORM model 类 (如 FileMention / ChatSession / Knowledge / Folder)
        where_clause: SQLAlchemy 表达式 (如 FileMention.created_at < cutoff)
        table_name: 用于备份文件名 + JSON payload 标识 (chat_sessions / knowledge / folders / file_mentions)
        extra_metadata: 可选, 写到 JSON payload 的 meta 字段 (cutoff / strategy 等)

    Returns:
        (row_count, backup_path): SELECT 出来的行数 + 备份文件路径 (None if disabled)

    铁律:
    1. 备份文件命名: `{CLEANUP_BACKUP_PREFIX}_{table_name}_{ts}.json` (容器内 /tmp)
    2. 备份时机: DELETE 之前 SELECT 完即写 (任何 DELETE 之前都有备份, 不可漏)
    3. 备份包含全字段: 每行所有 column 值, 含 datetime 转 ISO + nullable 保留
    4. 备份可恢复: scripts/restore_from_backup.py 可单条重 INSERT (id 冲突由 caller 决定)
    """
    if not settings.BACKUP_BEFORE_DELETE_ENABLED:
        logger.debug(
            f"🟡 [backup_before_delete] BACKUP_BEFORE_DELETE_ENABLED=False, "
            f"跳过 {table_name} JSON 备份 (直接 DELETE)"
        )
        # 仍然返回 count (SELECT 不跳过, 给 caller 信息)
        count_stmt = select(model).where(where_clause)
        result = await db.execute(count_stmt)
        rows = result.scalars().all()
        return len(rows), None

    # 1. SELECT 拿行
    select_stmt = select(model).where(where_clause)
    result = await db.execute(select_stmt)
    rows = result.scalars().all()
    row_count = len(rows)

    if row_count == 0:
        logger.debug(f"🟢 [backup_before_delete] {table_name} 无满足 where_clause 的行, 无需备份")
        return 0, None

    # 2. 写 JSON 备份
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{settings.CLEANUP_BACKUP_PREFIX}_{table_name}_{ts}.json"
    backup_path = f"/tmp/{backup_filename}"

    payload = {
        "backup_at": datetime.now().isoformat(),
        "table_name": table_name,
        "row_count": row_count,
        "operator_hint": "app/services/cleanup_backup.py:backup_rows_to_json",
        "meta": extra_metadata or {},
        "items": [_row_to_dict(row) for row in rows],
    }

    try:
        with open(backup_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        logger.warning(
            f"📦 [backup_before_delete] {table_name} 备份 {row_count} 行 → {backup_path} "
            f"(💡 容器重启即清空, 请及时 docker cp 到宿主机)"
        )
    except Exception as e:
        # 备份失败不能阻塞 DELETE (caller 决策), 但 logger.error 必留
        logger.error(
            f"❌ [backup_before_delete] {table_name} 备份失败: {e} (row_count={row_count})",
            exc_info=True,
        )
        # 抛出异常让 caller 决定是否中止删除 (保守策略)
        raise

    return row_count, backup_path


async def execute_backup_then_delete(
    db: AsyncSession,
    *,
    model: Type,
    where_clause: Any,
    table_name: str,
    extra_metadata: Optional[dict] = None,
) -> Tuple[int, Optional[str]]:
    """先备份后 DELETE 的 helper (一步到位, 适合简单场景)

    Args:
        同 backup_rows_to_json

    Returns:
        (deleted_count, backup_path): 实际删除行数 + 备份文件路径

    流程:
        1. SELECT 拿行 → 写 JSON 备份
        2. DELETE WHERE where_clause
        3. commit
        4. return (deleted_count, backup_path)
    """
    row_count, backup_path = await backup_rows_to_json(
        db,
        model=model,
        where_clause=where_clause,
        table_name=table_name,
        extra_metadata=extra_metadata,
    )

    # 即使 0 行也跑 DELETE (idempotent)
    delete_stmt = delete(model).where(where_clause)
    result = await db.execute(delete_stmt)
    await db.commit()

    deleted_count = result.rowcount or 0
    return deleted_count, backup_path
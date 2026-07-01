"""audit_service — v2 PR7 安全审计服务

职责:
1. log(): 同步记录审计 (admin 安全决策, 不能异步丢)
2. query(): admin 端点拉取审计 (cursor 分页 + 多种 filter)
3. cleanup_old_logs(): Celery beat 任务 (30 天物理删)

Action 标准化分类 (防止脏数据):
- read / write / delete
- login / logout
- share / unshare
- upload / download
- file_request_create / file_request_submit

设计要点:
- 同步 commit: 中间件 + service 都必须可靠, 失败不静默
- metadata JSONB: 动作特定扩展 (脱敏后存, 不存 token/密码)
- user_id NULL = 匿名 (公开提交)
- query 必须 admin role 验证 (在 endpoint 层做, service 不假设)

性能:
- created_at 索引 + (user_id, action, created_at) 复合索引
- 90 天后 Celery beat 物理清除 (敏感信息保留期)
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select, and_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import AuditLog

logger = logging.getLogger(__name__)

# 合法 action 白名单 (防止脏数据)
VALID_ACTIONS = frozenset({
    # 基础 CRUD
    "read", "write", "delete",
    # 认证
    "login", "logout", "register",
    # drive 协作
    "upload", "download", "rename", "move",
    "share", "unshare", "star", "unstar",
    "share_token_create", "share_token_revoke",
    # visibility / 权限
    "visibility_change", "permission_change",
    # 文件请求
    "file_request_create", "file_request_submit",
    "file_request_deactivate",
    # admin
    "admin_action",
    # ws + 通知
    "ws_connect", "ws_disconnect",
    "notification_read",
})

# 不脱敏的元数据字段白名单 (即只允许这些字段存 metadata)
SAFE_META_KEYS = frozenset({
    "file_name", "file_size", "file_type",
    "from_folder_id", "to_folder_id",
    "old_value", "new_value",
    "request_id", "request_token_prefix",
    "uploader_name",  # 用户填的公开名字
    "extension", "allowed_extensions",
    "share_token_prefix", "expires_at",
})


def _sanitize_meta(metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """脱敏 metadata (只保留白名单字段 + 截断超长)

    反例: 完整 token (32 字符), password, IP 内部细节
    """
    if not metadata:
        return {}
    sanitized = {}
    for k, v in metadata.items():
        if k not in SAFE_META_KEYS:
            continue
        if isinstance(v, str) and len(v) > 200:
            v = v[:200] + "..."
        sanitized[k] = v
    return sanitized


class AuditService:
    """v2 PR7: audit_log 写入 + 查询"""

    @staticmethod
    async def log(
        db: AsyncSession,
        *,
        user_id: Optional[int],
        ip_address: Optional[str],
        user_agent: Optional[str],
        method: str,
        path: str,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        status_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """同步写入审计日志

        失败不抛 (audit 不能阻塞主流程, 但要 log.warning 暴露问题)
        """
        if action not in VALID_ACTIONS:
            logger.warning(f"[Audit] 非法 action={action!r}, fall back to 'read'")
            action = "read"

        # 路径截断 (URL > 500 char 直接截)
        if len(path) > 500:
            path = path[:500] + "..."

        # IP 截断 (IPv6 max 45 char)
        if ip_address and len(ip_address) > 45:
            ip_address = ip_address[:45]

        ua_clean = user_agent[:1000] if user_agent else None

        entry = AuditLog(
            user_id=user_id,
            ip_address=ip_address,
            user_agent=ua_clean,
            method=method.upper()[:10],
            path=path,
            action=action,
            resource_type=resource_type[:20] if resource_type else None,
            resource_id=str(resource_id)[:50] if resource_id is not None else None,
            status_code=status_code,
            duration_ms=duration_ms,
            meta_data=_sanitize_meta(metadata),
        )
        db.add(entry)
        try:
            await db.commit()
            await db.refresh(entry)
        except Exception as e:
            logger.warning(f"[Audit] commit 失败: {e}", exc_info=True)
            try:
                await db.rollback()
            except Exception:
                pass
        return entry

    @staticmethod
    async def query(
        db: AsyncSession,
        *,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        ip_address: Optional[str] = None,
        path_prefix: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """admin 查询审计

        支持组合 filter: user_id + action + ip + 时间段 + 路径前缀
        page_size 上限 200 防爆
        """
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 200:
            page_size = 50

        stmt = select(AuditLog)
        count_stmt = select(func.count()).select_from(AuditLog)

        conditions = []
        if user_id is not None:
            conditions.append(AuditLog.user_id == user_id)
        if action:
            conditions.append(AuditLog.action == action)
        if ip_address:
            conditions.append(AuditLog.ip_address == ip_address)
        if path_prefix:
            conditions.append(AuditLog.path.startswith(path_prefix))
        if from_dt:
            conditions.append(AuditLog.created_at >= from_dt)
        if to_dt:
            conditions.append(AuditLog.created_at <= to_dt)

        if conditions:
            for c in conditions:
                stmt = stmt.where(c)
                count_stmt = count_stmt.where(c)

        # total
        total = (await db.execute(count_stmt)).scalar() or 0

        # page
        offset = (page - 1) * page_size
        stmt = stmt.order_by(desc(AuditLog.created_at)).offset(offset).limit(page_size)
        rows = (await db.execute(stmt)).scalars().all()

        return {
            "items": [
                {
                    "id": r.id,
                    "user_id": r.user_id,
                    "ip_address": r.ip_address,
                    "method": r.method,
                    "path": r.path,
                    "action": r.action,
                    "resource_type": r.resource_type,
                    "resource_id": r.resource_id,
                    "status_code": r.status_code,
                    "duration_ms": r.duration_ms,
                    "metadata": r.meta_data,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    async def cleanup_old_logs(
        db: AsyncSession, *, days: int = 30
    ) -> int:
        """Celery beat: 清理 N 天前的审计 (脱敏 + 物理删)

        默认 30 天 (与 file_mentions / sessions 一致)
        """
        threshold = datetime.utcnow() - timedelta(days=days)
        stmt = AuditLog.__table__.delete().where(AuditLog.created_at < threshold)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount or 0


# 全局单例
audit_service = AuditService()

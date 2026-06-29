"""聊天历史持久化模型 — #043 账号持久化（ChatGPT/Doubao 模式）

设计要点：
- ChatSession: 会话元信息（用户拥有，含 soft delete + 标签 + 收藏 + 归档）
- ChatMessage: 消息主体（role / content / rich_blocks JSONB / tool_trace / 流式中断 partial 标记）
- ChatShare: 分享链接（短 token，匿名只读，可过期）

软删除模式（对齐 Task.deleted_at + auto_purge_trash_task）：
- deleted_at: DateTime, nullable, indexed
- 30 天后 Celery beat 任务物理清除

user_id 强制关联 members.id（CASCADE）：用户销户时连带清会话
session_id 沿用前端格式 "user_<ts>_<rand>"（24 字符内），保持 localStorage 兼容

metadata 字段：SQLAlchemy 保留字，使用 Column("metadata", JSONB) 别名映射
"""

from sqlalchemy import (
    Column, BigInteger, Integer, String, Text, Boolean, ForeignKey, Index, DateTime, ARRAY,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


# 角色枚举
ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"
ROLE_SYSTEM = "system"
ROLE_TOOL = "tool"

VALID_ROLES = (ROLE_USER, ROLE_ASSISTANT, ROLE_SYSTEM, ROLE_TOOL)

# 分享权限
SHARE_PERMISSION_READ = "read"
SHARE_PERMISSION_READ_WRITE = "read_write"  # 预留，未来开放

VALID_SHARE_PERMISSIONS = (SHARE_PERMISSION_READ, SHARE_PERMISSION_READ_WRITE)


class ChatSession(Base, TimestampMixin):
    """聊天会话（账号拥有，跨设备同步）

    - id: 沿用前端 user_<ts>_<rand> 格式（如 "user_1730123456_a1b2c3"），不强制 UUID
    - user_id: 必须关联 members.id，用户销户时 CASCADE 删除
    - title: 用户可改（前端首条 user 消息前 30 字）
    - is_pinned / is_archived: 收藏 / 归档状态（前端快速访问）
    - tags: 字符串数组（如 ["work", "research", "urgent"]），GIN 索引支持 tag 过滤
    - message_count: 冗余字段，append_message 时 +1，避免 COUNT(*)
    - last_message_at: 排序字段（侧栏按时间倒序）
    - deleted_at: 软删除时间，NULL = 活跃；30 天后 Celery 物理清除
    """
    __tablename__ = "chat_sessions"

    id = Column(String(64), primary_key=True)
    user_id = Column(
        Integer, ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title = Column(String(200), nullable=False, default="新对话")
    preview = Column(Text, default="")  # 首条 user 消息前 200 字符
    is_pinned = Column(Boolean, default=False, nullable=False, index=True)
    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    tags = Column(ARRAY(String), default=list, nullable=False)  # PostgreSQL array
    message_count = Column(Integer, default=0, nullable=False)
    last_message_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True, index=True)  # 软删除

    # 关系
    messages = relationship(
        "ChatMessage",
        backref="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
        lazy="selectin",
    )
    shares = relationship(
        "ChatShare",
        backref="session",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        # 主索引：按用户拉活跃会话，按 last_message_at 倒序
        Index("ix_chat_sessions_user_active", "user_id", "is_archived", "last_message_at"),
        # 收藏会话快速访问
        Index("ix_chat_sessions_user_pinned", "user_id", "is_pinned"),
    )


class ChatMessage(Base):
    """聊天消息主体（会话附属）

    - session_id: FK chat_sessions.id (CASCADE)
    - role: user / assistant / system / tool
    - content: 主文本（Text 类型，无长度限制，但建议单条 < 1MB，超过用 file_url 存 MinIO）
    - rich_blocks: Rich Block 数组（JSONB），含 meeting_card / task_list / knowledge_ref 等
    - tool_trace: 工具调用链路（JSONB），含 tool_name / input / output / duration_ms
    - metadata: 系统元信息（JSONB），含 model / usage / intent_category / session_id（防 SQL 注入）
      注意：metadata 是 SQLAlchemy 保留字，用 Column("metadata", JSONB) 别名
    - is_partial: 流式中断的半截消息（True = 用户关闭 / 断网 / 取消）
    - is_deleted: 单条软删除（前端"重新生成"会标记旧消息 is_deleted）
    - client_msg_id: 前端生成的幂等键（同一消息多次写不会重复入库）
    """
    __tablename__ = "chat_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(
        String(64), ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    role = Column(String(20), nullable=False)  # user / assistant / system / tool
    content = Column(Text, nullable=False)
    rich_blocks = Column(JSONB, default=list, nullable=False)
    tool_trace = Column(JSONB, default=dict, nullable=False)
    # 注：metadata 是 SQLAlchemy 保留字，用 Column 别名映射到 "metadata" 列
    message_metadata = Column("metadata", JSONB, default=dict, nullable=False)
    is_partial = Column(Boolean, default=False, nullable=False, index=True)
    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    client_msg_id = Column(String(64), nullable=True, index=True)  # 幂等键
    created_at = Column(DateTime, default=TimestampMixin.created_at.default.arg, nullable=False, index=True)

    __table_args__ = (
        # 主索引：按会话拉消息，按时间正序
        Index("ix_chat_messages_session_created", "session_id", "created_at"),
        # 流式中断的半截消息快速查询
        Index("ix_chat_messages_session_partial", "session_id", "is_partial"),
    )


class ChatShare(Base):
    """聊天会话分享链接（匿名只读）

    - id: 短 token，secrets.token_urlsafe(16)（约 22 字符）
    - session_id: FK chat_sessions.id (CASCADE)，会话删除时链接失效
    - shared_by: FK members.id (SET NULL)，分享者 ID（用户销户后保留链接）
    - permission: 权限（read / read_write 预留）
    - expires_at: 过期时间，NULL = 永不过期
    - view_count: 访问次数（每次 GET /chat/shares/{token} +1）
    """
    __tablename__ = "chat_shares"

    id = Column(String(32), primary_key=True)
    session_id = Column(
        String(64), ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    shared_by = Column(
        Integer, ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )
    permission = Column(String(20), default=SHARE_PERMISSION_READ, nullable=False)
    expires_at = Column(DateTime, nullable=True, index=True)
    view_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=TimestampMixin.created_at.default.arg, nullable=False, index=True)

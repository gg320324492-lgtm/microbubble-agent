"""聊天附加文档模型 — #P5 (W-N-G+ / W2 +N)

设计:
- ChatSessionAttachedDocument: 用户级全局附加文档 (跨 session 复用)
  - 类似 ChatGPT Project Memory
  - 唯一约束 (user_id, knowledge_id) 保证幂等
- ChatMessage.attached_knowledge_ids: 本次消息引用的附件 ID (JSONB 数组)
  - 审计 + UI 引用标注
  - 默认 '[]' 兼容旧消息

约束:
- knowledge_id 必须 storage_mode='kb' (避免网盘文件泄露, 由 API 层校验)
- 用户级硬上限 8 条 (由 API 层校验)
"""
from sqlalchemy import (
    Column, BigInteger, Integer, String, ForeignKey, Index, DateTime, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class ChatSessionAttachedDocument(Base):
    """聊天附加文档 (用户级全局, 跨 session 复用)

    类似 ChatGPT Project Memory: 用户手动附加的文档
    会话期间始终作为 system prompt 的"强制参考来源"。
    """
    __tablename__ = "chat_session_attached_documents"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_id = Column(
        Integer,
        ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False,
    )
    attached_at = Column(
        DateTime,
        default=TimestampMixin.created_at.default.arg,
        nullable=False,
    )

    # 唯一约束: 同一用户对同一文档只能附加一次 (避免重复添加)
    __table_args__ = (
        UniqueConstraint("user_id", "knowledge_id", name="uq_chat_session_attached_user_doc"),
        # 主索引: 按用户查全局附加列表 (chat_stream 每次都查)
        Index("ix_chat_session_attached_user", "user_id"),
    )
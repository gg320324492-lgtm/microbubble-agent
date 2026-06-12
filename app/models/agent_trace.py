"""AgentTrace 模型 — 每次 chat 的可观测性记录

字段：
- user_id / session_id / message: 谁问的
- tool_calls: 工具调用链（JSON）
- rich_blocks: 生成的富文本块
- brief / detail: 简要/详细回复
- input_tokens / output_tokens / total_tokens
- total_duration_ms
- error: 错误（如果有）
"""
from sqlalchemy import Column, BigInteger, Integer, String, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class AgentTrace(Base, TimestampMixin):
    """Agent 对话 trace 记录（每次 chat 一条）"""
    __tablename__ = "agent_traces"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("members.id"), nullable=False, index=True)
    session_id = Column(String(64), nullable=False, index=True)
    message = Column(Text, nullable=False)

    # 工具调用链
    tool_calls = Column(JSON, default=list)   # [{name, input, output, duration_ms, error}]
    # 富文本块
    rich_blocks = Column(JSON, default=list)  # [{type, title}]

    # 回复内容
    brief = Column(Text)
    detail = Column(Text)

    # Token 统计
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    total_tokens = Column(Integer)

    # 性能
    total_duration_ms = Column(Integer)

    # 错误
    error = Column(Text, nullable=True)

    # 关系
    user = relationship("Member", backref="agent_traces", lazy="joined")

    # 复合索引
    __table_args__ = (
        Index("idx_traces_user_created", "user_id", "created_at"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "user_name": getattr(self.user, "name", None) if self.user else None,
            "session_id": self.session_id,
            "message": (self.message or "")[:200],
            "tool_count": len(self.tool_calls or []),
            "tool_names": [tc.get("name") for tc in (self.tool_calls or []) if isinstance(tc, dict)],
            "rich_block_count": len(self.rich_blocks or []),
            "rich_block_types": [rb.get("type") for rb in (self.rich_blocks or []) if isinstance(rb, dict)],
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "total_duration_ms": self.total_duration_ms,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

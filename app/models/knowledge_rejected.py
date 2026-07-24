"""knowledge_rejected 模型 — W68 第 10 批 B-2 (2026-07-24)

设计要点:
- qa-bench save_to_kb.py 全自动入库 5 道防线**任一失败**记录到本表
- B-3 auto_intake_rollback_service 24h 后自动重试 (retry_count < 3)
- 3 次失败永久挂起 → 写 knowledge_pending_review (人工审阅)
- retry_count + next_retry_at + permanent_suspended 三字段追踪生命周期

字段语义:
- qa_id: 唯一幂等键 (sha-256 短 hash 或 qa-bench 业务 ID)
- question / content / score / intent: 失败原因诊断数据 (冗余存储避免回查)
- failed_gate: 5 道防线哪一道失败 (score / content / intent / grayscale / intake_flag)
- error_msg: 错误详情 (前 500 字符, 防止超长)
- retry_count: 已重试次数 (0-3, ≥3 触发永久挂起)
- next_retry_at: 下次重试时间 (24h 间隔, NULL = 不重试)
- permanent_suspended: True = 已转 knowledge_pending_review (不再自动重试)

依赖: members 表 (FK created_by, 可空 = 系统自动入库无人)
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.models.base import TimestampMixin


# 5 道防线常量 (与 save_to_kb_service 5 defenses 对齐)
GATE_SCORE = "score"             # 防线 1: 分数门控
GATE_CONTENT = "content"         # 防线 2: 内容长度门控
GATE_INTENT = "intent"           # 防线 3: 意图白名单
GATE_GRAYSCALE = "grayscale"     # 防线 4: 灰度未命中
GATE_INTAKE_FLAG = "intake_flag"  # 防线 4+: AUTO_KB_INTAKE_ENABLED 关闭

VALID_FAILED_GATES = (
    GATE_SCORE,
    GATE_CONTENT,
    GATE_INTENT,
    GATE_GRAYSCALE,
    GATE_INTAKE_FLAG,
)


class KnowledgeRejected(Base, TimestampMixin):
    """qa-bench 高分问答入库失败记录表 (B-2 + B-3 联合追踪)

    5 道防线任一失败 → 写一行到本表 → B-3 Celery retry/suspend 跟踪.
    与 qa-bench observer JSONL 区别: observer 是短期运行时统计 (数天),
    本表是 DB 长期记录 (跨周), 永久挂起后转 knowledge_pending_review.
    """

    __tablename__ = "knowledge_rejected"

    id = Column(Integer, primary_key=True, index=True)

    # qa-bench 业务 ID (S-001 格式) + 幂等约束
    qa_id = Column(String(64), nullable=False, index=True)

    # 失败原因诊断数据 (冗余存储, 避免回查 onebyone_log.jsonl)
    question = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    score = Column(Integer, nullable=True)
    intent = Column(String(64), nullable=True)

    # 5 道防线哪一道失败 (GATE_* 常量之一)
    failed_gate = Column(String(32), nullable=False)

    # 错误详情 (前 500 字符, 防止超长)
    error_msg = Column(Text, nullable=True)

    # 额外元数据 (JSONB: 灰度档 / 调用方 / request_id / tool_calls 等)
    extra = Column(JSONB, nullable=True)

    # B-3 跟踪字段 (alembic 067 加, 见 knowledge_rejected_retry.py)
    # 注意: 模型此处也声明以兼容 Base.metadata.create_all 场景
    retry_count = Column(Integer, nullable=False, server_default="0")
    next_retry_at = Column(DateTime, nullable=True)
    permanent_suspended = Column(Boolean, nullable=False, server_default="false")

    # 系统标识 (NULL = 系统自动入库, 否则记录用户)
    created_by = Column(Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True)

    # 索引: 高频查询 (按 qa_id 幂等 + 按 failed_gate 统计 + 按永久挂起扫描)
    __table_args__ = (
        Index("ix_knowledge_rejected_qa_id", "qa_id", unique=True),
        Index("ix_knowledge_rejected_failed_gate", "failed_gate"),
        Index("ix_knowledge_rejected_permanent_suspended", "permanent_suspended"),
        Index(
            "ix_knowledge_rejected_next_retry_at",
            "next_retry_at",
            postgresql_where=(Column("permanent_suspended") == False),  # noqa: E712
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgeRejected id={self.id} qa_id={self.qa_id!r} "
            f"failed_gate={self.failed_gate!r} retry_count={self.retry_count} "
            f"permanent_suspended={self.permanent_suspended}>"
        )


class KnowledgePendingReview(Base, TimestampMixin):
    """3 次重试仍失败的条目转人工审阅 (W68 第 10 批 B-3)

    永久挂起 = knowledge_rejected.permanent_suspended=True → 写本表 →
    用户在 KB Admin UI 看到 Pending Review 列表手动审核 (approve 入库 / reject 丢弃).

    与 knowledge_rejected 关系:
    - knowledge_rejected.permanent_suspended=True 标记不再自动重试
    - knowledge_pending_review.rejected_id 关联原失败记录 (审计追溯)
    """

    __tablename__ = "knowledge_pending_review"

    id = Column(Integer, primary_key=True, index=True)

    # 关联原 rejected 记录 (审计追溯, NULL = 孤儿记录)
    rejected_id = Column(
        Integer, ForeignKey("knowledge_rejected.id", ondelete="SET NULL"), nullable=True
    )

    # 业务字段 (从 rejected 复制, 减少回查)
    qa_id = Column(String(64), nullable=False, index=True)
    question = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    score = Column(Integer, nullable=True)
    intent = Column(String(64), nullable=True)
    failed_gate = Column(String(32), nullable=False)
    last_error_msg = Column(Text, nullable=True)

    # 审阅状态: pending (默认) / approved / rejected
    review_status = Column(String(16), nullable=False, server_default="pending")
    reviewed_by = Column(Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)

    # 累计尝试次数 (= 1 首次 + 3 retry)
    total_attempts = Column(Integer, nullable=False, server_default="4")

    __table_args__ = (
        Index("ix_knowledge_pending_review_qa_id", "qa_id", unique=True),
        Index("ix_knowledge_pending_review_review_status", "review_status"),
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgePendingReview id={self.id} qa_id={self.qa_id!r} "
            f"review_status={self.review_status!r} attempts={self.total_attempts}>"
        )
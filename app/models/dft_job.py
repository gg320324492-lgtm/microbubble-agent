"""DFT/MD 任务持久化模型 — alembic 099 创建

字段:
- id: UUID, 主键
- user_id: 提交人 (FK members.id)
- tool: gaussian / gromacs / mace / pyscf
- smiles: 输入 SMILES
- params: JSONB (完整参数)
- status: queued / running / success / failed / unavailable / completed_with_warnings
- result: JSONB (完整结果 dict, 含 energy/log_path/error_msg 等)
- log_path: .log 文件路径 (Gaussian 16W 输出)
- submit_time / finish_time: UTC
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Text, Integer, DateTime, ForeignKey, Index,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class DFTJob(Base, TimestampMixin):
    """DFT/MD 异步任务记录"""
    __tablename__ = "dft_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True,
                default=lambda: uuid.uuid4())
    user_id = Column(Integer, ForeignKey("members.id", ondelete="SET NULL"),
                     nullable=True, index=True)
    tool = Column(String(32), nullable=False, index=True)
    smiles = Column(Text, nullable=False)
    params = Column(JSONB, nullable=False, default=dict)
    status = Column(String(32), nullable=False, default="queued", index=True)
    result = Column(JSONB, nullable=True)
    log_path = Column(Text, nullable=True)
    error_msg = Column(Text, nullable=True)
    submit_time = Column(DateTime(timezone=True),
                         default=lambda: datetime.now(timezone.utc))
    finish_time = Column(DateTime(timezone=True), nullable=True)

    # 复合索引: 按 tool+status 查任务列表
    __table_args__ = (
        Index("ix_dft_jobs_tool_status", "tool", "status"),
        Index("ix_dft_jobs_user_submit", "user_id", "submit_time"),
    )

    def __repr__(self) -> str:
        return (
            f"<DFTJob id={self.id} tool={self.tool} status={self.status} "
            f"smiles={self.smiles[:20]!r}>"
        )

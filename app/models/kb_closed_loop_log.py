"""KB Closed Loop Log — 闭环 audit log 表 (W68 第 10 批 B-4, 2026-07-24)

## 背景

qa-bench 自动入库 (save_to_kb.py + 5 道防线) 之前是**单点写入**:
- 写入 KB → 跑 LLM 分析 (analysis_status=done) → 后续无关联/抽检/告警闭环
- 缺 5 步 pipeline (入库 → poll → intent_classify → 标注 → 抽检) 的状态记录

本表是 `kb_closed_loop` 闭环 pipeline 的 audit trail — 每条 KB 在 5 个 stage 写一行,
用于 SLA 监控 + 失败告警 + 抽检 dashboard.

## 字段设计

- knowledge_id: FK to knowledge.id (CASCADE), 关联的 KB 行
- stage: enum (intake/poll/intent_classify/labeling/sample_check), 5 步
- status: enum (pending/success/failed/skipped), 每步状态
- duration_ms: 该 stage 耗时 (ms), 用于 SLA 监控
- error_message: 失败原因 (status=failed 时填), 用于告警
- meta_data JSONB: stage 特定扩展数据 (灰度 hash / intent / 关联 KB id / 抽检员 id)
- created_at: 该 stage 记录创建时间 (单条 KB 同 stage 可多次失败重试)

## 依赖

- knowledge 表必须存在 (FK)
- 关联表 kb_links 在同 migration 072 部署

## 实施纪律

- 0 production code 改动铁律 (W68 第 10 批): 本表 + 配套 service 全部新增, 不动老路径
- W68 第 3 批串单链纪律: down_revision 接 065_push_subscriptions (B-3 后续 PR 部署后再调)
- 0-N 关系, 不冗余 stage 维度 (避免枚举膨胀)
"""
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


# ============== 5 步 pipeline stage 枚举 (与 service 层 ClosedLoopStage 保持一致) ==============

STAGE_INTAKE = "intake"
STAGE_POLL = "poll"
STAGE_INTENT_CLASSIFY = "intent_classify"
STAGE_LABELING = "labeling"
STAGE_SAMPLE_CHECK = "sample_check"

VALID_STAGES = (
    STAGE_INTAKE,
    STAGE_POLL,
    STAGE_INTENT_CLASSIFY,
    STAGE_LABELING,
    STAGE_SAMPLE_CHECK,
)

# ============== stage 状态枚举 ==============

STATUS_PENDING = "pending"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_SKIPPED = "skipped"

VALID_STATUSES = (
    STATUS_PENDING,
    STATUS_SUCCESS,
    STATUS_FAILED,
    STATUS_SKIPPED,
)


class KbClosedLoopLog(Base):
    """KB 闭环 pipeline 5 步状态 audit

    每次 KB 进入闭环 (5 步 pipeline) 都写一行, 用于:
    - SLA 监控 (各 stage 平均 duration_ms)
    - 失败告警 (status=failed + error_message 触发 alert)
    - 抽检统计 (sample_check stage 成功率)

    同一 KB 可在多个 stage 多次写 (重试机制), 因此不 UNIQUE (knowledge_id, stage).
    """

    __tablename__ = "kb_closed_loop_log"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_id = Column(
        Integer,
        ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Knowledge.id — 受影响的 KB 行",
    )
    stage = Column(String(20), nullable=False, index=True)  # 5 步
    status = Column(String(20), nullable=False, index=True)  # 4 态
    duration_ms = Column(Integer, nullable=True)  # 该 stage 耗时
    error_message = Column(Text, nullable=True)  # 失败原因
    meta_data = Column(JSONB, nullable=True)  # 扩展数据
    created_at = Column(DateTime, nullable=False, server_default="now()", index=True)

    __table_args__ = (
        Index("idx_kb_loop_log_kb_stage", "knowledge_id", "stage"),
        Index("idx_kb_loop_log_stage_status_time", "stage", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<KbClosedLoopLog(id={self.id}, knowledge_id={self.knowledge_id}, "
            f"stage='{self.stage}', status='{self.status}', duration_ms={self.duration_ms})>"
        )
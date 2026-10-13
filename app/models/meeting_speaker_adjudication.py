"""会议说话人**人工裁决**模型 (迁移 146, 2026-10-14)

## 为什么独立成表, 而不是往 ``meetings.transcript`` 里加个 ``speaker_manual`` 标记

``reanalyze_with_speakers`` 重建转录时**只写** ``{"speaker", "text"}`` —— 丢掉
``start`` / ``end`` / ``speaker_label`` 并覆盖整个 ``speaker_mapping``
(CLAUDE.md H.9 教训)。裁决若只存在转录 JSON 里, 一次重跑就没了。
独立表只靠 (meeting_id, 时间区间) 与音频绑定, 转录怎么重建都不影响。

## 为什么需要"重跑时跳过"

会议 256 实测: 主指挥逐段听辨确认 570-623 / 729-871 / 872-910 三段**不是赵航佳**
(台账 729-871 已改判王天志, 排除她后的独立识别 27/29 也判王天志, 互相印证)。
但这 51 段距赵航佳质心仅 **0.07-0.33**, 远在 ``MATCH_THRESHOLD 0.65`` 之内 ——

    按 0.8 权重融合旧质心重算, 新质心**照样认领 52/53 段**, 零改善。

即: 这是**人工听辨的裁决**, 不是算法能收敛的量。重跑流水线会把它们判回赵航佳。
本表把裁决固化下来, 让重跑识别跳过这些区间。

## 匹配口径: 段中点落入区间

用「段中点是否落在某条裁决的 [seg_start, seg_end] 内」判定, 不用下标也不用精确相等:

- 转录重建后段边界可能微漂, 中点判定对此免疫;
- 下标会随段落增删整体错位;
- 中点唯一归属, 不会出现一条段被两条裁决重复认领。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class MeetingSpeakerAdjudication(Base, TimestampMixin):
    """一场会议里, 某段语音经人工听辨裁决后的说话人。

    重跑说话人识别时, 命中本表的区间**直接采用 ``speaker``, 不再过声纹匹配**。
    """

    __tablename__ = "meeting_speaker_adjudications"

    id = Column(Integer, primary_key=True, index=True)

    #: 所属会议。会议删除时级联清理。
    meeting_id = Column(
        Integer,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: 裁决区间 (秒), 绑定**音频**而非转录下标 —— 转录重建后仍然成立。
    seg_start = Column(Float, nullable=False)
    seg_end = Column(Float, nullable=False)

    #: 裁决时的转录下标, 仅供溯源/人工比对; **不参与匹配**。
    seg_index = Column(Integer, nullable=True)

    #: 裁决后的说话人名 (与 members.name 一致; 可为「发言人?」等占位)
    speaker = Column(String(64), nullable=False)

    #: 裁决来源, 如 'commander-listening-2026-10-13' / 'ledger'
    source = Column(String(60), nullable=True)

    #: 裁决理由 (人可读)。例: "距赵航佳质心 0.07-0.33, 属同音色区间, 算法不可分辨"
    note = Column(Text, nullable=True)

    meeting = relationship("Meeting", lazy="selectin")

    __table_args__ = (
        Index("idx_msa_meeting_start", "meeting_id", "seg_start"),
        # 区间不变量: 必须是正向区间 (零长/倒序区间会让中点匹配退化成永远不命中)
        CheckConstraint("seg_end > seg_start", name="ck_msa_range_positive"),
    )

    def covers(self, start: float, end: float) -> bool:
        """段 [start, end] 是否被本条裁决覆盖 (按段中点判定)"""
        if start is None or end is None:
            return False
        mid = (float(start) + float(end)) / 2.0
        return float(self.seg_start) <= mid <= float(self.seg_end)

    def __repr__(self) -> str:
        return (
            f"<MeetingSpeakerAdjudication(id={self.id}, meeting_id={self.meeting_id}, "
            f"{self.seg_start}-{self.seg_end} -> {self.speaker})>"
        )


__all__ = ["MeetingSpeakerAdjudication"]

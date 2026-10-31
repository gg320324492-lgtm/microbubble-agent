"""会议说话人**簇级命名**裁决模型 (迁移 148, 2026-10-31)

## 为什么独立成表, 不复用 `meeting_speaker_adjudications`

两张表的**决策粒度不同**, 混在一张表里会丢掉信息、也让回滚分不清:

| 表 | 决策粒度 | 一次决策的语义 |
|---|---|---|
| `meeting_speaker_adjudications` (146) | **段** | 「这一小段是某人」—— 人逐段听辨后的定点纠正 |
| `meeting_cluster_adjudications` (148) | **簇** | 「这一整簇是某人」—— 人听了一段样本后, 给**整簇**起名 |

簇级命名是 Phase 1f/1h 范式 («自动聚类 + 人工给簇命名») 的产物:
簇纯度 0.85 但簇命名正确率仅 0.64, 且「簇名错 ⇒ 整簇皆错」。
⇒ 人只需给**每个簇起一次名** (一次决策覆盖数十~数百段), 而不是逐段听辨。

⚠️ **不要把簇级决策展开成逐段行写进 146 表** —— 那样:
① 丢掉了「这是簇级决策」这一事实 (事后无法区分它与逐段听辨);
② 一次批量重标动辄上千行, 回滚粒度从「一个簇」退化成「上千行」;
③ 两类裁决的**冲突消解**无从下手 (同一段两表都有时谁赢? 见下)。

## 冲突消解: 段级优先

同一段若同时命中段级裁决与簇级裁决 ⇒ **段级赢**:

- 段级是**定点纠正** (人在那一段上听到了确凿证据);
- 簇级是**整簇推广** (人听的是簇里的一段样本, 推广到全簇是推断)；
- 类 20.244 确立的原则: **裁决更细 ⇒ 优先**。

⇒ 簇级裁决只填补段级裁决**没覆盖**的那些段。

## 簇的身份: member_spans

簇号 (cluster_id) 只在**一次聚类运行内**有意义 —— 重跑聚类, 同样的 c3
可能对应完全不同的一批段 ⇒ 不能拿 cluster_id 当稳定标识。

⇒ 本表存 `member_spans` (簇内各段的时间区间 [[start, end], ...]):
① **应用时**靠它把转录段映射回簇 (段中点落入任一 member_span 即属于该簇);
② `member_fingerprint` (member_spans 的 sha256 前 16 位) 用来识别
「重跑之后这个簇还是不是当初那个簇」—— 变了就该重新起名, 不能沿用旧裁决。

## 匹配口径: 段中点落入 member_span

与 146 表同口径 (段中点判定), 理由相同:
转录重建后段边界会微漂, 中点判定免疫; 下标会随段落增删整体错位。
"""
from __future__ import annotations

import hashlib
import json
from typing import List, Optional, Sequence

from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


def member_fingerprint(spans: Sequence[Sequence[float]]) -> str:
    """簇成员区间集合的指纹 (sha256 前 16 位)。

    用**排序后的区间**算 ⇒ 同一批段换顺序不影响指纹;
    段集合变了指纹就变 ⇒ 可用来判断「重跑后这个簇还是不是当初那个」。
    """
    norm = sorted([round(float(a), 3), round(float(b), 3)] for a, b in spans)
    raw = json.dumps(norm, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


class MeetingClusterAdjudication(Base, TimestampMixin):
    """一场会议里, 某个**簇**经人工起名后的说话人。

    重跑说话人识别时, 命中本表的段直接采用 ``speaker``, 不再过声纹匹配。
    """

    __tablename__ = "meeting_cluster_adjudications"

    id = Column(Integer, primary_key=True, index=True)

    #: 所属会议。**RESTRICT**: 裁决是人工听辨的不可再生成果, 误删会议不得连带销毁;
    #: 合法删除路径 (app/api/v1/meeting.py) 已在删会议前显式清本表。
    #: 外键由迁移 149 建立 (148 当时因生产库 meetings 无主键建不了, 类 20.256)。
    meeting_id = Column(
        Integer,
        ForeignKey("meetings.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    #: 簇的稳定标识 (同一会议内唯一)。人可读, 例: "c3"。
    cluster_key = Column(String(64), nullable=False)

    #: 该次聚类运行内的簇号 (仅供溯源; **不参与匹配**)。
    cluster_id = Column(Integer, nullable=True)

    #: 人工起的名字 (与 members.name 一致; 可为「发言人?」等占位)
    speaker = Column(String(64), nullable=False)

    #: 簇内段数 (冗余, 便于展示与审计)。
    n_members = Column(Integer, nullable=False, default=0)

    #: 簇内各段的时间区间 [[start, end], ...] —— **参与匹配**。
    member_spans = Column(JSONB, nullable=False, default=list)

    #: member_spans 的指纹 (见 :func:`member_fingerprint`)。
    #: 重跑聚类后指纹变了 ⇒ 簇已不是当初那个 ⇒ 旧裁决不得沿用。
    member_fingerprint = Column(String(16), nullable=True)

    #: 裁决来源, 如 'cluster-naming:2026-10-31'
    source = Column(String(60), nullable=True)

    #: 裁决理由 (人可读)。例: "听 19s 样本, 报的是臭氧杀菌课题"
    note = Column(Text, nullable=True)

    meeting = relationship("Meeting", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("meeting_id", "cluster_key", name="uq_mca_meeting_cluster_key"),
        Index("idx_mca_meeting_cluster", "meeting_id", "cluster_key"),
    )

    def covers(self, start: float, end: float) -> bool:
        """段 [start, end] 是否属于本簇 (按段中点落入任一 member_span 判定)。"""
        if start is None or end is None:
            return False
        mid = (float(start) + float(end)) / 2.0
        for span in self.member_spans or []:
            try:
                a, b = float(span[0]), float(span[1])
            except (TypeError, ValueError, IndexError):
                continue
            if a <= mid <= b:
                return True
        return False

    def __repr__(self) -> str:
        return (
            f"<MeetingClusterAdjudication(id={self.id}, meeting_id={self.meeting_id}, "
            f"cluster_key={self.cluster_key}, speaker={self.speaker}, "
            f"n_members={self.n_members})>"
        )


__all__ = ["MeetingClusterAdjudication", "member_fingerprint"]

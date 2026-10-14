"""146: meeting_speaker_adjudications —— 会议说话人人工裁决表

**Revision ID**: 146_speaker_adjudications
**Revises**: 145_kpt_content_tsvector
**Create Date**: 2026-10-14

为什么
----
会议 256 实测出一个算法**无法自行收敛**的边界:

    主指挥逐段听辨确认 570-623 / 729-871 / 872-910 三段**不是赵航佳**
    (台账 729-871 已改判王天志; 排除她后的独立识别 27/29 也判王天志, 互相印证)。
    但这 51 段距赵航佳质心仅 **0.07-0.33**, 远在 MATCH_THRESHOLD 0.65 之内。

按主指挥提供的构造法 (alpha=0.8 权重给旧质心 ``members_backup_pre_2``) 重算,
新质心与现役距离仅 0.00145, **照样认领 52/53 段 —— 零改善**;
抢占 31→32 / 兜底 7→6, 净值为零。按类 20.226 ⑧「净增益不显著为正不写库」不重建。

即: 这是**人工听辨的裁决**, 不是调质心能解决的量 —— 王天志与赵航佳音色本就接近。
本表把裁决固化, 让重跑说话人识别跳过这些区间, 避免「裁决 → 重跑 → 判回」的循环。

为什么独立成表而不是往 ``meetings.transcript`` 里塞 ``speaker_manual`` 标记
``reanalyze_with_speakers`` 重建转录时只写 ``{"speaker","text"}``, 丢掉 start/end/
speaker_label 并覆盖 speaker_mapping (CLAUDE.md H.9)。裁决只存转录 JSON 的话,
一次重跑就丢。独立表按 (meeting_id, 时间区间) 绑定**音频**, 与转录重建解耦。

匹配口径
--------
段**中点**落在某条裁决的 [seg_start, seg_end] 内即命中:

- 转录重建后段边界会微漂, 中点判定免疫;
- 下标会随段落增删整体错位;
- 中点唯一归属, 一条段不会被两条裁决重复认领。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "146_speaker_adjudications"
down_revision: Union[str, None] = "145_kpt_content_tsvector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meeting_speaker_adjudications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("seg_start", sa.Float(), nullable=False),
        sa.Column("seg_end", sa.Float(), nullable=False),
        sa.Column("seg_index", sa.Integer(), nullable=True),
        sa.Column("speaker", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=60), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "seg_end > seg_start", name="ck_msa_range_positive"
        ),
        sa.ForeignKeyConstraint(
            ["meeting_id"], ["meetings.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_meeting_speaker_adjudications_meeting_id",
        "meeting_speaker_adjudications",
        ["meeting_id"],
    )
    op.create_index(
        "ix_meeting_speaker_adjudications_id",
        "meeting_speaker_adjudications",
        ["id"],
    )
    op.create_index(
        "idx_msa_meeting_start",
        "meeting_speaker_adjudications",
        ["meeting_id", "seg_start"],
    )


def downgrade() -> None:
    op.drop_index("idx_msa_meeting_start", table_name="meeting_speaker_adjudications")
    op.drop_index(
        "ix_meeting_speaker_adjudications_id",
        table_name="meeting_speaker_adjudications",
    )
    op.drop_index(
        "ix_meeting_speaker_adjudications_meeting_id",
        table_name="meeting_speaker_adjudications",
    )
    op.drop_table("meeting_speaker_adjudications")

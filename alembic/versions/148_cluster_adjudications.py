"""148: meeting_cluster_adjudications —— 会议说话人**簇级命名**裁决表

**Revision ID**: 148_cluster_adjudications
**Revises**: 147_members_role_server_default
**Create Date**: 2026-10-31

为什么
----
Phase 1f/1h 实测把「说话人归属」拆成两半:

    聚类 (纯声学)  已经可用      —— 簇纯度 0.85 / 主导簇占比 0.83
    命名 (需要人)  是瓶颈        —— 簇命名正确率仅 0.64, 且「簇名错 ⇒ 整簇皆错」

⇒ 落地形态是「自动聚类 + 人工给**簇**起名」: 人听一段 10–20s 样本,
   给整簇起一次名 (一次决策覆盖数十~数百段), 而不是逐段听辨。

为什么不复用 146 的 ``meeting_speaker_adjudications``
--------------------------------------------------
两张表的**决策粒度不同**:

- 146: **段**级 —— 「这一小段是某人」, 定点纠正;
- 148: **簇**级 —— 「这一整簇是某人」, 一次决策覆盖整簇。

混在一张表会: ① 丢掉「这是簇级决策」的事实; ② 批量重标动辄上千行,
回滚粒度从「一个簇」退化成「上千行」; ③ 两类裁决冲突时无从消解。

⇒ 冲突消解规则: **段级优先** (段级是定点证据, 簇级是整簇推广;
类 20.244 的「裁决更细 ⇒ 优先」)。

簇的身份
--------
簇号只在**一次聚类运行内**有意义 ⇒ 本表存 ``member_spans`` (簇内各段时间区间),
应用时靠「段中点落入任一 member_span」把转录段映射回簇;
``member_fingerprint`` 用来识别「重跑聚类后这个簇还是不是当初那个」。

⚠️ ``revision`` 必须 ≤32 字符 (CI 的 alembic_version.version_num 是 VARCHAR(32),
   生产是 VARCHAR(64) ⇒ 本地/生产全绿、只有 CI 红; 类 20.227)。

⚠️ **本迁移不建指向 ``meetings.id`` 的外键** —— 生产库的 ``meetings`` 表
**没有主键也没有任何唯一约束** (2026-10-31 实测: ``pg_constraint`` 里 meetings
的 contype='p' 计数为 0, ``pg_indexes`` 里 tablename='meetings' 为空;
全库 187 张表只有 6 张有主键)。
⇒ PostgreSQL 拒绝为「无唯一约束的列」建外键 (asyncpg:
   ``there is no unique constraint matching given keys for referenced table
   "meetings"``) ⇒ 建了这条迁移就**跑不起来**。
⇒ 连带发现: **全库没有任何外键指向 meetings** —— 包括 146 号迁移建的
   ``meeting_speaker_adjudications.meeting_id`` 外键(它现在也不在库里)。
   ⇒ 推测 meetings 的主键曾被 ``DROP CONSTRAINT ... CASCADE`` 掉, 连带删掉了
   所有引用它的外键。**这是既存的 schema 漂移, 已单独立项报主指挥, 不在本迁移范围。**
⇒ 因此级联删除改为**应用层**负责 (见 ``app/api/v1/meeting.py`` 的删除路径:
   显式删 ``meeting_speaker_adjudications`` 与本表, 不用 ON DELETE CASCADE)。
⇒ ⛔ **不要**在本迁移里"顺手"给 meetings 补主键 —— 那是 187 张表级别的动作,
   必须主指挥拍板 (类 20.212: 动生产接线前先查引用)。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "148_cluster_adjudications"
down_revision: Union[str, None] = "147_members_role_server_default"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "meeting_cluster_adjudications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("cluster_key", sa.String(length=64), nullable=False),
        sa.Column("cluster_id", sa.Integer(), nullable=True),
        sa.Column("speaker", sa.String(length=64), nullable=False),
        sa.Column("n_members", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("member_spans", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("member_fingerprint", sa.String(length=16), nullable=True),
        sa.Column("source", sa.String(length=60), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        # ⛔ 不建 ForeignKeyConstraint("meeting_id" -> meetings.id):
        #    生产库 meetings 表无主键/唯一约束 ⇒ PG 拒绝 (见模块 docstring)
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "meeting_id", "cluster_key", name="uq_mca_meeting_cluster_key"
        ),
    )
    op.create_index(
        "ix_meeting_cluster_adjudications_meeting_id",
        "meeting_cluster_adjudications",
        ["meeting_id"],
    )
    op.create_index(
        "ix_meeting_cluster_adjudications_id",
        "meeting_cluster_adjudications",
        ["id"],
    )
    op.create_index(
        "idx_mca_meeting_cluster",
        "meeting_cluster_adjudications",
        ["meeting_id", "cluster_key"],
    )


def downgrade() -> None:
    op.drop_index("idx_mca_meeting_cluster", table_name="meeting_cluster_adjudications")
    op.drop_index(
        "ix_meeting_cluster_adjudications_id",
        table_name="meeting_cluster_adjudications",
    )
    op.drop_index(
        "ix_meeting_cluster_adjudications_meeting_id",
        table_name="meeting_cluster_adjudications",
    )
    op.drop_table("meeting_cluster_adjudications")

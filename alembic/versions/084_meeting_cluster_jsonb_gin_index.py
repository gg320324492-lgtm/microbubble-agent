"""W74 第 1 批 B-1: 9 表 2 索引缺口修复 (P1 fix - 084 走 B 路径)

锚点范式: W73 第 1 批 242 → W74 第 1 批 B-1 246 守恒 (+1)
串单链: down_revision = '083_commercial_tenant_isolation' (W73 B-1 083 接续)

W73 A-2 调研 commit a2243a650 §2.5 派生:
- JSON 字段缺索引: meetings.cluster_id_history / speaker_mapping / speaker_stats
- voice_confirmed_* 4 字段缺联合索引 (member)

E-1 P1 报告修复 (084 走 B 路径, 派工 v6 段 5 反馈 #7):
- 缺陷 1: 表名 meeting → meetings (E-1 真验证 ORM __tablename__='meetings')
- 缺陷 2: JSON 字段不能直接 GIN (GIN 只支持 jsonb) → ALTER COLUMN TYPE jsonb
- 修复后: 3 GIN (jsonb_path_ops) on jsonb 列 + 1 联合部分索引 on members

类 20.7 (E-1 实战沉淀): 调研派生的 schema 任务, 实施前必先 information_schema 实查
表名 + 列类型, 不能凭 docstring/ORM 文件名推断.
"""
from alembic import op
import sqlalchemy as sa


revision = "084_meeting_cluster_jsonb_gin_index"
down_revision = "083_commercial_tenant_isolation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 0. ALTER COLUMN TYPE jsonb (json → jsonb, GIN 索引要求 jsonb)
    # 这是 P1 修复的关键, 不修索引必失败
    op.execute("ALTER TABLE meetings ALTER COLUMN cluster_id_history TYPE jsonb USING cluster_id_history::jsonb")
    op.execute("ALTER TABLE meetings ALTER COLUMN speaker_mapping TYPE jsonb USING speaker_mapping::jsonb")
    op.execute("ALTER TABLE meetings ALTER COLUMN speaker_stats TYPE jsonb USING speaker_stats::jsonb")

    # 1. 3 GIN 索引 (jsonb_path_ops) — 加速 meetings JSON 字段查询
    op.create_index(
        "ix_meetings_cluster_id_history_gin",
        "meetings",
        ["cluster_id_history"],
        postgresql_using="gin",
        postgresql_ops={"cluster_id_history": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_meetings_speaker_mapping_gin",
        "meetings",
        ["speaker_mapping"],
        postgresql_using="gin",
        postgresql_ops={"speaker_mapping": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_meetings_speaker_stats_gin",
        "meetings",
        ["speaker_stats"],
        postgresql_using="gin",
        postgresql_ops={"speaker_stats": "jsonb_path_ops"},
    )

    # 2. 联合部分索引 — 加速 anchor 查询 (member → members)
    op.create_index(
        "ix_members_voice_confirmed_partial",
        "members",
        ["voice_confirmed_at", "voice_confirmed_by", "voice_confirmed_meeting_id"],
        postgresql_where="voice_confirmed_at IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("ix_members_voice_confirmed_partial", table_name="members")
    op.drop_index("ix_meetings_speaker_stats_gin", table_name="meetings")
    op.drop_index("ix_meetings_speaker_mapping_gin", table_name="meetings")
    op.drop_index(
        "ix_meetings_cluster_id_history_gin", table_name="meetings"
    )
    # 回滚 ALTER COLUMN TYPE jsonb → json
    op.execute("ALTER TABLE meetings ALTER COLUMN cluster_id_history TYPE json USING cluster_id_history::json")
    op.execute("ALTER TABLE meetings ALTER COLUMN speaker_mapping TYPE json USING speaker_mapping::json")
    op.execute("ALTER TABLE meetings ALTER COLUMN speaker_stats TYPE json USING speaker_stats::json")
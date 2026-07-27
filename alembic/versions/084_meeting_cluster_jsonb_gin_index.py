"""W74 第 1 批 B-1: 9 表 2 索引缺口修复

锚点范式: W73 第 1 批 242 → W74 第 1 批 B-1 246 守恒 (+1)
串单链: down_revision = '083_commercial_tenant_isolation' (W73 B-1 083 接续, 严格 W73 A-1 修复后单链 076→078→080→081→082→083)

W73 A-2 调研 commit a2243a650 §2.5 派生:
- JSON 字段缺索引: meeting.cluster_id_history / speaker_mapping / speaker_stats
  全是 JSON 但无 GIN 索引, 大规模会议 (>1h, >50 段) JSON 字段查询慢
- voice_confirmed_* 4 字段缺联合索引: voice_confirmed_at IS NOT NULL = anchor
  判定, 当前无部分索引 (partial index) 优化 anchor 查询

实施 4 件:
- 3 GIN 索引 (jsonb_path_ops): meeting.cluster_id_history / speaker_mapping / speaker_stats
- 1 联合部分索引 (partial index): member.voice_confirmed_at/by/meeting_id
  WHERE voice_confirmed_at IS NOT NULL

不破坏老路径: 仅在 alembic/versions/084_*.py 新增, 不动 083 老迁移, 不改
app/models/meeting.py / member.py 老字段定义. 0 production code 改动 (仅
alembic + DDL 范畴, 例同 W72 第 2 批 B-3 alembic 080).
"""
from alembic import op


revision = "084_meeting_cluster_jsonb_gin_index"
down_revision = "083_commercial_tenant_isolation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 3 GIN 索引 (jsonb_path_ops) — 加速 meeting JSON 字段查询
    # jsonb_path_ops 性能优于默认 jsonb_ops (单路径查询更紧凑)
    op.create_index(
        "ix_meeting_cluster_id_history_gin",
        "meeting",
        ["cluster_id_history"],
        postgresql_using="gin",
        postgresql_ops={"cluster_id_history": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_meeting_speaker_mapping_gin",
        "meeting",
        ["speaker_mapping"],
        postgresql_using="gin",
        postgresql_ops={"speaker_mapping": "jsonb_path_ops"},
    )
    op.create_index(
        "ix_meeting_speaker_stats_gin",
        "meeting",
        ["speaker_stats"],
        postgresql_using="gin",
        postgresql_ops={"speaker_stats": "jsonb_path_ops"},
    )

    # 2. 联合部分索引 — 加速 anchor 查询
    # voice_confirmed_at IS NOT NULL = anchor (永不再修改 embedding, 2026-06-28
    # 增量 Cross-Anchor 策略)
    op.create_index(
        "ix_member_voice_confirmed_partial",
        "member",
        ["voice_confirmed_at", "voice_confirmed_by", "voice_confirmed_meeting_id"],
        postgresql_where="voice_confirmed_at IS NOT NULL",
    )


def downgrade() -> None:
    op.drop_index("ix_member_voice_confirmed_partial", table_name="member")
    op.drop_index("ix_meeting_speaker_stats_gin", table_name="meeting")
    op.drop_index("ix_meeting_speaker_mapping_gin", table_name="meeting")
    op.drop_index(
        "ix_meeting_cluster_id_history_gin", table_name="meeting"
    )

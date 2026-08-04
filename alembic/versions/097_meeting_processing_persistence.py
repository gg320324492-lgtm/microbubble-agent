"""meeting_processing_runs + meeting_processing_stages + Meeting nullable cols

2026-08-04 (Batch B-1): 持久化会议阶段记录 + 真实媒体时长, 接 096 head.
- meeting_processing_runs: 一次初次处理或重跑一行
- meeting_processing_stages: 每阶段/每尝试一行
- meetings nullable 增加 processing_status / quality_status /
  media_duration_seconds / last_processing_run_id
- 不修改历史 migration, 严格接 096 单链

Run ``alembic upgrade head`` after this file is added.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "097_meeting_processing_persistence"
down_revision = "096_add_rag_multimodal_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. meeting_processing_runs
    op.create_table(
        "meeting_processing_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "meeting_id",
            sa.Integer(),
            sa.ForeignKey("meetings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_id", sa.String(64), nullable=True),
        sa.Column("trigger", sa.String(32), nullable=False, server_default="initial"),
        # running / success / warning / error
        sa.Column("overall_status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("requested_stages", JSONB, nullable=True),
        sa.Column("warning_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("metrics", JSONB, nullable=True),
        sa.Column("pipeline_version", sa.String(32), nullable=True),
    )
    op.create_index(
        "idx_meeting_proc_runs_meeting_started",
        "meeting_processing_runs",
        ["meeting_id", "started_at"],
    )
    op.create_index(
        "idx_meeting_proc_runs_status",
        "meeting_processing_runs",
        ["overall_status", "started_at"],
    )

    # 2. meeting_processing_stages
    op.create_table(
        "meeting_processing_stages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.BigInteger(),
            sa.ForeignKey("meeting_processing_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("stage", sa.String(32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        # started / success / retry / error / skipped
        sa.Column("status", sa.String(16), nullable=False, server_default="started"),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("retryable", sa.Boolean(), nullable=True),
        sa.Column("error_class", sa.String(64), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metrics", JSONB, nullable=True),
    )
    op.create_index(
        "idx_meeting_proc_stages_run",
        "meeting_processing_stages",
        ["run_id", "stage", "attempt"],
    )

    # 3. Meeting nullable 扩展
    op.add_column(
        "meetings",
        sa.Column(
            "processing_status",
            sa.String(16),
            nullable=True,
            comment="阶段状态 (running/success/warning/error), 与 status 字段协同",
        ),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "quality_status",
            sa.String(16),
            nullable=True,
            comment="质量评估 pass/warn/fail/not_evaluable",
        ),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "media_duration_seconds",
            sa.Integer(),
            nullable=True,
            comment="ffprobe 解码真实媒体时长, 与 audio_duration(墙钟)区分",
        ),
    )
    op.add_column(
        "meetings",
        sa.Column(
            "last_processing_run_id",
            sa.BigInteger(),
            sa.ForeignKey("meeting_processing_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "meetings_last_processing_run_id_fkey",
        "meetings",
        type_="foreignkey",
    )
    op.drop_column("meetings", "last_processing_run_id")
    op.drop_column("meetings", "media_duration_seconds")
    op.drop_column("meetings", "quality_status")
    op.drop_column("meetings", "processing_status")
    op.drop_index("idx_meeting_proc_stages_run", table_name="meeting_processing_stages")
    op.drop_table("meeting_processing_stages")
    op.drop_index("idx_meeting_proc_runs_status", table_name="meeting_processing_runs")
    op.drop_index("idx_meeting_proc_runs_meeting_started", table_name="meeting_processing_runs")
    op.drop_table("meeting_processing_runs")
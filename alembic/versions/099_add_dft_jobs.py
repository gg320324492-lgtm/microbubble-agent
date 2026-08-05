"""add dft_jobs table (Phase 5 DFT 工具集成)

Revision ID: 099_add_dft_jobs
Revises: 103_add_embedding_model_version
Create Date: 2026-08-05

串单链纪律 (CLAUDE.md W68-W92 实战): 不允许双 head, down_revision 必须接最新 head。
实测 main alembic 链顶端 (100 → 101 → 102 → 103), 103 是当前最新 head, 099 接 103 保持单链。
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "099_add_dft_jobs"
down_revision = "103_add_embedding_model_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dft_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.Integer,
                  sa.ForeignKey("members.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("tool", sa.String(32), nullable=False),
        sa.Column("smiles", sa.Text, nullable=False),
        sa.Column("params", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("log_path", sa.Text, nullable=True),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("submit_time", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("finish_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )
    op.create_index("ix_dft_jobs_user_id", "dft_jobs", ["user_id"])
    op.create_index("ix_dft_jobs_tool", "dft_jobs", ["tool"])
    op.create_index("ix_dft_jobs_status", "dft_jobs", ["status"])
    op.create_index("ix_dft_jobs_tool_status", "dft_jobs", ["tool", "status"])
    op.create_index("ix_dft_jobs_user_submit",
                    "dft_jobs", ["user_id", "submit_time"])


def downgrade() -> None:
    op.drop_index("ix_dft_jobs_user_submit", table_name="dft_jobs")
    op.drop_index("ix_dft_jobs_tool_status", table_name="dft_jobs")
    op.drop_index("ix_dft_jobs_status", table_name="dft_jobs")
    op.drop_index("ix_dft_jobs_tool", table_name="dft_jobs")
    op.drop_index("ix_dft_jobs_user_id", table_name="dft_jobs")
    op.drop_table("dft_jobs")

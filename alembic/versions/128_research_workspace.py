"""alembic migration 2026-08-21 #Step2: research_workspaces

Phase 15.0 §2 — persistent research project workspace.

设计:
- 0 业务代码改动: 仅新增 1 张表 (research_workspaces)
- status / current_stage 使用 VARCHAR(20) + server_default 守恒
- hypotheses / evidence_summary / progress_payload 三 JSONB 列存动态数据
- (user_id, status) 与 (domain, current_stage) 两组联合索引支持产品化
  dashboard 查询
- 回滚路径: alembic downgrade() 直接 drop_table
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "128_research_workspace"
down_revision = "127_research_user_profile"  # 单链守恒
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_workspaces",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("domain", sa.String(80), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("goal", sa.String(1000), nullable=True),
        sa.Column("hypotheses", sa.JSON(), nullable=True),
        sa.Column("evidence_summary", sa.JSON(), nullable=True),
        sa.Column(
            "current_stage",
            sa.String(20),
            nullable=False,
            server_default="exploration",
        ),
        sa.Column("progress_payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "idx_research_workspaces_user_id",
        "research_workspaces",
        ["user_id"],
    )
    op.create_index(
        "idx_research_workspaces_domain",
        "research_workspaces",
        ["domain"],
    )
    op.create_index(
        "idx_research_workspaces_user_status",
        "research_workspaces",
        ["user_id", "status"],
    )
    op.create_index(
        "idx_research_workspaces_domain_stage",
        "research_workspaces",
        ["domain", "current_stage"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_research_workspaces_domain_stage",
        table_name="research_workspaces",
    )
    op.drop_index(
        "idx_research_workspaces_user_status",
        table_name="research_workspaces",
    )
    op.drop_index(
        "idx_research_workspaces_domain",
        table_name="research_workspaces",
    )
    op.drop_index(
        "idx_research_workspaces_user_id",
        table_name="research_workspaces",
    )
    op.drop_table("research_workspaces")

"""alembic migration 2026-08-21 #Step1: research_user_profiles

Phase 15.0 §1 — persistent researcher identity for the Research Agent V1.0
productization layer.

设计:
- 0 业务代码改动: 仅新增 1 张表 (research_user_profiles)
- user_id UNIQUE (1 个 member 对应 1 份 profile)
- research_domain + expertise_level 联合索引加速 profile-driven intent
  classification 回查
- research_topics / research_preferences / current_projects 三 JSONB 列
  存动态 per-user 信号
- 回滚路径: alembic downgrade() 直接 drop_table
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = "127_research_user_profile"
down_revision = "107_add_summary_columns"  # 当前 main HEAD (按 CLAUDE.md 守恒)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_user_profiles",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("research_domain", sa.String(80), nullable=False),
        sa.Column("expertise_level", sa.String(20), nullable=False),
        sa.Column("research_topics", sa.JSON(), nullable=True),
        sa.Column("preferred_answer_style", sa.String(40), nullable=True),
        sa.Column("research_preferences", sa.JSON(), nullable=True),
        sa.Column("current_projects", sa.JSON(), nullable=True),
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
        sa.UniqueConstraint("user_id", name="uq_research_user_profiles_user_id"),
    )
    op.create_index(
        "idx_research_user_profiles_user_id",
        "research_user_profiles",
        ["user_id"],
    )
    op.create_index(
        "idx_research_user_profiles_domain",
        "research_user_profiles",
        ["research_domain"],
    )
    op.create_index(
        "idx_research_user_profiles_domain_expertise",
        "research_user_profiles",
        ["research_domain", "expertise_level"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_research_user_profiles_domain_expertise",
        table_name="research_user_profiles",
    )
    op.drop_index(
        "idx_research_user_profiles_domain",
        table_name="research_user_profiles",
    )
    op.drop_index(
        "idx_research_user_profiles_user_id",
        table_name="research_user_profiles",
    )
    op.drop_table("research_user_profiles")

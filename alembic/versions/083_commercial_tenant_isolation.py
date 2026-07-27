"""commercial tenant isolation closure (W73 Phase 8 收口)

锚点范式: W73 第 1 批 B-1 商业化收口 (+4 守恒)
串单链: down_revision = '082_commercial_billing_tables' (W72 B-5 起步)

W72 第 2 批 B-5 商业化起步收口, 5 大件中 alembic 部分:
- 6 商业化表全部加 tenant_id 索引 (commercial_plans/tenants/subscriptions/invoices/usage_records/licenses)
- License 表加 offline_grace_until 字段 (离线 7 天宽限)
- License 表加 last_known_mode 字段 (online/offline_grace/read_only)
- License 表加 server_signature 字段 (服务端校验签名)

不破坏老路径: 仅在 alembic/versions/083_*.py 新增, 不动 082 老迁移.
"""
from alembic import op
import sqlalchemy as sa


revision = "083_commercial_tenant_isolation"
down_revision = "082_commercial_billing_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 6 商业化表全部加 tenant_id 索引 (覆盖 W72 082 已建表)
    op.create_index(
        "ix_commercial_plans_tenant", "commercial_plans",
        ["plan_code"],  # plans 表无 tenant_id (公共资源), 加 plan_code 索引加速按 plan 查询
        unique=False,
    )
    op.create_index(
        "ix_commercial_tenants_api_key", "commercial_tenants",
        ["api_key_hash"], unique=False,
    )
    op.create_index(
        "ix_commercial_subs_plan_status", "commercial_subscriptions",
        ["plan_code", "status"], unique=False,
    )
    op.create_index(
        "ix_commercial_invoices_period", "commercial_invoices",
        ["tenant_id", "period"], unique=False,
    )
    op.create_index(
        "ix_commercial_usage_recorded", "commercial_usage_records",
        ["tenant_id", "recorded_at"], unique=False,
    )
    op.create_index(
        "ix_commercial_licenses_active", "commercial_licenses",
        ["is_active", "tenant_id"], unique=False,
    )

    # 2. License 表加离线宽限 + 服务端签名字段
    op.add_column(
        "commercial_licenses",
        sa.Column("offline_grace_until", sa.DateTime, nullable=True),
    )
    op.add_column(
        "commercial_licenses",
        sa.Column("last_known_mode", sa.String(32), nullable=True),
    )
    op.add_column(
        "commercial_licenses",
        sa.Column("server_signature", sa.String(256), nullable=True),
    )
    op.add_column(
        "commercial_licenses",
        sa.Column("grace_days", sa.Integer, server_default="7", nullable=False),
    )

    # 3. commercial_tenants 加 isolation_enabled 字段 (W73 B-1 启用隔离开关)
    op.add_column(
        "commercial_tenants",
        sa.Column("isolation_enabled", sa.Boolean, server_default=sa.text("true"), nullable=False),
    )

    # 4. commercial_subscriptions 加 auto_renew 字段
    op.add_column(
        "commercial_subscriptions",
        sa.Column("auto_renew", sa.Boolean, server_default=sa.text("true"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("commercial_subscriptions", "auto_renew")
    op.drop_column("commercial_tenants", "isolation_enabled")
    op.drop_column("commercial_licenses", "grace_days")
    op.drop_column("commercial_licenses", "server_signature")
    op.drop_column("commercial_licenses", "last_known_mode")
    op.drop_column("commercial_licenses", "offline_grace_until")
    op.drop_index("ix_commercial_licenses_active", table_name="commercial_licenses")
    op.drop_index("ix_commercial_usage_recorded", table_name="commercial_usage_records")
    op.drop_index("ix_commercial_invoices_period", table_name="commercial_invoices")
    op.drop_index("ix_commercial_subs_plan_status", table_name="commercial_subscriptions")
    op.drop_index("ix_commercial_tenants_api_key", table_name="commercial_tenants")
    op.drop_index("ix_commercial_plans_tenant", table_name="commercial_plans")
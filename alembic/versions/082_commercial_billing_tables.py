"""commercial billing tables (W72 Phase 8 起步)

锚点范式: W72 第 2 批 B-5 商业化启动 (+9 守恒)
串单链: down_revision = '081_drive_share_enhancements' (派工预设)

6 张表:
- commercial_plans
- commercial_tenants
- commercial_subscriptions
- commercial_invoices
- commercial_usage_records
- commercial_licenses
"""
from alembic import op
import sqlalchemy as sa


revision = "082_commercial_billing_tables"
down_revision = "081_drive_share_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. commercial_plans
    op.create_table(
        "commercial_plans",
        sa.Column("plan_code", sa.String(32), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("monthly_price_cents", sa.Integer, server_default="0"),
        sa.Column("yearly_price_cents", sa.Integer, server_default="0"),
        sa.Column("currency", sa.String(8), server_default="CNY"),
        sa.Column("limits", sa.JSON, default={}),
        sa.Column("features", sa.JSON, default=[]),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )

    # 2. commercial_tenants
    op.create_table(
        "commercial_tenants",
        sa.Column("tenant_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("contact_email", sa.String(255), nullable=False),
        sa.Column("plan_code", sa.String(32), sa.ForeignKey("commercial_plans.plan_code"), server_default="free"),
        sa.Column("status", sa.String(32), server_default="active"),
        sa.Column("api_key_hash", sa.String(128)),
        sa.Column("isolation_token", sa.String(64)),
        sa.Column("metadata", sa.JSON, default={}),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_commercial_tenants_status", "commercial_tenants", ["status"])
    op.create_index("ix_commercial_tenants_plan", "commercial_tenants", ["plan_code"])

    # 3. commercial_subscriptions
    op.create_table(
        "commercial_subscriptions",
        sa.Column("subscription_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("commercial_tenants.tenant_id"), nullable=False),
        sa.Column("plan_code", sa.String(32), sa.ForeignKey("commercial_plans.plan_code"), nullable=False),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), server_default="active"),
        sa.Column("started_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("cancelled_at", sa.DateTime, nullable=True),
        sa.Column("invoice_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_commercial_subs_tenant", "commercial_subscriptions", ["tenant_id"])
    op.create_index("ix_commercial_subs_status", "commercial_subscriptions", ["status"])

    # 4. commercial_invoices
    op.create_table(
        "commercial_invoices",
        sa.Column("invoice_id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("commercial_tenants.tenant_id"), nullable=False),
        sa.Column("plan_code", sa.String(32), sa.ForeignKey("commercial_plans.plan_code"), nullable=False),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(8), server_default="CNY"),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("payment_provider", sa.String(32), nullable=True),
        sa.Column("payment_ref", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("paid_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_commercial_invoices_tenant", "commercial_invoices", ["tenant_id"])
    op.create_index("ix_commercial_invoices_status", "commercial_invoices", ["status"])

    # 5. commercial_usage_records
    op.create_table(
        "commercial_usage_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("commercial_tenants.tenant_id"), nullable=False),
        sa.Column("metric", sa.String(64), nullable=False),
        sa.Column("value", sa.Numeric(20, 4), nullable=False),
        sa.Column("metadata", sa.JSON, default={}),
        sa.Column("recorded_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_commercial_usage_tenant_metric", "commercial_usage_records", ["tenant_id", "metric"])
    op.create_index("ix_commercial_usage_recorded_at", "commercial_usage_records", ["recorded_at"])

    # 6. commercial_licenses
    op.create_table(
        "commercial_licenses",
        sa.Column("license_key_hash", sa.String(128), primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("commercial_tenants.tenant_id"), nullable=False),
        sa.Column("tier", sa.String(32), nullable=False),
        sa.Column("last_verified_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
    )
    op.create_index("ix_commercial_licenses_tenant", "commercial_licenses", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_commercial_licenses_tenant", table_name="commercial_licenses")
    op.drop_table("commercial_licenses")
    op.drop_index("ix_commercial_usage_recorded_at", table_name="commercial_usage_records")
    op.drop_index("ix_commercial_usage_tenant_metric", table_name="commercial_usage_records")
    op.drop_table("commercial_usage_records")
    op.drop_index("ix_commercial_invoices_status", table_name="commercial_invoices")
    op.drop_index("ix_commercial_invoices_tenant", table_name="commercial_invoices")
    op.drop_table("commercial_invoices")
    op.drop_index("ix_commercial_subs_status", table_name="commercial_subscriptions")
    op.drop_index("ix_commercial_subs_tenant", table_name="commercial_subscriptions")
    op.drop_table("commercial_subscriptions")
    op.drop_index("ix_commercial_tenants_plan", table_name="commercial_tenants")
    op.drop_index("ix_commercial_tenants_status", table_name="commercial_tenants")
    op.drop_table("commercial_tenants")
    op.drop_table("commercial_plans")

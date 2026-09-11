"""recreate commercial_* tables lost in schema drift (2026-09-11)

背景 (类 20.142 变体): 生产 alembic_version 已被 stamp 推进到 137, 但 082/083
建的 6 张商业化表在库内实际不存在 — 8/28 事故恢复 + 8/30 备份补恢复链路里
DB 曾 DROP+CREATE 并从旧备份还原, alembic 版本按代码 stamp 前跳, 082/083
的 upgrade() 从未在当前库上真跑。症状: /commercial/billing/* 与
/commercial/tenants/* 每个请求 UndefinedTableError 500 (24h 内 22 次)。

修法: 082+083 合并重建 (表结构与两迁移叠加后的终态一致), 每张表/索引先用
inspector 判存 — 若某环境 (如全新库 create_all) 已有该表则跳过, 全幂等。
不回填数据: 商业化功能从未在此生产库启用过, 6 表空即正确终态;
/commercial/billing/plans 返回 [] 而非 500。

串单链: down_revision = '137_drive_folder_shares_cols' (当前 head)。
"""
from alembic import op
import sqlalchemy as sa


revision = "138_recreate_commercial_tables"
down_revision = "137_drive_folder_shares_cols"
branch_labels = None
depends_on = None


TABLES = [
    "commercial_plans",
    "commercial_tenants",
    "commercial_subscriptions",
    "commercial_invoices",
    "commercial_usage_records",
    "commercial_licenses",
]


def _inspector():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    insp = _inspector()
    existing = set(insp.get_table_names())

    if "commercial_plans" not in existing:
        op.create_table(
            "commercial_plans",
            sa.Column("plan_code", sa.String(32), primary_key=True),
            sa.Column("display_name", sa.String(128), nullable=False),
            sa.Column("monthly_price_cents", sa.Integer, server_default="0"),
            sa.Column("yearly_price_cents", sa.Integer, server_default="0"),
            sa.Column("currency", sa.String(8), server_default="CNY"),
            sa.Column("limits", sa.JSON),
            sa.Column("features", sa.JSON),
            sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
        )
        op.create_index("ix_commercial_plans_tenant", "commercial_plans", ["plan_code"])

    if "commercial_tenants" not in existing:
        op.create_table(
            "commercial_tenants",
            sa.Column("tenant_id", sa.String(64), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("contact_email", sa.String(255), nullable=False),
            sa.Column("plan_code", sa.String(32), sa.ForeignKey("commercial_plans.plan_code"), server_default="free"),
            sa.Column("status", sa.String(32), server_default="active"),
            sa.Column("api_key_hash", sa.String(128)),
            sa.Column("isolation_token", sa.String(64)),
            sa.Column("metadata", sa.JSON),
            sa.Column("isolation_enabled", sa.Boolean, server_default=sa.text("true"), nullable=False),
            sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
        )
        op.create_index("ix_commercial_tenants_status", "commercial_tenants", ["status"])
        op.create_index("ix_commercial_tenants_plan", "commercial_tenants", ["plan_code"])
        op.create_index("ix_commercial_tenants_api_key", "commercial_tenants", ["api_key_hash"])

    if "commercial_subscriptions" not in existing:
        op.create_table(
            "commercial_subscriptions",
            sa.Column("subscription_id", sa.String(64), primary_key=True),
            sa.Column("tenant_id", sa.String(64), sa.ForeignKey("commercial_tenants.tenant_id"), nullable=False),
            sa.Column("plan_code", sa.String(32), sa.ForeignKey("commercial_plans.plan_code"), nullable=False),
            sa.Column("period", sa.String(16), nullable=False),
            sa.Column("status", sa.String(32), server_default="active"),
            sa.Column("auto_renew", sa.Boolean, server_default=sa.text("true"), nullable=False),
            sa.Column("started_at", sa.DateTime, server_default=sa.text("now()")),
            sa.Column("expires_at", sa.DateTime, nullable=False),
            sa.Column("cancelled_at", sa.DateTime, nullable=True),
            sa.Column("invoice_id", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()")),
        )
        op.create_index("ix_commercial_subs_tenant", "commercial_subscriptions", ["tenant_id"])
        op.create_index("ix_commercial_subs_status", "commercial_subscriptions", ["status"])
        op.create_index("ix_commercial_subs_plan_status", "commercial_subscriptions", ["plan_code", "status"])

    if "commercial_invoices" not in existing:
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
        op.create_index("ix_commercial_invoices_period", "commercial_invoices", ["tenant_id", "period"])

    if "commercial_usage_records" not in existing:
        op.create_table(
            "commercial_usage_records",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.String(64), sa.ForeignKey("commercial_tenants.tenant_id"), nullable=False),
            sa.Column("metric", sa.String(64), nullable=False),
            sa.Column("value", sa.Numeric(20, 4), nullable=False),
            sa.Column("metadata", sa.JSON),
            sa.Column("recorded_at", sa.DateTime, server_default=sa.text("now()")),
        )
        op.create_index("ix_commercial_usage_tenant_metric", "commercial_usage_records", ["tenant_id", "metric"])
        op.create_index("ix_commercial_usage_recorded_at", "commercial_usage_records", ["recorded_at"])
        op.create_index("ix_commercial_usage_recorded", "commercial_usage_records", ["tenant_id", "recorded_at"])

    if "commercial_licenses" not in existing:
        op.create_table(
            "commercial_licenses",
            sa.Column("license_key_hash", sa.String(128), primary_key=True),
            sa.Column("tenant_id", sa.String(64), sa.ForeignKey("commercial_tenants.tenant_id"), nullable=False),
            sa.Column("tier", sa.String(32), nullable=False),
            sa.Column("last_verified_at", sa.DateTime, server_default=sa.text("now()")),
            sa.Column("expires_at", sa.DateTime, nullable=True),
            sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
            sa.Column("offline_grace_until", sa.DateTime, nullable=True),
            sa.Column("last_known_mode", sa.String(32), nullable=True),
            sa.Column("server_signature", sa.String(256), nullable=True),
            sa.Column("grace_days", sa.Integer, server_default="7", nullable=False),
        )
        op.create_index("ix_commercial_licenses_tenant", "commercial_licenses", ["tenant_id"])
        op.create_index("ix_commercial_licenses_active", "commercial_licenses", ["is_active", "tenant_id"])


def downgrade() -> None:
    for t in reversed(TABLES):
        op.drop_table(t)  # 索引随表自动删除

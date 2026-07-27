"""billing payment tables (W74 第 1 批 B-2 真支付接入)

锚点范式: W73 第 1 批 B-1 242 → W74 第 1 批 B-2 247 守恒 (+5)
串单链: down_revision = '083_commercial_tenant_isolation' (W73 B-1 083 接续)

W74 第 1 批 B-2 5 大件 alembic 部分:
- 4 张新表 (W74 B-2 真支付接入):
  1. billing_payments: 支付记录 (payment_id PK + invoice_id FK + provider + status + amount + intent_id + provider_ref + 状态机)
  2. billing_subscriptions_audit: 订阅审计 (subscription_id + tenant_id + action + actor + 5 字段, 与 commercial_subscriptions 配套审计)
  3. billing_invoices_ext: invoice 扩展 (与 commercial_invoices 配套, 加 provider + intent_id + refund_amount 等)
  4. billing_webhook_events: webhook 事件日志 (event_id PK + provider + event_type + payload_size + processed_at + 幂等去重)

派工 v6 段 5 反馈 #6 实战:
- 3 支付渠道 (stripe / alipay / wechat_pay) 字段完整
- 4 表全部加 tenant_id 索引 (W72 B-5 082 索引纪律复用)
- 状态机: pending → success / failed / refunded

不破坏老路径: 仅在 alembic/versions/085_*.py 新增, 不动 082/083 老迁移,
不改 app/models/billing.py 老字段定义. 0 production code 改动铁律.
"""
from alembic import op
import sqlalchemy as sa


revision = "085_billing_payment_tables"
down_revision = "084_meeting_cluster_jsonb_gin_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. billing_payments: 支付记录主表
    op.create_table(
        "billing_payments",
        sa.Column("payment_id", sa.String(64), primary_key=True),
        sa.Column("invoice_id", sa.String(64), sa.ForeignKey("commercial_invoices.invoice_id"), nullable=False),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("commercial_tenants.tenant_id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),  # stripe / alipay / wechat_pay / mock
        sa.Column("intent_id", sa.String(128), nullable=True),
        sa.Column("provider_ref", sa.String(128), nullable=True),
        sa.Column("amount_cents", sa.Integer, nullable=False),
        sa.Column("currency", sa.String(8), server_default="CNY"),
        sa.Column("status", sa.String(32), server_default="pending"),  # pending / success / failed / refunded
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("client_secret", sa.String(128), nullable=True),
        sa.Column("redirect_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_billing_payments_invoice", "billing_payments", ["invoice_id"])
    op.create_index("ix_billing_payments_tenant", "billing_payments", ["tenant_id"])
    op.create_index("ix_billing_payments_provider_status", "billing_payments", ["provider", "status"])

    # 2. billing_subscriptions_audit: 订阅审计 (与 commercial_subscriptions 配套)
    op.create_table(
        "billing_subscriptions_audit",
        sa.Column("audit_id", sa.String(64), primary_key=True),
        sa.Column("subscription_id", sa.String(64), sa.ForeignKey("commercial_subscriptions.subscription_id"), nullable=False),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("commercial_tenants.tenant_id"), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),  # created / renewed / cancelled / expired / plan_changed
        sa.Column("actor", sa.String(128), nullable=True),  # 操作者 (system / tenant_id / admin)
        sa.Column("old_plan_code", sa.String(32), nullable=True),
        sa.Column("new_plan_code", sa.String(32), nullable=True),
        sa.Column("details", sa.JSON, default={}),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_billing_subs_audit_tenant", "billing_subscriptions_audit", ["tenant_id"])
    op.create_index("ix_billing_subs_audit_sub", "billing_subscriptions_audit", ["subscription_id"])
    op.create_index("ix_billing_subs_audit_action", "billing_subscriptions_audit", ["action"])

    # 3. billing_invoices_ext: invoice 扩展 (W74 B-2 加 provider + intent_id + refund_amount)
    op.create_table(
        "billing_invoices_ext",
        sa.Column("ext_id", sa.String(64), primary_key=True),
        sa.Column("invoice_id", sa.String(64), sa.ForeignKey("commercial_invoices.invoice_id"), nullable=False, unique=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("commercial_tenants.tenant_id"), nullable=False),
        sa.Column("last_payment_id", sa.String(64), sa.ForeignKey("billing_payments.payment_id"), nullable=True),
        sa.Column("refund_amount_cents", sa.Integer, server_default="0"),
        sa.Column("refund_reason", sa.String(256), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("now()"), onupdate=sa.text("now()")),
    )
    op.create_index("ix_billing_invoices_ext_tenant", "billing_invoices_ext", ["tenant_id"])
    op.create_index("ix_billing_invoices_ext_payment", "billing_invoices_ext", ["last_payment_id"])

    # 4. billing_webhook_events: webhook 事件日志 (幂等去重)
    op.create_table(
        "billing_webhook_events",
        sa.Column("event_id", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(32), nullable=False),  # stripe / alipay / wechat_pay
        sa.Column("event_type", sa.String(64), nullable=True),  # payment_intent.succeeded / charge.refunded 等
        sa.Column("payload_size", sa.Integer, server_default="0"),
        sa.Column("signature_verified", sa.Boolean, server_default=sa.text("true")),
        sa.Column("processed", sa.Boolean, server_default=sa.text("true")),
        sa.Column("received_at", sa.DateTime, server_default=sa.text("now()")),
    )
    op.create_index("ix_billing_webhook_events_provider", "billing_webhook_events", ["provider"])
    op.create_index("ix_billing_webhook_events_received", "billing_webhook_events", ["received_at"])


def downgrade() -> None:
    op.drop_index("ix_billing_webhook_events_received", table_name="billing_webhook_events")
    op.drop_index("ix_billing_webhook_events_provider", table_name="billing_webhook_events")
    op.drop_table("billing_webhook_events")

    op.drop_index("ix_billing_invoices_ext_payment", table_name="billing_invoices_ext")
    op.drop_index("ix_billing_invoices_ext_tenant", table_name="billing_invoices_ext")
    op.drop_table("billing_invoices_ext")

    op.drop_index("ix_billing_subs_audit_action", table_name="billing_subscriptions_audit")
    op.drop_index("ix_billing_subs_audit_sub", table_name="billing_subscriptions_audit")
    op.drop_index("ix_billing_subs_audit_tenant", table_name="billing_subscriptions_audit")
    op.drop_table("billing_subscriptions_audit")

    op.drop_index("ix_billing_payments_provider_status", table_name="billing_payments")
    op.drop_index("ix_billing_payments_tenant", table_name="billing_payments")
    op.drop_index("ix_billing_payments_invoice", table_name="billing_payments")
    op.drop_table("billing_payments")
"""
商业化 SaaS 平台 — billing gateway (mock)

W72 Phase 8 起步. 计费网关**不接真支付**, 预留接口 + mock 支付流程.
- plan: free / pro / enterprise
- 计费周期: monthly / yearly
- 接口: Stripe / Alipay / WeChat Pay (mock, 后续 W76 实物接入)
"""
from __future__ import annotations

import json
import logging
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

BILLING_STORE_PATH = Path(os.getenv("MICROBUBBLE_BILLING_STORE", "/app/data/billing.json"))

# 商业化定价 (mock, 后续 W76 实物接入后调整)
PLAN_PRICING = {
    "free": {"monthly": 0, "yearly": 0, "limits": {"api_calls": 1000, "storage_mb": 100}},
    "pro": {"monthly": 299, "yearly": 2988, "limits": {"api_calls": 50000, "storage_mb": 10240}},
    "enterprise": {"monthly": 1999, "yearly": 19988, "limits": {"api_calls": 500000, "storage_mb": 102400}},
}

PAYMENT_PROVIDERS = ["stripe", "alipay", "wechat_pay"]  # mock, 只占位


@dataclass
class Invoice:
    invoice_id: str
    tenant_id: str
    plan: str
    period: str  # monthly / yearly
    amount_cents: int
    currency: str = "CNY"
    status: str = "pending"  # pending / paid / failed / refunded
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    paid_at: Optional[str] = None
    payment_provider: Optional[str] = None
    payment_ref: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "invoice_id": self.invoice_id,
            "tenant_id": self.tenant_id,
            "plan": self.plan,
            "period": self.period,
            "amount_cents": self.amount_cents,
            "currency": self.currency,
            "status": self.status,
            "created_at": self.created_at,
            "paid_at": self.paid_at,
            "payment_provider": self.payment_provider,
            "payment_ref": self.payment_ref,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Invoice":
        return cls(**d)


@dataclass
class Subscription:
    tenant_id: str
    plan: str
    period: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = field(default_factory=lambda: (datetime.now(timezone.utc) + timedelta(days=30)).isoformat())
    status: str = "active"
    invoice_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "plan": self.plan,
            "period": self.period,
            "started_at": self.started_at,
            "expires_at": self.expires_at,
            "status": self.status,
            "invoice_id": self.invoice_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Subscription":
        return cls(**d)


class BillingGateway:
    """Billing gateway (mock version)."""

    def __init__(self, store_path: Path = BILLING_STORE_PATH):
        self.store_path = store_path
        self.invoices: dict[str, Invoice] = {}
        self.subscriptions: dict[str, Subscription] = {}
        self._load()

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        try:
            with open(self.store_path) as f:
                raw = json.load(f)
            self.invoices = {i: Invoice.from_dict(d) for i, d in raw.get("invoices", {}).items()}
            self.subscriptions = {t: Subscription.from_dict(d) for t, d in raw.get("subscriptions", {}).items()}
        except Exception as e:
            logger.warning(f"billing store load failed: {e}")

    def _flush(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.store_path, "w") as f:
            json.dump({
                "invoices": {i: inv.to_dict() for i, inv in self.invoices.items()},
                "subscriptions": {t: sub.to_dict() for t, sub in self.subscriptions.items()},
            }, f, indent=2)

    def get_plan(self, plan: str) -> dict:
        return PLAN_PRICING.get(plan, PLAN_PRICING["free"])

    def list_plans(self) -> dict:
        return PLAN_PRICING

    def create_invoice(self, tenant_id: str, plan: str, period: str, provider: str = "mock") -> Invoice:
        """创建账单 (mock)."""
        if plan not in PLAN_PRICING:
            raise ValueError(f"unknown plan: {plan}")
        if period not in ("monthly", "yearly"):
            raise ValueError(f"unknown period: {period}")
        if provider not in PAYMENT_PROVIDERS + ["mock"]:
            raise ValueError(f"unknown provider: {provider}")

        pricing = PLAN_PRICING[plan]
        amount_cents = pricing[period] * 100  # 分

        invoice_id = "inv_" + secrets.token_hex(6)
        invoice = Invoice(
            invoice_id=invoice_id,
            tenant_id=tenant_id,
            plan=plan,
            period=period,
            amount_cents=amount_cents,
            payment_provider=provider,
        )
        self.invoices[invoice_id] = invoice
        self._flush()
        logger.info(f"created invoice {invoice_id} for {tenant_id} ({plan}/{period})")
        return invoice

    def pay_invoice(self, invoice_id: str, payment_ref: Optional[str] = None) -> Invoice:
        """Mock 支付成功 (后续 W76 接真实支付)."""
        if invoice_id not in self.invoices:
            raise ValueError(f"invoice {invoice_id} not found")
        inv = self.invoices[invoice_id]
        if inv.status != "pending":
            raise ValueError(f"invoice {invoice_id} already {inv.status}")
        inv.status = "paid"
        inv.paid_at = datetime.now(timezone.utc).isoformat()
        inv.payment_ref = payment_ref or f"mock_{secrets.token_hex(8)}"

        # 同步创建 subscription
        days = 30 if inv.period == "monthly" else 365
        sub = Subscription(
            tenant_id=inv.tenant_id,
            plan=inv.plan,
            period=inv.period,
            expires_at=(datetime.now(timezone.utc) + timedelta(days=days)).isoformat(),
            status="active",
            invoice_id=invoice_id,
        )
        self.subscriptions[inv.tenant_id] = sub
        self._flush()
        logger.info(f"invoice {invoice_id} paid, subscription activated for {inv.tenant_id}")
        return inv

    def get_subscription(self, tenant_id: str) -> Optional[Subscription]:
        return self.subscriptions.get(tenant_id)

    def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        return self.invoices.get(invoice_id)


_singleton: Optional[BillingGateway] = None


def get_gateway() -> BillingGateway:
    global _singleton
    if _singleton is None:
        _singleton = BillingGateway()
    return _singleton

"""私有化部署 4 层架构变体配置 (W79 第 1 批 B-2).

W78 C-1 commit 4ce9dd5d3 SaaS 平台部署 4 层架构:
  镜像层 / SaaS 平台层 / 计费服务层 / 前端层

本模块给出**每层的私有化变体**声明 + 校验函数, 供:
- scripts/private_deployment_monitor.sh 静态巡检
- tests/test_w79_commercial_private_deployment_e2e.py e2e 断言
- docs/w79-...-runbook 部署 checklist

私有化 vs SaaS 4 大差异:
1. offline-first  — 无外网时靠 license 离线 7 天宽限继续跑 (SaaS 强制在线)
2. single-tenant  — 6 商业化表仍在, 但只落 1 个 tenant_id (SaaS multi-tenant)
3. billing 可降级 — 离线时支付网关不可达 → mock 降级 (SaaS 必真支付)
4. 公网隐藏      — BillingView / PlanSelector 不暴露公网 (SaaS 公网自助购买)

0 production code 改动铁律例外 2 已批 (纯新增, 不 import app/ 老链路).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Literal

# ===== 私有化部署常量 (W73 B-5 + W78 C-1 复用口径) =====

OFFLINE_GRACE_DAYS = int(os.getenv("MICROBUBBLE_LICENSE_GRACE_DAYS", "7"))
"""离线宽限天数 — 与 app/services/license_service.OFFLINE_GRACE_DAYS 及
docker/commercial/license-check.py GRACE_DAYS 三处口径必须一致 (=7)."""

SINGLE_TENANT_ID = os.getenv("MICROBUBBLE_PRIVATE_TENANT_ID", "private-default")
"""私有化单租户 tenant_id — 6 商业化表全部落这一个租户."""

PRIVATE_PUBLIC_HIDDEN_VIEWS = (
    "BillingView.vue",
    "PlanSelector.vue",
    "PaymentMethodSelector.vue",
    "PaymentResultView.vue",
)
"""公网隐藏的 4 前端商业化视图 — 私有化部署下由 nginx deny 拦截, 仅内网可达."""

SIX_COMMERCIAL_TABLES = (
    "commercial_plans",
    "commercial_tenants",
    "commercial_subscriptions",
    "commercial_invoices",
    "commercial_usage_records",
    "commercial_licenses",
)
"""6 商业化表 (W72 B-5 alembic 082 + W73 B-1 alembic 083 索引) — 私有化单租户变体沿用同一 schema."""

SAAS_PLATFORM_SCRIPTS = (
    "tenant_manager",
    "usage_tracker",
    "billing_gateway",
    "audit_export",
    "deploy",
)
"""W73 B-5 SaaS 平台 5 脚本 — 私有化变体全部保留, 以 single-tenant 模式运行."""

LicenseMode = Literal["online", "offline_grace", "read_only", "revoked", "unknown"]

READ_ONLY_MODES: tuple[str, ...] = ("read_only", "revoked")
"""触发自动降级 read-only 的 license mode — 与 license_service.verify_license 返回值对齐."""


# ===== 4 层架构私有化变体声明 =====


@dataclass(frozen=True)
class LayerVariant:
    """单层私有化变体声明."""

    layer: str
    saas_baseline: str
    private_variant: str
    artifacts: tuple[str, ...] = field(default_factory=tuple)


FOUR_LAYER_PRIVATE_VARIANTS: tuple[LayerVariant, ...] = (
    LayerVariant(
        layer="镜像层",
        saas_baseline="docker/Dockerfile.commercial + entrypoint.sh + license-check.py (W73 B-5)",
        private_variant="docker/Dockerfile.private — offline-first, MICROBUBBLE_PRIVATE=1, "
        "MICROBUBBLE_OFFLINE_FIRST=1, 继承商业化 watermark + 非 root + read-only fs",
        artifacts=(
            "docker/Dockerfile.private",
            "docker/commercial/entrypoint.sh",
            "docker/commercial/license-check.py",
        ),
    ),
    LayerVariant(
        layer="SaaS 平台层",
        saas_baseline="commercial/saas-platform 5 脚本 multi-tenant (W73 B-5 + W74 B-1)",
        private_variant="single-tenant 变体 — 5 脚本全保留, tenant_id 固定 SINGLE_TENANT_ID, "
        "tenant_manager 不开放动态建租户",
        artifacts=tuple(f"commercial/saas-platform/{s}.py" for s in SAAS_PLATFORM_SCRIPTS),
    ),
    LayerVariant(
        layer="计费服务层",
        saas_baseline="W78 B-2 真支付生产 key (3 SDK + 重放保护 + Webhook 签名, commit 41c879726)",
        private_variant="离线可降级 mock — 支付网关不可达时走 billing_degrade.py, "
        "BILLING_LIVE_ENABLED 默认 false 硬门控不变 (类 20.13)",
        artifacts=(
            "commercial/private-deployment/billing_degrade.py",
            "app/services/billing/stripe_sdk.py",
            "app/services/billing/alipay_sdk.py",
            "app/services/billing/wechat_pay_sdk.py",
        ),
    ),
    LayerVariant(
        layer="前端层",
        saas_baseline="web/src/views/commercial 4 视图公网自助购买 (W73 B-5 + W77 C-1)",
        private_variant="公网隐藏 — 4 视图仅内网可达, nginx deny 公网路径, "
        "read-only 模式下 PlanSelector 提交按钮禁用",
        artifacts=tuple(f"web/src/views/commercial/{v}" for v in PRIVATE_PUBLIC_HIDDEN_VIEWS),
    ),
)


def layer_names() -> tuple[str, ...]:
    """返回 4 层名称, 供 monitor / e2e 断言层数完整."""
    return tuple(v.layer for v in FOUR_LAYER_PRIVATE_VARIANTS)


def get_layer(layer: str) -> LayerVariant:
    """按层名取变体声明, 未知层抛 KeyError."""
    for v in FOUR_LAYER_PRIVATE_VARIANTS:
        if v.layer == layer:
            return v
    raise KeyError(f"unknown layer: {layer}")


# ===== 私有化运行时判定 =====


def is_private_deployment() -> bool:
    """当前进程是否跑在私有化部署镜像内 (Dockerfile.private 注入 MICROBUBBLE_PRIVATE=1)."""
    return os.getenv("MICROBUBBLE_PRIVATE", "0") == "1"


def is_offline_first() -> bool:
    """offline-first 开关 — 开启后 license 在线校验失败不致命, 走离线宽限."""
    return os.getenv("MICROBUBBLE_OFFLINE_FIRST", "0") == "1"


def should_degrade_read_only(license_mode: str) -> bool:
    """license mode 是否触发自动降级 read-only.

    W73 B-5 license_service.verify_license 返回 mode ∈
    {online, offline_grace, read_only, revoked, unknown}:
    - online / offline_grace → 正常可写
    - read_only / revoked    → 自动降级只读
    - unknown                → 保守降级只读 (license 不存在 / 租户不匹配)
    """
    return license_mode in READ_ONLY_MODES or license_mode == "unknown"


def grace_days_remaining(days_since_last_verified: int) -> int:
    """剩余离线宽限天数 (负数表示已超期 → read-only)."""
    return OFFLINE_GRACE_DAYS - days_since_last_verified


def summary() -> dict:
    """私有化部署配置快照 — monitor / runbook 打印用."""
    return {
        "version": "1.0.0-private",
        "offline_grace_days": OFFLINE_GRACE_DAYS,
        "single_tenant_id": SINGLE_TENANT_ID,
        "layers": list(layer_names()),
        "six_commercial_tables": list(SIX_COMMERCIAL_TABLES),
        "saas_platform_scripts": list(SAAS_PLATFORM_SCRIPTS),
        "public_hidden_views": list(PRIVATE_PUBLIC_HIDDEN_VIEWS),
        "is_private_deployment": is_private_deployment(),
        "is_offline_first": is_offline_first(),
    }

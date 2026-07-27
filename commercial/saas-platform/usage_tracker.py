"""
商业化 SaaS 平台 — usage tracker CLI (W73 第 1 批 B-1)

W72 第 2 批 B-5 起步 (file-based tracker) + W73 第 1 批 B-1 收口 (DB-backed).

Celery beat hourly 调度 + CLI 手动跑:
    python -m commercial.saas-platform.usage_tracker --window 1h --output /tmp/usage.json
    # Celery beat 调度 (在 celery_app.conf.beat_schedule 加 entry)
    # 由 Celery beat 每小时调度 track_usage_window("1h")

不破坏老路径: 仅在 commercial/saas-platform/usage_tracker.py 升级 CLI 入口,
业务逻辑委托 app/services/usage_service.py (本文件 DB 接口).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select, func, and_  # noqa: E402

from app.core.database import async_session  # noqa: E402
from app.models.billing import CommercialTenant, Plan, UsageRecord  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("saas.usage_tracker")

SUPPORTED_WINDOWS = {"1h": timedelta(hours=1), "24h": timedelta(hours=24), "30d": timedelta(days=30)}


async def track_usage_window(window: str = "1h") -> Dict:
    """统计每个租户过去 window 时间的用量.

    Returns: dict {tenant_id: {totals: {...}, over_limit: [...], window, plan_code}, ...}
    """
    if window not in SUPPORTED_WINDOWS:
        raise ValueError(f"unsupported window '{window}', supported: {list(SUPPORTED_WINDOWS)}")

    cutoff = datetime.utcnow() - SUPPORTED_WINDOWS[window]
    out: Dict = {}

    async with async_session() as db:
        # 1. 列出所有 active 租户
        tenants_q = select(CommercialTenant).where(CommercialTenant.status == "active")
        tenants = (await db.execute(tenants_q)).scalars().all()

        for tenant in tenants:
            # 2. 各 metric 聚合
            q = (
                select(UsageRecord.metric, func.sum(UsageRecord.value))
                .where(and_(UsageRecord.tenant_id == tenant.tenant_id, UsageRecord.recorded_at >= cutoff))
                .group_by(UsageRecord.metric)
            )
            rows = (await db.execute(q)).all()
            totals = {metric: float(total or 0) for metric, total in rows}

            # 3. 校验 plan 限额
            plan = await db.get(Plan, tenant.plan_code)
            limits = (plan.limits if plan else {}) or {}
            over_limit = []
            for metric, value in totals.items():
                limit_val = limits.get(metric)
                if limit_val is not None and value > limit_val:
                    over_limit.append({"metric": metric, "value": value, "limit": limit_val})

            out[tenant.tenant_id] = {
                "tenant_name": tenant.name,
                "plan_code": tenant.plan_code,
                "totals": totals,
                "over_limit": over_limit,
                "window": window,
            }
            if over_limit:
                logger.warning(
                    "tenant %s (%s) over limit in window %s: %s",
                    tenant.tenant_id, tenant.name, window, over_limit,
                )

    logger.info("usage tracked: window=%s tenants=%d", window, len(out))
    return out


async def record_usage(tenant_id: str, metric: str, value: float, metadata: Dict = None) -> None:
    """写入单条用量记录 (供业务 endpoint 调用)."""
    async with async_session() as db:
        rec = UsageRecord(
            tenant_id=tenant_id,
            metric=metric,
            value=value,
            record_metadata=metadata or {},
            recorded_at=datetime.utcnow(),
        )
        db.add(rec)
        await db.commit()
        logger.debug("usage recorded: tenant=%s metric=%s value=%.4f", tenant_id, metric, value)


def main() -> int:
    parser = argparse.ArgumentParser(description="SaaS 用量统计 (W73 B-1 收口)")
    parser.add_argument("--window", default="1h", choices=list(SUPPORTED_WINDOWS))
    parser.add_argument("--output", default=None, help="写到 JSON 文件")
    args = parser.parse_args()

    result = asyncio.run(track_usage_window(args.window))
    text = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        logger.info("written to %s", args.output)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
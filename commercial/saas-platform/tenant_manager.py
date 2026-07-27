"""
商业化 SaaS 平台 — multi-tenant manager CLI (W73 第 1 批 B-1)

W72 第 2 批 B-5 起步 (file-based store) + W73 第 1 批 B-1 收口 (DB-backed).

用法:
    python -m commercial.saas-platform.tenant_manager create --name acme --email ops@acme.com --plan pro
    python -m commercial.saas-platform.tenant_manager list
    python -m commercial.saas-platform.tenant_manager suspend --tenant-id ten_xxx --reason payment_overdue
    python -m commercial.saas-platform.tenant_manager rotate-key --tenant-id ten_xxx
    python -m commercial.saas-platform.tenant_manager delete --tenant-id ten_xxx [--hard]

不破坏老路径: 仅在 commercial/saas-platform/tenant_manager.py 升级 CLI 入口,
业务逻辑委托 app/services/tenant_service.py (新增).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# 路径 hack: 让脚本能 import app.*
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# W73 第 1 批 B-1 收口: 修正 import (app.core.database 提供 async_session, 不叫 async_session_factory)
from app.core.database import async_session  # noqa: E402
from app.services import tenant_service  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("saas.tenant_manager")


async def cmd_create(args) -> None:
    async with async_session() as db:
        tenant = await tenant_service.create_tenant(
            db, name=args.name, contact_email=args.email, plan_code=args.plan,
        )
        await db.commit()
        print(json.dumps({
            "tenant_id": tenant.tenant_id,
            "name": tenant.name,
            "plan_code": tenant.plan_code,
            "api_key": getattr(tenant, "_initial_api_key", ""),
            "isolation_token": tenant.isolation_token,
        }, indent=2, ensure_ascii=False))


async def cmd_list(args) -> None:
    async with async_session() as db:
        tenants = await tenant_service.list_tenants(
            db, status=args.status, plan_code=args.plan, limit=args.limit, offset=args.offset,
        )
        out = [
            {
                "tenant_id": t.tenant_id, "name": t.name, "plan_code": t.plan_code,
                "status": t.status, "contact_email": t.contact_email,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tenants
        ]
        print(json.dumps(out, indent=2, ensure_ascii=False))


async def cmd_suspend(args) -> None:
    async with async_session() as db:
        t = await tenant_service.suspend_tenant(db, args.tenant_id, reason=args.reason)
        await db.commit()
        print(json.dumps({"tenant_id": t.tenant_id, "status": t.status, "reason": args.reason}, indent=2))


async def cmd_reactivate(args) -> None:
    async with async_session() as db:
        t = await tenant_service.reactivate_tenant(db, args.tenant_id)
        await db.commit()
        print(json.dumps({"tenant_id": t.tenant_id, "status": t.status}, indent=2))


async def cmd_rotate(args) -> None:
    async with async_session() as db:
        new_key = await tenant_service.rotate_api_key(db, args.tenant_id)
        await db.commit()
        print(json.dumps({"tenant_id": args.tenant_id, "api_key": new_key}, indent=2))


async def cmd_delete(args) -> None:
    async with async_session() as db:
        await tenant_service.delete_tenant(db, args.tenant_id, hard=args.hard)
        await db.commit()
        print(json.dumps({"tenant_id": args.tenant_id, "deleted": True, "hard": args.hard}, indent=2))


def main() -> int:
    parser = argparse.ArgumentParser(description="SaaS 多租户 CLI (W73 B-1 收口)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("create", help="创建租户")
    p.add_argument("--name", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--plan", default="free", choices=["free", "pro", "enterprise"])
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("list", help="列出租户")
    p.add_argument("--status", default=None)
    p.add_argument("--plan", default=None)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--offset", type=int, default=0)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("suspend", help="暂停租户")
    p.add_argument("--tenant-id", required=True)
    p.add_argument("--reason", default="manual")
    p.set_defaults(func=cmd_suspend)

    p = sub.add_parser("reactivate", help="恢复租户")
    p.add_argument("--tenant-id", required=True)
    p.set_defaults(func=cmd_reactivate)

    p = sub.add_parser("rotate-key", help="轮换 API key")
    p.add_argument("--tenant-id", required=True)
    p.set_defaults(func=cmd_rotate)

    p = sub.add_parser("delete", help="删除租户")
    p.add_argument("--tenant-id", required=True)
    p.add_argument("--hard", action="store_true", help="物理删除 (默认软删)")
    p.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    asyncio.run(args.func(args))
    return 0


if __name__ == "__main__":
    sys.exit(main())
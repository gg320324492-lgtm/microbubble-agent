"""
商业化 SaaS 平台 — multi-tenant manager

W72 Phase 8 起步. 负责多租户注册/隔离/路由 (单进程隔离, 后续 W75 升级到分库).
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

TENANT_STORE_PATH = Path(os.getenv("MICROBUBBLE_TENANT_STORE", "/app/data/tenants.json"))


# 租户 ID 规则: 8-32 位, 字母数字中划线下划线
_TENANT_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{8,32}$")


@dataclass
class Tenant:
    tenant_id: str
    name: str
    contact_email: str
    plan: str = "free"  # free / pro / enterprise
    status: str = "active"  # active / suspended / deleted
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    api_key_hash: str = ""
    isolation_token: str = ""

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "name": self.name,
            "contact_email": self.contact_email,
            "plan": self.plan,
            "status": self.status,
            "created_at": self.created_at,
            "api_key_hash": self.api_key_hash,
            "isolation_token": self.isolation_token,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Tenant":
        return cls(**d)


def _load_store() -> dict[str, dict]:
    """加载本地租户存储."""
    if not TENANT_STORE_PATH.exists():
        return {}
    try:
        import json
        with open(TENANT_STORE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_store(tenants: dict[str, dict]) -> None:
    """写入本地租户存储."""
    import json
    TENANT_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TENANT_STORE_PATH, "w") as f:
        json.dump(tenants, f, indent=2)


def _hash_key(plain: str) -> str:
    return hashlib.sha256(plain.encode()).hexdigest()


def register_tenant(name: str, contact_email: str, plan: str = "free") -> Tenant:
    """注册新租户, 返回 (Tenant, 一次性 API key 明文).

    layer 1: tenant_id 校验
    layer 2: api_key 一次性 (不持久化明文)
    layer 3: isolation_token 强制每个 tenant 独立
    """
    if not name or not contact_email:
        raise ValueError("name and contact_email required")

    tenant_id = "tenant_" + secrets.token_hex(4)
    api_key = "mbk_" + secrets.token_urlsafe(32)
    isolation_token = secrets.token_urlsafe(16)

    tenant = Tenant(
        tenant_id=tenant_id,
        name=name,
        contact_email=contact_email,
        plan=plan,
        api_key_hash=_hash_key(api_key),
        isolation_token=isolation_token,
    )

    store = _load_store()
    if tenant_id in store:
        raise RuntimeError(f"tenant_id {tenant_id} collision, retry")

    store[tenant_id] = tenant.to_dict()
    _save_store(store)

    logger.info(f"registered tenant {tenant_id} ({plan})")
    return tenant


def verify_tenant(tenant_id: str, api_key: str) -> Optional[Tenant]:
    """验证 tenant_id + api_key, 隔离检查."""
    store = _load_store()
    data = store.get(tenant_id)
    if not data:
        return None
    if data.get("status") != "active":
        return None
    if data.get("api_key_hash") != _hash_key(api_key):
        return None
    return Tenant.from_dict(data)


def get_tenant(tenant_id: str) -> Optional[Tenant]:
    """按 tenant_id 查询 (管理用)."""
    store = _load_store()
    data = store.get(tenant_id)
    return Tenant.from_dict(data) if data else None


def suspend_tenant(tenant_id: str) -> bool:
    """暂停租户."""
    store = _load_store()
    if tenant_id not in store:
        return False
    store[tenant_id]["status"] = "suspended"
    _save_store(store)
    return True


def init_routes() -> None:
    """SaaS 平台启动时初始化路由 (Phase 8 stub).

    W75 升级到 alembic 081 多租户分库, Phase 2 SaaS 排期正式启用.
    """
    logger.info("[saas] tenant routes initialized (single-process isolation)")
    # 兜底单租户模式: 若无 tenant 记录, 自动创建 default tenant
    store = _load_store()
    if not store:
        default = register_tenant(
            name="default",
            contact_email="admin@microbubble.cloud",
            plan="enterprise",
        )
        logger.info(f"[saas] default tenant created: {default.tenant_id}")

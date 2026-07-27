"""
商业化 SaaS 平台 — audit export

W72 Phase 8 起步. 导出审计日志 (JSONL 格式), 用于合规审计和客户导出.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

AUDIT_LOG_PATH = Path(os.getenv("MICROBUBBLE_AUDIT_LOG", "/app/data/audit.jsonl"))


@dataclass
class AuditEvent:
    tenant_id: str
    actor: str  # user_id / system
    action: str  # register / login / pay / config_change / data_export
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict = field(default_factory=dict)

    def to_jsonl(self) -> str:
        return json.dumps({
            "tenant_id": self.tenant_id,
            "actor": self.actor,
            "action": self.action,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }, ensure_ascii=False)


def log_event(tenant_id: str, actor: str, action: str, **metadata) -> None:
    """记录审计事件 (JSONL append)."""
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    event = AuditEvent(tenant_id=tenant_id, actor=actor, action=action, metadata=metadata)
    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(event.to_jsonl() + "\n")


def export_audit(tenant_id: Optional[str] = None, since: Optional[str] = None) -> Iterator[AuditEvent]:
    """导出审计日志 (按 tenant_id 或时间过滤)."""
    if not AUDIT_LOG_PATH.exists():
        return iter([])

    def _gen():
        with open(AUDIT_LOG_PATH) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if tenant_id and d.get("tenant_id") != tenant_id:
                    continue
                if since and d.get("timestamp", "") < since:
                    continue
                yield AuditEvent(
                    tenant_id=d["tenant_id"],
                    actor=d["actor"],
                    action=d["action"],
                    timestamp=d["timestamp"],
                    metadata=d.get("metadata", {}),
                )

    return _gen()


def export_to_file(tenant_id: str, output_path: Path, since: Optional[str] = None) -> int:
    """导出指定 tenant 审计到文件, 返回行数."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(output_path, "w") as f:
        for event in export_audit(tenant_id=tenant_id, since=since):
            f.write(event.to_jsonl() + "\n")
            count += 1
    return count

"""
商业化 SaaS 平台 — usage tracker

W72 Phase 8 起步. 负责按 tenant 统计用量 (API 调用 / 存储 / 语音 / agent 轮次).
"""
from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)

USAGE_STORE_PATH = Path(os.getenv("MICROBUBBLE_USAGE_STORE", "/app/data/usage.json"))


@dataclass
class UsageRecord:
    tenant_id: str
    metric: str  # api_calls / storage_mb / asr_seconds / agent_turns
    value: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "metric": self.metric,
            "value": self.value,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


class UsageTracker:
    """线程安全的用量统计器."""

    def __init__(self, store_path: Path = USAGE_STORE_PATH):
        self.store_path = store_path
        self._lock = Lock()
        self._records: list[UsageRecord] = []
        self._load()

    def _load(self) -> None:
        if not self.store_path.exists():
            return
        try:
            with open(self.store_path) as f:
                raw = json.load(f)
            self._records = [UsageRecord(**r) for r in raw]
        except Exception as e:
            logger.warning(f"usage store load failed: {e}")
            self._records = []

    def _flush(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.store_path, "w") as f:
            json.dump([r.to_dict() for r in self._records], f, indent=2)

    def record(self, tenant_id: str, metric: str, value: float, metadata: Optional[dict] = None) -> None:
        """记录一次用量."""
        with self._lock:
            rec = UsageRecord(
                tenant_id=tenant_id,
                metric=metric,
                value=value,
                metadata=metadata or {},
            )
            self._records.append(rec)
            self._flush()

    def get_tenant_summary(self, tenant_id: str, since: Optional[str] = None) -> dict[str, float]:
        """按指标汇总某 tenant 的用量."""
        with self._lock:
            summary: dict[str, float] = defaultdict(float)
            for r in self._records:
                if r.tenant_id != tenant_id:
                    continue
                if since and r.timestamp < since:
                    continue
                summary[r.metric] += r.value
            return dict(summary)

    def get_all_tenants_summary(self) -> dict[str, dict[str, float]]:
        """汇总所有 tenant 的用量."""
        with self._lock:
            result: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
            for r in self._records:
                result[r.tenant_id][r.metric] += r.value
            return {t: dict(m) for t, m in result.items()}


_singleton: Optional[UsageTracker] = None


def get_tracker() -> UsageTracker:
    """获取全局单例."""
    global _singleton
    if _singleton is None:
        _singleton = UsageTracker()
    return _singleton

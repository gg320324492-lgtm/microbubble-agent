"""
声纹 B+C 方案实施 — 质量门禁实时监控 (W75 第 1 批 B-1)

6 件套监控凑齐:
- W73 B-2 4 类 hot-fix 监控 (CELERY beat schedule)
- W74 D-1 多租户监控
- W75 B-1 声纹质量门监控 (本模块)

监控项:
1. 4 子门禁实时通过率
2. 12 会议音频 reprocess 进度
3. #151 rollback 重演状态
4. 跨会议识别率实时
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional

# Celery beat schedule: 30 分钟监控周期
MONITOR_INTERVAL_SECONDS = 30 * 60  # 1800s
MONITOR_NAME = "voiceprint_quality_gate_monitor_v1"
MONITOR_VERSION = "2026-07-27"


@dataclass
class MonitorSnapshot:
    """单次监控快照."""

    timestamp: datetime
    subgate_pass_rates: Dict[str, float]  # 4 子门禁各自通过率
    overall_pass_rate: float
    reprocess_12_progress: float  # 0.0 - 1.0
    meeting_151_replay_status: str  # "passed" / "failed" / "in_progress"
    cross_meeting_recognition_rate: float  # 实时跨会议识别率
    alerting: bool = False
    alert_reason: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "subgate_pass_rates": self.subgate_pass_rates,
            "overall_pass_rate": self.overall_pass_rate,
            "reprocess_12_progress": self.reprocess_12_progress,
            "meeting_151_replay_status": self.meeting_151_replay_status,
            "cross_meeting_recognition_rate": self.cross_meeting_recognition_rate,
            "alerting": self.alerting,
            "alert_reason": self.alert_reason,
            "monitor_version": MONITOR_VERSION,
        }


def build_celery_beat_schedule_entry() -> dict:
    """Celery beat schedule 30 分钟调度入口."""
    return {
        MONITOR_NAME: {
            "task": "app.services.voiceprint_quality_monitor.run_quality_gate_monitor",
            "schedule": MONITOR_INTERVAL_SECONDS,
            "kwargs": {"monitor_version": MONITOR_VERSION},
        }
    }


# 6 件套监控入口聚合 (凑齐 W73 B-2 + W74 D-1 + W75 B-1)
SIX_PIECE_MONITORING = {
    "w73_b2_hotfix_4class": {
        "name": "W73-B-2 4 类 hot-fix 监控",
        "interval_seconds": 3600,
    },
    "w74_d1_tenant_stress": {
        "name": "W74-D-1 多租户监控",
        "interval_seconds": 3600,
    },
    "w75_b1_quality_gate": {
        "name": "W75-B-1 声纹质量门监控",
        "interval_seconds": MONITOR_INTERVAL_SECONDS,
    },
}

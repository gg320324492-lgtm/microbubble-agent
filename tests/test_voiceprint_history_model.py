"""测试 VoiceprintHistory 模型"""
import pytest
from datetime import datetime, timezone
from app.models.voiceprint_history import VoiceprintHistory


def test_voiceprint_history_fields():
    """VoiceprintHistory 应有 meeting_id / member_id / confidence / recorded_at"""
    h = VoiceprintHistory(
        meeting_id=1,
        member_id=5,
        confidence=0.85,
        recorded_at=datetime.now(timezone.utc),
    )
    assert h.meeting_id == 1
    assert h.member_id == 5
    assert h.confidence == 0.85

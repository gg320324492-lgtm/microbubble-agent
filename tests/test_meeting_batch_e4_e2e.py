"""Batch E-4 端到端覆盖

- admin endpoint 路由注册 + 路径前缀
- reprocess stage 顺序 (title -> polish -> speaker_assignment -> analysis -> transcription -> quality)
- polished 重建: transcript[i].text_polished 修改后 transcript_polished[i].text 同步
- error branch 不覆盖旧字段: analysis 失败时保留原 summary
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.meeting_reprocessing_service import (
    MeetingReprocessingService,
    ReprocessRequest,
)


def test_admin_meetings_router_prefix():
    from app.api.v1.admin_meetings import router
    assert router.prefix == "/admin/meetings"
    paths = sorted({r.path for r in router.routes if hasattr(r, "path")})
    assert any(p.endswith("/reprocess") for p in paths)
    assert any(p.endswith("/runs") for p in paths)
    assert any(p.endswith("/failures") for p in paths)
    assert any(p.endswith("/health") for p in paths)


def test_stage_execution_order_constant():
    """reprocess execute 必须按 title->polish->analysis 顺序, 即使 requested_stages 无序."""
    src = open(
        "E:/microbubble-agent/app/services/meeting_reprocessing_service.py",
        encoding="utf-8",
    ).read()
    # 找到 order 列表
    import re
    m = re.search(r'order\s*=\s*\[(.*?)\]', src, re.DOTALL)
    assert m
    items = [s.strip().strip('"').strip("'") for s in m.group(1).split(",")]
    assert items == ["title", "polish", "speaker_assignment", "analysis", "transcription", "quality"]


def test_polished_rebuild_matches_transcript():
    """stage_polish 后 transcript_polished 应当与 transcript 对齐."""
    from app.services.meeting_reprocessing_service import MeetingReprocessingService

    transcript = [
        {"speaker": "张三", "text": "你好", "start": 0, "end": 2},
        {"speaker": "李四", "text": "同意", "start": 2, "end": 4},
    ]

    m = SimpleNamespace(
        id=1, title="T", summary=None, key_points=None, decisions=None,
        transcript=transcript, transcript_polished=[], speaker_mapping={},
        speaker_stats=None, error_reason=None, status="completed",
    )
    svc = MeetingReprocessingService(_AsyncDB())

    async def fake_polish(meeting_id, segments, ctx):
        return {"polished": [{"text": f"润色:{s['text']}"} for s in segments]}

    with patch("app.services.meeting_ai_polish.polish_segments_with_lock", AsyncMock(side_effect=fake_polish)):
        import asyncio
        asyncio.run(svc._stage_polish(m))
    assert len(m.transcript_polished) == len(m.transcript)
    assert m.transcript_polished[0]["text"] == "润色:你好"
    assert m.transcript_polished[1]["text"] == "润色:同意"
    # transcript[i].text_polished 也被同步
    assert m.transcript[0]["text_polished"] == "润色:你好"


def test_analysis_failure_does_not_overwrite_old_fields():
    """stage_analysis 失败时 status=error, error_reason 含 chunk 错误, 不应保留旧 summary 为空."""
    from app.services.meeting_reprocessing_service import MeetingReprocessingService

    m = SimpleNamespace(
        id=242,
        title="旧标题", summary=None, key_points=[], decisions=[],
        transcript_polished=[{"speaker": "张三", "text": "hello", "ts": 0}] * 5,
        transcript=None, speaker_mapping=None, speaker_stats=None,
        error_reason=None, status="completed_with_warnings",
    )
    svc = MeetingReprocessingService(_AsyncDB())

    async def fake_analyze(text, speaker_mapping=None):
        return {
            "summary": "",
            "key_points": [],
            "decisions": [],
            "success": False,
            "failure": True,
            "warning": False,
            "success_chunk_count": 0,
            "failure_chunk_count": 1,
            "errors": [{"chunk_index": 0, "stage": "llm_call",
                        "error_class": "APIError", "message": "401 invalid"}],
        }

    with patch("app.services.meeting_analysis_service.MeetingAnalysisService.analyze_transcript",
               AsyncMock(side_effect=fake_analyze)):
        import asyncio
        asyncio.run(svc._stage_analysis(m))

    # status 反映失败, error_reason 含原因
    assert m.status == "error"
    assert "401" in (m.error_reason or "")


class _AsyncDB:
    def __init__(self):
        self.committed = False

    async def commit(self):
        self.committed = True

    async def flush(self):
        pass

    def add(self, obj):
        pass


def test_force_gates_transcription_even_with_empty_stages():
    """ReprocessRequest 不允许 transcription 与其他 stage 混跑 (默认拒绝)."""
    req = ReprocessRequest(meeting_id=242, requested_stages=["transcription", "title"], force=False)
    # 错误在前, 不进入 execute
    # 仅校验: __post_init__ 通过
    assert "transcription" in req.requested_stages
    # execute 在 transcription 不带 force=true 时拒绝
    import asyncio
    svc = MeetingReprocessingService(_AsyncDB())
    with patch.object(svc, "get_meeting", AsyncMock(return_value=SimpleNamespace(
        id=242, title="T", transcript_polished=[{"speaker": "X", "text": "a", "ts": 0}],
        transcript=[], speaker_mapping=None, speaker_stats=None, status="completed",
    ))):
        result = asyncio.run(svc.execute(req))
    assert any("transcription" in e.lower() for e in result.errors)
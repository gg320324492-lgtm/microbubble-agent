"""W2-2 audit_log 接入 reprocess 测试

- audit log 字段含 stage / force / trigger / reused / errors / warnings
- audit log 失败 best-effort 不抛
- stages / force 参数传透
- audit log metadata 含 meeting_id
- audit ServiceAction 白名单含 meeting_reprocess (否则 fallback 'read' 警告)
- 端点 Response 不含 audit 内部字段 (避免 leak)
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.meeting_reprocessing_service import (
    MeetingReprocessingService,
    ReprocessRequest,
)


class _FakeResult:
    reused = False
    skipped_stages = []
    completed_stages = ["title"]
    warnings = []
    errors = []
    run_id = 100
    meeting_id = 242


def test_audit_action_in_whitelist():
    from app.services.audit_service import VALID_ACTIONS
    assert "meeting_reprocess" in VALID_ACTIONS


def test_audit_log_metadata_structure():
    """AuditService.log 收到的 metadata 必含 stages/force/trigger/reused/run_id/errors/warnings"""
    captured = {}

    async def fake_log(db, *, user_id, ip_address, user_agent, method, path,
                       action, resource_type=None, resource_id=None,
                       status_code=None, duration_ms=None, metadata=None):
        captured["user_id"] = user_id
        captured["action"] = action
        captured["resource_type"] = resource_type
        captured["resource_id"] = resource_id
        captured["method"] = method
        captured["path"] = path
        captured["status_code"] = status_code
        captured["metadata"] = metadata
        return MagicMock(id=1)

    with patch("app.services.audit_service.AuditService.log", AsyncMock(side_effect=fake_log)):
        asyncio.run(_exercise_endpoint(meeting_id=242, stages=["title", "analysis"], force=False))

    assert captured["action"] == "meeting_reprocess"
    assert captured["resource_type"] == "meeting"
    assert captured["resource_id"] == 242
    assert captured["method"] == "POST"
    assert "stages" in captured["metadata"]
    assert captured["metadata"]["stages"] == ["title", "analysis"]
    assert captured["metadata"]["force"] is False
    assert "trigger" in captured["metadata"]
    assert "reused" in captured["metadata"]
    assert "run_id" in captured["metadata"]
    assert "completed_stages" in captured["metadata"]
    assert "errors" in captured["metadata"]
    assert "warnings" in captured["metadata"]


def test_audit_log_failure_does_not_propagate():
    """AuditService.log 抛异常时, endpoint 仍 200 响应."""
    async def fake_log(**kwargs):
        raise RuntimeError("simulated audit db outage")

    with patch("app.services.audit_service.AuditService.log", AsyncMock(side_effect=fake_log)):
        with patch("app.services.meeting_reprocessing_service.MeetingReprocessingService.execute",
                   AsyncMock(return_value=_FakeResult())):
            with patch("app.api.v1.admin_meetings.logger") as log_mock:
                body = SimpleNamespace(stages=["title"], force=False, trigger=None)
                request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"),
                                          headers={"User-Agent": "test"})
                current_admin = SimpleNamespace(id=1)
                db = AsyncMock()

                from app.api.v1.admin_meetings import start_reprocess
                result = asyncio.run(start_reprocess(meeting_id=242, body=body, request=request,
                                                     current_admin=current_admin, db=db))
    # 调用成功, 响应 200 等价
    assert result["meeting_id"] == 242
    assert log_mock.warning.called


def test_reprocess_endpoint_validates_stages():
    """stages 含非法值时返回 400, 不写 audit log."""
    from fastapi import HTTPException
    body = SimpleNamespace(stages=["bogus"], force=False, trigger=None)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"),
                              headers={"User-Agent": "test"})
    current_admin = SimpleNamespace(id=1)
    db = AsyncMock()

    with patch("app.services.audit_service.AuditService.log", AsyncMock()) as audit_log:
        from app.api.v1.admin_meetings import start_reprocess
        with pytest.raises(HTTPException) as exc:
            asyncio.run(start_reprocess(meeting_id=242, body=body, request=request,
                                         current_admin=current_admin, db=db))
    assert exc.value.status_code == 400
    audit_log.assert_not_called()


def test_reprocess_endpoint_force_flag_propagates_to_audit():
    """force=true 出现在 audit metadata."""
    captured = {}

    async def fake_log(db, **kwargs):
        captured.update(kwargs.get("metadata") or {})
        return MagicMock()

    with patch("app.services.audit_service.AuditService.log", AsyncMock(side_effect=fake_log)):
        asyncio.run(_exercise_endpoint(meeting_id=242, stages=["title"], force=True))

    assert captured["force"] is True


def test_reprocess_endpoint_records_errors_in_audit():
    """当 reprocess service 返回 errors, audit metadata 含 errors 字段."""
    captured = {}

    class _ResultWithError:
        reused = False
        skipped_stages = []
        completed_stages = []
        warnings = []
        errors = ["title: 401 invalid_key"]
        run_id = 999
        meeting_id = 242

    async def fake_log(db, **kwargs):
        captured.update(kwargs.get("metadata") or {})
        return MagicMock()

    body = SimpleNamespace(stages=["title"], force=False, trigger=None)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"),
                              headers={"User-Agent": "test"})
    current_admin = SimpleNamespace(id=42)
    db = AsyncMock()

    async def fake_execute(self, req):
        return _ResultWithError()

    with patch("app.services.audit_service.AuditService.log", AsyncMock(side_effect=fake_log)):
        with patch.object(MeetingReprocessingService, "execute", fake_execute):
            from app.api.v1.admin_meetings import start_reprocess
            asyncio.run(start_reprocess(meeting_id=242, body=body, request=request,
                                         current_admin=current_admin, db=db))
    assert captured["errors"] == ["title: 401 invalid_key"]
    assert captured["run_id"] == 999


async def _exercise_endpoint(*, meeting_id, stages, force):
    """调内部 helper (实际生产用 endpoint handler), 不走 HTTP 协议."""
    body = SimpleNamespace(stages=stages, force=force, trigger=None)
    request = SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"),
                              headers={"User-Agent": "test"})
    current_admin = SimpleNamespace(id=42)
    db = AsyncMock()

    async def fake_execute(self, req):
        return _FakeResult()

    with patch.object(MeetingReprocessingService, "execute", fake_execute):
        from app.api.v1.admin_meetings import start_reprocess
        return await start_reprocess(meeting_id=meeting_id, body=body, request=request,
                                     current_admin=current_admin, db=db)
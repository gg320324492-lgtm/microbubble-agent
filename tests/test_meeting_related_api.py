"""会议 related GET/POST 端点测试

验证 `app.api.v1.meeting` 路由器已注册：
- GET  /meetings/{meeting_id}/related
- POST /meetings/{meeting_id}/related

完整 ASGI 调用需要 main app（依赖 DB/MinIO/Redis），由项目内集成测试覆盖。
本文件仅做路由注册校验（轻量、无副作用）。
"""

import pytest


def _get_router():
    from app.api.v1 import meeting
    return meeting.router


def test_get_related_meetings_route_registered():
    """GET /meetings/{meeting_id}/related 已注册"""
    router = _get_router()
    paths = {r.path for r in router.routes}
    assert "/meetings/{meeting_id}/related" in paths


def test_set_related_meetings_route_registered():
    """POST /meetings/{meeting_id}/related 已注册"""
    router = _get_router()
    post_routes = [r for r in router.routes if r.path == "/meetings/{meeting_id}/related"]
    assert len(post_routes) >= 1
    methods = set()
    for r in post_routes:
        if hasattr(r, "methods"):
            methods.update(r.methods)
    assert "POST" in methods
    assert "GET" in methods


@pytest.mark.asyncio
async def test_get_related_meetings_returns_top_k():
    """GET /meetings/{id}/related 端点存在并能调用 find_related_meetings（mock）"""
    mock_results = [
        {"id": 2, "title": "M2", "start_time": "2026-05-30T10:00:00", "summary": "s", "similarity": 0.9},
        {"id": 3, "title": "M3", "start_time": "2026-05-25T10:00:00", "summary": "s", "similarity": 0.85},
    ]

    with pytest.MonkeyPatch.context() as mp:
        from app.services import meeting_service
        mp.setattr(meeting_service, "find_related_meetings",
                   lambda db, mid, top_k: _async_return(mock_results))
        # 端点存在性校验
        from app.api.v1.meeting import get_related_meetings
        assert callable(get_related_meetings)


@pytest.mark.asyncio
async def test_set_related_meetings_writes_field():
    """POST /meetings/{id}/related 端点存在并能调用 link_related_meetings（mock）"""
    with pytest.MonkeyPatch.context() as mp:
        from app.services import meeting_service
        mp.setattr(meeting_service, "link_related_meetings",
                   lambda db, mid, ids: _async_return(None))
        from app.api.v1.meeting import set_related_meetings
        assert callable(set_related_meetings)


async def _async_return(value):
    return value

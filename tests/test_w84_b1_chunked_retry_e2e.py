"""W84 第 1 批 B-1 P1-4 — drive_chunked_upload_service _stream_concat_chunks put_object 走 drive_retry.

派工前提铁律 12 (沿用 W82 B-2 拦截铁律): 修裸调 put_object 必先 grep 实测.
沿用 app.services.drive_service.drive_retry(max_attempts=3, backoff_base=0.2, backoff_max=1.6).
"""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("SKIP_DB_SETUP", "1")

import pytest
import pytest_asyncio


@pytest.mark.asyncio(loop_scope="function")
async def test_put_object_with_retry_runs_under_retry_decorator(monkeypatch):
    """P1-4: _put_object_with_retry 必须调用 drive_retry 装饰器 (transient 错误可重试).

    patch drive_retry 为透传包装, 验证被应用 + put_object 失败正常 reraise.
    """
    import sqlalchemy.exc as sa_exc
    from app.services.drive_chunked_upload_service import _put_object_with_retry

    decorator_calls = {"n": 0}

    def fake_drive_retry(*dargs, **dkwargs):
        def wrap(fn):
            decorator_calls["n"] += 1
            return fn  # 透传, 不重试
        return wrap

    monkeypatch.setattr(
        "app.services.drive_chunked_upload_service.drive_retry", fake_drive_retry
    )

    class FakeClient:
        def put_object(self, *args, **kwargs):
            raise sa_exc.OperationalError("stmt", {}, OSError("never recovers"))

    fake_service = MagicMock()
    fake_service.client = FakeClient()
    fake_service.bucket = "b1"

    with patch(
        "app.services.drive_chunked_upload_service.file_service", fake_service
    ):
        with pytest.raises(sa_exc.OperationalError):
            await _put_object_with_retry(
                "obj_key", b"data", "application/octet-stream"
            )

    assert decorator_calls["n"] == 1, "drive_retry 装饰器未应用"


@pytest.mark.asyncio(loop_scope="function")
async def test_put_object_with_retry_happy_path(monkeypatch):
    """P1-4: 正常路径 put_object 成功 → 不抛, decorator 仍然应用."""
    from app.services.drive_chunked_upload_service import _put_object_with_retry

    decorator_calls = {"n": 0}

    def fake_drive_retry(*dargs, **dkwargs):
        def wrap(fn):
            decorator_calls["n"] += 1
            return fn
        return wrap

    monkeypatch.setattr(
        "app.services.drive_chunked_upload_service.drive_retry", fake_drive_retry
    )

    class FakeClient:
        def put_object(self, *args, **kwargs):
            return None

    fake_service = MagicMock()
    fake_service.client = FakeClient()
    fake_service.bucket = "b1"

    with patch(
        "app.services.drive_chunked_upload_service.file_service", fake_service
    ):
        await _put_object_with_retry("obj_key", b"data", "application/octet-stream")

    assert decorator_calls["n"] == 1


import json
from unittest.mock import patch

import pytest
import pytest_asyncio

from app.services.progress_service import (
    ProgressStage,
    STAGE_ORDER,
    cleanup_progress,
    get_progress,
    init_progress,
    update_progress,
)
from tests._fake_redis import FakeRedis


def test_progress_stage_enum_values():
    assert ProgressStage.EXTRACTING_TRANSCRIPT.value == "extracting_transcript"
    assert ProgressStage.IDENTIFYING_SPEAKERS.value == "identifying_speakers"
    assert ProgressStage.GENERATING_TITLE.value == "generating_title"
    assert ProgressStage.GENERATING_MINUTES.value == "generating_minutes"
    assert ProgressStage.CREATING_TASKS.value == "creating_tasks"
    assert ProgressStage.LINKING_HISTORY.value == "linking_history"
    assert ProgressStage.DONE.value == "done"


def test_stage_order():
    assert STAGE_ORDER == [
        "extracting_transcript",
        "identifying_speakers",
        "generating_title",
        "generating_minutes",
        "creating_tasks",
        "linking_history",
        "done",
    ]


# --- 新增：update_progress 行为测试（使用 FakeRedis 避免依赖真 Redis） ---


@pytest_asyncio.fixture
async def fake_redis():
    """每个测试一个独立 FakeRedis 实例，patch 到 progress_service.get_redis"""
    fake = FakeRedis()
    with patch("app.services.progress_service.get_redis", return_value=fake):
        yield fake


@pytest.mark.asyncio
async def test_progress_lifecycle(fake_redis):
    """完整生命周期：init → update → get"""
    meeting_id = 12345

    await init_progress(meeting_id)
    try:
        snapshot = await get_progress(meeting_id)
        assert snapshot is not None
        assert snapshot["stage"] == "extracting_transcript"
        assert snapshot["status"] == "running"

        await update_progress(
            meeting_id,
            ProgressStage.GENERATING_TITLE,
            detail="AI 正在生成标题",
        )
        snapshot = await get_progress(meeting_id)
        assert snapshot["stage"] == "generating_title"
        assert snapshot["detail"] == "AI 正在生成标题"
        # 阶段 2/6 ≈ 33.3%
        assert 30.0 <= snapshot["percent"] <= 35.0, (
            f"percent={snapshot['percent']} 期望 30~35 之间"
        )

        await update_progress(meeting_id, ProgressStage.DONE)
        snapshot = await get_progress(meeting_id)
        assert snapshot["status"] == "done"
        assert snapshot["percent"] == 100.0
    finally:
        await cleanup_progress(meeting_id)


@pytest.mark.asyncio
async def test_progress_pubsub_publishes(fake_redis):
    """update_progress 应同时 PUBLISH 到 channel"""
    import asyncio

    meeting_id = 12346

    await init_progress(meeting_id)
    try:
        pubsub = fake_redis.pubsub()
        await pubsub.subscribe(f"progress:{meeting_id}")
        try:
            # 等订阅生效
            await asyncio.sleep(0.05)

            await update_progress(
                meeting_id,
                ProgressStage.CREATING_TASKS,
                detail="创建任务",
            )

            message = await asyncio.wait_for(
                pubsub.get_message(ignore_subscribe_messages=True),
                timeout=2.0,
            )
            assert message is not None, "未收到 pub/sub 消息"
            payload = json.loads(message["data"])
            assert payload["type"] == "progress_update"
            assert payload["data"]["stage"] == "creating_tasks"
        finally:
            await pubsub.unsubscribe(f"progress:{meeting_id}")
            await pubsub.aclose()
    finally:
        await cleanup_progress(meeting_id)

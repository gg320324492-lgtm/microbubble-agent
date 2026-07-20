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
    # W2 T2 (2026-07-21) 修类 3 orm_edge — production enum 在 2026-06-04 重构 (commit 9e16cf9e),
    # DOWNLOADING_AUDIO + TRANSCRIBING + IDENTIFYING_SPEAKERS 替代旧 EXTRACTING_TRANSCRIPT
    # GENERATING_ANALYSIS + STORING_RESULTS 替代旧 GENERATING_MINUTES + LINKING_HISTORY
    assert ProgressStage.DOWNLOADING_AUDIO.value == "downloading_audio"
    assert ProgressStage.TRANSCRIBING.value == "transcribing"
    assert ProgressStage.IDENTIFYING_SPEAKERS.value == "identifying_speakers"
    assert ProgressStage.GENERATING_TITLE.value == "generating_title"
    assert ProgressStage.GENERATING_ANALYSIS.value == "generating_analysis"
    assert ProgressStage.CREATING_TASKS.value == "creating_tasks"
    assert ProgressStage.STORING_RESULTS.value == "storing_results"
    assert ProgressStage.DONE.value == "done"


def test_stage_order():
    # W2 T2: 跟 production STAGE_ORDER 一致 (2026-06-04 重构后)
    assert STAGE_ORDER == [
        "downloading_audio",
        "transcribing",
        "identifying_speakers",
        "generating_title",
        "generating_analysis",
        "creating_tasks",
        "storing_results",
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
        # W2 T2: 2026-06-04 重构后初始 stage 是 downloading_audio (下载+转码+VAD)
        assert snapshot["stage"] == "downloading_audio"
        assert snapshot["status"] == "running"

        await update_progress(
            meeting_id,
            ProgressStage.GENERATING_TITLE,
            detail="AI 正在生成标题",
        )
        snapshot = await get_progress(meeting_id)
        assert snapshot["stage"] == "generating_title"
        assert snapshot["detail"] == "AI 正在生成标题"
        # W2 T2: stage 3/6 = 50% (production TOTAL_STAGES=6, 老 enum stage_index 算法没改,
        # 新 7 stage 索引到 stage 3 (generating_title) 还是 3/6 = 50%)
        assert 48.0 <= snapshot["percent"] <= 52.0, (
            f"percent={snapshot['percent']} 期望 48~52 之间 (stage 3/6)"
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

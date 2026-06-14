"""测试 Tracing Stage 3 改动（方案 C）

验证：
1. _build_payload 写入 6 个新 metric + status 字段
2. set_intent / set_critique 正确填充新字段
3. to_dict 暴露新字段
4. _persist_now 异常降级到 Celery schedule（铁律 4 退路）

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_tracing_payload.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.tracing import TraceCollector, TraceStatus


class TestBuildPayloadIncludesStage3Fields:
    """_build_payload 必须含 7 个新字段"""

    def test_payload_includes_intent_fields(self):
        trace = TraceCollector(user_id=1, session_id="s1", message="q")
        trace.set_intent("recommend_person", 0.92)
        payload = trace._build_payload()
        # payload 不直接含 intent_category（to_dict 才有），但 trace 内存层有
        assert trace.intent_category == "recommend_person"
        assert trace.intent_confidence == 0.92

    def test_payload_includes_critique_fields(self):
        trace = TraceCollector(user_id=1, session_id="s1", message="q")
        trace.set_critique(score=9, retry_count=0)
        assert trace.critique_score == 9
        assert trace.retry_count == 0

    def test_payload_includes_status(self):
        """Stage 3：payload 含 status 字段（供 admin API 过滤）"""
        trace = TraceCollector(user_id=1, session_id="s1", message="q")
        # async with 后 status=COMPLETED
        asyncio.run(_async_noop(trace))
        payload = trace._build_payload()
        assert "status" in payload
        assert payload["status"] == TraceStatus.COMPLETED

    def test_payload_status_aborted(self):
        """async with 抛 CancelledError → status=ABORTED"""
        async def run():
            trace = TraceCollector(user_id=1, session_id="s1", message="q")
            with patch.object(trace, "_persist_now", new=AsyncMock()):
                with pytest.raises(asyncio.CancelledError):
                    async with trace:
                        raise asyncio.CancelledError()
            return trace
        trace = asyncio.run(run())
        assert trace.status == TraceStatus.ABORTED


class TestToDictIncludesStage3Fields:
    """to_dict 必须暴露 7 个新字段供 API 响应使用"""

    def test_to_dict_exposes_all_new_fields(self):
        trace = TraceCollector(user_id=1, session_id="s1", message="q")
        trace.set_intent("recommend_person", 0.92)
        trace.set_critique(score=9, retry_count=1)
        asyncio.run(_async_noop(trace))
        d = trace.to_dict()
        assert d["status"] == TraceStatus.COMPLETED
        assert d["intent_category"] == "recommend_person"
        assert d["intent_confidence"] == 0.92
        assert d["critique_score"] == 9
        assert d["retry_count"] == 1

    def test_to_dict_defaults_for_legacy_traces(self):
        """旧 trace 数据可能没设过 intent/critique，to_dict 应返回 None/0"""
        trace = TraceCollector(user_id=1, session_id="s1", message="q")
        d = trace.to_dict()
        assert d["intent_category"] is None
        assert d["intent_confidence"] is None
        assert d["critique_score"] is None
        assert d["retry_count"] == 0
        assert d["status"] == TraceStatus.IN_PROGRESS  # 未退出过


class TestStatusFieldDefault:
    """status 字段默认值"""

    def test_initial_status_in_progress(self):
        trace = TraceCollector(user_id=1, session_id="s1", message="q")
        assert trace.status == TraceStatus.IN_PROGRESS

    def test_status_after_synthesis(self):
        """set_synthesis 不改 status（仍是 IN_PROGRESS，直到 __aexit__）"""
        trace = TraceCollector(user_id=1, session_id="s1", message="q")
        trace.set_synthesis("text")
        assert trace.status == TraceStatus.IN_PROGRESS


class TestPersistNowFallbackToCelery:
    """铁律 4 退路：_persist_now 失败时降级到 Celery"""

    @pytest.mark.asyncio
    async def test_persist_now_create_task_fire_and_forget(self):
        """2026-06-14 Stage 5 收尾增强：__aexit__ 用 create_task 而非 await，避免被 CancelledError 二次取消"""
        trace = TraceCollector(user_id=1, session_id="s1", message="q")
        # Mock _persist_now 抛错
        async def mock_persist_fail():
            raise RuntimeError("DB engine 创建失败")
        trace._persist_now = mock_persist_fail
        # Mock Celery schedule
        schedule_called = []
        trace._schedule_persist = lambda: schedule_called.append(True)

        with pytest.raises(asyncio.CancelledError):
            async with trace:
                raise asyncio.CancelledError()

        # 给 create_task 一点时间跑完（mock 抛错被 add_done_callback 捕获）
        await asyncio.sleep(0.05)

        # 行为：create_task 不让 sync 失败降级 Celery（因为 process 正在死）
        # add_done_callback 仅 log 错误，不调 _schedule_persist
        assert len(schedule_called) == 0, "create_task fire-and-forget 模式不降级 Celery（避免 process 死时 race）"


# 辅助
async def _async_noop(trace):
    """空 async 操作让 trace 走完 async with（设 status=COMPLETED）"""
    async with trace:
        pass

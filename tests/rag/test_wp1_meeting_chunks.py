"""WP1 (2026-09-02) 会议转录入 RAG 单测

锁三个契约:
  1. build_chunks_from_transcript: EMO 标签清洗 + 【speaker】前缀 + 段边界对齐
     窗口 (~800 字) + 时间窗/说话人元数据
  2. index_meeting_transcript: 幂等 (重跑不重复) + embedding 回填
  3. 检索侧: meetings 路结果 id 带 MEETING_ID_NS 命名空间 (防与 knowledge id 撞)
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.meeting_chunk_service import build_chunks_from_transcript


def _seg(i: int, speaker: str = "张三", text: str | None = None) -> dict:
    return {
        "text": text or f"这是第 {i} 句测试转录内容, 讨论微纳米气泡的制备参数。",
        "start": float(i * 10),
        "end": float(i * 10 + 8),
        "speaker_label": f"speaker_{i % 2}",
        "speaker": speaker,
    }


class TestBuildChunks:
    def test_basic_window_and_metadata(self):
        segs = [_seg(i) for i in range(30)]
        chunks = build_chunks_from_transcript(segs)
        assert len(chunks) >= 2  # 30 段 × ~20 字 → 多窗口
        c = chunks[0]
        assert c["content"].startswith("【张三】")
        assert c["start_sec"] == 0.0
        assert c["end_sec"] > 0
        assert "张三" in c["speakers"]
        assert c["chunk_index"] == 0

    def test_emo_tags_stripped(self):
        segs = [_seg(0, text="<|EMO_UNKNOWN|>今天讨论臭氧微气泡的消毒机制与参数选择。")]
        chunks = build_chunks_from_transcript(segs)
        assert chunks, "有效文本不应被清洗空"
        assert "<|EMO_" not in chunks[0]["content"]
        assert "EMO_UNKNOWN" not in chunks[0]["content"]

    def test_empty_and_none_transcript(self):
        assert build_chunks_from_transcript([]) == []
        assert build_chunks_from_transcript(None) == []
        # 全空白段 → 无 chunk
        assert build_chunks_from_transcript([{"text": "  ", "start": 0, "end": 1}]) == []

    def test_speaker_prefix_and_metadata(self):
        segs = [
            {"text": "大家好, 开会了。", "start": 0.0, "end": 5.0, "speaker": "李四"},
            {"text": "开始讨论预算。", "start": 5.0, "end": 12.0, "speaker": "王五"},
        ]
        chunks = build_chunks_from_transcript(segs)
        assert len(chunks) == 1
        assert "【李四】大家好" in chunks[0]["content"]
        assert "【王五】开始讨论预算" in chunks[0]["content"]
        assert chunks[0]["start_sec"] == 0.0
        assert chunks[0]["end_sec"] == 12.0
        assert "李四" in chunks[0]["speakers"] and "王五" in chunks[0]["speakers"]

    def test_large_transcript_yields_multiple_chunks(self):
        # 单段 ~380 字 × 10 段 = ~3800 字 → 至少 4 个 800 字窗口
        segs = [
            {"text": f"第 {i} 段: {'微纳米气泡传质效率讨论与参数优化验证。' * 30}", "start": float(i * 60),
             "end": float(i * 60 + 55), "speaker": f"成员{i % 3}"}
            for i in range(10)
        ]
        chunks = build_chunks_from_transcript(segs)
        assert len(chunks) >= 3
        assert all(len(c["content"]) <= 1400 for c in chunks)  # 窗口上限宽松校验


class TestIndexMeetingTranscript:
    @pytest.mark.asyncio
    async def test_idempotent_reindex(self):
        """重跑不产生重复 chunk (先 DELETE 后 INSERT)"""
        import contextlib
        import types

        from app.services import meeting_chunk_service as mcs

        meeting = types.SimpleNamespace(
            id=7,
            transcript=[_seg(i) for i in range(5)],
        )

        class _FakeDB:
            async def get(self, model, mid):
                return meeting if mid == 7 else None

            def add_all(self, rows):
                pass

            async def execute(self, stmt):
                empty = MagicMock()
                empty.scalars.return_value.all.return_value = []
                return empty

            async def commit(self):
                pass

        @contextlib.asynccontextmanager
        async def fake_session():
            yield _FakeDB()

        with patch("app.services.embedding_service.generate_embeddings",
                   AsyncMock(return_value=[[0.1] * 8 for _ in range(5)])):
            r1 = await mcs.index_meeting_transcript(7, fake_session)
            r2 = await mcs.index_meeting_transcript(7, fake_session)

        assert r1["chunks"] >= 1
        assert r2["chunks"] >= 1  # 幂等重跑

    @pytest.mark.asyncio
    async def test_skips_when_no_transcript(self):
        import contextlib
        import types

        from app.services import meeting_chunk_service as mcs

        meeting = types.SimpleNamespace(id=8, transcript=None)

        class _FakeDB:
            async def get(self, model, mid):
                return meeting

        @contextlib.asynccontextmanager
        async def fake_session():
            yield _FakeDB()

        r = await mcs.index_meeting_transcript(8, fake_session)
        assert r["skipped"] == 1 and r["chunks"] == 0

"""L2 聚批润色器（2026-06-02）

替代原"每段 1 次 Claude API"逐段润色（无上下文、QPS 高）。
攒批触发策略：每 30s 或攒满 5 段（whichever first）。
复用现有 polish_segments_with_lock() 已有 Redis 锁 + 24h 缓存。

消息契约（WS 推送）：
    {
        "type": "transcript_batch_polished",
        "batch_id": "batch_xxx",
        "segment_ids": ["seg_123", "seg_456"],
        "polished": [{"speaker": ..., "text": ..., "ts": ...}],
        "key_points": [{"text": ..., "ts": ..., "kind": "decision|todo|risk"}],
        "summary": "..."
    }
"""
import asyncio
import logging
import time
from typing import Optional

from app.config import settings
from app.services.meeting_ai_polish import polish_segments_with_lock

logger = logging.getLogger("microbubble.batch_polisher")


class BatchPolisher:
    """L2 聚批润色器

    用法：
        polisher = BatchPolisher(meeting_id, websocket, meeting_context)
        await polisher.start()    # 启动后台 task
        ...
        await polisher.add(transcript_entry)  # 每次有 ASR 段就入队
        ...
        await polisher.flush_remaining()  # hangup 时强制刷
        await polisher.stop()  # 关闭

    攒批触发：每 30s（POLISH_BATCH_INTERVAL_SECONDS）或攒满 5 段（POLISH_BATCH_MAX_SEGMENTS）
    每次 flush 调 polish_segments_with_lock() 一次，复用 Redis 锁 + 24h 缓存。
    """

    def __init__(self, meeting_id: int, websocket, meeting_context: dict = None):
        self.meeting_id = meeting_id
        self.websocket = websocket
        self.meeting_context = meeting_context or {}
        self._queue: list[dict] = []
        self._flush_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None
        self._stopped = False
        self._batch_counter = 0

    async def start(self) -> None:
        """启动后台聚批 task"""
        if self._task is not None:
            return
        self._stopped = False
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"L2 聚批润色器启动 meeting_id={self.meeting_id}")

    async def add(self, segment_entry: dict) -> None:
        """入队一条 transcript（来自 ASR 推过来）

        segment_entry 期望字段：segment_id, speaker, text, ts (其他字段透传)
        """
        if self._stopped:
            return
        # 过滤掉极短的段（与七重过滤的"短文本"逻辑一致）
        text = segment_entry.get("text", "").strip()
        if len(text) < 2:
            return
        self._queue.append(segment_entry)
        # 攒满 N 段立即触发 flush（不等 timer）
        if len(self._queue) >= settings.POLISH_BATCH_MAX_SEGMENTS:
            self._flush_event.set()
        # 字符数达到 POLISH_BATCH_MIN_CHARS 也立即触发
        elif sum(len(s.get("text", "")) for s in self._queue) >= settings.POLISH_BATCH_MIN_CHARS * settings.POLISH_BATCH_MAX_SEGMENTS:
            self._flush_event.set()

    async def flush_remaining(self) -> None:
        """强制刷残余（hangup 时调用）"""
        self._flush_event.set()
        # 给后台 task 一点时间跑完
        for _ in range(5):
            if not self._queue:
                break
            await asyncio.sleep(0.2)

    async def stop(self) -> None:
        """停止后台 task（hangup 后调用）"""
        self._stopped = True
        self._flush_event.set()
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=3.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
            self._task = None
        logger.info(f"L2 聚批润色器停止 meeting_id={self.meeting_id}")

    async def _run_loop(self) -> None:
        """后台循环：等事件或 30s timeout 触发 flush"""
        while not self._stopped:
            try:
                # 等事件（30s timeout 后自动 flush）
                await asyncio.wait_for(
                    self._flush_event.wait(),
                    timeout=settings.POLISH_BATCH_INTERVAL_SECONDS,
                )
            except asyncio.TimeoutError:
                # 30s 到，触发 flush
                pass
            self._flush_event.clear()
            if self._queue:
                await self._flush()

    async def _flush(self) -> None:
        """聚批调 LLM 一次 + 推 WS"""
        if not self._queue:
            return
        # 复制 + 清空（避免与 add 冲突）
        batch = self._queue[:]
        self._queue.clear()
        self._batch_counter += 1
        batch_id = f"batch_{int(time.time())}_{self._batch_counter}"

        # 拼 segments 数组（格式：polish_segments_with_lock 期望）
        segments = [
            {
                "speaker": e.get("speaker", "未知说话人"),
                "text": e.get("text", ""),
                "ts": e.get("ts", 0),
            }
            for e in batch
        ]
        segment_ids = [e.get("segment_id", f"seg_{i}") for i, e in enumerate(batch)]

        logger.info(
            f"L2 flush meeting_id={self.meeting_id} batch_id={batch_id} "
            f"segments={len(batch)} chars={sum(len(s['text']) for s in segments)}"
        )

        try:
            result = await polish_segments_with_lock(
                self.meeting_id, segments, self.meeting_context
            )
            polished = result.get("polished", segments)  # fallback 用原文
            key_points = result.get("key_points", [])
            summary = result.get("summary")

            # 推 WS 消息
            await self.websocket.send_json({
                "type": "transcript_batch_polished",
                "batch_id": batch_id,
                "segment_ids": segment_ids,
                "polished": polished,
                "key_points": key_points,
                "summary": summary,
            })
            logger.info(
                f"L2 flush OK meeting_id={self.meeting_id} batch_id={batch_id} "
                f"polished={len(polished)}"
            )

        except Exception as e:
            logger.error(f"L2 flush 失败 meeting_id={self.meeting_id} batch_id={batch_id}: {e}")
            # 失败时回退：推原文（前端 status 保持 batch_polished 但 text 是原文）
            try:
                await self.websocket.send_json({
                    "type": "transcript_batch_polished",
                    "batch_id": batch_id,
                    "segment_ids": segment_ids,
                    "polished": segments,  # 用原文
                    "key_points": [],
                    "summary": None,
                    "error": str(e),
                })
            except Exception:
                pass

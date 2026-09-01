"""MeetingChunk service — 会议转录 chunk 级索引 (WP1, 2026-09-02)

审计缺口修复: 会议转录 (22 场 ≈ 250 万字) 从未被 RAG 索引。本服务:
1. build_chunks_from_transcript: transcript 分段数组 → 清洗 EMO 标签 →
   【speaker】前缀 → ~800 字文本窗口 (段边界对齐, 不跨段切断)
2. index_meeting_transcript: 幂等写 meeting_chunks + 批量 embedding 回填
3. index_meeting_chunks_task: Celery 包装 (post_meeting 管线 dispatch)
4. remove_meeting_chunks: 会议删除时清理 (FK CASCADE 之外的显式入口)

设计:
- 段边界对齐分块 (不跨段切断) — 转录段本身即语义单元 (一人一句话)
- 窗口超限时的当前段仍完整保留 (单段超长由 truncate_for_embedding 兜底)
- EMO/事件标签 (<|EMO_UNKNOWN|> 等) 全部剥离
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select

logger = logging.getLogger("microbubble.meeting_chunk_service")

# 转录文本窗口目标大小 (字符) — 与知识库 chunking 的 800 字窗对齐
WINDOW_CHARS = 800
# EMO/事件特殊标签: <|EMO_UNKNOWN|> <|SILENCE|> <|NEED_RECOGNIZE|> 等
_SPECIAL_TAG_RE = re.compile(r"<\|[^|]*\|>")
# 多余空白
_WS_RE = re.compile(r"\s+")


def _clean_segment_text(text: str) -> str:
    """剥离 <|...|> 特殊标签 + 压缩空白"""
    cleaned = _SPECIAL_TAG_RE.sub("", text or "")
    return _WS_RE.sub(" ", cleaned).strip()


def build_chunks_from_transcript(
    transcript: Optional[List[Dict[str, Any]]],
    window_chars: int = WINDOW_CHARS,
) -> List[Dict[str, Any]]:
    """transcript 分段数组 → chunk 列表

    每个 chunk = 连续若干段的拼接文本, 段渲染为 "【说话人】文本";
    chunk 元数据携带时间窗 (start_sec/end_sec) 与涉及说话人。
    段边界对齐: 不把一句话切成两半。

    Returns:
        [{content, start_sec, end_sec, speakers, chunk_index}]
    """
    if not transcript:
        return []

    # 1. 清洗段落 (保序)
    cleaned: List[Dict[str, Any]] = []
    for seg in transcript:
        if not isinstance(seg, dict):
            continue
        text = _clean_segment_text(str(seg.get("text_polished") or seg.get("text") or ""))
        if not text:
            continue
        speaker = str(seg.get("speaker") or seg.get("speaker_label") or "").strip()
        try:
            start = float(seg.get("start")) if seg.get("start") is not None else None
            end = float(seg.get("end")) if seg.get("end") is not None else None
        except (TypeError, ValueError):
            start = end = None
        cleaned.append({"text": text, "speaker": speaker, "start": start, "end": end})

    # 2. 累积成窗口 (段边界对齐)
    chunks: List[Dict[str, Any]] = []
    buf_texts: List[str] = []
    buf_start: Optional[float] = None
    buf_end: Optional[float] = None
    buf_speakers: List[str] = []

    def _flush():
        nonlocal buf_texts, buf_start, buf_end, buf_speakers
        if not buf_texts:
            return
        chunks.append({
            "content": "\n".join(buf_texts),
            "start_sec": buf_start,
            "end_sec": buf_end,
            "speakers": ",".join(dict.fromkeys(buf_speakers)),
            "chunk_index": len(chunks),
        })
        buf_texts = []
        buf_start = buf_end = None
        buf_speakers = []

    for seg in cleaned:
        rendered = f"【{seg['speaker']}】{seg['text']}" if seg["speaker"] else seg["text"]
        if sum(len(t) for t in buf_texts) + len(rendered) > window_chars and buf_texts:
            _flush()
        if buf_start is None:
            buf_start = seg["start"]
        buf_texts.append(rendered)
        buf_end = seg["end"]
        if seg["speaker"] and seg["speaker"] not in buf_speakers:
            buf_speakers.append(seg["speaker"])
    _flush()

    return chunks


async def index_meeting_transcript(
    meeting_id: int,
    session_factory,
) -> Dict[str, Any]:
    """为单场会议重建转录 chunk 索引 (幂等: 先 DELETE 后 INSERT + embedding 回填)

    Args:
        meeting_id: 会议 id
        session_factory: async_sessionmaker (API/Celery/脚本各自注入)

    Returns:
        {"chunks": 写入行数, "embedded": embedding 回填行数, "skipped": 无转录}
    """
    from app.models.meeting import Meeting
    from app.models.meeting_chunk import MeetingChunk
    from app.services.embedding_service import generate_embeddings
    from app.services.embedding_truncation_policy import truncate_for_embedding

    stats = {"chunks": 0, "embedded": 0, "skipped": 0}
    async with session_factory() as db:
        meeting = await db.get(Meeting, meeting_id)
        if meeting is None:
            stats["skipped"] = 1
            return stats
        transcript = meeting.transcript
        if isinstance(transcript, str):
            import json as _json
            try:
                transcript = _json.loads(transcript)
            except (ValueError, TypeError):
                transcript = None

        chunks = build_chunks_from_transcript(transcript)
        if not chunks:
            stats["skipped"] = 1
            return stats

        # 幂等: 清旧 chunk
        await db.execute(
            delete(MeetingChunk).where(MeetingChunk.meeting_id == meeting_id)
        )

        rows = [
            MeetingChunk(
                meeting_id=meeting_id,
                chunk_index=c["chunk_index"],
                content=c["content"],
                start_sec=c["start_sec"],
                end_sec=c["end_sec"],
                speakers=c["speakers"][:500] if c["speakers"] else None,
            )
            for c in chunks
        ]
        db.add_all(rows)
        await db.commit()
        stats["chunks"] = len(rows)

    # embedding 批量回填 (行已落库, 失败 warning 不阻塞 — 可由回填脚本补)
    try:
        texts = [truncate_for_embedding(c["content"]) for c in chunks]
        embeddings = await generate_embeddings(texts, for_query=False)
        if embeddings and len(embeddings) == len(rows):
            async with session_factory() as db:
                db_rows = (
                    await db.execute(
                        select(MeetingChunk).where(MeetingChunk.meeting_id == meeting_id)
                    )
                ).scalars().all()
                by_index = {r.chunk_index: r for r in db_rows}
                for idx, emb in enumerate(embeddings):
                    target = by_index.get(idx)
                    if target is not None and emb is not None:
                        target.embedding = emb
                        stats["embedded"] += 1
                await db.commit()
    except Exception as e:
        logger.warning(
            "meeting chunk embedding 回填失败(meeting_id=%s, 可重跑补): %s",
            meeting_id, e,
        )

    logger.info(
        "meeting 转录索引完成(meeting_id=%s): chunks=%d embedded=%d",
        meeting_id, stats["chunks"], stats["embedded"],
    )
    return stats


async def remove_meeting_chunks(meeting_id: int, session_factory) -> bool:
    """删除某会议的全部转录 chunk (会议删除时调用)"""
    from app.models.meeting_chunk import MeetingChunk

    async with session_factory() as db:
        await db.execute(
            delete(MeetingChunk).where(MeetingChunk.meeting_id == meeting_id)
        )
        await db.commit()
    return True


# ===== Celery 任务包装 (post_meeting 管线 dispatch) =====
try:
    from app.core.celery import celery_app  # noqa: E402
    _HAS_CELERY = True
except ImportError:  # pragma: no cover
    _HAS_CELERY = False

if _HAS_CELERY:
    from app.core.celery_db import create_celery_engine_and_session  # noqa: E402

    @celery_app.task(
        name="app.services.meeting_chunk_service.index_meeting_chunks_task",
        bind=True,
        max_retries=2,
        default_retry_delay=30,
    )
    def index_meeting_chunks_task(self, meeting_id: int) -> Dict[str, Any]:
        """会议转录 chunk 索引任务 — post_meeting 完成后 dispatch"""
        import asyncio

        async def _run():
            from app.services.meeting_chunk_service import index_meeting_transcript
            from app.core.celery_db import create_celery_engine_and_session as _mk

            engine, session_factory = _mk()
            try:
                return await index_meeting_transcript(meeting_id, session_factory)
            finally:
                await engine.dispose()

        try:
            return asyncio.run(_run())
        except Exception as e:
            logger.error(f"index_meeting_chunks_task failed meeting_id={meeting_id}: {e}")
            try:
                raise self.retry(exc=e)
            except self.MaxRetriesExceededError:
                return {"meeting_id": meeting_id, "error": str(e)}

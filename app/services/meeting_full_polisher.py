"""L3 全文精润色器（2026-06-02）

挂断时触发：用高质量 Claude Sonnet 模型对全量 transcript 一次性精润色。
- 分块（每 FULL_POLISH_CHUNK_CHARS 字符一片），避免超 max_tokens
- 逐块调 LLM，带跨块 context history（前面 chunk 的 polished 结果作为后续 chunk 的 context）
- 失败 chunk 用 raw + polish_failed:true，不中断其他 chunk
- 持久化到 meeting.transcript_polished
- 推 transcript_full_polished 给前端（Redis pub/sub 兜底 WS 已断）
"""
import asyncio
import logging
from typing import Optional

from app.config import settings
from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json
from app.core.redis import get_redis
from app.services.prompts.meeting_full_polish import SYSTEM_PROMPT, build_user_prompt
from app.services.progress_service import ProgressStage, update_progress

logger = logging.getLogger("microbubble.full_polisher")


def _chunk_segments(segments: list[dict], max_chars: int) -> list[list[dict]]:
    """按字符数分块（保证每块 JSON 序列化后不超过 max_chars）

    简单策略：累积直到超 max_chars 就切下一块（最后一条完整保留）
    """
    chunks: list[list[dict]] = []
    current: list[dict] = []
    current_chars = 0
    for seg in segments:
        seg_chars = len(seg.get("text", "")) + 64  # 64 字节 JSON 包装预算
        if current and current_chars + seg_chars > max_chars:
            chunks.append(current)
            current = [seg]
            current_chars = seg_chars
        else:
            current.append(seg)
            current_chars += seg_chars
    if current:
        chunks.append(current)
    return chunks


async def _polish_one_chunk(
    chunk: list[dict],
    title: str,
    participants: list,
    context_segments: list[dict],
) -> dict:
    """调 LLM 润色 1 个 chunk

    返回 {"polished": [...], "removed": [...], "key_points": [...], "summary": str|None}

    2026-06-02 优化 3：加 Redis 缓存，缓存键 = sha1(chunk + model)，24h TTL。
    重入会话或测试环境重复触发时直接命中缓存，节省 Claude 调用。
    """
    import hashlib
    import json as _json

    # 1. 构造缓存键（用 chunk 的稳定序列化 + 模型名）
    cache_key_material = _json.dumps(
        {"chunk": chunk, "title": title, "participants": participants, "model": settings.FULL_POLISH_MODEL},
        sort_keys=True, ensure_ascii=False,
    ).encode("utf-8")
    cache_hash = hashlib.sha1(cache_key_material).hexdigest()[:16]
    cache_key = f"full_polish:{cache_hash}"

    # 2. 查缓存
    try:
        r = await get_redis()
        cached = await r.get(cache_key)
        if cached:
            logger.info(f"L3 缓存命中 key={cache_key}")
            return _json.loads(cached)
    except Exception as e:
        logger.warning(f"L3 读缓存失败（继续调 LLM）: {e}")

    # 3. 调 LLM
    client = get_anthropic_client()
    model = settings.FULL_POLISH_MODEL or get_default_model()
    user_prompt = build_user_prompt(
        title=title,
        participants=participants,
        topic_line="",
        segments=chunk,
        context_segments=context_segments,
    )

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=settings.FULL_POLISH_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        # 取第一段 text
        from app.core.llm import extract_text_from_response
        text = extract_text_from_response(response)
        if not text:
            raise ValueError("LLM 返回空文本")
        result = parse_llm_json(text)
        result_out = {
            "polished": result.get("polished") or [],
            "removed": result.get("removed") or [],
            "key_points": result.get("key_points") or [],
            "summary": result.get("summary"),
        }

        # 4. 写缓存（24h TTL）
        try:
            await r.set(cache_key, _json.dumps(result_out, ensure_ascii=False), ex=86400)
            logger.debug(f"L3 缓存写入 key={cache_key}")
        except Exception as e:
            logger.warning(f"L3 写缓存失败（不影响主流程）: {e}")

        return result_out
    except Exception as e:
        logger.error(f"L3 chunk polish 失败: {e}", exc_info=True)
        # 降级：原样返回，让调用方标记 polish_failed
        return {
            "polished": chunk,
            "removed": [],
            "key_points": [],
            "summary": None,
            "polish_failed": True,
        }


async def run_full_polish_pipeline(
    meeting_id: int,
    transcript_entries: list[dict],
    db_session_factory=None,
) -> None:
    """L3 全文精润色主入口

    Args:
        meeting_id: 会议 ID
        transcript_entries: 全量 transcript entry 列表（每条含 segment_id, speaker, text, ts）
        db_session_factory: 异步 DB session 工厂（async_session）
    """
    if not transcript_entries or not settings.ENABLE_FULL_POLISH_ON_HANGUP:
        logger.info(f"L3 全文润色跳过 meeting_id={meeting_id} (无 transcript 或未启用)")
        return

    # 1. 推进度
    try:
        await update_progress(meeting_id, ProgressStage.TRANSCRIBING, "全文润色中")
    except Exception as e:
        logger.warning(f"L3 推 POLISHING_TRANSCRIPT 进度失败: {e}")

    # 2. 分块
    chunks = _chunk_segments(transcript_entries, settings.FULL_POLISH_CHUNK_CHARS)
    logger.info(
        f"L3 全文润色开始 meeting_id={meeting_id} "
        f"total_segments={len(transcript_entries)} chunks={len(chunks)}"
    )

    # 3. 准备 segments 数组（标准化字段）
    all_segments = [
        {
            "segment_id": e.get("segment_id", f"seg_{i}"),
            "speaker": e.get("speaker", "未知说话人"),
            "text": e.get("text", ""),
            "ts": e.get("start", e.get("ts", 0)),
        }
        for i, e in enumerate(transcript_entries)
        if e.get("text", "").strip()
    ]

    # 4. 逐块调 LLM（带跨块 context history）
    all_polished: list[dict] = []
    all_removed: list[dict] = []
    all_key_points: list[dict] = []
    final_summary: Optional[str] = None
    context_segments: list[dict] = []

    for i, chunk in enumerate(chunks):
        logger.info(f"L3 chunk {i+1}/{len(chunks)} meeting_id={meeting_id} segments={len(chunk)}")
        result = await _polish_one_chunk(
            chunk=chunk,
            title=f"会议 {meeting_id}",  # 简化：实际可从 meeting.title 取
            participants=list({s.get("speaker") for s in all_segments if s.get("speaker")}),
            context_segments=context_segments[-10:] if context_segments else [],  # 最近 10 条作为 context
        )

        # 失败标记
        if result.get("polish_failed"):
            logger.warning(f"L3 chunk {i+1} 降级为原文 meeting_id={meeting_id}")
            all_polished.extend([
                {**s, "polish_failed": True} for s in chunk
            ])
        else:
            all_polished.extend(result.get("polished", chunk))
            all_removed.extend(result.get("removed", []))
            all_key_points.extend(result.get("key_points", []))
            # 把本 chunk 的 polished 结果作为下一 chunk 的 context
            context_segments.extend(result.get("polished", chunk))
            if result.get("summary"):
                final_summary = result["summary"]

    # 5. 持久化到 DB
    if db_session_factory is not None:
        try:
            from app.models.meeting import Meeting
            async with db_session_factory() as db:
                m = await db.get(Meeting, meeting_id)
                if m is not None:
                    m.transcript_polished = all_polished
                    # 2026-06-02 优化 1：L3 key_points 回写到 meeting.key_points
                    # meeting.key_points 是 ARRAY(String)，从 L3 的 [{text, ts, kind}] 提取纯 text
                    if all_key_points:
                        m.key_points = [
                            kp.get("text", "") for kp in all_key_points
                            if kp.get("text", "").strip()
                        ]
                        logger.info(
                            f"L3 关键点回写 meeting_id={meeting_id} key_points={len(m.key_points)}"
                        )
                    await db.commit()
                    logger.info(f"L3 全文润色已持久化 meeting_id={meeting_id} polished={len(all_polished)}")
        except Exception as e:
            logger.error(f"L3 持久化失败 meeting_id={meeting_id}: {e}", exc_info=True)

    # 6. 推 Redis pub/sub（WS 可能已断，前端若已离开会议页面也接得到）
    try:
        from app.core.redis import get_redis
        import json as _json
        r = await get_redis()
        await r.publish(
            f"transcript_polished:{meeting_id}",
            _json.dumps(
                {
                    "type": "transcript_full_polished",
                    "meeting_id": meeting_id,
                    "polished_segments": all_polished,
                    "removed": all_removed,
                    "key_points": all_key_points,
                    "summary": final_summary,
                },
                ensure_ascii=False,
            ),
        )
    except Exception as e:
        logger.error(f"L3 推 transcript_full_polished 失败 meeting_id={meeting_id}: {e}")

    # 7. 推进度完成
    try:
        from app.services.progress_service import ProgressStage as _PS
        await update_progress(meeting_id, _PS.GENERATING_ANALYSIS, "全文润色完成")
    except Exception as e:
        logger.warning(f"L3 推 GENERATING_MINUTES 进度失败: {e}")

    logger.info(
        f"L3 全文润色完成 meeting_id={meeting_id} "
        f"polished={len(all_polished)} removed={len(all_removed)} "
        f"key_points={len(all_key_points)}"
    )

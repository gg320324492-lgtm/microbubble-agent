"""一次性脚本：用 L3 prompt 重新精润色会议 #83 (2026-06-11)

执行：cd g:/microbubble-agent && docker cp scripts/repolish_meeting_83.py microbubble-agent-app-1:/tmp/ && docker exec -i microbubble-agent-app-1 python /tmp/repolish_meeting_83.py

或本地执行（需要 ANTHROPIC_API_KEY 等环境变量）：
cd g:/microbubble-agent && python scripts/repolish_meeting_83.py
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# 让脚本能找到 app 包
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.llm import (
    extract_text_from_response,
    get_anthropic_client,
    get_default_model,
    parse_llm_json,
)
from app.services.prompts.meeting_full_polish import SYSTEM_PROMPT, build_user_prompt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("repolish_meeting_83")

MEETING_ID = 83


async def fetch_transcript_from_db(meeting_id: int) -> tuple[list[dict], str, list[str]]:
    """从数据库读取会议的 transcript + title + 参会人。"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy import select
    from app.config import settings
    from app.models.meeting import Meeting, MeetingParticipant
    from app.models.member import Member

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )
    session_factory = async_sessionmaker(engine, class_=__import__("sqlalchemy.ext.asyncio", fromlist=["AsyncSession"]).AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as db:
            m = await db.get(Meeting, meeting_id)
            if not m:
                raise ValueError(f"Meeting {meeting_id} not found")
            transcript = m.transcript or []
            # 取参会人
            stmt = select(Member.name).join(MeetingParticipant, MeetingParticipant.member_id == Member.id).where(MeetingParticipant.meeting_id == meeting_id)
            result = await db.execute(stmt)
            participants = [r[0] for r in result.all()]
            return transcript, m.title or f"会议 {meeting_id}", participants
    finally:
        await engine.dispose()


async def update_db_polished(meeting_id: int, polished: list[dict], key_points: list[dict], summary: str | None) -> None:
    """把 L3 结果写回 meetings 表。"""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from app.config import settings
    from app.models.meeting import Meeting

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as db:
            m = await db.get(Meeting, meeting_id)
            if not m:
                raise ValueError(f"Meeting {meeting_id} not found")
            m.transcript_polished = polished
            if key_points:
                m.key_points = [kp.get("text", "") for kp in key_points if kp.get("text", "").strip()]
            if summary:
                m.summary = summary
            await db.commit()
            logger.info(f"✅ 会议 {meeting_id} 已更新 transcript_polished ({len(polished)}段)")
    finally:
        await engine.dispose()


def chunk_segments(segments: list[dict], max_chars: int = 4000) -> list[list[dict]]:
    """按字符数分块（沿用 L3 的 chunk 策略）。"""
    chunks: list[list[dict]] = []
    cur: list[dict] = []
    cur_chars = 0
    for seg in segments:
        seg_chars = len(seg.get("text", "")) + 64
        if cur and cur_chars + seg_chars > max_chars:
            chunks.append(cur)
            cur = [seg]
            cur_chars = seg_chars
        else:
            cur.append(seg)
            cur_chars += seg_chars
    if cur:
        chunks.append(cur)
    return chunks


async def polish_one_chunk(
    client,
    model: str,
    title: str,
    participants: list[str],
    chunk: list[dict],
    context_segments: list[dict],
) -> dict:
    user_prompt = build_user_prompt(
        title=title,
        participants=participants,
        topic_line="",
        segments=chunk,
        context_segments=context_segments,
    )
    response = await client.messages.create(
        model=model,
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = extract_text_from_response(response)
    if not text:
        raise ValueError("LLM 返回空文本")
    return parse_llm_json(text)


async def main():
    # 1. 读 DB
    logger.info(f"读取会议 {MEETING_ID} 的 transcript...")
    transcript, title, participants = await fetch_transcript_from_db(MEETING_ID)
    logger.info(f"标题: {title} | 参会人: {participants} | segments: {len(transcript)}")

    if not transcript:
        logger.error("transcript 为空")
        return

    # 2. 分块
    chunks = chunk_segments(transcript, max_chars=4000)
    logger.info(f"分 {len(chunks)} 块")

    # 3. 准备 segments 数组（标准化字段）
    all_segments = [
        {
            "segment_id": seg.get("speaker_label", f"seg_{i}"),
            "speaker": seg.get("speaker", "未知说话人"),
            "text": seg.get("text", ""),
            "ts": seg.get("start", seg.get("ts", 0)),
        }
        for i, seg in enumerate(transcript)
        if seg.get("text", "").strip()
    ]

    # 4. 逐块调 LLM
    client = get_anthropic_client()
    model = get_default_model()
    all_polished: list[dict] = []
    all_removed: list[dict] = []
    all_key_points: list[dict] = []
    final_summary: str | None = None
    context_segments: list[dict] = []

    for i, chunk in enumerate(chunks):
        logger.info(f"处理 chunk {i+1}/{len(chunks)} ({len(chunk)} 段)...")
        try:
            result = await polish_one_chunk(
                client=client,
                model=model,
                title=title,
                participants=participants,
                chunk=chunk,
                context_segments=context_segments[-10:],
            )
            polished_seg = result.get("polished") or chunk
            all_polished.extend(polished_seg)
            all_removed.extend(result.get("removed") or [])
            all_key_points.extend(result.get("key_points") or [])
            context_segments.extend(polished_seg)
            if result.get("summary"):
                final_summary = result["summary"]
        except Exception as e:
            logger.error(f"chunk {i+1} 失败: {e}", exc_info=True)
            all_polished.extend(chunk)

    logger.info(f"总 polished: {len(all_polished)} | removed: {len(all_removed)} | key_points: {len(all_key_points)}")

    # 5. 写回 DB
    await update_db_polished(MEETING_ID, all_polished, all_key_points, final_summary)

    # 6. 输出 removed 摘要
    if all_removed:
        logger.info(f"=== 删除的幻觉段（前 20 个）===")
        for r in all_removed[:20]:
            logger.info(f"  index={r.get('index')} reason={r.get('reason')}")

    logger.info("🎉 完成")


if __name__ == "__main__":
    asyncio.run(main())

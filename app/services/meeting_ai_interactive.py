"""会议实时 AI 互动服务

4 个能力：
1. summarize_recent(seconds) - 复述最近 N 秒
2. translate(text, src, dst) - 中英互译
3. summarize_now() - 阶段性纪要
4. ask_agent(question) - AI 提问
"""
import logging
from typing import Optional

from app.core.llm import extract_text_from_response, get_anthropic_client, get_default_model
from app.core.redis import get_redis
from app.services.meeting_transcript_buffer import get_recent_transcript

logger = logging.getLogger("microbubble.ai_interactive")


async def summarize_recent(meeting_id: int, seconds: int = 30) -> str:
    """重述最近 N 秒的转录"""
    entries = await get_recent_transcript(meeting_id, seconds)
    if not entries:
        return "（最近没有说话）"
    text = "\n".join(f"【{e['speaker']}】{e['text']}" for e in entries)
    prompt = f"请用中文简洁复述以下会议内容（150 字内）：\n\n{text}"
    return await _simple_llm_call(prompt)


async def translate(text: str, src: str = "zh", dst: str = "en") -> str:
    """中英互译"""
    lang_map = {"zh": "中文", "en": "English"}
    prompt = f"请将以下{lang_map.get(src, src)}翻译成{lang_map.get(dst, dst)}，保持原意：\n\n{text}"
    return await _simple_llm_call(prompt)


async def summarize_now(meeting_id: int) -> dict:
    """阶段性纪要（按议题）"""
    from app.services.meeting_analysis_service import meeting_analysis
    entries = await get_recent_transcript(meeting_id, seconds=3600 * 24)
    if not entries:
        return {"summary": "（无内容）", "key_points": [], "decisions": []}
    text = "\n".join(f"【{e['speaker']}】{e['text']}" for e in entries)
    return await meeting_analysis.analyze_transcript(text)


async def ask_agent(meeting_id: int, question: str) -> str:
    """AI 提问（小气反向提问基于当前转录）"""
    entries = await get_recent_transcript(meeting_id, seconds=120)
    text = "\n".join(f"【{e['speaker']}】{e['text']}" for e in entries)
    prompt = f"""基于以下会议内容（最近 2 分钟）回答提问。回答要简洁（50 字内）：

会议内容：
{text}

提问：{question}

回答："""
    return await _simple_llm_call(prompt)


async def _simple_llm_call(prompt: str) -> str:
    """轻量 LLM 调用（不走 agent 工具链）"""
    client = get_anthropic_client()
    model = get_default_model()
    response = await client.messages.create(
        model=model,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return extract_text_from_response(response)

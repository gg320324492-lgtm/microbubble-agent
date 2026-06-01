"""会议转录 AI 润色服务

职责：调用 Claude 把 ASR 口语化转录润色为书面语，结构化输出决策/待办/风险。
设计：纯 LLM 调用层 + Redis 缓存层。缓存命中时延迟 < 100ms。
"""
import hashlib
import json
import logging

from app.config import settings
from app.core.llm import (
    extract_text_from_response,
    get_anthropic_client,
    get_default_model,
    parse_llm_json,
)
from app.core.redis import get_redis
from app.services.prompts.meeting_polish import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

logger = logging.getLogger("microbubble.meeting_polish")


async def polish_segments(
    segments: list[dict],
    meeting_context: dict,
) -> dict:
    """
    把若干 ASR 原始转录段润色为书面语，结构化输出决策/待办/风险。

    Args:
        segments: [{"speaker": str, "text": str, "ts": float}]
        meeting_context: {"title": str, "participants": list[str], "topic": str|None, "context": list[dict]|None}

    Returns:
        {
            "polished": [{"speaker": str, "text": str, "ts": float}],
            "key_points": [{"text": str, "ts": float, "kind": "decision|todo|risk"}],
            "boundary_after_index": int | None,
            "summary": str | None,
        }
    """
    if not segments:
        return {"polished": [], "key_points": [], "boundary_after_index": None, "summary": None}

    title = meeting_context.get("title", "")
    participants = meeting_context.get("participants", [])
    topic = meeting_context.get("topic")
    context_history = meeting_context.get("context") or []

    topic_line = f"当前话题：{topic}" if topic else ""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        title=title,
        participants="、".join(participants) if participants else "未指定",
        topic_line=topic_line,
        segments_json=json.dumps(segments, ensure_ascii=False),
        context_json=json.dumps(context_history, ensure_ascii=False) if context_history else "无",
    )

    client = get_anthropic_client()
    model = get_default_model()
    response = await client.messages.create(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    # 使用项目统一 helper：处理 ThinkingBlock（mimo-v2.5/claude-sonnet-4 扩展思维）+ ```json``` 包裹
    raw_text = extract_text_from_response(response)

    try:
        result = parse_llm_json(raw_text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"AI 润色 JSON 解析失败: {e}, raw_text={raw_text[:200]}")
        return _fallback_polished(segments)

    return _validate_polish_result(result, segments)


def _fallback_polished(segments: list[dict]) -> dict:
    """LLM 失败时的降级路径：返回原文 + 空标注"""
    return {
        "polished": [{"speaker": s.get("speaker", "发言人"), "text": s["text"], "ts": s["ts"]} for s in segments],
        "key_points": [],
        "boundary_after_index": None,
        "summary": None,
    }


def _validate_polish_result(result: dict, original_segments: list[dict]) -> dict:
    """校验并规范化 AI 返回结果"""
    polished = result.get("polished") or []
    key_points = result.get("key_points") or []
    boundary = result.get("boundary_after_index")
    summary = result.get("summary")

    # 兜底：polished 为空时回退原文
    if not polished:
        polished = [{"speaker": s.get("speaker", "发言人"), "text": s["text"], "ts": s["ts"]} for s in original_segments]

    # 过滤非法 key_point kind
    valid_kinds = {"decision", "todo", "risk"}
    key_points = [kp for kp in key_points if kp.get("kind") in valid_kinds]

    return {
        "polished": polished,
        "key_points": key_points,
        "boundary_after_index": boundary if isinstance(boundary, int) else None,
        "summary": summary if isinstance(summary, str) else None,
    }


async def polish_segments_with_cache(
    meeting_id: int,
    segments: list[dict],
    meeting_context: dict,
) -> dict:
    """
    带缓存的润色入口。meeting_id 用于 Redis key 隔离。
    缓存命中时延迟 < 100ms（无 LLM 调用）。
    """
    if not segments:
        return {"polished": [], "key_points": [], "boundary_after_index": None, "summary": None}

    # 计算 segment hash（与测试保持一致：json.dumps(segments, sort_keys=True)，默认 ensure_ascii=True）
    segment_hash = hashlib.sha1(
        json.dumps(segments, sort_keys=True).encode()
    ).hexdigest()[:16]
    cache_key = f"polish:{meeting_id}:{segment_hash}"

    # 检查缓存
    r = await get_redis()
    cached = await r.get(cache_key)
    if cached:
        logger.debug(f"AI 润色缓存命中: {cache_key}")
        return json.loads(cached)

    # 缓存未命中，调 LLM
    if not settings.ENABLE_AI_POLISH:
        logger.info("ENABLE_AI_POLISH=False，跳过润色返回原文")
        return _fallback_polished(segments)

    result = await polish_segments(segments, meeting_context)

    # 写缓存（24h TTL）
    await r.set(cache_key, json.dumps(result, ensure_ascii=False), ex=settings.POLISH_CACHE_TTL_SECONDS)

    return result

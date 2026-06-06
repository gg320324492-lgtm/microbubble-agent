"""会议转录 AI 润色服务

职责：调用 Claude 把 ASR 口语化转录润色为书面语，结构化输出决策/待办/风险。
设计：纯 LLM 调用层 + Redis 缓存层。缓存命中时延迟 < 100ms。
"""
import hashlib
import json
import logging
import re

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


_PUNCTUATION_RE = re.compile(r"[\s,，.。!！?？;；:：、\"'“”‘’（）()【】\[\]《》<>-]+")
_FILLER_RE = re.compile(r"^(嗯|呃|啊|额|那个|就是|就是说)+")


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

    user_prompt = USER_PROMPT_TEMPLATE.format(
        segments_json=json.dumps(segments, ensure_ascii=False),
    )

    client = get_anthropic_client()
    model = get_default_model()
    response = await client.messages.create(
        model=model,
        max_tokens=8192,
        temperature=0.3,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    # 使用项目统一 helper：处理 ThinkingBlock（mimo-v2.5/claude-sonnet-4 扩展思维）+ ```json``` 包裹
    raw_text = extract_text_from_response(response)

    try:
        result = parse_llm_json(raw_text)
    except (json.JSONDecodeError, ValueError) as e:
        # 尝试修复截断的 JSON
        logger.warning(f"AI 润色 JSON 解析失败: {e}, raw_text={raw_text[:200]}")
        try:
            # 补全末尾的 ]
            fixed = raw_text.strip()
            if not fixed.endswith(']}'):
                # 找到最后一个完整的 speaker 条目
                last_complete = fixed.rfind('},')
                if last_complete > 0:
                    fixed = fixed[:last_complete + 1] + '\n  ]\n}'
            if not fixed.startswith('{'):
                fixed = '{' + fixed
            result = parse_llm_json(fixed)
            logger.info("JSON 修复成功")
        except Exception:
            logger.error("JSON 修复也失败，使用原文")
            return _fallback_polished(segments)

    return _validate_polish_result(result, segments)


def _fallback_polished(segments: list[dict]) -> dict:
    """LLM 失败时的降级路径：返回原文 + 空标注"""
    return {
        "polished": [{"speaker": s.get("speaker", "未知说话人"), "text": s["text"], "ts": s["ts"]} for s in segments],
        "key_points": [],
        "boundary_after_index": None,
        "summary": None,
    }


def _normalize_for_punctuation_check(text: str) -> str:
    """Normalize text to verify punctuation-only edits."""
    normalized = _PUNCTUATION_RE.sub("", text or "")
    normalized = _FILLER_RE.sub("", normalized)
    return normalized


def _is_punctuation_only_edit(original: str, polished: str) -> bool:
    """Return True when polished text only adds punctuation/removes fillers."""
    return _normalize_for_punctuation_check(original) == _normalize_for_punctuation_check(polished)


def _validate_polish_result(result: dict, original_segments: list[dict]) -> dict:
    """校验并规范化 AI 返回结果"""
    polished = result.get("polished") or []
    key_points = result.get("key_points") or []
    boundary = result.get("boundary_after_index")
    summary = result.get("summary")

    # 兜底：polished 为空时回退原文
    if not polished:
        polished = [{"speaker": s.get("speaker", "未知说话人"), "text": s["text"], "ts": s["ts"]} for s in original_segments]
    else:
        checked = []
        for i, original in enumerate(original_segments):
            item = polished[i] if i < len(polished) and isinstance(polished[i], dict) else {}
            candidate = item.get("text", "")
            if candidate and _is_punctuation_only_edit(original.get("text", ""), candidate):
                checked.append({
                    "speaker": item.get("speaker", original.get("speaker", "未知说话人")),
                    "text": candidate,
                    "ts": item.get("ts", original.get("ts")),
                })
            else:
                logger.warning(
                    "AI 润色疑似改写，已回退原文: original=%s polished=%s",
                    original.get("text", "")[:80],
                    candidate[:80],
                )
                checked.append({
                    "speaker": original.get("speaker", "未知说话人"),
                    "text": original.get("text", ""),
                    "ts": original.get("ts"),
                })
        polished = checked

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


async def polish_segments_with_lock(
    meeting_id: int,
    segments: list[dict],
    meeting_context: dict,
    _retry: int = 0,
) -> dict:
    """
    带并发锁的润色入口。同 meeting_id 同一时间只允许 1 个 LLM 调用。
    后到的请求会等待锁释放，然后共享同一缓存结果。

    锁语义：Redis SETNX + TTL（防崩溃导致死锁），无重试上限但实践中：
    - 持锁方完成后会写缓存
    - 等待方 200ms 后重读缓存，命中即返回
    - 缓存未命中才递归重试（持锁方可能还在写）
    - 兜底：递归 5 次后仍拿不到锁则直接调 with_cache（防极端情况死循环）
    """
    import asyncio

    if not segments:
        return {"polished": [], "key_points": [], "boundary_after_index": None, "summary": None}

    lock_key = f"polish:lock:{meeting_id}"
    r = await get_redis()

    # 尝试获取锁（SETNX + TTL）
    acquired = await r.set(lock_key, "1", nx=True, ex=settings.POLISH_LOCK_TTL_SECONDS)

    try:
        if not acquired:
            # 锁被占用，等待 200ms 后重读缓存（持锁方可能刚写入）
            await asyncio.sleep(0.2)
            segment_hash = hashlib.sha1(
                json.dumps(segments, sort_keys=True).encode()
            ).hexdigest()[:16]
            cached = await r.get(f"polish:{meeting_id}:{segment_hash}")
            if cached:
                return json.loads(cached)
            # 缓存仍无，递归重试（兜底：5 次后放弃抢锁，直接调 with_cache）
            if _retry >= 5:
                logger.warning(f"polish 锁递归重试 {_retry} 次仍未拿到，降级为 with_cache")
                return await polish_segments_with_cache(meeting_id, segments, meeting_context)
            return await polish_segments_with_lock(meeting_id, segments, meeting_context, _retry=_retry + 1)

        # 拿到锁，执行润色
        return await polish_segments_with_cache(meeting_id, segments, meeting_context)
    finally:
        if acquired:
            await r.delete(lock_key)

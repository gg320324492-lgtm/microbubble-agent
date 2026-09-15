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
    LLMClient,
    extract_text_from_response,
    parse_llm_json,
)
from app.core.redis import get_redis
from app.services.prompts.meeting_polish import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

logger = logging.getLogger("microbubble.meeting_polish")

# 2026-07-20 polish dispatch 修 (P0): get_anthropic_client() 写死只走 anthropic,
# LLM_BACKEND=openai_compat/ollama 时仍会拿 CLAUDE_API_KEY 打 mimo anthropic endpoint,
# 401 invalid_key. 改用 LLMClient().complete() 自动 dispatch 任意 backend.
_LLM_SINGLETON: LLMClient | None = None


def _get_llm() -> LLMClient:
    """模块级 LLMClient 单例（polish batch 200 条避免 200 次 init）"""
    global _LLM_SINGLETON
    if _LLM_SINGLETON is None:
        _LLM_SINGLETON = LLMClient()
    return _LLM_SINGLETON


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

    # 2026-07-20 P0 fix: 走 LLMClient dispatch (anthropic/openai_compat/ollama 自动切换)
    # - thinking={"type": "disabled"} 强制纯文本输出（qwen3:8b / mimo-v2.5 thinking block
    #   会污染 JSON parse，extract_text_from_response 只取 .text 不取 .thinking）
    # - max_tokens=8192 与旧实现一致（polish 输出 ~80 segments JSON 需 ~6K tokens）
    llm = _get_llm()
    response = await llm.complete(
        messages=[{"role": "user", "content": user_prompt}],
        system=SYSTEM_PROMPT,
        max_tokens=8192,
        temperature=0.3,
        thinking={"type": "disabled"},
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


def _is_reasonable_edit(original: str, polished: str) -> bool:
    """2026-06-11 升级：允许轻量清理（幻觉删除 + 同音错字修正）。

    规则：
    1. 字符差异 ≤ 10%（去除标点和空格后）— 允许标点、少量字符增删
    2. polished 是 original 的子串 — 允许删除中间内容（如幻觉）
    3. 双方都为空 — 允许
    """
    norm_orig = _normalize_for_punctuation_check(original)
    norm_polish = _normalize_for_punctuation_check(polished)

    if not norm_orig and not norm_polish:
        return True
    if not norm_orig:
        return not norm_polish  # 原为空，polished 也应为空
    if not norm_polish:
        return False  # 原文非空但 polished 为空 — 整段被删（需走 removed 逻辑）

    # 规则 1: 字符差异 ≤ 10%
    len_diff = abs(len(norm_orig) - len(norm_polish))
    max_allowed = max(5, int(len(norm_orig) * 0.10))
    if len_diff <= max_allowed:
        return True

    # 规则 2: polished 是 original 的子串（允许删除中间内容）
    if norm_polish in norm_orig:
        return True

    return False


def _validate_polish_result(result: dict, original_segments: list[dict]) -> dict:
    """校验并规范化 AI 返回结果（2026-06-11 升级：支持 removed 段 + 合理编辑验证）"""
    polished = result.get("polished") or []
    removed = result.get("removed") or []
    key_points = result.get("key_points") or []
    boundary = result.get("boundary_after_index")
    summary = result.get("summary")

    # 构建被删除段的 index 集合
    removed_indices: set[int] = set()
    for r in removed:
        if isinstance(r, dict) and isinstance(r.get("index"), int):
            removed_indices.add(r["index"])

    # 兜底：polished 为空时回退原文
    if not polished:
        polished = [{"speaker": s.get("speaker", "未知说话人"), "text": s["text"], "ts": s["ts"]} for s in original_segments]
    else:
        # 2026-06-11 升级：polished 可能比 original_segments 少（被 removed 的段不出现在 polished 中）
        # 用 original 索引匹配 polished — 跳过 removed 的段
        polished_iter = iter(polished)
        checked = []
        for i, original in enumerate(original_segments):
            if i in removed_indices:
                # 该段被 AI 标记删除，跳过（不进 checked）
                continue
            try:
                item = next(polished_iter)
            except StopIteration:
                # polished 遍历完，剩下 original 段都按原文
                checked.append({
                    "speaker": original.get("speaker", "未知说话人"),
                    "text": original.get("text", ""),
                    "ts": original.get("ts"),
                })
                continue
            if not isinstance(item, dict):
                checked.append({
                    "speaker": original.get("speaker", "未知说话人"),
                    "text": original.get("text", ""),
                    "ts": original.get("ts"),
                })
                continue
            candidate = item.get("text", "")
            if candidate and _is_reasonable_edit(original.get("text", ""), candidate):
                checked.append({
                    "speaker": item.get("speaker", original.get("speaker", "未知说话人")),
                    "text": candidate,
                    "ts": item.get("ts", original.get("ts")),
                })
            else:
                # 改写幅度过大，回退原文
                logger.warning(
                    "AI 润色疑似改写（差异超过 10%%），已回退原文: original=%s polished=%s",
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
        "removed": removed if isinstance(removed, list) else [],
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

    ⚠️ 注意：本函数把**传入的全部 segments 一次性**发一个 prompt。整场会议
    （上千段、3~6 万字）会远超模型上下文。长会议请改用
    `polish_segments_batched()`（2026-09-15 P0 新增）。
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


# ====================================================================
# 2026-09-15 P0 新增：整场会议的**分批**润色
# ====================================================================
def split_polish_batches(segments: list[dict],
                         max_chars: int | None = None,
                         max_segments: int | None = None) -> list[list[dict]]:
    """按"累计字符数 + 段数"双阈值切批，保证单个 prompt 落在模型上下文内。

    事故（会议 250 / 2026-09-15）：流水线把 1904 段一次性交给 polish，
    prompt 达 **63,545 tokens**，而 ollama 的 num_ctx 只有 **16,386** ——
    服务端日志 `truncating input prompt limit=16386 prompt=63545`，
    截断后的请求又撞上客户端 10 分钟超时 → `AI 润色失败（降级为原文）:
    Request timed out.` → 1904 段全部原样保留 → 质量指标
    `polish_real_change_ratio=0.0`（历史会议 246 同样是 0，同一个根因）。
    """
    max_chars = max_chars or settings.POLISH_LLM_BATCH_MAX_CHARS
    max_segments = max_segments or settings.POLISH_LLM_BATCH_MAX_SEGMENTS
    batches: list[list[dict]] = []
    cur: list[dict] = []
    cur_chars = 0
    for seg in segments:
        seg_chars = len(json.dumps(seg, ensure_ascii=False))
        if cur and (cur_chars + seg_chars > max_chars or len(cur) >= max_segments):
            batches.append(cur)
            cur, cur_chars = [], 0
        cur.append(seg)
        cur_chars += seg_chars
    if cur:
        batches.append(cur)
    return batches


async def polish_segments_batched(
    meeting_id: int,
    segments: list[dict],
    meeting_context: dict,
    on_progress=None,
) -> dict:
    """把整场会议分段后逐批润色，批次间互不影响。

    - 每批走 `polish_segments_with_cache`（保留原有缓存/锁语义）
    - 单批失败只影响这一批（用原文兜底），不会像原实现那样**一场会议整批降级**
    - 按输入顺序拼接结果，保持与输入一一对应（下游靠 index 回写）
    """
    if not segments:
        return {"polished": [], "key_points": [], "boundary_after_index": None, "summary": None}

    batches = split_polish_batches(segments)
    total = len(batches)
    logger.info(
        f"AI 润色分批: {len(segments)} 段 → {total} 批"
        f"（每批 ≤{settings.POLISH_LLM_BATCH_MAX_CHARS} 字 / "
        f"{settings.POLISH_LLM_BATCH_MAX_SEGMENTS} 段）"
    )

    polished_all: list[dict] = []
    key_points_all: list[dict] = []
    failed_batches = 0

    for i, batch in enumerate(batches):
        try:
            result = await polish_segments_with_cache(meeting_id, batch, meeting_context)
            polished = (result or {}).get("polished") or []
            if len(polished) != len(batch):
                # 长度不一致说明模型漏项/多项 → 本批用原文兜底，避免 index 错位污染全文
                logger.warning(
                    f"润色批 {i + 1}/{total} 段数不匹配 "
                    f"(输入 {len(batch)} / 输出 {len(polished)})，本批用原文兜底"
                )
                polished = _fallback_polished(batch)["polished"]
                failed_batches += 1
            polished_all.extend(polished)
            key_points_all.extend((result or {}).get("key_points") or [])
        except Exception as e:  # noqa: BLE001 — 单批失败不拖垮整场
            failed_batches += 1
            logger.warning(f"润色批 {i + 1}/{total} 失败（本批用原文兜底）: "
                           f"{type(e).__name__}: {e}")
            polished_all.extend(_fallback_polished(batch)["polished"])
        if on_progress:
            try:
                on_progress(i + 1, total)
            except Exception:  # noqa: BLE001
                pass

    logger.info(
        f"AI 润色分批完成: {total - failed_batches}/{total} 批成功, "
        f"共 {len(polished_all)} 段"
    )
    return {
        "polished": polished_all,
        "key_points": key_points_all,
        "boundary_after_index": None,
        "summary": None,
    }

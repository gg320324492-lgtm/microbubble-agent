"""对话长期记忆 (2026-11-04 C 档) —— 被上下文预算裁掉的轮次向量化存档 + 按需召回

## 解决什么问题

B 档把会话窗口从「30 条」改成「按 token 预算裁」之后，多出一批**被裁掉但并没过期**
的历史: 用户十几轮前说过的约束、报过的参数、给过的名字，如今超出 60k 预算就送不进
模型了。C 档把这部分**原文向量化存起来**，等用户再次问到相关内容时，按语义召回
top-K 条、以「长期记忆」section 的形式注入系统提示词 —— 窗口装不下的，用检索补。

## 三条设计取舍 (都写在这里，因为它们都是「违反直觉但故意这么做」的)

**① 只存 user 轮，绝不存 assistant 轮。**
把模型的输出回灌成长期记忆 = 把幻觉固化成"事实"，本仓已为此付过代价
(memory #30「助手幻觉经记忆提取固化引用」)。user 轮是用户说过的原话，
天然带来源，错了也是用户的表述，不是模型编的。
⇒ `pick_memorable_turns` 里 `role != "user"` 直接跳过，**没有例外通道**。

**② 不依赖 LLM，只用本地 embedding。**
已有的 `_extract_knowledge_bg` 走 LLM 提炼后写 `knowledge` 表 —— 那是"知识"，
需要判断值不值得存。本档存的是" Episode 原文"，不需要判断，也就不该引入依赖:
2026-10-30 MiniMax 额度用尽 (429 code 2056) 时纪要/RAG/对话全死，
若记忆写入库也要 LLM，那种日子里连记忆都会静默停摆。
⇒ 本模块只调 `generate_embedding` (本地 Qwen3-Embedding-0.6B)。

**③ 写路径必须是后台任务 + 独立 session。**
embedding 模型按需加载，冷启动实测 **20–36 秒** (memory #52 / 类 20.237) ——
放进对话主路径就是把首字延迟从 1 秒变成 30 秒。
⇒ `capture_overflow` 由调用方 `asyncio.create_task` 起，内部自带
`async_session()`，异常只记日志、**绝不影响本轮对话**。

## 与 B 档的接口

`_trim_messages_to_budget` 返回 `(送给模型的窗口, 被裁掉的那一段)`，
被裁掉的这一段就是本模块的原料 —— 两条对话路径 (chat / chat_stream) 共用同一个
函数，所以「裁剪」和「捕获」在结构上不可能只接了一条 (类 20.250 ①)。

## ⚠️ `memories` 表在库里没有任何约束 (类 20.256)

无主键 / 无外键 / 无索引 ⇒ 唯一性与性能都在应用层兜:
- 唯一性: `key` 存内容 sha256 前 16 位，写入前先查 (见 `capture_overflow`)
- 性能: 表只有几十到几千行，向量精确扫描 (<=> 无索引 = 全表精扫) 反而**召回率 100%**，
  比 HNSW 近似更准; 行数超万再考虑建索引 (届时才是类 20.163 的适用场景)
- 增长: `CONVERSATION_MEMORY_MAX_PER_USER` 到量后把最旧的置 `is_active=False`
  (**停用不删**，可回退)
"""
import hashlib
import logging
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import select, update

from app.agent.context_budget import _has_tool_result
from app.config import settings
from app.core.message_sanitizer import contains_native_tool_marker

logger = logging.getLogger(__name__)

# `memories.memory_type` 是本档专用的取值 (varchar(20))
MEMORY_TYPE_EPISODE = "episode"

# 短于此长度的轮次没有信息量 ("嗯" / "好的" / "继续")
MIN_TURN_CHARS = 20
# 单条记忆的正文字数上限: 召回结果要塞进 system，太长会把预算吃回去
MAX_CONTENT_CHARS = 800


def parse_allowed_users(raw: str) -> set:
    """解析 `CONVERSATION_MEMORY_ALLOWED_USERS` (逗号分隔的 user_id)。

    坏值**跳过 + 记日志**而不是整个解析失败 —— 一个手误写进来的 "3，58"
    (中文逗号) 不该让灰度静默全关; 但也不能悄悄把非数字当成通配。
    """
    out = set()
    for chunk in (raw or "").split(","):
        s = chunk.strip()
        if not s:
            continue
        try:
            out.add(int(s))
        except ValueError:
            logger.warning("[长期记忆] 白名单里有非数字项, 已跳过: %r", s)
    return out


def is_conversation_memory_enabled(user_id: Optional[int]) -> bool:
    """**唯一**的生效判据 —— 写路径与读路径都必须调它 (类 20.250 ①)。

    语义 (2026-11-04 主指挥选「按白名单灰度」):

    | 白名单 | 总开关 | 结果 |
    |---|---|---|
    | 非空 | 任意 | **只有名单内用户启用** (白名单优先, 便于总开关还关着就先灰度) |
    | 空   | True  | 全员启用 (将来全量的开关) |
    | 空   | False | 全员关闭 (默认) |

    为什么不允许「读时判、写时不判」这种分叉: 那会让名单外的用户**召回不到任何东西**
    (读关) 却仍被后台写入, 或反过来写入关掉但召回一直空跑 —— 两侧不同步的缺陷
    在功能测试里极难看出 (类 20.220)。
    """
    if not user_id:
        return False
    raw = getattr(settings, "CONVERSATION_MEMORY_ALLOWED_USERS", "") or ""
    allowed = parse_allowed_users(raw)
    if allowed:
        return int(user_id) in allowed
    return bool(getattr(settings, "CONVERSATION_MEMORY_ENABLED", False))


def content_key(text: str) -> str:
    """内容指纹 (sha256 前 16 位) —— 库里该表**没有唯一约束**，去重全靠它。"""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def _plain_text(content: Any) -> str:
    """取一条消息里的纯文本。

    只认 `str` 与 `type=="text"` 的块 —— **tool_result 块不算用户说的话**，
    它是工具返回，存进"用户记忆"里会在召回时把系统数据冒充成用户原话。
    """
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        pieces = [
            str(b.get("text") or "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        return " ".join(p for p in pieces if p).strip()
    return ""


def pick_memorable_turns(
    dropped: Iterable[Any],
    min_chars: int = MIN_TURN_CHARS,
    max_chars: int = MAX_CONTENT_CHARS,
) -> List[str]:
    """从被裁掉的消息里挑出「值得存成记忆」的用户原话。

    纯函数，不碰 DB / 不碰模型 —— 便于测试，也让筛选规则一眼可审。

    跳过四种: 非 user 轮 / 含 tool_result 的 user 轮 / 太短 / 带原生工具标记的污染轮。
    """
    out: List[str] = []
    seen: set = set()
    for msg in dropped or []:
        if not isinstance(msg, dict):
            continue
        if msg.get("role") != "user":
            continue
        if _has_tool_result(msg):
            continue
        text = _plain_text(msg.get("content"))
        if len(text) < min_chars:
            continue
        if contains_native_tool_marker(text):
            continue
        if max_chars and len(text) > max_chars:
            text = text[:max_chars]
        k = content_key(text)
        if k in seen:
            continue
        seen.add(k)
        out.append(text)
    return out


def format_memory_block(rows: List[Any]) -> str:
    """把召回到的记忆拼成注入 system 的 section。

    ⚠️ 标题必须含「长期记忆」四个字 —— `app/agent/prompts.py:381` 的反幻觉纪律
    正是按这个名字要求模型「只作参考、必须重新验证」。名字对不上，那条纪律
    就成了一句指向空气的话 (类 20.220)。
    """
    if not rows:
        return ""
    lines = [
        "\n## 长期记忆（历史对话中被裁掉的相关内容，仅供参考）",
        "以下是本用户更早的对话原话，因超出本轮上下文预算未直接给出，按语义召回。"
        "**这些是历史表述，不是本轮检索结果**：涉及人名/数据/结论时必须用工具重新确认，"
        "与本轮工具返回冲突时以工具返回为准。",
    ]
    for r in rows:
        content = (r.content or "").strip().replace("\n", " ")
        if len(content) > MAX_CONTENT_CHARS:
            content = content[:MAX_CONTENT_CHARS]
        lines.append("- " + content)
    return "\n".join(lines) + "\n"


async def capture_overflow(
    user_id: int,
    dropped: Optional[List[Dict[str, Any]]],
    session_id: str = "",
) -> int:
    """把被裁掉的用户轮次向量化写入 `memories` (episode)。

    返回新写入行数。任何异常都只记日志并返回 0 —— **记忆是增益，不能拖垮对话**
    (调用方本来就在 create_task 里，这里再兜一层，因为 embedding 不可用时
    抛出来也没人接)。
    """
    if not user_id or not dropped:
        return 0
    if not is_conversation_memory_enabled(user_id):
        return 0

    texts = pick_memorable_turns(dropped)
    if not texts:
        return 0

    try:
        from app.services.embedding_service import generate_embeddings
        from app.core.database import async_session
        from app.models.memory import Memory

        keys = [content_key(t) for t in texts]

        async with async_session() as db:
            # 去重: 该表无唯一约束，先查已有 key 再插 (类 20.256)
            existing = set((await db.execute(
                select(Memory.key).where(
                    Memory.user_id == user_id,
                    Memory.memory_type == MEMORY_TYPE_EPISODE,
                    Memory.key.in_(keys),
                )
            )).scalars().all())

            fresh = [(t, k) for t, k in zip(texts, keys) if k not in existing]
            if not fresh:
                logger.debug(
                    "[长期记忆] 本轮溢出 %d 条全部已存在, 未写入 (user=%s)",
                    len(texts), user_id,
                )
                return 0

            # 向量化 (本地模型, 冷启动 20-36s —— 这就是本函数必须在后台跑的原因)
            vecs = await generate_embeddings([t for t, _ in fresh], for_query=False)
            if not vecs or len(vecs) != len(fresh):
                logger.warning(
                    "[长期记忆] embedding 不可用, 本轮 %d 条未入库 (user=%s)",
                    len(fresh), user_id,
                )
                return 0

            now = _utcnow_naive()
            for (text, key), vec in zip(fresh, vecs):
                if vec is None:
                    continue
                db.add(Memory(
                    user_id=user_id,
                    memory_type=MEMORY_TYPE_EPISODE,
                    key=key,
                    content=text,
                    importance=0.5,
                    access_count=0,
                    last_accessed_at=now,
                    source_session=(session_id or "")[:100],
                    is_active=True,
                    embedding=vec,
                ))
            await db.commit()
            written = sum(1 for _, v in zip(fresh, vecs) if v is not None)
            logger.info(
                "[长期记忆] 捕获溢出对话 %d 条 (user=%s, 本轮丢弃 %d 条消息)",
                written, user_id, len(dropped),
            )
            await _apply_capacity_cap(db, user_id)
            return written
    except Exception as e:  # noqa: BLE001 — 记忆写失败必须静默降级, 但要有日志
        logger.warning(f"[长期记忆] 捕获异常 (user={user_id}): {e}")
        return 0


def _utcnow_naive():
    """naive UTC —— 该表两个时间列都是 `timestamp without time zone`。

    与类 20.251 ① 同条纪律: `datetime.now(timezone.utc)` 直接传给 naive 列，
    asyncpg 会 `DataError: can't subtract offset-naive and offset-aware`。
    本仓标准写法就是 `.replace(tzinfo=None)` (app/models/base.py 的 utcnow)。
    """
    from app.models.base import utcnow
    return utcnow()


async def _apply_capacity_cap(db, user_id: int) -> None:
    """超过 `CONVERSATION_MEMORY_MAX_PER_USER` 时把最旧的置 is_active=False。

    **停用而不是删除** —— 数据留着，调大上限即可恢复；删了就没有下一次拍板的机会。
    """
    cap = getattr(settings, "CONVERSATION_MEMORY_MAX_PER_USER", 1000) or 0
    if cap <= 0:
        return
    try:
        from app.models.memory import Memory
        keep_ids = (await db.execute(
            select(Memory.id).where(
                Memory.user_id == user_id,
                Memory.memory_type == MEMORY_TYPE_EPISODE,
                Memory.is_active.is_(True),
            ).order_by(Memory.id.desc()).limit(cap)
        )).scalars().all()
        if not keep_ids:
            return
        await db.execute(
            update(Memory).where(
                Memory.user_id == user_id,
                Memory.memory_type == MEMORY_TYPE_EPISODE,
                Memory.is_active.is_(True),
                Memory.id.notin_(keep_ids),
            ).values(is_active=False)
        )
        await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[长期记忆] 容量封顶异常 (user={user_id}): {e}")


async def recall_memories(
    db,
    user_id: int,
    query: str,
    top_k: Optional[int] = None,
):
    """按语义召回该用户的历史对话记忆 (pgvector 余弦距离, 无索引 ⇒ 全表精扫)。

    返回 `Memory` 列表 (已触发 ORM 对象属性可读)。失败一律返 [] ——
    召回不到只是"没有增益", 不能变成对话报错。
    """
    # 与写路径**同一个判据** (类 20.250 ①): 白名单内外必须读写一致,
    # 否则会出现"名单外的用户一直被后台写入却永远召回不到"。
    if not is_conversation_memory_enabled(user_id):
        return []
    if db is None or not (query or "").strip():
        return []
    k = top_k if top_k is not None else (
        getattr(settings, "CONVERSATION_MEMORY_TOP_K", 4) or 0)
    if k <= 0:
        return []

    try:
        # ⚠️ 读路径的门禁: 模型**没热就不召回**, 而不是顺便去加载。
        # 原因很具体: 本函数在 `_build_system_prompt` 里被调, 挂在**首字延迟**的
        # 关键路径上; 而按需加载的冷启动实测 20–36s (类 20.237), `generate_embedding`
        # 的 60s 超时挡不住这种慢, 只会让它慢慢走完 ⇒ 用户看到的是"助手卡住半分钟"。
        # 写路径 (`capture_overflow`) 不加这道门 —— 它在后台任务里, 顺便预热是收益。
        from app.services.embedding_service import generate_embedding, is_embedding_loaded
        from app.models.memory import Memory

        if not is_embedding_loaded():
            logger.debug("[长期记忆] embedding 模型未加载, 本轮跳过召回 (不触发加载)")
            return []

        # for_query=False: 与**现役检索的实际口径**一致, 不是随手写的。
        # hybrid_retriever.py:112 传的是 (for_query=True, has_query_prompt=False),
        # 而 build_embedding_prompt(True, False) 返回 **None** ⇒ 两侧都是无前缀向量。
        # 存档侧同样无前缀。若这里改成真 query 模式, 查询向量会与存档向量落在
        # 两种表征上, 召回静默变差且不报错 (类 20.220)。
        qvec = await generate_embedding(query.strip(), for_query=False, has_query_prompt=False)
        if not qvec:
            logger.debug("[长期记忆] query embedding 不可用, 跳过召回")
            return []

        dist = Memory.embedding.cosine_distance(qvec).label("dist")
        rows = (await db.execute(
            select(Memory, dist)
            .where(
                Memory.user_id == user_id,
                Memory.memory_type == MEMORY_TYPE_EPISODE,
                Memory.is_active.is_(True),
                Memory.embedding.isnot(None),
            )
            .order_by(dist)
            .limit(k)
        )).all()

        memories = [m for m, _ in rows]
        if memories:
            logger.info(
                "[长期记忆] 召回 %d 条 (user=%s, 最近距离=%.3f)",
                len(memories), user_id, rows[0][1],
            )
        return memories
    except Exception as e:  # noqa: BLE001 — 召回失败不阻断对话
        logger.warning(f"[长期记忆] 召回异常 (user={user_id}): {e}")
        return []


async def recall_and_format(db, user_id: int, query: str) -> str:
    """召回 + 拼成可直接追加到 system 的文本块 (无结果返 "")。"""
    rows = await recall_memories(db, user_id, query)
    if not rows:
        return ""
    block = format_memory_block(rows)
    if block:
        await _touch_access(db, [r.id for r in rows if r.id is not None])
    return block


async def _touch_access(db, ids: List[int]) -> None:
    """记一次访问 (access_count / last_accessed_at)。失败静默。"""
    if not ids:
        return
    try:
        from app.models.memory import Memory
        await db.execute(
            update(Memory).where(Memory.id.in_(ids)).values(
                access_count=Memory.access_count + 1,
                last_accessed_at=_utcnow_naive(),
            )
        )
        await db.commit()
    except Exception as e:  # noqa: BLE001 — 统计字段写失败不值得影响回答
        logger.debug(f"[长期记忆] access_count 更新失败: {e}")


__all__ = [
    "MEMORY_TYPE_EPISODE",
    "MIN_TURN_CHARS",
    "MAX_CONTENT_CHARS",
    "content_key",
    "pick_memorable_turns",
    "format_memory_block",
    "capture_overflow",
    "recall_memories",
    "recall_and_format",
]

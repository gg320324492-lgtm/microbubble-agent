"""MicroBubbleAgent — 主类（v2 架构）

设计：
- 主类只做依赖装配（~150 行）
- 所有 chat 逻辑委托给 ChatEngine
- 向后兼容旧的 MicroBubbleAgent 接口（chat/chat_stream/clear_session）

对外接口（保持与旧 core.py 一致）：
- agent = MicroBubbleAgent()  单例
- await agent.chat(message, session_id, db, user_id, ...) -> dict
- async for event in agent.chat_stream(message, session_id, db, user_id, ...): ...
- await agent.clear_session(session_id)

#043 账号持久化聊天历史 — 流式 chat_stream 持久化（2026-06-29）
流式 chat 进入时 append_message(user_msg) + 结束时 append_message(assistant_full)
中断/异常时 mark_partial，session 行由 ensure_session_for_stream() 保证存在。
"""

import asyncio
import base64
import logging
import time
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

from sqlalchemy import select

from app.agent.chat_engine import ChatEngine
from app.agent.intent_classifier import classify_intent
from app.agent.prompts import (
    _is_meeting_transcript_query,
    get_intent_aware_guidelines,
    get_meeting_analyzer_prompt,
    get_system_prompt,
)
from app.agent.protocol import StreamEvent
from app.agent.session_manager import session_manager
from app.agent.thinking_config import resolve_thinking_config
from app.agent.tool_registry import ToolContext
from app.agent.tracing import TraceCollector
from app.config import settings
from app.models.base import BEIJING_TZ
# CHAT-P0-D W98 +0: RAG 评估可选抽样钩子 (EVAL_SAMPLE_RATE, 默认 0 关闭)
from app.services.rag_evaluator import get_eval_sample_rate, maybe_evaluate_async
# CHAT-P2-F W98 +6: 会话上下文公共函数 (微信 handler 同步共用)
# 旧实现下划线私有函数已被删除, 通过 alias 暴露给老测试桩 (TestFetchPgMessages
# / TestEnsureSessionContext / TestLastPgId / TestChatStreamHistoryInjection)
from app.services.session_context import (
    _fetch_pg_messages,
    _get_last_pg_id,
    SESSION_CONTEXT_MAX_MSGS as _SESSION_CONTEXT_MAX_MSGS,
    ensure_session_context as _ensure_session_context,
    set_last_pg_id as _set_last_pg_id,
)

logger = logging.getLogger("microbubble.agent")


def _is_questionish(s: str) -> bool:
    """追问 chip 出口校验辅助 — 无问号但含疑问词也算问句形态 (2026-09-01)"""
    import re as _re_q
    return bool(
        _re_q.search(
            r"(什么|怎么|如何|哪些|多少|为什么|吗|呢|能不能|可不可以|"
            r"详细|原理|标准|范围|案例|方向|操作|步骤|介绍|比较)",
            s or "",
        )
    )


# ============================================================================
# 2026-07-31 #CHAT-P0-A: 会话上下文闭环 — PG 回填 Redis（"失忆客服"根因修复）
# ============================================================================
# W98 P2-F 抽公共: ensure_session_context + set_last_pg_id 已迁至
#   app/services/session_context.py (微信 handler 共用)。本文件保留
#   _window_messages (chat 内调用, 不动) + _LAST_TURN_META_FIELD (回填元数据)。

# 回填元数据: session_meta 字段名 (CHAT-P0-A 配套, 保留)
_LAST_TURN_META_FIELD = "last_turn"


def _compact_topic_results(results: List[Dict], limit: int = 10) -> List[Dict]:
    """把 search_knowledge 结果压缩为 last_turn 可序列化锚点。"""
    compact: List[Dict] = []
    for row in results[:limit]:
        if not isinstance(row, dict) or row.get("id") is None:
            continue
        compact.append({
            "id": row["id"],
            "title": (row.get("title") or "")[:200],
            "content": (row.get("content") or "")[:500],
        })
    return compact


def _build_last_turn(intent, query: str, answer: str, results: List[Dict]) -> Dict[str, Any]:
    """构造回答完成后写入 Redis Hash 的 last_turn。"""
    compact = _compact_topic_results(results)
    return {
        "intent": intent.category.value if intent is not None else "casual_chat",
        "query": query,
        "chunk_ids": [row["id"] for row in compact],
        "answer_summary": (answer or "")[:200],
        "topics": [row["title"] for row in compact[:5] if row.get("title")],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _set_last_turn(session_id: str, intent, query: str, answer: str, results: List[Dict]):
    """best-effort 保存 last_turn，Redis 故障不阻断流式。"""
    try:
        await session_manager.set_session_meta(
            session_id,
            _LAST_TURN_META_FIELD,
            _build_last_turn(intent, query, answer, results),
        )
    except Exception as e:
        logger.warning(f"set last_turn failed (best-effort): {e}")


async def _load_knowledge_by_ids(db, ids: List[int]) -> List[Dict]:
    """按 last_turn 顺序回查上一轮知识条目。"""
    if db is None or not ids:
        return []
    from app.models.knowledge import Knowledge

    rows = (await db.execute(select(Knowledge).where(
        Knowledge.id.in_(ids),
        Knowledge.deleted_at.is_(None),
        Knowledge.storage_mode == "kb",
        Knowledge.visibility.in_(["team", "public"]),
    ))).scalars().all()
    by_id = {row.id: row for row in rows}
    return [
        {"id": row.id, "title": row.title or "", "content": (row.content or "")[:500]}
        for kid in ids
        if (row := by_id.get(kid)) is not None
    ]


async def _build_follow_up_context(db, session_id: str, query: str) -> str:
    """若上一轮是 search_info，复用其结果并追加一次 0.8s 上限检索。"""
    try:
        last_turn = await session_manager.get_session_meta(session_id, _LAST_TURN_META_FIELD)
        if not isinstance(last_turn, dict) or last_turn.get("intent") != "search_info":
            return ""

        reused: List[Dict] = []
        ids = [int(x) for x in last_turn.get("chunk_ids", [])[:10]]
        if db is not None and ids:
            try:
                reused = await _load_knowledge_by_ids(db, ids)
            except Exception as e:
                logger.warning(f"follow_up id reuse skipped: {e}")

        fresh: List[Dict] = []
        if db is not None:
            try:
                from app.services.hybrid_retriever import get_hybrid_retriever
                retrieval_query = " ".join(filter(None, [
                    str(last_turn.get("query") or "").strip(),
                    " ".join(str(x) for x in last_turn.get("topics", [])[:5] if x),
                    query.strip(),
                ]))
                fresh = await asyncio.wait_for(
                    get_hybrid_retriever(db).retrieve(
                        query=retrieval_query or query, top_k=5,
                        enable_vector=True, enable_bm25=True,
                        enable_graph=False, enable_rerank=False,
                    ),
                    timeout=0.8,
                )
            except asyncio.TimeoutError:
                logger.warning("follow_up additional retrieval timed out")
            except Exception as e:
                logger.warning(f"follow_up additional retrieval skipped: {e}")

        combined: List[Dict] = []
        seen = set()
        for row in reused + fresh:
            rid = row.get("id") if isinstance(row, dict) else None
            if rid is None or rid in seen:
                continue
            seen.add(rid)
            combined.append(row)

        topics = [str(x) for x in last_turn.get("topics", []) if x][:5]
        lines = [
            "## 上一轮话题（续讲指代消解）",
            f"上一轮主题：{str(last_turn.get('answer_summary') or '')[:200]}",
            f"话题：{'、'.join(topics)}",
            "用户是在要求续讲上一轮，不是开启无关新话题。优先沿用以下资料，再自然补充新角度：",
        ]
        lines.extend(
            f"- [{row.get('id')}] {row.get('title') or '未命名'}：{(row.get('content') or '')[:240]}"
            for row in combined[:10]
        )
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"follow_up context failed (best-effort): {e}")
        return ""


async def _build_attached_knowledge_block(db, knowledge_ids: List[int]) -> str:
    """从知识库加载用户手动附加的文档, 拼成 system context block。

    2026-08-15 #P4: 资料库 → 聊天闭环核心。
    - 硬上限 8 条 (防 system prompt 爆炸)
    - 每条 content 截断 2000 字
    - 按输入顺序保持
    - 失败 / 不存在 / 已删除 / 网盘文件 静默跳过 (best-effort)
    """
    logger.info(f"[P4-attached] 收到 {len(knowledge_ids)} 个 ID: {knowledge_ids[:10]}")
    try:
        # 1. 去重 + 截断到上限
        seen: set = set()
        unique_ids: List[int] = []
        for kid in (knowledge_ids or [])[:8]:
            try:
                kid_int = int(kid)
            except (ValueError, TypeError):
                continue
            if kid_int and kid_int not in seen:
                seen.add(kid_int)
                unique_ids.append(kid_int)

        if not unique_ids:
            return ""

        # 2. 查库 (复用与 KB list 相同的 storage_mode 过滤, 避免 drive 文件泄露)
        from app.models.knowledge import Knowledge
        from sqlalchemy import select
        result = await db.execute(
            select(Knowledge).where(
                Knowledge.id.in_(unique_ids),
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "kb",
            )
        )
        rows = list(result.scalars().all())
        if not rows:
            return ""

        # 3. 按输入顺序排序
        id_order = {kid: i for i, kid in enumerate(unique_ids)}
        rows.sort(key=lambda r: id_order.get(r.id, 999))

        # 4. 拼 system prompt block
        lines = [
            "## 【用户手动附加的知识库文档】(本轮对话的**强制参考来源**, 优先级高于历史对话和工具检索)",
            "",
            f"用户从项目知识库手动选择了 **{len(rows)} 份文档**作为本次对话的强制参考资料。",
            "",
            "**重要规则**:",
            "1. **必须**基于以下文档内容回答用户当前问题, 不要被历史对话中的其他主题干扰",
            "2. 如果当前问题与历史对话主题不同 (例如历史在谈声纹, 附加文档是微纳米气泡), 以**附加文档**为准",
            "3. **必须**在回答中引用文档 ID (如 [123]) 让用户知道信息来源",
            "4. 不要去调用 search_knowledge 工具检索其他文档 — 用户已经手动指定了参考来源",
            "",
        ]
        for r in rows:
            content_preview = (r.content or "")[:2000]
            if len(r.content or "") > 2000:
                content_preview += "\n... (内容过长, 已截断)"
            lines.append(f"### [{r.id}] {r.title}")
            if r.category:
                lines.append(f"分类: {r.category}")
            tags = r.tags or []
            if tags:
                lines.append(f"标签: {', '.join(tags)}")
            if r.summary:
                lines.append(f"摘要: {r.summary[:300]}")
            lines.append("")
            lines.append("```")
            lines.append(content_preview)
            lines.append("```")
            lines.append("")

        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"build_attached_knowledge_block failed (best-effort): {e}")
        return ""


def _window_messages(messages: List[Dict]) -> List[Dict]:
    """窗口化 + 按消息 id 语义去重（进 LLM 前调用）

    - 只保留最近 _SESSION_CONTEXT_MAX_MSGS (24) 条（12 轮）
    - 去重: 同一 role + 同一 content 的相邻重复只保留最后一条
      (防御 PG 重复行 / Redis 与 PG 双写叠加的重复)
    """
    if not messages:
        return messages
    deduped: List[Dict] = []
    for m in messages:
        if deduped and deduped[-1].get("role") == m.get("role") and deduped[-1].get("content") == m.get("content"):
            deduped[-1] = m  # 相邻重复 → 保留最后一条
        else:
            deduped.append(m)
    return deduped[-_SESSION_CONTEXT_MAX_MSGS:]


async def _inject_memories(db, user_id: int, query: str) -> str:
    """长期记忆注入段（共享函数, 流式/非流式路径统一调用 — A4）

    返回追加文本（如 "\n关于用户的长期记忆:\n- [...]"）；无记忆或失败返回 ""。
    """
    try:
        from app.services.memory_service import MemoryService
        mem_svc = MemoryService(db)
        memories = await mem_svc.search_memories(user_id, query, top_k=5)
        if memories:
            memory_text = "\n".join(
                f"- [{m['memory_type']}] {m['content']}" for m in memories
            )
            return f"\n关于用户的长期记忆:\n{memory_text}"
    except Exception as e:
        logger.warning(f"构建记忆提示词失败: {e}")
    return ""


# ============================================================================
# 2026-07-15 #P2: 课题组概览上下文注入 (Redis 1h 缓存)
# ============================================================================
# 背景: 之前 system prompt 不注入课题组成员/项目, "详细介绍本课题组" 类查询
#       只能拿到 KB 通用条目 (#12 标题党) → 返回通用 web-search 模板
# 修法: _build_team_overview_text() 拼成员花名册 + 项目列表, Redis 缓存 1h
#       _build_system_prompt() 每条 query 都注入 (~2-3k token)
# 缓存失效: 管理员成员/项目变动后 redis-cli DEL team_overview:v1 即可
# ============================================================================

_TEAM_OVERVIEW_CACHE_KEY = "team_overview:v1"
_TEAM_OVERVIEW_CACHE_TTL_SEC = 3600  # 1h


async def _build_team_overview_text(db, max_members: int = 30, max_projects: int = 10) -> str:
    """构造【课题组概览】上下文文本, 注入 system prompt

    返回文本格式 (~2-3k token):
    ```
    ## 【课题组概览】（由 system 注入，每小时刷新）

    课题组当前 N 位成员，主要研究方向：xxx、yyy

    ### 成员列表（按角色 + 年级排序）
    - **王天志**（副教授/组长）：微纳米气泡技术与应用
    - **赵航佳**（博一）：黑臭水体治理, 臭氧微纳米气泡
    - ...

    ### 活跃项目
    - **微纳米气泡水处理**（水处理方向，3 人）
    - ...
    ```

    Args:
        db: AsyncSession (异步 SQLAlchemy session)
        max_members: 最多列多少成员 (默认 30)
        max_projects: 最多列多少活跃项目 (默认 10)

    Returns:
        str: 注入文本；db=None 或异常时返回空字符串 (best-effort)
    """
    if db is None:
        logger.warning("_build_team_overview_text called with db=None, returning empty (no injection)")
        return ""

    # 1. Redis 缓存查
    try:
        from app.core.redis import get_redis
        r = await get_redis()
        cached = await r.get(_TEAM_OVERVIEW_CACHE_KEY)
        if cached:
            logger.debug(f"team_overview cache hit ({len(cached)} chars)")
            return cached
        logger.debug("team_overview cache miss, querying DB")
    except Exception as e:
        logger.warning(f"team_overview redis read failed (proceed to DB): {e}")

    # 2. 查 DB
    try:
        from app.models.member import Member
        from app.models.project import Project

        # 成员: 排除 is_active=False，按 role 优先级 + name 排序
        # role 顺序: admin > leader > member (admin/leader 放前面)
        members_rows = await db.execute(
            select(Member)
            .where(Member.is_active == True)  # noqa: E712
            .order_by(Member.role.desc(), Member.name.asc())
            .limit(max_members + 10)  # 多取 10 个, 过滤测试账号后再限 max_members
        )
        all_members = members_rows.scalars().all()

        # 2026-07-15 #P2 反幻觉修复: 过滤测试账号 (drive_test, 测试小助手)
        # 避免 Alice/Bob/Charlie/测试小助手 出现在 team_overview 顶部误导用户
        # 识别规则: username 含 "test" 或 name 含 "Test" / "测试"
        def is_test_account(m) -> bool:
            username = (m.username or "").lower()
            name = m.name or ""
            if "test" in username or "test" in name.lower():
                return True
            if name in ("测试小助手", "xiaoqi_testbot", "xiaoqi_testbot_2"):
                return True
            if username in ("xiaoqi_testbot", "xiaoqi_testbot_2"):
                return True
            return False

        members = [m for m in all_members if not is_test_account(m)][:max_members]
        logger.debug(
            f"team_overview filtered: {len(all_members)} total -> {len(members)} real "
            f"({len(all_members) - len(members)} test accounts removed)"
        )

        # 活跃项目
        projects_rows = await db.execute(
            select(Project)
            .where(Project.status == "active")
            .order_by(Project.name.asc())
            .limit(max_projects)
        )
        projects = projects_rows.scalars().all()
    except Exception as e:
        logger.warning(f"team_overview DB query failed: {e}", exc_info=True)
        return ""

    if not members and not projects:
        return ""

    # 3. 拼文本
    lines = ["## 【课题组概览】（由 system 自动注入，每小时刷新一次）", ""]

    # 成员分布 + 主要研究方向
    if members:
        role_count = {"admin": 0, "leader": 0, "member": 0}
        for m in members:
            role = m.role or "member"
            role_count[role] = role_count.get(role, 0) + 1
        all_research_areas = [m.research_area for m in members if m.research_area]
        unique_areas = list(dict.fromkeys(all_research_areas))[:8]  # 去重保序取前 8
        lines.append(
            f"课题组当前 **{len(members)} 位活跃成员**"
            f"（管理员 {role_count.get('admin', 0)} / "
            f"组长 {role_count.get('leader', 0)} / "
            f"普通成员 {role_count.get('member', 0)}）。"
        )
        if unique_areas:
            lines.append(f"**主要研究方向**：{'、'.join(unique_areas)}。")
        lines.append("")

    # 成员列表
    if members:
        lines.append("### 成员列表（按角色 + 姓名排序）")
        lines.append("")
        for m in members:
            role_label = {"admin": "[管理员]", "leader": "[组长]", "member": ""}.get(m.role, "")
            grade = m.grade or ""
            grade_str = f"（{grade}）" if grade else ""
            ra = m.research_area or "未明确研究方向"
            # bio 不注入（太长），只留姓名 + 年级 + 研究方向
            lines.append(f"- {role_label}**{m.name}**{grade_str}：{ra}".replace("****", "**").replace("****", "**"))
        lines.append("")

    # 项目列表
    if projects:
        lines.append(f"### 活跃项目（共 {len(projects)} 个）")
        lines.append("")
        for p in projects:
            member_count = len(p.members or [])
            ra = p.research_area or "未明确方向"
            member_str = f"，{member_count} 人参与" if member_count else ""
            lines.append(f"- **{p.name}**（{ra}{member_str}）")
        lines.append("")

    # 2026-07-15 #P2 反幻觉: GROUND TRUTH 名单（强制 LLM 不准编造）
    # 把所有真实姓名 / 项目名 / 方向打包成显式白名单, LLM 看到后必须严格遵守
    lines.append("### ⚠️ GROUND TRUTH 白名单（严禁出现以下名单之外的成员 / 项目）")
    lines.append("")
    if members:
        member_names = "、".join(m.name for m in members)
        lines.append(f"**真实成员姓名（共 {len(members)} 人）**：{member_names}")
    if projects:
        project_names = "、".join(p.name for p in projects)
        lines.append(f"**真实活跃项目名（共 {len(projects)} 个）**：{project_names}")
    lines.append("")
    lines.append(
        "**反幻觉纪律**：回答「本课题组/我们组/组里/实验室」类问题时, "
        "出现的**每一个成员姓名 / 项目名 / 会议主题 / 任务标题**都必须在以上白名单或工具返回中真实存在. "
        "**严禁**编造任何不在白名单内的姓名 (如李晓辉、张伟杰等常见名), "
        "**严禁**为凑完整性而虚构成员/项目数量. "
        "如概览块为空或工具返回空, **必须直接说**'暂时无法获取课题组信息', 禁止凭训练知识瞎写."
    )

    text = "\n".join(lines)

    # 4. 写 Redis 缓存 (best-effort, 失败不阻塞)
    try:
        from app.core.redis import get_redis
        r = await get_redis()
        await r.set(_TEAM_OVERVIEW_CACHE_KEY, text, ex=_TEAM_OVERVIEW_CACHE_TTL_SEC)
        logger.info(
            f"team_overview cached: {len(members)} members + {len(projects)} projects, "
            f"{len(text)} chars, ttl={_TEAM_OVERVIEW_CACHE_TTL_SEC}s"
        )
    except Exception as e:
        logger.warning(f"team_overview redis write failed: {e}")

    return text


class MicroBubbleAgent:
    """微纳米气泡课题组 Agent 主类（v2 架构）"""

    def __init__(self):
        self.engine = ChatEngine()
        logger.info("MicroBubbleAgent v2 初始化完成")

    # =========================================================================
    # 公开 API
    # =========================================================================

    async def chat(
        self,
        message: str,
        session_id: str = "default",
        history: Optional[List[Dict]] = None,
        db=None,
        image_data: Optional[bytes] = None,
        image_media_type: str = "image/png",
        user_id: Optional[int] = None,
        channel_user_id: Optional[str] = None,
        *,
        model: Optional[str] = None,
        # 2026-07-13 #P1 三档推理模式透传
        thinking_mode: Optional[str] = None,
        # #P5: 用户手动附加的知识库文档 ID 列表
        attached_knowledge_ids: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """对话接口（非流式）

        返回 dict 兼容旧接口：
        {
            "content": str,  # brief 文本
            "content_blocks": list,
            "tool_calls": list,
            "tool_results": list,
            "rich_blocks": list,  # 新增
            "tool_trace": list,   # 新增
            "usage": dict,        # 新增
            "duration_ms": int,   # 新增
        }
        """
        # 1. 加载 session
        messages = await session_manager.get_messages(session_id)
        if history:
            messages = history

        # 2. 构造 user content（图片 or 文本）
        content = self._build_user_content(
            message, image_data, image_media_type
        )
        messages.append({"role": "user", "content": content})

        # 3. 构造 system prompt
        system = await self._build_system_prompt(user_id, message, db) if user_id else get_system_prompt()

        # #P5: 注入用户手动附加的文档 (与 chat_stream 对齐)
        if attached_knowledge_ids and db is not None:
            attached_block = await _build_attached_knowledge_block(db, attached_knowledge_ids)
            if attached_block:
                system = system + "\n" + attached_block

        # 4. 调用 ChatEngine
        result = await self.engine.chat_with_brief_and_detail(
            messages=messages,
            system=system,
            user_id=user_id,
            db=db,
            channel_user_id=channel_user_id,
            session_id=session_id,
            synthesis_model_override=model,
            # 2026-07-13 #P1 透传
            thinking_mode=thinking_mode,
            # #P5: 透传附加文档 ID → 屏蔽 RAG 工具 (与 chat_stream 一致)
            attached_knowledge_ids=attached_knowledge_ids,
        )

        # 5. 持久化 session（截断到 window size）
        if history is None:
            messages.append({"role": "assistant", "content": result["content"]})
            if len(messages) > settings.SESSION_WINDOW_SIZE:
                messages = messages[-settings.SESSION_WINDOW_SIZE:]
            await session_manager.save_messages(session_id, messages)
            await session_manager.update_meta(session_id, user_id=user_id)

        # 6. 异步后台：记忆 + 知识提取
        if user_id and db:
            asyncio.create_task(self._extract_memories_bg(user_id, messages, session_id))
            asyncio.create_task(self._extract_knowledge_bg(user_id, messages, session_id))

        return result

    async def chat_stream(
        self,
        message: str,
        session_id: str = "default",
        db=None,
        image_data: Optional[bytes] = None,
        image_media_type: str = "image/png",
        user_id: Optional[int] = None,
        channel_user_id: Optional[str] = None,
        *,
        model: Optional[str] = None,
        # 2026-07-13 #P1 三档推理模式透传
        thinking_mode: Optional[str] = None,
        # 2026-08-15 #P4: 用户手动附加的知识库文档 ID 列表, 注入 system prompt
        attached_knowledge_ids: Optional[List[int]] = None,
    ) -> AsyncIterator[StreamEvent]:
        """流式对话接口

        yield StreamEvent 序列

        #043 持久化（2026-06-29）：
        1. 入场：ensure_session_for_stream() 创建/复用 ChatSession 行
           + append_message(user_msg) 落 user 消息（含 client_msg_id 幂等键）
           + append_message(assistant_placeholder, is_partial=True) 占位
        2. 累积：text_delta 累加到 assistant_text；tool_use/tool_result 累加到 tool_trace；
           rich_block 累加到 rich_blocks
        3. 完成（done 事件）：update_message_content(content=full_text, is_partial=False)
           同时 yield message_persisted 事件通知前端
        4. 异常（User aborted / CancelledError / Exception）：
           mark_partial(message_id=...) 标记占位消息为 partial
           + yield sync_required(reason="aborted"|"error") 通知前端重新拉历史

        关键边界：
        - db=None 时（webchat 等无登录场景）跳过持久化（保留老行为）
        - user_id=None 时跳过持久化（兼容旧调用）
        - append_message 失败不阻塞流式（best-effort 持久化）
        """
        # 0. 持久化前置条件：无 db 或无 user_id 时跳过（兼容老调用）
        persist_enabled = db is not None and user_id is not None

        # 1. [CHAT-P0-A] 加载 session 上下文（PG 回填 Redis + 窗口化 + 去重）
        #    Redis 空 → PG 全量回填最近 24 条；Redis 非空 → last_pg_id 增量回填
        messages = await _ensure_session_context(db, user_id, session_id)
        messages = _window_messages(messages)

        # 2. 构造 user content
        content = self._build_user_content(message, image_data, image_media_type)
        messages.append({"role": "user", "content": content})

        # 3. 构造 system prompt（流式路径同样注入长期记忆 — A4）
        system = await self._build_system_prompt(user_id, message, db) if user_id else get_system_prompt()

        # B1: prompt 构造后分类一次；闲聊/续讲显式覆盖 fast，并传 engine 复用。
        try:
            intent = await classify_intent(
                question=message,
                ctx=ToolContext(db=db, user_id=user_id),
            )
        except Exception as e:
            # classify_intent 本身已有降级；顶层再兜一层，保证分类基础设施故障不阻断 chat。
            from app.agent.intent_classifier import IntentCategory, IntentResult
            logger.warning(f"chat_stream intent preclassification failed: {e}")
            intent = IntentResult(
                category=IntentCategory.CASUAL_CHAT,
                confidence=0.0,
                reasoning=f"preclassification failed: {e}",
            )
        if intent.category.value in ("casual_chat", "follow_up"):
            config = resolve_thinking_config("fast")
            thinking_mode = "fast"
            casual_section = get_intent_aware_guidelines(intent.category.value)
            if casual_section:
                system = system + "\n" + casual_section
            logger.debug(
                "chat_stream fast path: intent=%s rounds=%s critique=%s",
                intent.category.value,
                config.max_tool_rounds,
                config.skip_critique,
            )

        # B2: follow_up 读取上一轮结果集 + 追加一轮检索，注入指代消解 prompt。
        if intent.category.value == "follow_up":
            context_block = await _build_follow_up_context(db, session_id, message)
            if context_block:
                system = system + "\n" + context_block

        # 2026-08-15 #P4: 用户从知识库手动附加的文档 → 注入 system prompt (优先参考来源)
        logger.info(f"[P4-chat_stream] 收到 attached_knowledge_ids: {attached_knowledge_ids}")
        if attached_knowledge_ids and db is not None:
            attached_block = await _build_attached_knowledge_block(db, attached_knowledge_ids)
            logger.info(f"[P4-chat_stream] block 长度: {len(attached_block)} chars")
            if attached_block:
                system = system + "\n" + attached_block

        # 4. #043 持久化入场
        # 关键：所有持久化操作都用 try/except 兜底，绝不阻塞流式
        # 幂等键：同一 stream 重试时（网络断开重连）不会重复落库
        stream_ts = int(time.time() * 1000)  # 毫秒精度
        user_client_msg_id = f"stream_{session_id}_user_{stream_ts}"
        assistant_client_msg_id = f"stream_{session_id}_assistant_{stream_ts}"
        user_msg_id = None
        assistant_msg_id = None
        user_msg_persisted = False
        assistant_msg_persisted = False

        if persist_enabled:
            try:
                from app.services import chat_history_service as chat_svc
                await chat_svc.ensure_session_for_stream(
                    db, user_id, session_id, first_message=message,
                )
                # 持久化 user 消息（幂等键防重）
                user_msg = await chat_svc.append_message(
                    db, user_id, session_id,
                    role="user",
                    content=content if isinstance(content, str) else message,
                    message_metadata={
                        "source": "chat_stream",
                        "ts": stream_ts,
                        "image_attached": image_data is not None,
                    },
                    client_msg_id=user_client_msg_id,
                )
                user_msg_id = user_msg.id
                user_msg_persisted = True
                logger.info(f"[chat_stream persist] user_msg persisted: msg_id={user_msg_id}")
                yield StreamEvent(
                    type="message_persisted",
                    message_id=user_msg_id,
                    persisted_role="user",
                    persisted_client_msg_id=user_client_msg_id,
                    persisted_is_partial=False,
                )
            except Exception as e:
                # 持久化失败不阻塞流式（best-effort）
                logger.error(f"[chat_stream persist] user_msg 持久化失败: {e}", exc_info=True)

        # 5. 流式累积上下文（#043）
        assistant_text = ""  # assistant 完整文本累积
        assistant_rich_blocks: List[Dict[str, Any]] = []  # rich_block 累积
        assistant_tool_trace: List[Dict[str, Any]] = []  # tool_use/tool_result 累积
        assistant_intent: Optional[Dict[str, Any]] = None
        assistant_critique: Optional[Dict[str, Any]] = None
        assistant_usage: Optional[Dict[str, int]] = None
        assistant_duration_ms: Optional[int] = None
        retrieved_chunks: List[Dict[str, Any]] = []
        t0 = time.monotonic()

        # 6. 调用 ChatEngine 流式（for-await 累积所有事件）
        # 关键设计：ChatEngine.chat_stream() 透传 synthesize_stream() 的 events，
        # 我们在 micro_bubble_agent 这一层用 for-await 拦截并累积；意图在此入口
        # 预分类一次后透传给 engine，避免闲聊快路径重复调用分类 LLM。
        stream_iter = self.engine.chat_stream(
            messages=messages,
            system=system,
            user_id=user_id,
            db=db,
            channel_user_id=channel_user_id,
            session_id=session_id,
            synthesis_model_override=model,
            # 2026-07-13 #P1 透传 + CHAT-P1-B 复用预分类
            thinking_mode=thinking_mode,
            preclassified_intent=intent,
            # #P5: 透传 attached_knowledge_ids → 屏蔽 RAG 工具
            attached_knowledge_ids=attached_knowledge_ids,
        )

        try:
            async for event in stream_iter:
                # 累积上下文（不动原始 yield 事件）
                if event.type == "text_delta":
                    assistant_text += event.delta or ""
                elif event.type == "tool_use":
                    assistant_tool_trace.append({
                        "type": "tool_use",
                        "id": event.tool_use_id,
                        "name": event.tool_name,
                        "input": event.tool_input,
                    })
                elif event.type == "tool_result":
                    assistant_tool_trace.append({
                        "type": "tool_result",
                        "tool_use_id": event.tool_use_id,
                        "name": event.tool_name,
                        "result": event.tool_output,
                        "duration_ms": event.tool_duration_ms,
                        "error": event.tool_error,
                    })
                    if event.tool_name == "search_knowledge" and isinstance(event.tool_output, dict):
                        rows = event.tool_output.get("results")
                        if isinstance(rows, list):
                            retrieved_chunks.extend(rows)
                elif event.type == "rich_block" and event.block:
                    assistant_rich_blocks.append(event.block.model_dump())
                elif event.type == "intent_detected" and event.intent:
                    assistant_intent = event.intent
                elif event.type == "critique" and event.critique:
                    assistant_critique = event.critique
                elif event.type == "retry":
                    assistant_text = ""
                elif event.type == "done":
                    if event.text_without_json is not None:
                        assistant_text = event.text_without_json
                    assistant_usage = event.usage
                    assistant_duration_ms = event.duration_ms

                # 原样 yield 给前端
                yield event

                # 在 done 事件后立即落库 assistant（client 看到 done 后即可查 history）
                if event.type == "done":
                    # B2: done 已先下发给客户端；紧接着写本轮 last_turn（与 PG 持久化独立）。
                    await _set_last_turn(
                        session_id=session_id,
                        intent=intent,
                        query=message,
                        answer=assistant_text,
                        results=retrieved_chunks,
                    )
                    if persist_enabled:
                        logger.info(f"[P5-debug] 进入 assistant append, assistant_text len={len(assistant_text) if assistant_text else 0}")
                        try:
                            from app.services import chat_history_service as chat_svc
                            # 把 accumulated rich_blocks + tool_trace + intent + critique + usage
                            # 作为 metadata 一并存到 assistant message
                            meta = {
                                "source": "chat_stream_done",
                                "ts": stream_ts,
                                "intent": assistant_intent,
                                "critique": assistant_critique,
                                "usage": assistant_usage,
                                "duration_ms": assistant_duration_ms,
                            }
                            # 直接 append_message（不用 update_message_content）——流式占位消息
                            # 反而会增加 round-trip，且如果 ensure_session 失败用户消息都没落
                            # assistant 占位反而成孤儿。简化：直接 append final assistant
                            assistant_msg = await chat_svc.append_message(
                                db, user_id, session_id,
                                role="assistant",
                                content=assistant_text,
                                rich_blocks=assistant_rich_blocks,
                                tool_trace={"trace": assistant_tool_trace} if assistant_tool_trace else {},
                                message_metadata=meta,
                                is_partial=False,
                                client_msg_id=assistant_client_msg_id,
                            )
                            assistant_msg_id = assistant_msg.id
                            assistant_msg_persisted = True
                            # [CHAT-P0-A A3] assistant 落库后更新 last_pg_id（增量回填游标）
                            await _set_last_pg_id(session_id, assistant_msg_id)
                            # [CHAT-P0-A A4] 流式完成后 fire-and-forget 记忆提取（闭环: 流式
                            # 回答也进长期记忆, 不再"非流式才提取")
                            if user_id and db:
                                conv_msgs = [
                                    {"role": m.get("role"), "content": m.get("content")}
                                    for m in messages
                                    if isinstance(m, dict)
                                ] + [{"role": "assistant", "content": assistant_text}]
                                asyncio.create_task(
                                    self._extract_memories_bg(user_id, conv_msgs, session_id)
                                )
                            # 2026-08-17 #Step14: summary 写路径 (Plan v1 P2)
                            # 复用 fire-and-forget 模式: 异步 LLM 压缩 chat_messages.summary + key_topics
                            # 不阻塞主流程. 走 settings.SUMMARY_LLM_ENABLED 开关
                            if user_id and db and getattr(settings, "SUMMARY_LLM_ENABLED", False):
                                asyncio.create_task(
                                    self._save_message_summary_bg(assistant_msg_id, assistant_text)
                                )
                            logger.info(
                                f"[chat_stream persist] assistant_msg persisted: "
                                f"msg_id={assistant_msg_id} len={len(assistant_text)}"
                            )
                            # （前端可据 message_id 做"这个回答没用"反馈）
                            # 注意: text_without_json 必须复用首个 done 的干净文本
                            # (event.text_without_json, 已剥 fake XML/元话语) —
                            # 不能用 raw assistant_text (text_delta 累积可能含脏文本)
                            yield StreamEvent(
                                type="done",
                                duration_ms=assistant_duration_ms,
                                session_id=session_id,
                                text_without_json=event.text_without_json,
                                message_id=assistant_msg_id,
                                mode=event.mode,
                                model=event.model,
                                thinking_tokens_used=event.thinking_tokens_used,
                            )
                            # [CHAT-P1-E E2] 追问 chips: 优先 LLM 生成对话式追问（失败降级到本地启发式）
                            try:
                                suggestions = await self._build_smart_followups_with_llm(
                                    assistant_text=assistant_text,
                                    tool_trace=assistant_tool_trace,
                                    thinking_mode=thinking_mode,
                                )
                                if not suggestions:
                                    # LLM 调用失败 / 超时 → 降级到本地启发式
                                    suggestions = self._build_followup_suggestions(
                                        assistant_text=assistant_text,
                                        tool_trace=assistant_tool_trace,
                                        thinking_mode=thinking_mode,
                                    )
                                if suggestions:
                                    yield StreamEvent(
                                        type="suggestions",
                                        suggestions=suggestions,
                                    )
                            except Exception as sug_e:
                                logger.warning(f"[chat_stream] suggestions 生成失败 (非阻塞): {sug_e}")
                            # CHAT-P0-D W98 +0: RAG 评估可选抽样钩子 (2 行, best-effort)
                            # EVAL_SAMPLE_RATE>0 时按概率 fire-and-forget 评估, 绝不阻断流式
                            if get_eval_sample_rate() > 0:
                                asyncio.create_task(
                                    maybe_evaluate_async(
                                        user_id, session_id, assistant_msg_id,
                                    )
                                )
                            # yield 持久化通知事件（前端可以选择性 reload history）
                            yield StreamEvent(
                                type="message_persisted",
                                message_id=assistant_msg_id,
                                persisted_role="assistant",
                                persisted_client_msg_id=assistant_client_msg_id,
                                persisted_is_partial=False,
                            )
                        except Exception as e:
                            logger.error(
                                f"[chat_stream persist] assistant_msg 持久化失败: {e}",
                                exc_info=True,
                            )
                            # 失败时尝试落 partial（让用户重进能看到内容）
                            if assistant_text:
                                try:
                                    from app.services import chat_history_service as chat_svc
                                    partial_msg = await chat_svc.append_message(
                                        db, user_id, session_id,
                                        role="assistant",
                                        content=assistant_text,
                                        rich_blocks=assistant_rich_blocks,
                                        tool_trace={"trace": assistant_tool_trace} if assistant_tool_trace else {},
                                        message_metadata={"source": "partial_after_done_error", "ts": stream_ts},
                                        is_partial=True,
                                        client_msg_id=assistant_client_msg_id + "_partial",
                                    )
                                    yield StreamEvent(
                                        type="message_persisted",
                                        message_id=partial_msg.id,
                                        persisted_role="assistant",
                                        persisted_client_msg_id=assistant_client_msg_id + "_partial",
                                        persisted_is_partial=True,
                                    )
                                except Exception as e2:
                                    logger.error(f"[chat_stream persist] partial 持久化也失败: {e2}")

        except asyncio.CancelledError:
            # 流式中断（用户关浏览器 / 主动 stop）
            logger.warning(
                f"[chat_stream persist] CancelledError: "
                f"user_msg_id={user_msg_id} assistant_text_len={len(assistant_text)}"
            )
            if persist_enabled and assistant_text:
                try:
                    from app.services import chat_history_service as chat_svc
                    # 中断时把已累积的 assistant_text 作为 partial 落库
                    # 用户重进 session 能看到"中断前的回答"，可点"重新生成"
                    partial_msg = await chat_svc.append_message(
                        db, user_id, session_id,
                        role="assistant",
                        content=assistant_text,
                        rich_blocks=assistant_rich_blocks,
                        tool_trace={"trace": assistant_tool_trace} if assistant_tool_trace else {},
                        message_metadata={
                            "source": "stream_cancelled",
                            "ts": stream_ts,
                            "duration_ms": int((time.monotonic() - t0) * 1000),
                        },
                        is_partial=True,
                        client_msg_id=assistant_client_msg_id + "_cancelled",
                    )
                    yield StreamEvent(
                        type="message_persisted",
                        message_id=partial_msg.id,
                        persisted_role="assistant",
                        persisted_client_msg_id=assistant_client_msg_id + "_cancelled",
                        persisted_is_partial=True,
                    )
                    # 通知前端：流式中断，建议重新拉历史
                    yield StreamEvent(
                        type="sync_required",
                        sync_reason="aborted",
                    )
                except Exception as e:
                    logger.error(f"[chat_stream persist] 中断 partial 落库失败: {e}", exc_info=True)
            raise  # 重新抛 CancelledError 让上层处理

        except Exception as e:
            # 流式异常（非中断）——同样的 best-effort 持久化策略
            logger.error(f"[chat_stream persist] 流式异常: {e}", exc_info=True)
            if persist_enabled and assistant_text:
                try:
                    from app.services import chat_history_service as chat_svc
                    partial_msg = await chat_svc.append_message(
                        db, user_id, session_id,
                        role="assistant",
                        content=assistant_text,
                        rich_blocks=assistant_rich_blocks,
                        message_metadata={
                            "source": "stream_error",
                            "error": str(e)[:500],
                            "ts": stream_ts,
                        },
                        is_partial=True,
                        client_msg_id=assistant_client_msg_id + "_error",
                    )
                    yield StreamEvent(
                        type="message_persisted",
                        message_id=partial_msg.id,
                        persisted_role="assistant",
                        persisted_client_msg_id=assistant_client_msg_id + "_error",
                        persisted_is_partial=True,
                    )
                    yield StreamEvent(
                        type="sync_required",
                        sync_reason="error",
                    )
                except Exception as e2:
                    logger.error(f"[chat_stream persist] 异常 partial 落库失败: {e2}")
            # 不 raise，让上层 StreamingResponse 处理（yield error 事件给前端）

    async def clear_session(self, session_id: str):
        """清除会话历史（保留 dirty flag 行为不变）

        新行为：只删 session 内容，不动 meta。WS 断连时用 mark_dirty。
        """
        await session_manager.delete(session_id)

    # =========================================================================
    # [CHAT-P1-E E2] 追问 chips 生成 (best-effort, 绝不阻塞主链路)
    # W-N 2026-08-14: 重写为"对话式"追问 — 不再用固定模板
    # ("展开讲讲 X"、"具体说说 X"、"还有哪些关于 X 的内容"),
    # 而是根据 AI 回复内容、工具调用 trace、thinking_mode 智能生成。
    # =========================================================================
    def _build_followup_suggestions(
        self,
        assistant_text: str,
        tool_trace: List[Dict[str, Any]],
        thinking_mode: str = "balanced",
    ) -> List[str]:
        """从 assistant 回答 + 工具调用派生 1-3 个追问 (best-effort, 无 LLM 调用)

        三种生成路径（按优先级）:
        1. 工具调用 trace 提取精确 topic → 精确模板
        2. AI 回复文本提取关键句（数字/单位/专有名词）→ 追问具体细节
        3. 兜底: 基于 thinking_mode 深度
        """
        suggestions: List[str] = []
        try:
            # 1. 从工具调用 trace 提取 topic + 上下文
            topic_context = self._extract_topic_from_tool_trace(tool_trace or [])

            # 2. 从 AI 回复文本提取关键句
            text_topics = self._extract_topic_from_assistant_text(assistant_text or "")

            # 合并 topic（去重）
            all_topics = []
            seen = set()
            for t in topic_context + text_topics:
                if t and t not in seen and len(t) >= 2:
                    seen.add(t)
                    all_topics.append(t)
                if len(all_topics) >= 3:
                    break

            # 3. 智能生成追问
            suggestions = self._build_smart_followups(all_topics, thinking_mode or "balanced")

            # 兜底: 完全没有 topic 时给通用对话追问
            if not suggestions:
                if (thinking_mode or "").lower() == "deep":
                    suggestions = ["能举个具体研究案例吗？", "还有哪些相关方向？"]
                else:
                    suggestions = ["能再详细说说吗？", "有什么实际应用场景？"]

            # 去重 + 截断到 3 个
            seen2 = set()
            unique = []
            for s in suggestions:
                if s and s not in seen2:
                    seen2.add(s)
                    unique.append(s)
                if len(unique) >= 3:
                    break
            # 2026-09-01 修复: 出口必须校验问句形态 — 此前『{topic}』模板包装
            # 陈述性 topic 时产出非问句垃圾 chips (截图实证)
            unique = [
                s for s in unique
                if ("？" in s or "?" in s or _is_questionish(s))
            ]
            return unique[:3]
        except Exception:
            return []

    def _extract_topic_from_tool_trace(self, tool_trace: List[Dict[str, Any]]) -> List[str]:
        """从工具调用 trace 提取对话式 topic — 区分工具类型用不同模板

        Args:
            tool_trace: 工具调用列表 [{"type": "tool_use", "name": "...", "input": {...}}]

        Returns:
            topic 列表（带短上下文，最多 3 个）
        """
        topics: List[str] = []
        try:
            for t in tool_trace:
                if not isinstance(t, dict) or t.get("type") != "tool_use":
                    continue
                tool_name = t.get("name") or ""
                tool_input = t.get("input") or {}

                # 按工具类型产生不同模板
                if tool_name in ("search_knowledge", "web_search", "hybrid_retrieve"):
                    query = (tool_input.get("query") or tool_input.get("q") or "").strip()
                    if not query:
                        continue
                    # 限制 5-15 字
                    if len(query) > 15:
                        query = query[:15]
                    topics.append(query)
                elif tool_name in ("get_meeting_transcript", "search_meetings"):
                    mt = (tool_input.get("meeting_id") or tool_input.get("title") or "").strip()
                    if mt:
                        topics.append(str(mt)[:15])
                elif tool_name.startswith("task_"):
                    # 任务相关
                    tname = (tool_input.get("task_name") or tool_input.get("title") or "").strip()
                    if tname:
                        topics.append(str(tname)[:15])
                else:
                    # 其他工具: 用工具名+第一个 string 参数
                    params = tool_input.get("query") or tool_input.get("q") or tool_input.get("name") or ""
                    if isinstance(params, str) and params.strip():
                        topics.append(params.strip()[:15])

                if len(topics) >= 3:
                    break
        except Exception:
            pass
        return topics

    def _extract_topic_from_assistant_text(self, assistant_text: str) -> List[str]:
        """从 AI 回复文本提取关键句 — 优先选含数字/单位/专有名词的句子

        Args:
            assistant_text: AI 完整回复

        Returns:
            关键句子列表（最多 3 个）
        """
        if not assistant_text:
            return []

        import re as _re

        # 2026-09-01 修复: 排除寒暄/礼仪/元话语/时间戳句 — 此前"今天是2026年9月1日
        # 23:08,希望您有个愉快的夜晚"这类收尾句因含数字被当 topic, 模板包装后产出
        # "和『今天是...』相关的还有哪些?" 垃圾追问 chips
        _SMALLTALK = _re.compile(
            r"(您好|你好|谢谢|感谢|高兴|欢迎|请随时|请告诉我|希望您|希望这|"
            r"今天是|晚安|再见|乐意|感兴趣|祝您|请注意|请描述|我是|有什么可以帮)"
        )

        # 按中英文标点切分完整句子
        sentences = _re.split(r'[。！？\n]+', assistant_text)
        scored = []
        for s in sentences:
            s = s.strip()
            if not s or len(s) < 5 or len(s) > 80:
                continue
            # 寒暄/礼仪/元话语句 → 直接跳过 (含时间戳收尾句)
            if _SMALLTALK.search(s):
                continue

            score = 0
            # 含数字/单位 → 高分（"X mg/L"、"Y 秒"、"Z 步"）
            if _re.search(r'\d+(\.\d+)?\s*(mg|μg|kg|g|cm|mm|°C|秒|分钟|小时|%)', s):
                score += 5
            elif _re.search(r'\d', s):
                score += 2
            # 含专有名词 → 中分
            if _re.search(r'(课题组|实验室|项目|论文|气泡|臭氧|反应器|传感器|浓度|粒径)', s):
                score += 3
            # 包含列表标记
            if _re.search(r'[\d一二三四五六七八九十]+[、，,]\s*[\d一二三四五六七八九十]', s):
                score += 3
            # 包含技术动作
            if _re.search(r'(校准|测试|测量|分析|记录|添加|调整)', s):
                score += 2
            # 包含 "例如" 类短语（暗示举例）
            if _re.search(r'(例如|比如|典型|通常)', s):
                score += 1

            if score > 0:
                scored.append((score, s))

        # 按分数排序, 取前 3 (每条限制 30 字, 保留完整名词)
        scored.sort(key=lambda x: -x[0])
        result = []
        for _, s in scored[:3]:
            if len(s) > 30:
                s = s[:30].rstrip('，,。 ')
            result.append(s)
        return result

    def _build_smart_followups(self, topics: List[str], thinking_mode: str) -> List[str]:
        """根据 topic + thinking_mode 生成"对话式"追问

        不再用固定模板, 而是基于:

        - topic 是否有数字 → 追问"具体数值范围/标准"
        - topic 是否有动作（校准/测试）→ 追问"具体操作步骤"
        - topic 是否是专有名词 → 追问"定义/原理"
        - thinking_mode 深度 → 追问角度

        Args:
            topics: 1-3 个 topic
            thinking_mode: fast / balanced / deep

        Returns:
            1-3 个追问
        """
        import re as _re
        suggestions: List[str] = []

        thinking_mode = (thinking_mode or "balanced").lower()

        for topic in topics[:3]:
            if not topic:
                continue

            # 按 topic 内容判断追问方向 — 优先级: 会议 > 动作 > 名词 > 数字
            if _re.search(r'(会议|纪要|讨论|周会|例会)', topic):
                # 会议纪要 → 追问关键点
                if thinking_mode == "deep":
                    suggestions.append(f"能详细列出『{topic}』的关键发现吗？")
                else:
                    suggestions.append(f"『{topic}』主要讨论了什么？")
            elif _re.search(r'(校准|测试|测量|分析|采集|处理|添加)', topic):
                # 动作 → 追问步骤
                suggestions.append(f"具体怎么操作？")
            elif _re.search(r'(课题组|实验室|项目|论文|气泡|装置|反应器|系统|设备)', topic):
                # 名词 → 追问定义/原理（优先于数字分支）
                if thinking_mode == "deep":
                    suggestions.append(f"能详细解释一下『{topic}』的原理吗？")
                else:
                    suggestions.append(f"这个『{topic}』主要做什么？")
            elif _re.search(r'\d+\s*(mg|μg|kg|g|cm|mm|°C|秒|分钟|小时|%)', topic):
                # 数字 + 单位 → 追问精度/范围
                if thinking_mode == "deep":
                    suggestions.append(f"这个数值的合理范围是多少？")
                else:
                    suggestions.append(f"参考资料里这个数值通常是多少？")
            else:
                # 通用：基于 thinking_mode
                if thinking_mode == "deep":
                    suggestions.append(f"『{topic}』的深层原理是什么？")
                elif thinking_mode == "fast":
                    suggestions.append(f"和『{topic}』相关的还有哪些？")
                else:
                    suggestions.append(f"能介绍下『{topic}』吗？")

        # 如果 topics 太少但还有空间, 加一个 thinking_mode 风格的通用追问
        if not suggestions:
            if thinking_mode == "deep":
                suggestions.append("能深入分析一下吗？")
            else:
                suggestions.append("能举个例子吗？")
        elif len(suggestions) < 2:
            if thinking_mode == "deep":
                suggestions.append("还有哪些延伸方向？")
            else:
                suggestions.append("它在实际中怎么用？")

        return suggestions[:3]

    async def _build_smart_followups_with_llm(
        self,
        assistant_text: str,
        tool_trace: List[Dict[str, Any]],
        thinking_mode: str = "balanced",
    ) -> List[str]:
        """调用 LLM 生成 3 个对话式追问（基于 AI 回复内容具体场景）

        W-N 2026-08-14: 硬调用 LLM 替换固定模板池 — 真正"对话式"

        失败降级：调用失败 / 网络异常 → 使用 _build_smart_followups 启发式结果
        超时：5 秒（避免阻塞主链路，但用户能接受）

        默认走本地 ollama（LLM_BACKEND=ollama 时），没有 ollama 时 fallback 到 Claude API。

        Args:
            assistant_text: AI 完整回复
            tool_trace: 工具调用 trace
            thinking_mode: fast / balanced / deep

        Returns:
            1-3 个对话式追问 string 列表
        """
        try:
            from app.core.llm import get_anthropic_client, get_default_model, extract_text_from_response, parse_llm_json
            from app.config import settings as _settings
            import asyncio
            import aiohttp
            import os

            if not assistant_text or not assistant_text.strip():
                return []

            # 提取关键 context 给 LLM
            snippet = assistant_text.strip()
            if len(snippet) > 800:
                snippet = snippet[:800] + "..."

            tool_summary = []
            for t in (tool_trace or [])[:3]:
                if isinstance(t, dict) and t.get("type") == "tool_use":
                    name = t.get("name") or ""
                    ti = t.get("input") or {}
                    q = ti.get("query") or ti.get("q") or ti.get("title") or ti.get("meeting_id") or ""
                    if isinstance(q, str):
                        tool_summary.append(f"{name}({q})")
            tool_summary_str = ", ".join(tool_summary) if tool_summary else "无"

            prompt = f"""你是课题组智能助手"小气"，刚回答了用户的问题，请基于回答内容生成 3 个用户最可能想继续追问的方向。

要求：
- 每条 8-20 字、像真人对话（不要"展开讲讲"、"具体说说"、"还有哪些关于"这种机械模板）
- 必须是针对这条具体回答的内容（不要宽泛的"举例"、"延伸"）
- 只返回 JSON: {{"questions": ["...", "...", "..."]}}

用户问题/回答上下文：
{snippet}

工具调用：{tool_summary_str}

直接输出 JSON，不要其他文字。"""

            backend = getattr(_settings, "LLM_BACKEND", "anthropic") or "anthropic"
            # 2026-09-01 修复: 硬编码 "qwen3:8b" 已从 ollama 移除 → 404 → 空响应 →
            # JSON 解析失败 → 永远落到启发式 (产出回答片段垃圾 chips)。
            # 改用 AGENT_INTENT_MODEL (与意图分类同源, 轻任务, 已验证存在)。
            model_name = (
                getattr(_settings, "AGENT_INTENT_MODEL", "") or "qwen3.5:9b-q4_K_M"
            ) if backend == "ollama" else get_default_model()

            # 优先走 ollama 本地（避免 Claude API 模型名限制）
            if backend == "ollama":
                # OLLAMA_BASE_URL 可能是 "http://localhost:11434/v1" / "http://ollama:11434/v1"
                # 提取 host:port, 拼接 "/api/chat"
                from urllib.parse import urlparse
                parsed_url = urlparse(_settings.OLLAMA_BASE_URL)
                host = parsed_url.hostname or "localhost"
                port = parsed_url.port or 11434
                # 优先用 OLLAMA_HOST 环境变量（"host.docker.internal" 或 "ollama"）
                # 容器内 localhost 解析不到 ollama 服务
                if host == "localhost" or host == "127.0.0.1":
                    host = os.environ.get("OLLAMA_HOST") or "ollama"
                ollama_url = f"http://{host}:{port}/api/chat"
                async with aiohttp.ClientSession() as session:
                    # ollama 首次调用需 load 模型到显存（30-60s）
                    async with asyncio.timeout(60.0):
                        async with session.post(ollama_url, json={
                            "model": model_name,
                            "messages": [{"role": "user", "content": prompt}],
                            "stream": False,
                            # qwen3 系思考型模型: 显式关闭思考, 保证 content 为纯答案
                            "think": False,
                        }) as resp:
                            data = await resp.json()
                            text = (data.get("message") or {}).get("content", "").strip()
                            # 兜底剥离思考标签 (旧版 ollama 把思考混入 content)
                            import re as _re_think
                            text = _re_think.sub(r"<think>[\s\S]*?</think>", "", text).strip()

            else:
                # Claude API 路径
                client = get_anthropic_client()
                response = await asyncio.wait_for(
                    client.messages.create(
                        model=model_name,
                        max_tokens=300,
                        messages=[{"role": "user", "content": prompt}],
                    ),
                    timeout=5.0,
                )
                text = extract_text_from_response(response).strip()

            parsed = parse_llm_json(text)
            questions = parsed.get("questions") or []
            valid = [q for q in questions if isinstance(q, str) and q.strip() and 5 <= len(q) <= 50]
            return valid[:3]
        except Exception as e:
            logger.warning(f"[build_followups] LLM 生成失败，降级到启发式: {e}")
            return []

    # =========================================================================
    # 内部方法
    # =========================================================================    # =========================================================================
    # 内部方法
    # =========================================================================

    def _build_user_content(
        self,
        message: str,
        image_data: Optional[bytes],
        image_media_type: str,
    ) -> Any:
        """构造 user 消息 content（图 or 文本）"""
        if image_data:
            image_b64 = base64.standard_b64encode(image_data).decode("utf-8")
            return [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": image_media_type,
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": message or "请描述这张图片"},
            ]
        # 纯文本：注入当前时间
        now = datetime.now(BEIJING_TZ)
        time_tag = f"[当前时间: {now.strftime('%Y-%m-%d %H:%M')}] "
        return time_tag + message

    async def _build_system_prompt(
        self,
        user_id: Optional[int],
        query: str,
        db=None,
    ) -> str:
        """构造系统提示词（用户身份 + 记忆 + 会议转录检测）"""
        # 1. 基础 prompt（DB 有自定义模板时优先用）
        base = None
        if db:
            try:
                from app.services.prompt_service import PromptTemplateService
                svc = PromptTemplateService(db)
                base = await svc.get_active_template("default")
            except Exception:
                pass
        if not base:
            base = get_system_prompt()

        if not user_id or not db:
            return base

        parts = [base]

        # 2. 用户身份
        try:
            from app.models.member import Member
            member = await db.get(Member, user_id)
            if member:
                role_map = {"admin": "管理员", "leader": "组长", "member": "普通成员"}
                role_label = role_map.get(member.role, member.role)
                parts.append(f"\n当前用户信息:\n- 姓名: {member.name}\n- 角色: {role_label}")
                if member.role in ("admin", "leader"):
                    parts.append("- 该用户拥有管理员权限")
                if member.custom_instructions:
                    parts.append(f"\n用户自定义指令:\n{member.custom_instructions}")
        except Exception as e:
            logger.warning(f"注入用户身份失败: {e}")

        # 2.5 课题组概览（2026-07-15 #P2 修复"回答不个性化"）
        # Redis 1h 缓存: 命中 <10ms 直接返, 未命中查 Member + Project 表拼 ~2-3k token
        try:
            team_overview = await _build_team_overview_text(db)
            if team_overview:
                parts.append(team_overview)
                logger.debug(f"_build_system_prompt: team_overview injected ({len(team_overview)} chars)")
            else:
                # 2026-07-15 #P2: 异常情况诊断——如果 db 非 None 但返空字符串, 必有 bug
                logger.warning(
                    f"_build_system_prompt: team_overview EMPTY (db={db is not None}), "
                    f"agent 回答可能编造成员姓名!"
                )
        except Exception as e:
            logger.error(f"_build_system_prompt: team_overview injection failed: {e}", exc_info=True)

        # 3. 长期记忆
        memory_text = await _inject_memories(db, user_id, query)
        if memory_text:
            parts.append(memory_text)

        # 4. 会议转录检测
        if _is_meeting_transcript_query(query):
            parts.append(get_meeting_analyzer_prompt())

        return "\n".join(parts)

    # =========================================================================
    # 后台任务
    # =========================================================================

    async def _extract_memories_bg(self, user_id: int, messages: List[Dict], session_id: str):
        """后台记忆提取"""
        from app.core.database import async_session
        try:
            async with async_session() as db:
                from app.services.memory_service import MemoryService
                mem_svc = MemoryService(db)
                await mem_svc.extract_memories_from_conversation(
                    user_id=user_id, messages=messages, session_id=session_id
                )
        except Exception as e:
            logger.error(f"后台记忆提取失败: {e}")

    async def _save_message_summary_bg(self, message_id: int, content: str) -> None:
        """2026-08-17 #Step14: chat_messages.summary 写路径 (Plan v1 P2)

        Fire-and-forget: 异步 LLM 压缩消息 → 写 chat_messages.summary + key_topics.
        不阻塞主流程, 失败仅 log (best-effort, 类 20.121 守恒).
        触发条件: settings.SUMMARY_LLM_ENABLED=True (默认 False, P2 启用时主拍决策).

        流程:
        1. LLM 调用生成 summary (1 句话 ≤ 200 字) + key_topics (3-5 个关键词)
        2. UPDATE chat_messages SET summary=$1, key_topics=$2 WHERE id=$3
        3. 失败: log + return (P2 启用时增强重试)
        """
        from app.core.database import async_session
        try:
            # 截断避免 LLM 超 token
            truncated = content[:3000] if len(content) > 3000 else content
            # 简化版 prompt (P2 启用时换更精细的 prompt)
            summary_prompt = f"用 1 句话 (≤ 100 字) 总结以下对话, 并列出 3-5 个关键词 (逗号分隔):\n\n{truncated}\n\n格式:\nSUMMARY: <一句话>\nTOPICS: <关键词1>, <关键词2>, <关键词3>"
            # LLM 调用 (复用现有 lru cache + 完整版块)
            from app.core.llm import get_anthropic_client, get_default_model
            client = get_anthropic_client()
            model = get_default_model()
            resp = await client.messages.create(
                model=model,
                max_tokens=300,
                temperature=0.0,
                messages=[{"role": "user", "content": summary_prompt}],
            )
            # 解析 SUMMARY + TOPICS
            text = ""
            for block in resp.content:
                if hasattr(block, "text"):
                    text = block.text
                    break
            summary = ""
            topics_str = ""
            for line in text.split("\n"):
                if line.startswith("SUMMARY:"):
                    summary = line[len("SUMMARY:"):].strip()[:500]
                elif line.startswith("TOPICS:"):
                    topics_str = line[len("TOPICS:"):].strip()
            topics = [t.strip() for t in topics_str.split(",") if t.strip()][:5]
            # 异步落库
            async with async_session() as db:
                from sqlalchemy import update, text as sa_text
                from app.models.chat_history import ChatMessage
                stmt = update(ChatMessage).where(ChatMessage.id == message_id).values(
                    summary=summary,
                    key_topics=topics,
                )
                await db.execute(stmt)
                await db.commit()
                logger.debug(f"[Step14] summary saved for msg_id={message_id}: {summary[:50]}...")
        except Exception as e:
            logger.error(f"[Step14] summary save failed for msg_id={message_id}: {e}", exc_info=True)
            # 0 阻塞: 失败仅 log, 不影响主流程

    async def _extract_knowledge_bg(self, user_id: int, messages: List[Dict], session_id: str):
        """后台知识提取（从对话中）

        2026-06-14 方案 C Stage 5：原本 delegate 给 legacy core.py.MicroBubbleAgent
        现把 _extract_and_save_knowledge 逻辑直接搬到本方法内（独立可移植）
        """
        from app.core.database import async_session
        from app.core.llm import get_anthropic_client, get_default_model
        try:
            # 构建对话文本（仅最近 10 条）
            conversation = ""
            for msg in messages[-10:]:
                role = "用户" if msg.get("role") == "user" else "助手"
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
                    )
                if content:
                    conversation += f"{role}: {content}\n"

            if len(conversation) < 100:
                return  # 太短不提取

            prompt = f"""分析以下对话，判断是否包含值得保存到知识库的专业知识。
只保存：实验方法、研究发现、技术方案、经验总结、专业概念解释、操作步骤。
不保存：闲聊、简单问答、临时性信息、任务安排、会议通知。

对话内容:
{conversation[:3000]}

如果没有值得保存的知识，返回 {{"save": false}}
如果有，返回严格的JSON格式（不要包含其他文字）：
{{"save": true, "title": "知识标题", "content": "整理后的完整知识内容", "category": "基础/方法/文献/FAQ", "tags": ["标签1", "标签2"]}}"""

            client = get_anthropic_client()
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}],
            )

            # 2026-06-14 Stage 5 收尾：兼容 mimo 等思考型模型只返 thinking block
            from app.core.llm import extract_text_from_response
            text = extract_text_from_response(response).strip()

            import json as _json
            try:
                result = _json.loads(text)
            except _json.JSONDecodeError:
                # 尝试剥 markdown 包裹
                if text.startswith("```"):
                    lines = text.split("\n")
                    if lines and lines[-1].strip() == "```":
                        text = "\n".join(lines[1:-1])
                    else:
                        text = "\n".join(lines[1:])
                    result = _json.loads(text)
                else:
                    raise

            if not result.get("save"):
                return

            # 写入 knowledge_items 表
            from app.core.database import KnowledgeItem
            async with async_session() as session:
                item = KnowledgeItem(
                    title=result["title"],
                    content=result["content"],
                    category=result.get("category", "基础"),
                    tags=result.get("tags", []),
                    source="conversation",
                    session_id=session_id,
                    user_id=user_id,
                )
                session.add(item)
                await session.commit()
                logger.info(f"知识提取成功: {result['title'][:50]}")
        except Exception as e:
            logger.error(f"后台知识提取失败: {e}")


# 全局单例
agent = MicroBubbleAgent()

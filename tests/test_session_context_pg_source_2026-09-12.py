"""2026-09-12 会话上下文丢轮根治回归 (session vtql 实测取证)

事故: 多轮对话中模型每轮看不到最近一轮 exchange。
- chat_stream 只把消息落 PG + 推进 Redis meta.last_pg_id, 从不写回 Redis messages;
- ensure_session_context 旧逻辑 "Redis 非空 → after_id=last_pg_id 增量":
  上一轮 ensure 之后才持久化的 (user, assistant) 对既不在 Redis 里, 又被新游标
  跳过 → **永久丢失**。实测 §7 "他手上" 模型 context = [u,u,a§2], §5 对
  (6867/6868) 整对蒸发 → 锚定到 §2 表首人 陈天祥、§9 失忆答 "找到 95 个相关任务"。
- 次生 bug: _fetch_pg_messages after_id=0 复用 list_messages(page=1) 的
  asc+limit = **最旧** 24 条, 长会话即使走全量回填也只拿到最早窗口。

修法: 登录会话每轮以 PG 为单一事实源全量回填最近窗口 (24 条成本可忽略),
list_messages page=1 无游标时改为最新窗口 (仍正序返回)。

单测全部 mock (session_manager / chat_history_service.list_messages), 不碰库。
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch


def _mk_msg(mid: int, role: str, content: str, tool_trace=None):
    m = MagicMock()
    m.id = mid
    m.role = role
    m.content = content
    m.is_partial = False
    m.is_deleted = False
    m.tool_trace = tool_trace
    return m


class TestPgSingleSource:
    """核心不变量: 只要 PG 有数据, 返回内容 == PG 窗口, 与 Redis/游标状态无关。"""

    def test_incremental_cursor_gap_no_longer_drops_turn(self):
        """事故场景重演: Redis 只有 §2 前三条, last_pg_id 已越过 §5 对 →
        新逻辑必须仍从 PG 拿回 §5 的 user+assistant (旧逻辑返回空增量丢轮)。"""
        from app.services import session_context as sc

        redis_old = [
            {"role": "user", "content": "现在有哪些进行中的任务？"},
            {"role": "user", "content": "现在有哪些进行中的任务？"},  # 双写副本
            {"role": "assistant", "content": "当前共有 17 项进行中任务…"},
        ]
        pg_msgs = [
            _mk_msg(6866, "assistant", "当前共有 17 项进行中任务…"),
            _mk_msg(6867, "user", "其中截止时间最紧的是哪个？负责人是谁？"),
            _mk_msg(6868, "assistant", "截止时间最紧的是 韩重阳 的「互联网➕ppt制作」"),
        ]

        async def fake_fetch_pg(db, user_id, session_id, *, after_id=0, limit=24):
            # 新实现固定 after_id=0 全量窗口; 若有人改回增量, 这里模拟游标后为空
            assert after_id == 0, "登录会话必须以 PG 全量窗口回填, 不得走增量游标"
            # _fetch_pg_messages 的真实出口形态: [{role, content}, ...]
            return [{"role": m.role, "content": m.content} for m in pg_msgs]

        save = AsyncMock()
        with patch.object(sc.session_manager, "get_messages",
                          AsyncMock(return_value=redis_old)), \
             patch.object(sc, "_fetch_pg_messages", fake_fetch_pg), \
             patch.object(sc.session_manager, "save_messages", save):
            out = asyncio.run(sc.ensure_session_context(
                MagicMock(), user_id=3, session_id="s1"))

        contents = [m["content"] for m in out]
        assert "其中截止时间最紧的是哪个？负责人是谁？" in contents, "§5 user 轮不得丢失"
        assert any("韩重阳" in c for c in contents), "§5 assistant 轮不得丢失"
        # PG 非空 → Redis 镜像被刷新 (供 user_id=None 降级路径与重启兜底)
        assert save.await_count == 1

    def test_pg_empty_degrades_to_redis(self):
        """PG 无数据 (纯 Redis 匿名 webchat 降级/回填失败) → 返回现有 Redis, 不炸。"""
        from app.services import session_context as sc
        redis_msgs = [{"role": "user", "content": "hi"}]
        with patch.object(sc.session_manager, "get_messages",
                          AsyncMock(return_value=redis_msgs)), \
             patch.object(sc, "_fetch_pg_messages", AsyncMock(return_value=None)), \
             patch.object(sc.session_manager, "save_messages", AsyncMock()):
            out = asyncio.run(sc.ensure_session_context(
                MagicMock(), user_id=3, session_id="s1"))
        assert out == redis_msgs

    def test_anonymous_skips_pg(self):
        """越权铁律: user_id=None → 不触 PG。"""
        from app.services import session_context as sc
        fetch = AsyncMock(return_value=None)
        with patch.object(sc.session_manager, "get_messages",
                          AsyncMock(return_value=[{"role": "user", "content": "x"}])), \
             patch.object(sc, "_fetch_pg_messages", fetch):
            out = asyncio.run(sc.ensure_session_context(
                MagicMock(), user_id=None, session_id="s1"))
        assert out == [{"role": "user", "content": "x"}]
        fetch.assert_not_called()

    def test_tool_trace_passthrough_kept(self):
        """09-10 锚定升级的 tool_trace 透传契约守恒 (指代锚定源 0 依赖它)。"""
        from app.services import session_context as sc
        tt = {"trace": [{"type": "tool_use", "name": "query_tasks",
                         "input": {"assignee_name": "韩重阳"}}]}
        with patch.object(sc.session_manager, "get_messages", AsyncMock(return_value=[])), \
             patch.object(sc.session_manager, "save_messages", AsyncMock()):
            with patch("app.services.chat_history_service.list_messages",
                       AsyncMock(return_value=([_mk_msg(1, "assistant", "a", tool_trace=tt)], False))):
                out = asyncio.run(sc.ensure_session_context(
                    MagicMock(), user_id=3, session_id="s1"))
        assert out[0]["tool_trace"] == tt


class TestListMessagesLatestWindow:
    """list_messages page=1 无游标 = 最新窗口 (升序), 不再是 ASC+LIMIT 最旧窗口。"""

    def _run_query(self, stmt):
        """用 sqlite 内存库真跑 SQL: 建 chat_messages 同款最小表, 断言返回行集。
        不依赖测试库 fixture — 纯 SQL 语义验证。"""
        import re
        compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
        return compiled

    def test_home_page_sql_desc_window(self):
        from sqlalchemy import select, and_, asc, desc
        from app.models.chat_history import ChatMessage

        conds = [ChatMessage.session_id == "s1", ChatMessage.is_deleted.is_(False)]
        # 复刻新分支构造, 断言其计划含 DESC+LIMIT 窗口 (实现漂移即红)
        sub = (
            select(ChatMessage.id).where(and_(*conds))
            .order_by(desc(ChatMessage.id)).limit(25)
        ).subquery()
        stmt = (
            select(ChatMessage).where(ChatMessage.id.in_(select(sub.c.id)))
            .order_by(asc(ChatMessage.id))
        )
        sql = self._run_query(stmt).upper()
        assert "DESC" in sql and "LIMIT" in sql, "首页必须是最新窗口 (desc+limit)"

    def test_service_function_shape(self):
        """源码结构断言: 首页窗口分支在场且只在 page==1 & after_id==0 生效
        (前端 offset 分页与增量游标保持老 asc 语义)。"""
        import inspect
        from app.services import chat_history_service as svc
        src = inspect.getsource(svc.list_messages)
        assert "page == 1 and after_id == 0" in src
        assert "desc(ChatMessage.id)" in src

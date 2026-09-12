"""2026-09-12 指代锚定错误实体修复回归 (生产实测 §7 "他手上" 锚成杜同贺事故)

现场 (session user_1789171148294_u6oq, chat_messages 6853-6861):
- §2 "现在有哪些进行中的任务" → 模型调 query_tasks(status, assignee_name=杜同贺)
  回答 "你当前没有进行中的任务" (回答文本不含任何成员名)
- §5 "其中截止时间最紧的是哪个？负责人是谁？" → 回答主语 韩重阳;
  但同轮模型还自查过一次 get_member_profile(member_name="截止时间") — 垃圾入参
- §7 "他手上还有其他任务吗？" → 锚定注入 "人物：杜同贺" (应为韩重阳) →
  模型忠实执行 → 整轮答错对象
- §9 "帮我给这个任务加一条备注" → 锚沿 §7 继续错, 但反谎报 guard 触发
  (write_done=False), 模型如实说"未执行 + 请澄清" — 未谎报 ✓

根因: _extract_prev_round_entities 源 0 (tool_trace.input) 两条纪律缺失:
① 无"最近有 trace 的一轮"关闸 — 跨轮翻到 §2 的历史入参;
② 无条件相信入参实体 — 模型内部自查 (get_member_profile 试探/默认当前用户)
   没出现在回答里的名字也被当"上轮主题"注入。

修复: ① src0_checked 关闸; ② 入参实体必须出现在该轮回答文本里 (用户看得见)。
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

ROSTER = ["杜同贺", "韩重阳", "陈天祥", "胡小琪", "蒋芦笛", "王天志"]


def _extract(messages):
    from app.agent.agentic_loop import _extract_prev_round_entities
    with patch("app.agent.agentic_loop._member_names_cache", return_value=ROSTER):
        return _extract_prev_round_entities(messages)


class TestSessionReplay20260912:
    """逐字回放生产 session 消息形态 (§2 → §5 → §7 链)。"""

    TURN2_ANSWER = (
        "你当前没有处于“进行中”状态的任务。\n\n"
        "需要我帮你查一下所有状态的任务（包括待办、已完成），或者帮你新建一个任务吗？"
    )
    TURN5_ANSWER = (
        "截止时间最紧的是 “互联网➕ppt制作”，截止日期 2026-05-29，负责人 **韩重阳**。\n\n"
        "⚠️ 这个任务已经逾期近 3 个月了（当前 2026-09-12），进度仍为 0%。\n\n"
        "其他已到期但仍在“进行中”的任务：\n\n"
        "| 任务 | 截止 | 负责人 |\n| 英语上机考试 | 06-04 | 陈天祥 |\n"
        "| 撰写第二篇文章 | 06-05 | 吴孟铨 |\n| 看文献（油田污水相关） | 09-30 | 蒋芦笛 |\n\n"
        "以上 5 个均已过期。唯一还没到期的进行中任务是蒋芦笛的“看文献”（截止 09-30）。\n\n"
        "需要我帮你跟进或调整这些逾期任务的状态吗？"
    )

    def _msgs_to_turn7(self):
        return [
            {"role": "user", "content": "现在有哪些进行中的任务？"},
            {
                "role": "assistant",
                "content": self.TURN2_ANSWER,
                # §2 轮模型自行把范围收成当前用户 — 但回答里没出现"杜同贺"
                "tool_trace": {"trace": [
                    {"type": "tool_use", "id": "t1", "name": "query_tasks",
                     "input": {"status": "in_progress", "assignee_name": "杜同贺"}},
                ]},
            },
            {"role": "user", "content": "其中截止时间最紧的是哪个？负责人是谁？"},
            {
                "role": "assistant",
                "content": self.TURN5_ANSWER,
                # §5 轮模型自查过一次垃圾入参 (member_name 填了"截止时间")
                "tool_trace": {"trace": [
                    {"type": "tool_use", "id": "t2", "name": "query_tasks", "input": {}},
                    {"type": "tool_use", "id": "t3", "name": "get_member_profile",
                     "input": {"member_name": "截止时间"}},
                ]},
            },
            {"role": "user", "content": "他手上还有其他任务吗？"},
        ]

    def test_pronoun_he_anchors_han_chongyang_not_dutonghe(self):
        """§7 "他" 必须锚 韩重阳 (上轮回答主语), 不得跨轮翻出 §2 的杜同贺。"""
        names, _titles = _extract(self._msgs_to_turn7())
        assert names == ["韩重阳"], f"锚定人物错误: {names}"
        assert "杜同贺" not in names

    def test_garbage_tool_input_not_promoted(self):
        """get_member_profile(member_name='截止时间') 垃圾入参不得进实体 (非 roster 名)。"""
        names, _ = _extract(self._msgs_to_turn7())
        assert "截止时间" not in names

    def test_anchor_note_full_chain(self):
        """_pronoun_anchor_note 端到端: §7 问句触发注入且文本含 韩重阳。"""
        from app.agent.agentic_loop import _pronoun_anchor_note
        with patch("app.agent.agentic_loop._member_names_cache", return_value=ROSTER):
            note = _pronoun_anchor_note(self._msgs_to_turn7())
        assert "人物：韩重阳" in note
        assert "杜同贺" not in note


class TestSource0Discipline:
    """源 0 两条新纪律的独立单元行为。"""

    def test_tool_input_visible_in_answer_still_wins(self):
        """入参实体出现在该轮回答里 (用户看得到) → 仍是最高优先源, 老能力守恒。"""
        msgs = [
            {"role": "assistant",
             "content": "韩重阳 名下还有 2 项进行中任务：搭建膜法产泡系统、互联网➕ppt制作。",
             "tool_trace": {"trace": [
                 {"type": "tool_use", "id": "t", "name": "query_tasks",
                  "input": {"assignee_name": "韩重阳"}}]}},
            {"role": "user", "content": "他的任务都逾期了吗？"},
        ]
        names, _ = _extract(msgs)
        assert names == ["韩重阳"]

    def test_gate_stops_at_latest_trace_message(self):
        """最近有 trace 的一轮产出实体后, 更早轮不得再贡献 tool 实体 (关闸)。"""
        msgs = [
            {"role": "assistant",
             "content": "王天志 的任务都已安排。",
             "tool_trace": {"trace": [
                 {"type": "tool_use", "id": "t", "name": "query_tasks",
                  "input": {"assignee_name": "王天志"}}]}},
            {"role": "assistant",
             "content": "韩重阳 当前最紧急的是搭建膜法产泡系统。",
             "tool_trace": {"trace": [
                 {"type": "tool_use", "id": "t2", "name": "query_tasks",
                  "input": {"assignee_name": "韩重阳"}}]}},
            {"role": "user", "content": "他手上还有什么？"},
        ]
        names, _ = _extract(msgs)
        assert names == ["韩重阳"], "源 0 只许取最近一条有 trace 的回答 (轮距优先)"

    def test_empty_answer_message_tool_input_rejected(self):
        """该轮回答文本为空/极短 → 内部工具入参不可信, 不注入。"""
        msgs = [
            {"role": "assistant",
             "content": "好的。",
             "tool_trace": {"trace": [
                 {"type": "tool_use", "id": "t", "name": "get_member_profile",
                  "input": {"member_name": "杜同贺"}}]}},
            {"role": "user", "content": "他有什么任务？"},
        ]
        names, _ = _extract(msgs)
        assert "杜同贺" not in names

    def test_tool_trace_json_string_shape(self):
        """tool_trace 为 JSON 字符串的形态 (session redis 反序列化差异) 同规则生效。"""
        import json as _json
        msgs = [
            {"role": "assistant",
             "content": "负责人是 韩重阳，他负责互联网➕ppt制作。",
             "tool_trace": _json.dumps({"trace": [
                 {"type": "tool_use", "id": "t", "name": "query_tasks",
                  "input": {"assignee_name": "韩重阳"}}]})},
            {"role": "user", "content": "他还有哪些？"},
        ]
        names, _ = _extract(msgs)
        assert names == ["韩重阳"]


class TestTracePayloadObservability:
    """2026-09-12 补洞: _build_payload 此前漏装 Stage 3 观测字段 →
    intent_category/critique_score 列恒空 (直写 + Celery 两条路径共用 payload)。"""

    def test_payload_carries_intent_and_critique(self):
        from app.agent.tracing import TraceCollector
        tc = TraceCollector(user_id=3, session_id="s1", message="m")
        tc.set_intent("data_query", 0.95)
        tc.set_critique(9, retry_count=1)
        tc.tool_rounds_used = 2
        tc.compression_applied_count = 3
        p = tc._build_payload()
        assert p["intent_category"] == "data_query"
        assert p["intent_confidence"] == 0.95
        assert p["critique_score"] == 9
        assert p["retry_count"] == 1
        assert p["tool_rounds_used"] == 2
        assert p["compression_applied_count"] == 3

    def test_payload_defaults_none_not_keyerror(self):
        from app.agent.tracing import TraceCollector
        tc = TraceCollector(user_id=None, session_id="", message="")
        p = tc._build_payload()
        assert p["intent_category"] is None
        assert p["critique_score"] is None


class TestTaskScopeRuleInPrompt:
    """§2 口径漂移修复: 任务问句未点名 → 默认全组 (prompt 硬规则在场)。"""

    def test_scope_rule_present(self):
        from app.agent import prompts
        src = prompts.__file__
        import io
        text = io.open(src, encoding="utf-8").read()
        assert "默认全组" in text
        assert "assignee_name` 留空" in text

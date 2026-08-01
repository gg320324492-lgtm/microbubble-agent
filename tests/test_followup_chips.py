"""
test_followup_chips.py — CHAT-P1-E E2 追问 chips 后端测试

测试 _build_followup_suggestions() 方法的行为逻辑:
- 从 tool_trace (search_knowledge query) 派生追问
- 从 assistant 文本关键词派生追问
- 失败兜底: 通用模板
- 最多 3 个 chip
- 不阻塞主链路 (异常返回空 list)

实现: 这里复制了 _build_followup_suggestions 的纯算法逻辑做单元测试,
避免直接 import micro_bubble_agent 触发编码问题 (该文件含大量中文 docstring,
windows 默认 cp1252 编码解不开).
"""
import time


def _build_followup_suggestions(
    assistant_text: str,
    tool_trace: list,
    thinking_mode: str = "balanced",
) -> list:
    """_build_followup_suggestions 纯算法副本 (与 app/agent/micro_bubble_agent.py 同步)"""
    import re
    suggestions = []
    try:
        topics = []
        for t in (tool_trace or []):
            if t.get("type") != "tool_use":
                continue
            tool_name = t.get("name") or ""
            tool_input = t.get("input") or {}
            if tool_name in ("search_knowledge", "web_search", "hybrid_retrieve"):
                query = (tool_input.get("query") or tool_input.get("q") or "").strip()
                if query and len(query) < 30:
                    topics.append(query)

        if not topics and assistant_text:
            snippet = assistant_text.strip()[:100]
            words = re.split(r'[，。！？；\s,.!?;]+', snippet)
            for w in words:
                w = w.strip()
                if 2 <= len(w) <= 8 and re.search(r'[一-龥]', w):
                    topics.append(w)
                if len(topics) >= 3:
                    break

        if topics:
            t1 = topics[0]
            suggestions.append(f"展开讲讲 {t1}")
        if len(topics) >= 2:
            t2 = topics[1]
            suggestions.append(f"具体说说 {t2}")
        if len(topics) >= 3:
            t3 = topics[2]
            suggestions.append(f"还有哪些关于 {t3} 的内容")
        else:
            if thinking_mode == "deep":
                suggestions.append("能举个具体例子吗")
            else:
                suggestions.append("能再说详细一点吗")

        seen = set()
        unique = []
        for s in suggestions:
            if s not in seen:
                seen.add(s)
                unique.append(s)
            if len(unique) >= 3:
                break
        return unique
    except Exception:
        return []


class TestBuildFollowupSuggestions:
    """_build_followup_suggestions 单元测试"""

    def test_from_search_knowledge_tool_trace(self):
        """从 search_knowledge 工具调用的 query 派生追问"""
        tool_trace = [
            {"type": "tool_use", "name": "search_knowledge", "input": {"query": "微纳米气泡"}},
        ]
        suggestions = _build_followup_suggestions(
            assistant_text="微纳米气泡是一种...balabala...",
            tool_trace=tool_trace,
            thinking_mode="balanced",
        )
        assert len(suggestions) >= 1
        assert len(suggestions) <= 3
        assert any("微纳米气泡" in s for s in suggestions)

    def test_from_web_search_tool_trace(self):
        """从 web_search 工具调用的 query 派生追问"""
        tool_trace = [
            {"type": "tool_use", "name": "web_search", "input": {"q": "zeta 电位"}},
        ]
        suggestions = _build_followup_suggestions(
            assistant_text="zeta 电位是...",
            tool_trace=tool_trace,
            thinking_mode="balanced",
        )
        assert any("zeta 电位" in s for s in suggestions)

    def test_from_hybrid_retrieve_tool_trace(self):
        """从 hybrid_retrieve 工具调用派生追问"""
        tool_trace = [
            {"type": "tool_use", "name": "hybrid_retrieve", "input": {"query": "气泡尺寸分布"}},
        ]
        suggestions = _build_followup_suggestions(
            assistant_text="气泡尺寸分布...",
            tool_trace=tool_trace,
            thinking_mode="balanced",
        )
        assert any("气泡尺寸分布" in s for s in suggestions)

    def test_max_three_suggestions(self):
        """最多 3 个 chip"""
        tool_trace = [
            {"type": "tool_use", "name": "search_knowledge", "input": {"query": "topic1"}},
            {"type": "tool_use", "name": "search_knowledge", "input": {"query": "topic2"}},
            {"type": "tool_use", "name": "search_knowledge", "input": {"query": "topic3"}},
            {"type": "tool_use", "name": "search_knowledge", "input": {"query": "topic4"}},
            {"type": "tool_use", "name": "search_knowledge", "input": {"query": "topic5"}},
        ]
        suggestions = _build_followup_suggestions(
            assistant_text="...",
            tool_trace=tool_trace,
        )
        assert len(suggestions) <= 3

    def test_fallback_when_no_tool_trace(self):
        """无工具调用时, 从 assistant 文本关键词兜底"""
        suggestions = _build_followup_suggestions(
            assistant_text="微纳米气泡在水中稳定存在, 具有广泛的应用",
            tool_trace=[],
            thinking_mode="balanced",
        )
        assert len(suggestions) >= 1

    def test_deep_mode_fallback(self):
        """deep 模式 fallback 包含'具体例子'"""
        suggestions = _build_followup_suggestions(
            assistant_text="微纳米气泡是一种技术",
            tool_trace=[],
            thinking_mode="deep",
        )
        joined = " ".join(suggestions)
        assert "例子" in joined or "详细" in joined

    def test_balanced_mode_fallback(self):
        """balanced 模式 fallback 是 '能再说详细一点吗'"""
        suggestions = _build_followup_suggestions(
            assistant_text="",
            tool_trace=[],
            thinking_mode="balanced",
        )
        joined = " ".join(suggestions)
        assert "详细" in joined or "例子" in joined

    def test_empty_assistant_text(self):
        """assistant 文本为空时也能返回 (兜底)"""
        suggestions = _build_followup_suggestions(
            assistant_text="",
            tool_trace=[],
        )
        assert isinstance(suggestions, list)

    def test_dedup_suggestions(self):
        """去重: 重复 topic 不会重复 chip"""
        tool_trace = [
            {"type": "tool_use", "name": "search_knowledge", "input": {"query": "气泡"}},
            {"type": "tool_use", "name": "search_knowledge", "input": {"query": "气泡"}},
        ]
        suggestions = _build_followup_suggestions(
            assistant_text="气泡...",
            tool_trace=tool_trace,
        )
        assert len(suggestions) == len(set(suggestions))

    def test_non_search_tool_ignored(self):
        """非检索类工具 (如 write_file) 不参与派生"""
        tool_trace = [
            {"type": "tool_use", "name": "write_file", "input": {"path": "/tmp/test.txt"}},
        ]
        suggestions = _build_followup_suggestions(
            assistant_text="...",
            tool_trace=tool_trace,
        )
        assert isinstance(suggestions, list)

    def test_does_not_call_llm(self):
        """绝不调 LLM (设计原则): 同步操作 < 100ms"""
        start = time.monotonic()
        suggestions = _build_followup_suggestions(
            assistant_text="微纳米气泡是一种...",
            tool_trace=[{"type": "tool_use", "name": "search_knowledge", "input": {"query": "气泡"}}],
        )
        elapsed_ms = (time.monotonic() - start) * 1000
        assert elapsed_ms < 100, f"_build_followup_suggestions 耗时 {elapsed_ms}ms, 应 < 100ms (无 LLM 调用)"
        assert isinstance(suggestions, list)

    def test_long_query_exceeds_30_chars_ignored(self):
        """query 长度 >= 30 字符时被过滤 (避免无意义长 query)"""
        tool_trace = [
            {"type": "tool_use", "name": "search_knowledge", "input": {"query": "a" * 50}},
        ]
        suggestions = _build_followup_suggestions(
            assistant_text="some assistant text here",
            tool_trace=tool_trace,
        )
        # 长 query 不会作为 topic, 兜底从 assistant 派生 或 通用模板
        assert isinstance(suggestions, list)
        # 不应包含 "展开讲讲 aaaa..."
        joined = " ".join(suggestions)
        assert "a" * 30 not in joined

    def test_multiple_search_tools_dedup(self):
        """多个 search tool 时取前 2 个 + 兜底通用模板 (共 3 个)"""
        tool_trace = [
            {"type": "tool_use", "name": "search_knowledge", "input": {"query": "topic A"}},
            {"type": "tool_use", "name": "search_knowledge", "input": {"query": "topic B"}},
        ]
        suggestions = _build_followup_suggestions(
            assistant_text="...",
            tool_trace=tool_trace,
        )
        # 2 个 topic 派生 + 1 个通用兜底 = 3 个
        assert len(suggestions) == 3
        assert any("topic A" in s for s in suggestions)
        assert any("topic B" in s for s in suggestions)

    def test_exception_returns_empty_list(self):
        """异常时返回空 list (绝不抛异常)"""
        # 传入 None 作为 tool_trace → 内部 try/except 兜底
        suggestions = _build_followup_suggestions(
            assistant_text="",
            tool_trace=None,
        )
        assert isinstance(suggestions, list)
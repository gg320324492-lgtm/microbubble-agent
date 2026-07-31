"""tests/rag_framework/test_query_translator.py — QueryTranslator 4 场景 mock 测试

Mock LLM 场景:
1. 成功 3 路: LLM 返回 JSON 数组 → multi_query 3 路 + 原 query 保底
2. LLM 失败: complete() 抛异常 → 回退原样 [query]
3. JSON 解析失败: LLM 返回非 JSON → 回退原样 [query]
4. 空 query: 空字符串 → 回退原样 [""]

运行: SKIP_DB_SETUP=1 pytest tests/rag_framework/test_query_translator.py -v
不需要真 PostgreSQL / 不需要 LangChain / LlamaIndex 框架依赖。
"""

import json

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.rag.query_translator import (
    QueryTranslator,
    _merge_query_results,
    _parse_json_array,
    get_query_translator,
)


class MockLLM:
    """假 LLM — complete() 返回可控 text / 抛异常"""

    def __init__(self, text: str = "", error: Exception = None):
        self._text = text
        self._error = error
        self.calls: list = []

    async def complete(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        if self._error:
            raise self._error
        resp = MagicMock()
        resp.text = self._text
        return resp


@pytest.fixture
def translator():
    return QueryTranslator(db=None, llm=None)


class TestMultiQuery:
    async def test_success_3_queries(self):
        """场景 1: LLM 成功返回 3 路同义改写 → 原 query 保底 + 3 路"""
        llm = MockLLM(text=json.dumps(["臭氧微气泡消毒", "ozone microbubble disinfection", "臭氧高级氧化 消毒 效率"]))
        qt = QueryTranslator(db=None, llm=llm)
        result = await qt.multi_query("臭氧微气泡消毒效果")
        assert len(result) == 4
        assert result[0] == "臭氧微气泡消毒效果"  # 原 query 保底置首
        assert "臭氧微气泡消毒" in result
        assert "ozone microbubble disinfection" in result
        assert "臭氧高级氧化 消毒 效率" in result
        # 完整 JSON → 走 parse_llm_json, 不触发 regex 兜底
        assert len(llm.calls) == 1
        assert llm.calls[0]["kwargs"].get("max_tokens") == 300

    async def test_llm_failure_fallback_original(self):
        """场景 2: LLM 失败抛异常 → 回退原样 [query]"""
        llm = MockLLM(error=TimeoutError("LLM timeout"))
        qt = QueryTranslator(db=None, llm=llm)
        result = await qt.multi_query("臭氧微气泡消毒效果")
        assert result == ["臭氧微气泡消毒效果"]

    async def test_json_parse_failure_fallback_original(self):
        """场景 3: LLM 返回垃圾文本无法解析 JSON → 回退原样 [query]"""
        llm = MockLLM(text="对不起, 我无法回答这个问题。")
        qt = QueryTranslator(db=None, llm=llm)
        result = await qt.multi_query("臭氧微气泡消毒效果")
        assert result == ["臭氧微气泡消毒效果"]

    async def test_empty_query_fallback(self):
        """场景 4: 空 query → 原样 [""] 且不调 LLM"""
        llm = MockLLM(text=json.dumps(["不应被调用的改写"]))
        qt = QueryTranslator(db=None, llm=llm)
        result = await qt.multi_query("")
        assert result == [""]
        assert llm.calls == []  # 空 query 不调 LLM


class TestHyde:
    async def test_success_returns_hypothetical_doc(self):
        llm = MockLLM(text="假设文献摘要: 本文研究臭氧微气泡对水中大肠杆菌的灭活效率...")
        qt = QueryTranslator(db=None, llm=llm)
        result = await qt.hyde("臭氧微气泡消毒效果")
        assert "臭氧微气泡" in result

    async def test_failure_fallback_original(self):
        llm = MockLLM(error=RuntimeError("boom"))
        qt = QueryTranslator(db=None, llm=llm)
        assert await qt.hyde("臭氧微气泡消毒效果") == "臭氧微气泡消毒效果"

    async def test_empty_fallback(self):
        qt = QueryTranslator(db=None, llm=MockLLM(text="不应被调用"))
        assert await qt.hyde("") == ""


class TestDecompose:
    async def test_success_returns_sub_queries(self):
        llm = MockLLM(text=json.dumps(["臭氧微气泡消毒机理", "臭氧微气泡消毒影响因素"]))
        qt = QueryTranslator(db=None, llm=llm)
        result = await qt.decompose("臭氧微气泡消毒效果如何, 受哪些因素影响")
        assert len(result) == 2

    async def test_failure_fallback_original(self):
        llm = MockLLM(error=ValueError("bad"))
        qt = QueryTranslator(db=None, llm=llm)
        assert await qt.decompose("复杂问题") == ["复杂问题"]


class TestTranslate:
    async def test_translate_multi_query(self):
        llm = MockLLM(text=json.dumps(["q1", "q2", "q3"]))
        qt = QueryTranslator(db=None, llm=llm)
        result = await qt.translate("原问题", mode="multi_query")
        assert result[0] == "原问题"
        assert "q1" in result

    async def test_translate_hyde_includes_original(self):
        llm = MockLLM(text="假设文档")
        qt = QueryTranslator(db=None, llm=llm)
        result = await qt.translate("原问题", mode="hyde")
        assert result == ["假设文档", "原问题"]  # HyDE + 原文

    async def test_translate_unknown_mode_returns_original(self):
        qt = QueryTranslator(db=None, llm=MockLLM(text="x"))
        assert await qt.translate("原问题", mode="unknown") == ["原问题"]

    async def test_translate_llm_failure_returns_original(self):
        """门控内 LLM 失败 → multi_query 层回退, translate 仍返回 [原问题]"""
        llm = MockLLM(error=TimeoutError("t"))
        qt = QueryTranslator(db=None, llm=llm)
        assert await qt.translate("原问题", mode="multi_query") == ["原问题"]


class TestExpandAndSearch:
    async def test_parallel_search_and_merge(self):
        """多路检索并行 → 合并去重 (同 id 保留最高分)"""
        llm = MockLLM(text=json.dumps(["改写1", "改写2"]))

        class FakeRetriever:
            async def retrieve(self, query, top_k=5, **kwargs):
                # 改写1 与 原 query 返回同一 doc, 改写2 返回新 doc
                if query == "改写1":
                    return [{"id": 1, "score": 0.8, "title": "doc1"}]
                if query == "改写2":
                    return [{"id": 2, "score": 0.9, "title": "doc2"}]
                return [{"id": 1, "score": 0.6, "title": "doc1"}]

        qt = QueryTranslator(db=None, llm=llm)
        result = await qt.expand_and_search("原问题", retriever=FakeRetriever())
        assert result["mode"] == "multi_query"
        assert result["queries"][0] == "原问题"  # 保底在首位
        # 合并去重: doc1 只出现一次 (最高分 0.8 保留)
        ids = sorted(r["id"] for r in result["results"])
        assert ids == [1, 2]
        doc1 = next(r for r in result["results"] if r["id"] == 1)
        assert doc1["score"] == 0.8

    async def test_retrieve_failure_does_not_kill_all(self):
        """单路检索失败 → 其余路结果保留"""
        llm = MockLLM(text=json.dumps(["改写1", "改写2"]))

        class FakeRetriever:
            async def retrieve(self, query, top_k=5, **kwargs):
                if query == "改写1":
                    raise RuntimeError("retrieve boom")
                return [{"id": 1, "score": 0.5, "title": "doc1"}]

        qt = QueryTranslator(db=None, llm=llm)
        result = await qt.expand_and_search("原问题", retriever=FakeRetriever())
        assert len(result["results"]) == 1
        assert result["results"][0]["id"] == 1

    async def test_no_retriever_requires_db(self):
        """未注入 retriever 且无 db → ValueError (前置校验, 不崩)"""
        qt = QueryTranslator(db=None, llm=MockLLM(text="[]"))
        with pytest.raises(ValueError):
            await qt.expand_and_search("原问题")


class TestHelpers:
    def test_parse_json_array_code_block(self):
        text = '```json\n["a", "b"]\n```'
        assert _parse_json_array(text) == ["a", "b"]

    def test_parse_json_array_plain(self):
        assert _parse_json_array('["a", "b"]') == ["a", "b"]

    def test_parse_json_array_garbage(self):
        assert _parse_json_array("没有数组") == []

    def test_parse_json_array_empty(self):
        assert _parse_json_array("") == []

    def test_parse_json_array_regex_fallback(self):
        # 前后夹带说明文字 → regex 兜底提取
        text = '好的: ["a", "b"] 以上是结果'
        assert _parse_json_array(text) == ["a", "b"]

    def test_merge_query_results_dedup(self):
        r1 = [{"id": 1, "score": 0.8}, {"id": 3, "score": 0.7}]
        r2 = [{"id": 1, "score": 0.5}]
        merged = _merge_query_results([r1, r2])
        assert len(merged) == 2
        doc1 = next(r for r in merged if r["id"] == 1)
        assert doc1["score"] == 0.8  # 保留最高分
        assert "query" in doc1["retrieval_methods"]

    def test_get_query_translator_factory(self):
        assert isinstance(get_query_translator(), QueryTranslator)


class TestGate:
    async def test_gate_flag_off_returns_none(self):
        """门控关闭 → translate 返回 None (gate 语义, 上层自行回退原 query)"""
        # translate 装饰器在 import 时捕获 flag 值, 此处直接用 gate 装饰器验证
        # feature_flag=False + fallback_fn=None 的语义: 不执行主体, 返回 None
        from app.rag.gate import framework_gate

        calls = {"n": 0}

        @framework_gate(feature_flag=False, fallback_fn=None)
        async def wrapped(query):
            calls["n"] += 1
            return ["should_not_run"]

        result = await wrapped("原问题")
        assert result is None
        assert calls["n"] == 0

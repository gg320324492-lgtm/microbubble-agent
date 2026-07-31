"""app/rag/query_translator.py — Query 翻译/重写/扩展

LangChain 三件套:
1. MultiQueryRetriever: 用户 1 问 → 3-5 路同义改写 → 并行检索 → 合并
2. HyDE: 用户 query → LLM 生成假设文档 → 嵌入假设文档检索 (recall +15-25%)
3. QueryDecomposition: 复杂问题 → 拆子问题 → 分别检索 → 合并

全部走 framework_gate 门控, 失败自动回退原 query 直传 hybrid_retriever。
"""

import asyncio
import json
import logging
import re
from typing import Any, List, Optional

from app.rag.config import QUERY_TRANSLATION_ENABLED
from app.rag.gate import framework_gate

logger = logging.getLogger("microbubble.rag.query_translator")

# 中文同义改写 prompt — 微纳米气泡领域
MULTI_QUERY_PROMPT = """你是一个中文科研文献检索助手。请把用户问题改写成 3-5 个不同角度的检索 query，覆盖同义词、上下位词、英文术语、缩写。

用户问题: {query}

只输出 JSON 数组，每个元素是一个字符串 query:
["...", "...", "..."]

示例:
用户问题: 臭氧微气泡消毒效果
输出: ["臭氧微气泡消毒", "ozone microbubble disinfection", "臭氧微气泡 灭活 细菌", "臭氧高级氧化 消毒 效率", "O3 微气泡 杀菌"]

不要输出其他内容。"""

HYDE_PROMPT = """你是一个科研文献检索助手。根据用户问题，生成一段"假设的理想文献摘要"（3-5 句），描述如果存在一篇完美回答该问题的文献，它的摘要应该长什么样。这个摘要将用于向量检索。

用户问题: {query}

只输出摘要文本，不要输出其他内容。"""

DECOMPOSITION_PROMPT = """你是一个科研问题分解助手。把复杂问题拆成 2-4 个独立的子问题，每个子问题应该能独立检索到文献。

用户问题: {query}

只输出 JSON 数组，每个元素是一个字符串子问题:
["...", "...", "..."]

不要输出其他内容。"""


def _parse_json_array(text: str) -> List[str]:
    """从 LLM 输出中提取 JSON 字符串数组, 失败返回 [].

    兼容: 裸 JSON 数组 / ```json 代码块 / 前后夹带说明文字 (regex 兜底).
    """
    if not text:
        return []
    text = text.strip()
    # 1) 完整 JSON 解析 (parse_llm_json 兼容 markdown 代码块包裹)
    try:
        from app.core.llm import parse_llm_json
        parsed = parse_llm_json(text)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    # 2) regex 兜底: 提取第一个 JSON 数组
    m = re.search(r"\[[^\[\]]*\]", text, re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group(0))
            if isinstance(arr, list):
                return [str(x).strip() for x in arr if str(x).strip()]
        except Exception:
            pass
    return []


def _extract_text(response: Any) -> str:
    """从 LLM 响应提取纯文本 (兼容 Anthropic Message 形状 / 注入的 mock 形状)."""
    if response is None:
        return ""
    text = getattr(response, "text", None)
    if text:
        return str(text)
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif hasattr(block, "text") and getattr(block, "text"):
                parts.append(str(block.text))
        return "".join(parts)
    return ""


def _merge_query_results(result_lists: List[List[dict]]) -> List[dict]:
    """合并多路查询结果去重 — 复用 hybrid_retriever._merge_results 模式.

    同一 doc id 保留最高分, 记录所有来源 (retrieval_methods 追加来源)。
    """
    merged: dict = {}
    for results in result_lists:
        for r in results or []:
            doc_id = r.get("id")
            if doc_id is None:
                continue
            if doc_id not in merged:
                merged[doc_id] = {**r, "retrieval_methods": list(r.get("retrieval_methods", [])) or ["query"]}
            else:
                existing = merged[doc_id]
                if r.get("score", 0) > existing.get("score", 0):
                    existing.update(r)
                existing.setdefault("retrieval_methods", []).append("query")
    return list(merged.values())


class QueryTranslator:
    """Query 翻译器 — MultiQuery + HyDE + Decomposition 三合一"""

    def __init__(self, db=None, llm=None):
        self.db = db
        self.llm = llm

    def _get_llm(self):
        """返回 LLM 客户端: 优先注入, 否则懒加载 app.core.llm.LLMClient 单例."""
        if self.llm is not None:
            return self.llm
        from app.core.llm import LLMClient
        return LLMClient()

    async def _call_llm(self, prompt: str) -> str:
        """统一 LLM 调用: 失败抛异常, 由上层回退原 query."""
        llm = self._get_llm()
        response = await llm.complete(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.3,
            thinking={"type": "disabled"},  # 强制纯文本输出, 避免 thinking block
        )
        return _extract_text(response)

    async def multi_query(self, query: str, count: int = 3) -> List[str]:
        """Multi-query: 同义改写 3-5 路"""
        query = (query or "").strip()
        if not query:
            return [query]
        try:
            prompt = MULTI_QUERY_PROMPT.format(query=query)
            text = await self._call_llm(prompt)
            variants = _parse_json_array(text)
            if variants:
                # 保底包含原 query (改写全跑偏时检索仍有兜底)
                if query not in variants:
                    variants.insert(0, query)
                # 上限: 原 query + 3-5 路改写 = 最多 5 条 (brief 语义 count=3 为改写路数)
                return variants[:5]
        except Exception as e:
            logger.warning(f"multi_query LLM 失败, 回退原 query (query={query!r}): {e}")
        return [query]

    async def hyde(self, query: str) -> str:
        """HyDE: 生成假设文档"""
        query = (query or "").strip()
        if not query:
            return query
        try:
            prompt = HYDE_PROMPT.format(query=query)
            text = await self._call_llm(prompt)
            if text.strip():
                return text.strip()
        except Exception as e:
            logger.warning(f"hyde LLM 失败, 回退原 query (query={query!r}): {e}")
        return query

    async def decompose(self, query: str) -> List[str]:
        """QueryDecomposition: 拆子问题"""
        query = (query or "").strip()
        if not query:
            return [query]
        try:
            prompt = DECOMPOSITION_PROMPT.format(query=query)
            text = await self._call_llm(prompt)
            sub_queries = _parse_json_array(text)
            if sub_queries:
                return sub_queries[:4]
        except Exception as e:
            logger.warning(f"decompose LLM 失败, 回退原 query (query={query!r}): {e}")
        return [query]

    @framework_gate(feature_flag=QUERY_TRANSLATION_ENABLED,
                    fallback_fn=None)
    async def translate(self, query: str, mode: str = "multi_query") -> List[str]:
        """翻译入口 — 按 mode 返回改写后的 query 列表

        注意: 门控关闭或内部异常时按 gate 语义返回 None (无 fallback_fn)。
        低层 multi_query/hyde/decompose 各自 try-except 回退 [query], 本方法不重复兜底。
        """
        if mode == "multi_query":
            return await self.multi_query(query)
        elif mode == "hyde":
            return [await self.hyde(query), query]  # HyDE + 原文
        elif mode == "decompose":
            return await self.decompose(query)
        return [query]

    async def expand_and_search(
        self,
        query: str,
        mode: str = "multi_query",
        retriever: Any = None,
        top_k: int = 5,
        **retrieve_kwargs,
    ) -> dict:
        """高阶层: translate → 并行调 hybrid_retriever.retrieve → 合并去重

        返回: {"results": List[dict], "queries": List[str], "mode": str}

        - translate 失败/门控关闭返回 None → 回退原 query 直传 (结果 = 单路原 query 检索)
        - 每路检索独立 try-except: 单路失败不拖垮整体
        - 合并复用 _merge_results 模式 (同 doc id 保留最高分 + 记录来源)
        """
        if retriever is None:
            from app.services.hybrid_retriever import get_hybrid_retriever
            if self.db is None:
                raise ValueError("QueryTranslator(db=...) 必须传入 db 或 retriever")
            retriever = get_hybrid_retriever(self.db)

        queries = await self.translate(query, mode=mode)
        if not queries:
            # 门控关闭 / 失败 → 原 query 直传
            queries = [query]

        async def _retrieve_one(q: str) -> List[dict]:
            try:
                return await retriever.retrieve(query=q, top_k=top_k, **retrieve_kwargs)
            except Exception as e:
                logger.error(f"expand_and_search 检索失败 (query={q!r}): {e}", exc_info=True)
                return []

        result_lists = await asyncio.gather(*[_retrieve_one(q) for q in queries])
        return {
            "results": _merge_query_results(result_lists),
            "queries": queries,
            "mode": mode,
        }


# 模块级工厂 (与 hybrid_retriever.get_hybrid_retriever 对齐)
def get_query_translator(db=None, llm=None) -> QueryTranslator:
    """获取 QueryTranslator 实例 (每请求新建, 不绑定全局单例)"""
    return QueryTranslator(db=db, llm=llm)

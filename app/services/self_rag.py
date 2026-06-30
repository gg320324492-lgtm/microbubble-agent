"""Self-RAG 自检服务 — 检索结果相关性检查 + 上下文压缩

在生成回答前检查检索结果是否真的相关，不相关则重新检索或降级。
同时对检索结果进行去重和压缩，减少 token 消耗。
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger("microbubble.self_rag")


class SelfRAGChecker:
    """Self-RAG 自检器"""

    def __init__(self):
        pass

    async def check_relevance(
        self, query: str, context: str, *, model: Optional[str] = None
    ) -> Dict:
        """检查检索结果是否能回答问题

        Args:
            query: 用户问题
            context: 检索到的上下文
            model: judge 模型 (None 时用 self._default_model, 默认 Sonnet via AGENT_REFLECTION_MODEL)

        Returns:
            {
                "can_answer": bool,
                "reason": str,
                "missing": str,
                "confidence": float,
                "model_used": str,
                "latency_ms": int,
            }
        """
        import time as _time
        start_ts = _time.monotonic()
        try:
            from app.core.llm import get_anthropic_client

            client = get_anthropic_client()
            chosen_model = model or getattr(self, "_default_model", None)
            if not chosen_model:
                # fallback to settings AGENT_REFLECTION_MODEL or get_default_model
                try:
                    from app.config import settings
                    chosen_model = settings.AGENT_REFLECTION_MODEL or None
                except Exception:
                    chosen_model = None
            if not chosen_model:
                from app.core.llm import get_default_model
                chosen_model = get_default_model()

            prompt = f"""你是一个知识库问答系统的质量检查员。
判断以下检索到的上下文是否能回答用户问题。

用户问题: {query}

检索到的上下文:
{context[:2000]}

请返回 JSON 格式:
{{"can_answer": true/false, "reason": "原因", "missing": "缺少什么信息", "confidence": 0.0-1.0}}

判断标准:
- can_answer=true: 上下文包含足够的信息来回答问题
- can_answer=false: 上下文信息不足或完全不相关
- confidence: 你对判断的置信度"""

            response = await client.messages.create(
                model=model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )

            import json
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

            # 提取 JSON
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            latency_ms = int((_time.monotonic() - start_ts) * 1000)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "can_answer": result.get("can_answer", False),
                    "reason": result.get("reason", ""),
                    "missing": result.get("missing", ""),
                    "confidence": float(result.get("confidence", 0.5)),
                    "model_used": chosen_model,
                    "latency_ms": latency_ms,
                }

            return {
                "can_answer": True,
                "reason": "无法判断，默认通过",
                "missing": "",
                "confidence": 0.5,
                "model_used": chosen_model,
                "latency_ms": latency_ms,
            }

        except Exception as e:
            latency_ms = int((_time.monotonic() - start_ts) * 1000)
            logger.warning(f"Self-RAG check failed: {e}")
            return {
                "can_answer": True,
                "reason": "检查失败，默认通过",
                "missing": "",
                "confidence": 0.3,
                "model_used": model or "unknown",
                "latency_ms": latency_ms,
            }

    async def should_retrieve(self, query: str) -> Dict:
        """判断是否需要检索

        Args:
            query: 用户问题

        Returns:
            {"need_retrieve": bool, "reason": str}
        """
        try:
            from app.core.llm import get_anthropic_client, get_default_model

            client = get_anthropic_client()
            model = get_default_model()

            prompt = f"""判断以下问题是否需要从知识库检索信息来回答。

用户问题: {query}

返回 JSON:
{{"need_retrieve": true/false, "reason": "原因"}}

不需要检索的情况:
- 通用问候（"你好"、"谢谢"）
- 简单计算（"1+1=?"）
- 系统操作（"帮我创建任务"）
- 闲聊（"今天天气怎么样"）

需要检索的情况:
- 专业知识问题（"什么是微纳米气泡"）
- 实验方法（"如何测量zeta电位"）
- 文献查询（"有没有关于XX的论文"）
- 技术对比（"超声法和化学法哪个好"）"""

            response = await client.messages.create(
                model=model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )

            import json
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                return {
                    "need_retrieve": result.get("need_retrieve", True),
                    "reason": result.get("reason", ""),
                }

            return {"need_retrieve": True, "reason": "无法判断，默认检索"}

        except Exception as e:
            logger.warning(f"Retrieve check failed: {e}")
            return {"need_retrieve": True, "reason": "检查失败，默认检索"}

    def refine_query(
        self,
        original_query: str,
        missing: str,
        intent_keywords: Optional[List[str]] = None,
        max_chars: int = 64,
    ) -> str:
        """2026-06-30 #009 Self-RAG: 确定性关键词改写查询

        v1 用纯字符串拼接 (intent.keywords + missing 关键词 + original_query),
        零额外 LLM latency (~节省 300ms)。LLM 改写版本留 #009c A/B test。

        Args:
            original_query: 原始用户问题
            missing: judge 返回的 missing 字段 (e.g. "缺少 zeta 电位实验数据")
            intent_keywords: intent.keywords 列表
            max_chars: 改写后 query 最长字符数 (中文按 1 字符)

        Returns:
            改写后的 query 字符串 (deterministic)
        """
        import re as _re
        tokens: list[str] = []

        # 1. intent_keywords (前 3 个)
        for kw in (intent_keywords or [])[:3]:
            kw = (kw or "").strip()
            if kw and kw not in tokens:
                tokens.append(kw)

        # 2. missing 关键词 (去标点 + 去中文停用词 + 去单字)
        stop_words = {"的", "了", "在", "是", "和", "与", "或", "及", "缺少", "需要"}
        if missing:
            # split by 中英文标点 + 空白
            parts = _re.split(r"[\s,，。.;；:：、!?？()()（）]+", missing)
            for p in parts:
                p = (p or "").strip()
                if len(p) < 2 or p in stop_words:
                    continue
                if p not in tokens:
                    tokens.append(p)
                if len(tokens) >= 6:  # 限制 keyword 总数
                    break

        # 3. original_query (放最前面)
        base = (original_query or "").strip()
        if base:
            # 拼接: original + 关键词 (original 在前保证语义连贯)
            refined = base + " " + " ".join(tokens)
        else:
            refined = " ".join(tokens)

        # 截断
        if len(refined) > max_chars:
            refined = refined[:max_chars].rsplit(" ", 1)[0] or refined[:max_chars]
        return refined


class ContextCompressor:
    """上下文压缩器 — 去重 + 摘要"""

    def __init__(self):
        pass

    def deduplicate(self, results: List[dict]) -> List[dict]:
        """去重：移除标题和内容高度相似的条目"""
        if not results:
            return results

        unique = []
        seen_titles = set()
        seen_contents = set()

        for r in results:
            title = r.get("title", "").strip()
            content = r.get("content", "")[:200].strip()

            # 标题去重
            if title in seen_titles:
                continue

            # 内容去重（前 200 字符）
            content_hash = hash(content)
            if content_hash in seen_contents:
                continue

            seen_titles.add(title)
            seen_contents.add(content_hash)
            unique.append(r)

        return unique

    async def compress(
        self, query: str, results: List[dict], max_tokens: int = 2000
    ) -> str:
        """压缩上下文为适合 LLM 的格式

        Args:
            query: 用户问题
            results: 检索结果
            max_tokens: 最大 token 数（约 4 字符/token）

        Returns:
            压缩后的上下文字符串
        """
        # 先去重
        unique_results = self.deduplicate(results)

        # 按相关性排序（假设已排序）
        context_parts = []
        total_chars = 0
        max_chars = max_tokens * 4  # 粗略估计

        for i, r in enumerate(unique_results, 1):
            title = r.get("title", "")
            content = r.get("content", "")[:300]
            score = r.get("score", r.get("rerank_score", 0))
            methods = r.get("retrieval_methods", [r.get("retrieval_method", "")])

            part = f"[{i}] {title} (相关度: {score:.2f}, 来源: {','.join(methods)})\n{content}\n"

            if total_chars + len(part) > max_chars:
                break

            context_parts.append(part)
            total_chars += len(part)

        return "\n---\n".join(context_parts) if context_parts else "知识库中暂无相关内容。"


# 全局单例
_self_rag_checker: Optional[SelfRAGChecker] = None
_context_compressor: Optional[ContextCompressor] = None


def get_self_rag_checker() -> SelfRAGChecker:
    """获取 Self-RAG 检查器单例"""
    global _self_rag_checker
    if _self_rag_checker is None:
        _self_rag_checker = SelfRAGChecker()
    return _self_rag_checker


def get_context_compressor() -> ContextCompressor:
    """获取上下文压缩器单例"""
    global _context_compressor
    if _context_compressor is None:
        _context_compressor = ContextCompressor()
    return _context_compressor

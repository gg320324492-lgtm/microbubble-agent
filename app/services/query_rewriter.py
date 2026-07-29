"""PR9 / W95 — query_rewriter 同义改写 (接 PR4 synonym_dict + LLM 兜底)

PR9 量化门禁 #3: 同义改写覆盖 query ≥ 50% (synonym_dict 扩到 ≥ 200 条)。

**两层策略**:
1. **Layer 1 (synonym_dict)**: 调 PR4 `app.services.synonym_dict.expand(query)` (若已建) 做术语级同义替换
2. **Layer 2 (LLM 兜底)**: 对 Layer 1 失败或空结果, 调 LLM 生成 3-5 个同义改写

**派工纪要 v6 §2 复用纪律**:
- 复用 PR4 `app.services.synonym_dict` (如已建, 自动降级仅 LLM)
- 复用 `app.core.llm.get_anthropic_client`
- 不动 v1 `search_service.search` 调用点 — 由 v2 入口显式调 `query_rewriter.rewrite(query)`

**feature flag**: `QUERY_REWRITER_ENABLED=False` (默认 False, 与 v2 绑定)

**API 设计**:
- `async def rewrite(query: str, max_variants: int = 5) -> List[str]`
- `class QueryRewriter` (不依赖 db, 仅 LLM 调用 + 可选 synonym_dict)

派工日期：2026-07-30
锚点范式：W95 +8..+11 (4 commits)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("microbubble.query_rewriter")

# Feature flag — PR9 默认 False (v2 启用时才开)
QUERY_REWRITER_ENABLED: bool = False

# LLM 兜底 prompt
LLM_REWRITE_PROMPT = """你是微纳米气泡课题组的AI知识助手。对用户的搜索查询生成 3-5 个同义改写版本，用于提升联网搜索召回率。

## 原始查询

{query}

## 要求

1. 保持核心语义不变（不要改变研究主题）
2. 用不同表述（中文 / 英文 / 长尾关键词 / 专业术语变体）
3. 至少包含 1 个中文 + 1 个英文（若原始为中文）或反向
4. 不要添加与原查询无关的扩展

## 输出

返回严格的 JSON 数组（不要包含其他文字）：

["改写1", "改写2", "改写3", "改写4"]"""


def _try_synonym_dict_expand(query: str, top_k: int = 5) -> List[str]:
    """尝试调 PR4 synonym_dict (若未建则降级返回 []).

    兼容两种 PR4 实现:
    - 模块顶层: `from app.services.synonym_dict import synonym_dict` (实例)
    - 工厂函数: `from app.services.synonym_dict import get_synonym_dict` (工厂)
    """
    # 模式 1: 顶层实例
    try:
        from app.services.synonym_dict import synonym_dict as _sd

        if _sd is None:
            return []
        result = _sd.expand(query, top_k=top_k) if hasattr(_sd, "expand") else []
        if isinstance(result, list):
            return [r for r in result if isinstance(r, str) and r.strip()]
        return []
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"synonym_dict 顶层调用失败: {e}")
    # 模式 2: 工厂函数
    try:
        from app.services.synonym_dict import get_synonym_dict

        sd = get_synonym_dict()
        if sd is None:
            return []
        result = sd.expand(query, top_k=top_k) if hasattr(sd, "expand") else []
        if isinstance(result, list):
            return [r for r in result if isinstance(r, str) and r.strip()]
        return []
    except ImportError:
        return []
    except Exception as e:
        logger.debug(f"synonym_dict 工厂调用失败: {e}")
        return []


class QueryRewriter:
    """同义改写服务 — synonym_dict (PR4) + LLM 兜底。"""

    def __init__(self, *, max_variants: int = 5, enable_llm: bool = True):
        self.max_variants = max_variants
        self.enable_llm = enable_llm

    async def rewrite(self, query: str) -> List[str]:
        """对 query 生成同义改写列表。

        Args:
            query: 原始查询字符串

        Returns:
            同义改写列表 (含原 query 在第 1 位, 便于直接拼接)
            失败/空 → 仅返回 [query]
        """
        if not query or not query.strip():
            return []

        variants: List[str] = [query.strip()]

        # Layer 1: synonym_dict (若可用)
        sd_variants = _try_synonym_dict_expand(query, top_k=self.max_variants)
        for v in sd_variants:
            if v.strip() not in variants:
                variants.append(v.strip())
                if len(variants) >= self.max_variants:
                    break

        # Layer 2: LLM 兜底 (变体不足时)
        if len(variants) < 3 and self.enable_llm:
            llm_variants = await self._llm_rewrite(query)
            for v in llm_variants:
                if v and v.strip() and v.strip() not in variants:
                    variants.append(v.strip())
                    if len(variants) >= self.max_variants:
                        break

        return variants[: self.max_variants]

    async def _llm_rewrite(self, query: str) -> List[str]:
        """LLM 兜底生成同义改写。"""
        try:
            from app.core.llm import (
                extract_text_from_response,
                get_anthropic_client,
                get_default_model,
            )

            client = get_anthropic_client()
            prompt = LLM_REWRITE_PROMPT.format(query=query)
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=300,
                timeout=30,
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": prompt}],
            )
            text = extract_text_from_response(response)
            # 直接尝试 JSON 数组
            import json
            import re

            # 兼容代码块 ```json [...]```
            m = re.search(r"\[[^\]]*\]", text, re.DOTALL)
            if m:
                try:
                    arr = json.loads(m.group(0))
                    if isinstance(arr, list):
                        return [str(x) for x in arr if x]
                except Exception:
                    pass
            # 兼容裸数组
            try:
                arr = json.loads(text.strip())
                if isinstance(arr, list):
                    return [str(x) for x in arr if x]
            except Exception:
                pass
            return []
        except Exception as e:
            logger.warning(f"_llm_rewrite 失败 (query={query!r}): {e}")
            return []

    def rewrite_sync(self, query: str) -> List[str]:
        """同步版: 仅 Layer 1 synonym_dict, 不调 LLM (供 PR9 e2e 用, 避免 async loop)."""
        if not query or not query.strip():
            return []
        variants = [query.strip()]
        for v in _try_synonym_dict_expand(query, top_k=self.max_variants):
            if v.strip() not in variants:
                variants.append(v.strip())
                if len(variants) >= self.max_variants:
                    break
        return variants[: self.max_variants]


# 全局单例 (不绑定 db)
def get_query_rewriter(max_variants: int = 5) -> QueryRewriter:
    return QueryRewriter(max_variants=max_variants)

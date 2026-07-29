"""PR9 / W95 — dedup_cross_doc 跨文档去重 (pgvector 余弦 + LLM-as-judge 双闸门)

PR9 量化门禁 #2: 跨文档去重准确率 ≥ 95%。

**双闸门策略**:
1. **闸门 1 (pgvector cosine ≥ threshold)**: 快速粗筛, 默认 threshold=0.92
2. **闸门 2 (LLM-as-judge)**: 对粗筛候选做语义判定, 排除同义改写但不同主题的假阳性

**派工纪要 v6 §2 复用纪律**:
- 复用 `Knowledge.embedding.cosine_distance` (pgvector 原生)
- 复用 `app.services.auto_research_v2.AutoResearchV2Service.llm_as_judge`
- 复用 `app.services.embedding_service.generate_embedding`

**API 设计 (PR9 新增, 不动 v1)**:
- `async def find_duplicates(title, summary, threshold=0.92, top_k=5) -> List[dict]`
- `async def is_duplicate(title, summary, threshold=0.92) -> Tuple[bool, Optional[int]]`
- `CrossDocDedupService` 类 (依赖 AsyncSession 注入)

**feature flag**: `CROSS_DOC_DEDUP_ENABLED=True` (本服务独立, v2 启用时自动接入)

派工日期：2026-07-30
锚点范式：W95 +4..+7 (4 commits)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import (
    extract_text_from_response,
    get_anthropic_client,
    get_default_model,
    parse_llm_json,
)

logger = logging.getLogger("microbubble.dedup_cross_doc")

# Feature flag — PR9 默认启用（与 v2 绑定, 由 v2 入口 guard 调用）
CROSS_DOC_DEDUP_ENABLED: bool = True

# LLM-as-judge prompt (语义级去重判定)
SEMANTIC_DUP_PROMPT = """你是微纳米气泡课题组的AI知识助手。判断两段知识是否**核心结论重复**（即它们讲同一件事、同一结论）。

## 内容 A

标题: {title_a}
摘要: {summary_a}

## 内容 B

标题: {title_b}
摘要: {summary_b}

## 输出

返回严格的 JSON（不要包含其他文字）：

{{
  "is_duplicate": true,
  "reason": "30 字以内解释（为何是重复 / 为何不是）"
}}

判别标准：
- 同一研究主题 + 同一核心结论 + 同一应用场景 → true
- 仅主题相似但具体结论不同 → false
- 同一数据来源不同表述（如同义改写）→ true"""


class CrossDocDedupService:
    """跨文档去重服务 — pgvector 余弦粗筛 + LLM-as-judge 精判。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _embedding_for(self, title: str, summary: str):
        """生成 (title+summary) 联合 embedding (复用 embedding_service)."""
        from app.services.embedding_service import generate_embedding

        text = f"{title}\n{summary}".strip()
        if not text:
            return None
        return await generate_embedding(text)

    async def find_duplicates(
        self,
        title: str,
        summary: str,
        threshold: float = 0.92,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """找出与 (title, summary) 余弦相似度 ≥ threshold 的 top_k 条已有 knowledge。

        Args:
            title: 待判定标题
            summary: 待判定摘要
            threshold: 余弦相似度阈值 (0~1, 默认 0.92)
            top_k: 返回最多 top_k 条

        Returns:
            List of dicts: [{id, title, summary, similarity}]
            余弦相似度降序排列
        """
        from sqlalchemy import select

        from app.models.knowledge import Knowledge

        emb = await self._embedding_for(title, summary)
        if emb is None:
            return []

        distance_expr = Knowledge.embedding.cosine_distance(emb)
        similarity_expr = 1 - distance_expr

        # 取 threshold 之上的 top_k + 一定 buffer (LLM judge 需要上下文)
        stmt = (
            select(
                Knowledge.id,
                Knowledge.title,
                Knowledge.summary,
                Knowledge.content,
                similarity_expr.label("similarity"),
            )
            .where(Knowledge.embedding.isnot(None))
            .order_by(distance_expr)
            .limit(top_k * 4)  # 4x buffer 让 LLM judge 有更多上下文
        )
        result = await self.db.execute(stmt)
        rows = result.all()

        output: List[Dict[str, Any]] = []
        for row in rows:
            sim = float(row.similarity) if row.similarity is not None else 0.0
            if sim >= threshold:
                output.append(
                    {
                        "id": int(row.id),
                        "title": row.title or "",
                        "summary": (row.summary or row.content or "")[:500],
                        "similarity": round(sim, 4),
                    }
                )
                if len(output) >= top_k:
                    break

        return output

    async def semantic_judge_duplicate(
        self,
        title_a: str,
        summary_a: str,
        title_b: str,
        summary_b: str,
    ) -> Dict[str, Any]:
        """LLM 精判两段是否核心结论重复。

        Returns:
            {"is_duplicate": bool, "reason": str}
        """
        try:
            client = get_anthropic_client()
            prompt = SEMANTIC_DUP_PROMPT.format(
                title_a=title_a,
                summary_a=summary_a[:500],
                title_b=title_b,
                summary_b=summary_b[:500],
            )
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=150,
                timeout=30,
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": prompt}],
            )
            text = extract_text_from_response(response)
            result = parse_llm_json(text)
            return {
                "is_duplicate": bool(result.get("is_duplicate", False)),
                "reason": str(result.get("reason", "")),
            }
        except Exception as e:
            logger.warning(f"semantic_judge_duplicate 失败: {e}")
            # 保守策略：失败默认不是重复（避免误杀新入库）
            return {"is_duplicate": False, "reason": "judge_failed"}

    async def is_duplicate(
        self,
        title: str,
        summary: str,
        threshold: float = 0.92,
        enable_llm_judge: bool = True,
    ) -> Tuple[bool, Optional[int]]:
        """综合判定：余弦粗筛 + LLM 精判。

        Args:
            title: 待判定标题
            summary: 待判定摘要
            threshold: 余弦阈值
            enable_llm_judge: 是否启用 LLM 精判 (PR9 默认 True)

        Returns:
            (is_duplicate, duplicate_of_id)
            - is_duplicate=True, duplicate_of_id=int: 与已有重复
            - is_duplicate=False, duplicate_of_id=None: 不重复
        """
        candidates = await self.find_duplicates(
            title=title, summary=summary, threshold=threshold, top_k=1
        )

        if not candidates:
            return False, None

        if not enable_llm_judge:
            return True, int(candidates[0]["id"])

        # LLM 精判: 取最相似 1 条
        cand = candidates[0]
        judge = await self.semantic_judge_duplicate(
            title_a=title,
            summary_a=summary,
            title_b=cand["title"],
            summary_b=cand["summary"],
        )

        return judge["is_duplicate"], (int(cand["id"]) if judge["is_duplicate"] else None)

    async def batch_dedup_check(
        self,
        items: List[Dict[str, str]],
        threshold: float = 0.92,
    ) -> List[Dict[str, Any]]:
        """批量去重检查 (供未来批量入库用)。

        Args:
            items: [{title, summary}, ...]

        Returns:
            [{title, summary, is_duplicate, duplicate_of_id, candidates}, ...]
        """
        results: List[Dict[str, Any]] = []
        for it in items:
            is_dup, dup_id = await self.is_duplicate(
                title=it.get("title", ""),
                summary=it.get("summary", ""),
                threshold=threshold,
            )
            cands = await self.find_duplicates(
                title=it.get("title", ""),
                summary=it.get("summary", ""),
                threshold=threshold,
                top_k=3,
            )
            results.append(
                {
                    "title": it.get("title", ""),
                    "summary": it.get("summary", ""),
                    "is_duplicate": is_dup,
                    "duplicate_of_id": dup_id,
                    "candidates": cands,
                }
            )
        return results


def get_cross_doc_dedup(db: AsyncSession) -> CrossDocDedupService:
    return CrossDocDedupService(db)

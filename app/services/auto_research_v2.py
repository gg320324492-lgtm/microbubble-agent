"""PR9 / W95 — auto_research_v2 升级版联网 + LLM-as-judge 入库闭环

v1 (auto_research_service.py) 仅按 URL 查重 + LLM 抽取 → 直接入库。
v2 在 v1 `_ingest_knowledge` 后插入 LLM-as-judge 兜底，仅当 judge=relevant+not_duplicate 才入库，
否则只建草稿（不入库，等人工复核）。

**派工纪要 v6 §2 复用纪律**:
- 复用 `app.services.auto_research_service.AutoResearchService` v1 入口 (`research_topic`)
- 复用 `app.services.search_service.search_service.search`
- 复用 `app.services.knowledge_graph_service.KnowledgeGraphService._calc_similarity`
- 复用 `app.services.embedding_service.generate_embedding`
- v2 通过 feature flag `AUTO_RESEARCH_V2_ENABLED` 默认 False 接入，**不破坏 v1 行为**

**LLM-as-judge 决策矩阵**:
| LLM judge | 行为 |
|-----------|------|
| relevant=True + not_duplicate=True | 入库（与 v1 相同） |
| relevant=True + not_duplicate=False | 跳过入库，记录为 duplicate (knowledge_id 引用已有) |
| relevant=False | 跳过入库（与 v1 相同） |
| LLM 调用失败 | **保守策略**: 默认 relevant=False（不入库），记录 warning |

派工日期：2026-07-30
锚点范式：W95 +0..+3 (4 commits)
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.llm import (
    extract_text_from_response,
    get_anthropic_client,
    get_default_model,
    parse_llm_json,
)

logger = logging.getLogger("microbubble.auto_research_v2")

# Feature flag (默认 False — 不破坏 v1 行为)
AUTO_RESEARCH_V2_ENABLED: bool = False

# LLM-as-judge prompt
JUDGE_PROMPT = """你是微纳米气泡课题组的AI知识助手。判断一段待入库知识是否:
1. relevant (是否与本课题组相关)
2. not_duplicate (是否与已有知识不重复)

## 待入库内容

标题: {title}
摘要: {summary}
分类: {category}
标签: {tags}

## 已有知识（最相关的 3 条，用于去重判断）

{candidates}

## 输出

返回严格的 JSON（不要包含其他文字）：

{{
  "relevant": true,
  "not_duplicate": true,
  "reason": "50 字以内的判断理由"
}}

如果待入库内容与已有知识核心结论高度相似（不要求字面相同），not_duplicate=False。"""


class AutoResearchV2Service:
    """v2 自主研究 — v1 基础上加 LLM-as-judge 兜底。

    与 v1 的区别:
    - v1 仅按 URL 去重
    - v2 加内容级 LLM-as-judge，**保守策略**（judge 失败默认不入库）
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def llm_as_judge(
        self,
        title: str,
        summary: str,
        category: str,
        tags: List[str],
        candidate_summaries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """LLM-as-judge：判断 (relevant, not_duplicate)。

        Args:
            title: 待入库标题
            summary: 待入库摘要
            category: 待入库分类
            tags: 待入库标签
            candidate_summaries: 已有 knowledge 候选 (e.g. [{id, title, summary, similarity}], 取 top-3)

        Returns:
            dict with keys: relevant (bool), not_duplicate (bool), reason (str)
            失败时: {"relevant": False, "not_duplicate": True, "reason": "judge_failed"}
        """
        try:
            # 构造候选段（top-3，无候选时为空字符串）
            candidate_text = ""
            for i, c in enumerate(candidate_summaries[:3], 1):
                sim = c.get("similarity", 0.0)
                candidate_text += (
                    f"{i}. [id={c.get('id')}, sim={sim:.3f}] "
                    f"{c.get('title', '')}\n"
                    f"   {c.get('summary', '')[:300]}\n\n"
                )

            client = get_anthropic_client()
            prompt = JUDGE_PROMPT.format(
                title=title,
                summary=summary,
                category=category,
                tags=", ".join(tags) if tags else "",
                candidates=candidate_text or "(无)",
            )
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=200,
                timeout=30,
                thinking={"type": "disabled"},
                messages=[{"role": "user", "content": prompt}],
            )
            text = extract_text_from_response(response)
            result = parse_llm_json(text)
            # 强制类型
            return {
                "relevant": bool(result.get("relevant", False)),
                "not_duplicate": bool(result.get("not_duplicate", True)),
                "reason": str(result.get("reason", "")),
            }
        except Exception as e:
            # 保守策略：失败默认不入库
            logger.warning(f"LLM-as-judge 失败 (title={title!r}): {e}")
            return {
                "relevant": False,
                "not_duplicate": True,
                "reason": "judge_failed",
            }

    async def build_candidates(
        self,
        title: str,
        summary: str,
        top_k: int = 3,
        sim_threshold: float = 0.75,
    ) -> List[Dict[str, Any]]:
        """构建候选集：取 KB 中与 (title+summary) 余弦相似度 ≥ sim_threshold 的 top_k 条。

        用 pgvector cosine_distance 直接 SQL 计算 (knowledge_graph_service._calc_similarity 复用模式)。
        """
        try:
            from sqlalchemy import select

            from app.models.knowledge import Knowledge
            from app.services.embedding_service import generate_embedding

            # 1. embedding (query 侧)
            emb = await generate_embedding(f"{title}\n{summary}")
            if emb is None:
                return []

            # 2. 取最近 N 条 + similarity (pgvector cosine_distance)
            # ORDER BY embedding <=> :emb → cosine_distance, similarity = 1 - distance
            N_FETCH = 20
            distance_expr = Knowledge.embedding.cosine_distance(emb)
            similarity_expr = 1 - distance_expr
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
                .limit(N_FETCH)
            )
            result = await self.db.execute(stmt)
            rows = result.all()

            # 3. 过滤 sim ≥ sim_threshold, 取 top_k
            output: List[Dict[str, Any]] = []
            for row in rows:
                sim = float(row.similarity) if row.similarity is not None else 0.0
                if sim >= sim_threshold:
                    text_summary = (row.summary or row.content or "")[:500]
                    output.append(
                        {
                            "id": int(row.id),
                            "title": row.title or "",
                            "summary": text_summary,
                            "similarity": round(sim, 4),
                        }
                    )
                if len(output) >= top_k:
                    break

            return output
        except Exception as e:
            logger.warning(f"build_candidates 失败 (title={title!r}): {e}")
            return []

    async def evaluate_for_ingest(
        self,
        title: str,
        summary: str,
        category: str,
        tags: List[str],
        sim_threshold: float = 0.75,
    ) -> Dict[str, Any]:
        """v2 主入口：judge + build_candidates 一站式评估。

        Returns:
            dict with keys:
                - should_ingest (bool): True=可入库
                - relevant (bool): LLM 判断相关
                - not_duplicate (bool): LLM 判断不重复
                - reason (str)
                - duplicate_of_id (Optional[int]): 重复时指向已有 knowledge id
                - candidates (List[Dict]): top-3 候选
        """
        candidates = await self.build_candidates(
            title=title, summary=summary, top_k=3, sim_threshold=sim_threshold
        )

        # 短路：候选完全为空 → LLM judge 必为 not_duplicate
        judge = await self.llm_as_judge(
            title=title,
            summary=summary,
            category=category,
            tags=tags,
            candidate_summaries=candidates,
        )

        should_ingest = judge["relevant"] and judge["not_duplicate"]
        duplicate_of_id: Optional[int] = None
        if not judge["not_duplicate"] and candidates:
            # 取最相似候选作 duplicate_of
            duplicate_of_id = int(candidates[0]["id"])

        return {
            "should_ingest": should_ingest,
            "relevant": judge["relevant"],
            "not_duplicate": judge["not_duplicate"],
            "reason": judge["reason"],
            "duplicate_of_id": duplicate_of_id,
            "candidates": candidates,
        }


# 全局工厂（不存 db 状态 — 每次注入）
def get_auto_research_v2(db: AsyncSession) -> AutoResearchV2Service:
    return AutoResearchV2Service(db)


async def run_v2_post_hook(
    auto_research_instance,
    all_results: List[Dict[str, Any]],
    new_count: int,
) -> tuple[List[Dict[str, Any]], int]:
    """v2 后处理钩子 — 在 v1 `research_topic` 末尾调用.

    对 all_results 中 ingested=True 的条目, 用 v2 judge 复核; 拒绝的标 ingested=False
    (不物理删除, 留主指挥人工复核).

    注: flag 守门由调用方 (research_topic) 负责. 本函数假定调用前已 flag=True.

    Args:
        auto_research_instance: AutoResearchService 实例 (需有 .db 属性)
        all_results: v1 已构建的结果列表
        new_count: v1 已计算的 new_count

    Returns:
        (v2_filtered_results, new_count_after_v2)
    """
    from app.models.knowledge import Knowledge  # 懒导入避重

    v2 = get_auto_research_v2(auto_research_instance.db)
    v2_filtered: List[Dict[str, Any]] = []
    for entry in all_results:
        if not entry.get("ingested"):
            v2_filtered.append(entry)
            continue
        kid = entry.get("knowledge_id")
        if kid is None:
            v2_filtered.append(entry)
            continue
        k = await auto_research_instance.db.get(Knowledge, kid)
        if not k:
            v2_filtered.append(entry)
            continue
        eval_result = await v2.evaluate_for_ingest(
            title=k.title or "",
            summary=(k.summary or k.content or "")[:500],
            category=k.category or "",
            tags=list(k.tags or []),
        )
        if eval_result["should_ingest"]:
            v2_filtered.append(entry)
        else:
            logger.warning(
                f"[PR9 v2] judge 拒绝入库 knowledge_id={kid} "
                f"reason={eval_result['reason']!r} dup_of={eval_result['duplicate_of_id']}"
            )
            entry["ingested"] = False
            entry["v2_reason"] = eval_result["reason"]
            entry["v2_duplicate_of_id"] = eval_result["duplicate_of_id"]
            v2_filtered.append(entry)
    new_count_after = sum(1 for e in v2_filtered if e.get("ingested"))
    return v2_filtered, new_count_after

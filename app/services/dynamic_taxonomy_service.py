"""动态分类体系 — 从内容中自然涌现的标签结构"""

import json
import logging
from typing import List, Optional, Dict, Any
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.models.knowledge import Knowledge
from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json, extract_text_from_response

logger = logging.getLogger("microbubble.taxonomy")

CLUSTER_NAMING_PROMPT = """你是一个研究领域分析专家。以下是一组相关的微纳米气泡研究关键词聚类：

{concepts}

请为这个聚类取一个简洁的研究方向名称（10字以内），并给出简要描述。

返回严格的JSON格式（不要包含其他文字）：
{{
  "name": "聚类名称",
  "description": "20字以内的描述"
}}"""


class DynamicTaxonomyService:
    """动态分类体系 — 从实际数据中聚合标签结构"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_emerging_categories(self) -> List[dict]:
        """获取涌现分类结构（基于 key_concepts 聚类）

        返回树状结构:
        [{ "name": "研究方向", "count": 5, "children": [{"name": "子方向", "count": 2}] }]
        """
        # 获取所有 key_concepts 非空的条目
        result = await self.db.execute(
            select(Knowledge.id, Knowledge.key_concepts, Knowledge.category, Knowledge.title)
            .where(Knowledge.key_concepts.isnot(None))
        )
        rows = result.all()

        if not rows:
            return []

        # 按已有 category 聚合（这是最直接的自然分类）
        result = await self.db.execute(
            select(Knowledge.category, func.count(Knowledge.id).label("count"))
            .where(Knowledge.category.isnot(None), Knowledge.category != "")
            .group_by(Knowledge.category)
            .order_by(func.count(Knowledge.id).desc())
        )
        category_counts = {row.category: row.count for row in result.all()}

        # 收集所有 key_concepts 并统计频率
        all_concepts: List[str] = []
        for row in rows:
            if row.key_concepts:
                all_concepts.extend(row.key_concepts)

        concept_freq = Counter(all_concepts)
        hot_concepts = [{"name": k, "count": v} for k, v in concept_freq.most_common(20)]

        # 构建分类树：一级 = category, 二级 = top concepts in that category
        categories = []
        for cat_name, cat_count in category_counts.items():
            # 获取该分类下的热门概念
            cat_result = await self.db.execute(
                select(Knowledge.key_concepts)
                .where(Knowledge.category == cat_name, Knowledge.key_concepts.isnot(None))
            )
            cat_concepts: List[str] = []
            for row in cat_result.all():
                if row.key_concepts:
                    cat_concepts.extend(row.key_concepts)
            cat_freq = Counter(cat_concepts)
            top_sub = [{"name": k, "count": v} for k, v in cat_freq.most_common(5)]

            categories.append({
                "name": cat_name or "未分类",
                "count": cat_count,
                "hot_concepts": top_sub,
            })

        return {
            "categories": categories,
            "hot_concepts": hot_concepts,
            "total": sum(category_counts.values()),
        }

    async def suggest_category(self, knowledge_id: int) -> Optional[str]:
        """基于最相似的已有知识条目建议分类"""
        result = await self.db.execute(
            select(Knowledge).where(Knowledge.id == knowledge_id)
        )
        target = result.scalar_one_or_none()
        # 必须用 is None 不用 not: pgvector embedding 是 numpy 数组,
        # `not numpy_array` 会抛 "truth value ambiguous" (2026-06-28 教训)
        if target is None or target.embedding is None:
            return None

        # 找最相似的有分类的条目
        try:
            stmt = text("""
                SELECT k.id, k.category, 1 - cosine_distance(k.embedding::vector, :emb::vector) AS sim
                FROM knowledge k
                WHERE k.id != :kid AND k.category IS NOT NULL AND k.category != ''
                ORDER BY sim DESC
                LIMIT 1
            """)
            result = await self.db.execute(stmt, {
                "emb": target.embedding,
                "kid": knowledge_id,
            })
            row = result.one_or_none()
            if row and row.sim >= 0.6:
                return row.category
        except Exception as e:
            logger.debug(f"分类建议查询失败: {e}")

        return None

    async def generate_category_report(self) -> str:
        """生成分类体系报告（用于展示）"""
        data = await self.get_emerging_categories()
        categories = data.get("categories", [])
        hot = data.get("hot_concepts", [])

        if not categories:
            return "知识库暂无足够数据生成分类报告。"

        lines = [
            "## 📊 知识库动态分类报告\n",
            f"**总条目**: {data['total']}",
            f"**活跃分类**: {len(categories)} 个\n",
            "### 分类分布",
        ]

        for cat in categories:
            concepts_str = ", ".join(c["name"] for c in cat.get("hot_concepts", [])[:3])
            lines.append(f"- **{cat['name']}** ({cat['count']}条)  {concepts_str}")

        if hot:
            lines.append("\n### 热门概念 Top 10")
            for i, c in enumerate(hot[:10], 1):
                lines.append(f"  {i}. {c['name']} ({c['count']}次)")

        return "\n".join(lines)

    async def get_theme_network(self) -> List[dict]:
        """获取主题关联网络（基于共享概念的分类间关联）"""
        # 获取所有分类及其key_concepts
        result = await self.db.execute(
            select(Knowledge.category, Knowledge.key_concepts)
            .where(Knowledge.category.isnot(None), Knowledge.category != "",
                   Knowledge.key_concepts.isnot(None))
        )
        rows = result.all()

        # 以分类为单位聚合概念
        cat_concepts: Dict[str, set] = {}
        for row in rows:
            if row.category not in cat_concepts:
                cat_concepts[row.category] = set()
            if row.key_concepts:
                cat_concepts[row.category].update(row.key_concepts)

        # 计算分类间概念重叠（Jaccard 相似度）
        links = []
        cat_names = list(cat_concepts.keys())
        for i in range(len(cat_names)):
            for j in range(i + 1, len(cat_names)):
                a, b = cat_concepts[cat_names[i]], cat_concepts[cat_names[j]]
                if not a or not b:
                    continue
                intersection = a & b
                union = a | b
                if union:
                    jaccard = len(intersection) / len(union)
                    if jaccard > 0.1:  # 阈值
                        links.append({
                            "source": cat_names[i],
                            "target": cat_names[j],
                            "overlap": list(intersection),
                            "strength": round(jaccard, 3),
                        })

        return sorted(links, key=lambda x: x["strength"], reverse=True)


dynamic_taxonomy_service = DynamicTaxonomyService

"""自主研究引擎 — 检测知识空白，自动搜索网络知识补充知识库"""

import json
import logging
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.models.knowledge import Knowledge, KnowledgeRelation
from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json, extract_text_from_response
from app.services.search_service import search_service

logger = logging.getLogger("microbubble.auto_research")

EXTRACT_PROMPT = """你是微纳米气泡课题组的AI知识助手。请从以下网页内容中提取与研究相关的核心知识。

## 网页信息

标题: {title}
来源: {url}
摘要: {snippet}

## 网页正文

{content}

## 提取要求

提取与该课题组研究方向（微纳米气泡在环保/农业/医疗等领域的应用）相关的核心知识。
如果内容无关，返回 {{"relevant": false}}。

返回严格的JSON格式（不要包含其他文字）：

{{
  "relevant": true,
  "summary": "200字以内的中文摘要，抓住核心发现和方法",
  "category": "根据内容自定具体分类",
  "tags": ["3-6个关键技术术语"],
  "key_findings": ["2-4个关键发现或数据"],
  "knowledge_type": "文献阅读/研究报告/技术方案/案例分析/新闻资讯"
}}"""

GAP_ANALYSIS_PROMPT = """你是微纳米气泡课题组的AI知识管理助手。分析当前知识库的主题分布，找出薄弱领域。

## 当前知识库统计

{stats}

## 分析要求

1. 识别哪些研究方向覆盖不足（条目少、无关联）
2. 针对每个薄弱领域生成搜索查询
3. 返回可操作的搜索策略

返回严格的JSON格式（不要包含其他文字）：

{{
  "weak_areas": [
    {{
      "area": "薄弱领域名称",
      "reason": "为什么薄弱",
      "queries": ["搜索查询1", "搜索查询2"]
    }}
  ],
  "strong_areas": ["覆盖良好的领域列表"],
  "total_queries": ["所有需要搜索的查询汇总"]
}}"""


class AutoResearchService:
    """自主研究引擎 — 检测知识空白并自动补充"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def research_topic(
        self,
        queries: List[str],
        max_results_per_query: int = 3,
    ) -> dict:
        """对一个或多个查询执行自主研究

        流程:
        1. 对每个查询执行联网搜索（搜狗+必应）
        2. 对搜索结果提取核心知识
        3. 去重（与已有知识库对比）
        4. 入库并建立关联
        """
        all_results = []
        new_count = 0

        for query in queries:
            logger.info(f"自主研究: {query}")
            search_result = await search_service.search(query, max_results=max_results_per_query)
            raw_results = search_result.get("results", [])

            for item in raw_results:
                # 检查是否已存在相同来源的知识
                if await self._exists_by_source(item["url"]):
                    all_results.append({
                        "title": item["title"],
                        "url": item["url"],
                        "snippet": item.get("snippet", ""),
                        "ingested": False,
                        "knowledge_id": None,
                    })
                    continue

                # 提取核心知识
                extracted = await self._extract_knowledge(
                    title=item["title"],
                    url=item["url"],
                    snippet=item.get("snippet", ""),
                )

                if not extracted.get("relevant"):
                    all_results.append({
                        "title": item["title"],
                        "url": item["url"],
                        "snippet": item.get("snippet", ""),
                        "ingested": False,
                        "knowledge_id": None,
                    })
                    continue

                # 入库
                knowledge = await self._ingest_knowledge(
                    title=item["title"],
                    content=extracted.get("summary", ""),
                    category=extracted.get("category", ""),
                    tags=extracted.get("tags", []),
                    source=item["url"],
                    source_type="auto_research",
                    key_findings=extracted.get("key_findings", []),
                    knowledge_type=extracted.get("knowledge_type", "研究报告"),
                )

                new_count += 1
                all_results.append({
                    "title": item["title"],
                    "url": item["url"],
                    "snippet": item.get("snippet", ""),
                    "ingested": True,
                    "knowledge_id": knowledge.id,
                })

            logger.info(f"查询 '{query}' 完成，新增 {new_count} 条知识")

        return {
            "query": queries[0] if queries else "",
            "results": all_results,
            "new_knowledge_count": new_count,
            "message": f"研究完成，新增 {new_count} 条知识",
        }

    async def fill_knowledge_gaps(self) -> dict:
        """分析知识库薄弱领域并触发定向研究"""
        # 收集统计信息
        stats = await self._collect_stats()

        # LLM 分析薄弱领域
        gap_analysis = await self._analyze_gaps(stats)
        weak_areas = gap_analysis.get("weak_areas", [])
        total_queries = gap_analysis.get("total_queries", [])

        if not total_queries:
            return {
                "weak_areas": [],
                "new_knowledge_count": 0,
                "message": "知识库覆盖良好，无需补充",
            }

        # 对每个薄弱领域执行研究
        total_new = 0
        for query in total_queries[:10]:  # 单次最多10个查询
            try:
                result = await self.research_topic(queries=[query], max_results_per_query=2)
                total_new += result["new_knowledge_count"]
            except Exception as e:
                logger.warning(f"领域研究失败 ({query}): {e}")

        return {
            "weak_areas": weak_areas,
            "new_knowledge_count": total_new,
            "message": f"知识空白补充完成，新增 {total_new} 条知识",
        }

    async def detect_and_handle_contradictions(self) -> List[dict]:
        """检测矛盾：高分相似但内容可能矛盾的条目对"""
        contradictions = []

        # 找出相似度 > 0.8 的关联且 relation_type='similar' 的条目对
        stmt = select(KnowledgeRelation).where(
            KnowledgeRelation.relation_type == "similar",
            KnowledgeRelation.score >= 0.8,
        )
        result = await self.db.execute(stmt)
        relations = result.scalars().all()

        for rel in relations:
            # 获取两个条目内容
            a = await self.db.get(Knowledge, rel.source_id)
            b = await self.db.get(Knowledge, rel.target_id)
            if not a or not b:
                continue

            # 用 LLM 快速判断是否矛盾
            is_conflict = await self._check_contradiction(a.title, a.content, b.title, b.content)
            if is_conflict:
                contradictions.append({
                    "source_id": rel.source_id,
                    "target_id": rel.target_id,
                    "source_title": a.title,
                    "target_title": b.title,
                    "relation_id": rel.id,
                })
                logger.warning(f"检测到可能矛盾: [{a.title}] ↔ [{b.title}]")

        return contradictions

    async def detect_duplicates(self, threshold: float = 0.92) -> List[dict]:
        """检测重复条目（语义相似度 > 阈值的条目对）"""
        duplicates = []

        # 获取所有有 embedding 的条目
        result = await self.db.execute(
            select(Knowledge).where(Knowledge.embedding.isnot(None))
        )
        all_knowledge = result.scalars().all()

        # 两两比较（避免重复比较）
        for i in range(len(all_knowledge)):
            for j in range(i + 1, len(all_knowledge)):
                a, b = all_knowledge[i], all_knowledge[j]
                if a.embedding is None or b.embedding is None:
                    continue

                try:
                    from app.services.knowledge_graph_service import KnowledgeGraphService
                    kg_svc = KnowledgeGraphService(self.db)
                    sim = await kg_svc._calc_similarity(a, b)
                    if sim and sim >= threshold:
                        duplicates.append({
                            "id_a": a.id,
                            "id_b": b.id,
                            "title_a": a.title,
                            "title_b": b.title,
                            "similarity": round(sim, 4),
                        })
                except Exception:
                    continue

        return duplicates

    async def detect_staleness(self, days: int = 365) -> List[dict]:
        """检测可能过期的条目（超过指定天数未更新）"""
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)

        stmt = select(Knowledge).where(
            Knowledge.updated_at < cutoff,
            Knowledge.source_type != "auto_research",  # 自动研究的本身可能已是最新
        ).order_by(Knowledge.updated_at.asc())

        result = await self.db.execute(stmt)
        stale = result.scalars().all()

        return [
            {
                "id": k.id,
                "title": k.title,
                "category": k.category,
                "source_type": k.source_type,
                "updated_at": k.updated_at.isoformat() if k.updated_at else None,
                "days_since_update": (datetime.utcnow() - k.updated_at).days if k.updated_at else None,
            }
            for k in stale
        ]

    # ── 内部方法 ──

    async def _exists_by_source(self, url: str) -> bool:
        """检查URL是否已入库"""
        result = await self.db.execute(
            select(Knowledge.id).where(Knowledge.source == url).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _extract_knowledge(self, title: str, url: str, snippet: str) -> dict:
        """从网页内容提取核心知识"""
        try:
            # 尝试获取完整页面内容
            full_content = snippet
            try:
                import httpx
                headers = {
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/125.0.0.0 Safari/537.36"
                    )
                }
                async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        import re
                        text = resp.text
                        # 简单提取正文文本
                        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
                        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
                        text = re.sub(r'<[^>]+>', '', text)
                        text = re.sub(r'\s+', ' ', text).strip()
                        full_content = text[:3000]  # 限制长度
            except Exception as e:
                logger.debug(f"获取页面内容失败 {url}: {e}")

            client = get_anthropic_client()
            prompt = EXTRACT_PROMPT.format(
                title=title,
                url=url,
                snippet=snippet,
                content=full_content,
            )
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=800,
                timeout=30,
                thinking={'type': 'disabled'},
                messages=[{"role": "user", "content": prompt}],
            )
            text = extract_text_from_response(response)
            result = parse_llm_json(text)
            return result
        except Exception as e:
            logger.warning(f"知识提取失败 ({title}): {e}")
            return {"relevant": False}

    async def _ingest_knowledge(
        self,
        title: str,
        content: str,
        category: str,
        tags: List[str],
        source: str,
        source_type: str,
        key_findings: List[str],
        knowledge_type: str,
    ) -> Knowledge:
        """将提取的知识入库"""
        knowledge = Knowledge(
            title=title[:200],
            content=content,
            category=category[:100] if category else None,
            tags=tags,
            source=source[:500] if source else None,
            source_type=source_type,
            created_by=None,  # 系统自动创建
            auto_researched=True,
            analysis_status="done",
            key_concepts=key_findings,
            knowledge_type=knowledge_type[:50] if knowledge_type else None,
        )
        self.db.add(knowledge)
        await self.db.commit()
        await self.db.refresh(knowledge)

        # 后台建立关联
        try:
            from app.services.knowledge_graph_service import KnowledgeGraphService
            graph_svc = KnowledgeGraphService(self.db)
            await graph_svc.build_relations_for(knowledge.id)
        except Exception as e:
            logger.warning(f"自动研究条目关联失败(knowledge_id={knowledge.id}): {e}")

        return knowledge

    async def _collect_stats(self) -> str:
        """收集知识库统计信息，用于薄弱分析"""
        # 总数
        result = await self.db.execute(select(func.count(Knowledge.id)))
        total = result.scalar() or 0

        # 分类分布
        result = await self.db.execute(
            select(Knowledge.category, func.count(Knowledge.id).label("count"))
            .where(Knowledge.category.isnot(None), Knowledge.category != "")
            .group_by(Knowledge.category)
            .order_by(func.count(Knowledge.id).desc())
        )
        categories = {row.category: row.count for row in result.all()}

        # 标签频率（取 top 20）
        result = await self.db.execute(
            select(func.unnest(Knowledge.tags).label("tag"),
                   func.count().label("freq"))
            .where(Knowledge.tags.isnot(None))
            .group_by(func.unnest(Knowledge.tags))
            .order_by(func.count().desc())
            .limit(20)
        )
        tags = [row.tag for row in result.all()]

        # 知识类型分布
        result = await self.db.execute(
            select(Knowledge.knowledge_type, func.count(Knowledge.id).label("count"))
            .where(Knowledge.knowledge_type.isnot(None))
            .group_by(Knowledge.knowledge_type)
        )
        types = {row.knowledge_type: row.count for row in result.all()}

        # 关联数
        result = await self.db.execute(select(func.count(KnowledgeRelation.id)))
        relation_count = result.scalar() or 0

        return json.dumps({
            "total_entries": total,
            "categories": categories,
            "top_tags": tags,
            "knowledge_types": types,
            "total_relations": relation_count,
        }, ensure_ascii=False, indent=2)

    async def _analyze_gaps(self, stats: str) -> dict:
        """LLM 分析知识库薄弱领域"""
        try:
            client = get_anthropic_client()
            prompt = GAP_ANALYSIS_PROMPT.format(stats=stats)
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=1000,
                timeout=30,
                thinking={'type': 'disabled'},
                messages=[{"role": "user", "content": prompt}],
            )
            text = extract_text_from_response(response)
            return parse_llm_json(text)
        except Exception as e:
            logger.error(f"知识空白分析失败: {e}")
            return {"weak_areas": [], "strong_areas": [], "total_queries": []}

    async def _check_contradiction(self, title_a: str, content_a: str,
                                    title_b: str, content_b: str) -> bool:
        """用 LLM 判断两篇内容是否矛盾"""
        try:
            client = get_anthropic_client()
            prompt = f"""判断以下两篇内容是否存在矛盾或冲突。

内容A: {title_a}
{content_a[:1000]}

内容B: {title_b}
{content_b[:1000]}

仅回答 true（存在矛盾）或 false（不存在矛盾），不要包含其他文字。"""
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=10,
                timeout=30,
                thinking={'type': 'disabled'},
                messages=[{"role": "user", "content": prompt}],
            )
            text = extract_text_from_response(response)
            return "true" in text.lower()
        except Exception as e:
            logger.debug(f"矛盾检测失败: {e}")
            return False


auto_research_service = AutoResearchService

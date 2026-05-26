"""RAG 问答引擎 — 基于知识库内容合成答案，附带来源引用"""

import json
import logging
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.knowledge import Knowledge, KnowledgeGap
from app.core.llm import get_anthropic_client, get_default_model, parse_llm_json, extract_text_from_response

logger = logging.getLogger("microbubble.knowledge_qa")

RAG_PROMPT = """你是微纳米气泡课题组的AI知识助手。请基于以下知识库内容回答用户问题。

## 知识库检索结果（按相关性排序）

{context}

## 回答要求

1. 优先使用检索到的知识库内容回答，不要凭记忆猜测
2. 综合多个来源的信息，给出完整的答案
3. 如果知识库信息不完整，明确指出哪些部分需要进一步研究
4. 在答案末尾列出引用的知识条目来源
5. 如果知识库内容不足以回答问题，明确说明

## 用户问题

{question}

## 你的回答（返回严格的JSON格式，不要包含其他文字）

{{
  "answer": "完整回答，引用格式为[来源:条目标题]",
  "sources": [{{"id": 1, "title": "条目标题", "relevance": 0.85}}],
  "confidence": "high/medium/low",
  "need_research": false,
  "research_queries": []
}}"""

RESEARCH_QUERY_PROMPT = """根据用户问题 "{question}" 和知识库已有内容，分析知识库的不足，
生成3-5个搜索查询，用于在网络上查找补充知识。查询应该：
1. 涵盖问题的不同方面
2. 包含具体的技术术语
3. 适合学术搜索引擎

返回严格的JSON格式（不要包含其他文字）：
["查询1", "查询2", "查询3", "查询4"]"""


class KnowledgeQAService:
    """RAG 问答引擎 — 基于知识库合成答案"""

    HIGH_CONFIDENCE_THRESHOLD = 0.7
    MEDIUM_CONFIDENCE_THRESHOLD = 0.4

    def __init__(self, db: AsyncSession):
        self.db = db

    async def answer_question(
        self,
        question: str,
        top_k: int = 8,
        auto_research: bool = True,
    ) -> dict:
        """回答知识库问题

        流程:
        1. 语义/关键词搜索知识库 → 获取 top_k 相关条目
        2. 按相关性阈值分类
        3. 如果触发研究条件 → 生成研究查询
        4. 构建 RAG prompt → LLM 合成答案
        5. 返回结构化结果
        """
        # Step 1: 检索知识库
        search_results = await self._search_knowledge_base(question, top_k)

        # Step 2: 按阈值分类
        high_quality = [r for r in search_results if r.get("score", 0) >= self.HIGH_CONFIDENCE_THRESHOLD]
        medium_quality = [r for r in search_results if self.MEDIUM_CONFIDENCE_THRESHOLD <= r.get("score", 0) < self.HIGH_CONFIDENCE_THRESHOLD]
        low_quality = [r for r in search_results if r.get("score", 0) < self.MEDIUM_CONFIDENCE_THRESHOLD]

        # Step 3: 判定是否需要研究
        need_research = auto_research and len(high_quality) < 2

        research_queries = []
        if need_research and not search_results:
            # 完全无结果时生成研究查询
            research_queries = await self._generate_research_queries(question)

        # Step 4: 构建 RAG prompt 并合成答案
        context_parts = []
        for i, r in enumerate(search_results, 1):
            label = "【高相关】" if r.get("score", 0) >= self.HIGH_CONFIDENCE_THRESHOLD else \
                    "【中相关】" if r.get("score", 0) >= self.MEDIUM_CONFIDENCE_THRESHOLD else \
                    "【低相关】"
            context_parts.append(
                f"{i}. {label}\n"
                f"   标题: {r['title']}\n"
                f"   摘要: {r.get('summary') or r['content'][:200]}\n"
                f"   分类: {r.get('category', '未分类')}\n"
                f"   相关性: {r.get('score', 0):.2%}\n"
            )
        context_str = "\n---\n".join(context_parts) if context_parts else "知识库中暂无相关内容。"

        answer_data = await self._llm_synthesize(question, context_str)

        confidence = answer_data.get("confidence", "low")

        # Step 5: 低置信度时自动触发研究 + 持久化空白
        if confidence == "low" and auto_research:
            try:
                gap = KnowledgeGap(
                    query=question,
                    area=high_quality[0].get("category") if high_quality else None,
                )
                self.db.add(gap)
                await self.db.commit()
                await self.db.refresh(gap)
                logger.info(f"知识空白已记录(gap_id={gap.id}): {question[:50]}")

                # 异步触发自主研究
                import asyncio
                from app.services.auto_research_service import AutoResearchService
                asyncio.create_task(
                    AutoResearchService(self.db).research_topic(
                        queries=research_queries[:3] if research_queries else [question],
                        max_results_per_query=2,
                    )
                )
                research_queries = research_queries or [question]
            except Exception as e:
                logger.warning(f"知识空白处理失败: {e}")

        # Step 6: 组装结果
        return {
            "answer": answer_data.get("answer", ""),
            "sources": answer_data.get("sources", []),
            "confidence": confidence,
            "research_triggered": need_research or confidence == "low",
            "research_queries": research_queries,
            "search_results": {
                "high": len(high_quality),
                "medium": len(medium_quality),
                "low": len(low_quality),
                "total": len(search_results),
            },
        }

    async def _search_knowledge_base(self, question: str, top_k: int) -> List[dict]:
        """搜索知识库，优先语义搜索，回退关键词搜索"""
        try:
            # 优先使用语义搜索
            from app.services.knowledge_service import KnowledgeService
            svc = KnowledgeService(self.db)
            results = await svc.search_semantic(query=question, top_k=top_k)
            if results:
                return results
        except Exception as e:
            logger.debug(f"语义搜索失败，回退关键词: {e}")

        # 关键词搜索回退
        return await self._keyword_search(question, top_k)

    async def _keyword_search(self, question: str, top_k: int) -> List[dict]:
        """关键词搜索"""
        from sqlalchemy import or_
        stmt = select(Knowledge).where(or_(
            Knowledge.title.ilike(f"%{question}%"),
            Knowledge.content.ilike(f"%{question}%")
        )).limit(top_k)
        result = await self.db.execute(stmt)
        rows = result.scalars().all()
        return [
            {
                "id": r.id,
                "title": r.title,
                "content": r.content[:500],
                "summary": r.summary,
                "category": r.category,
                "tags": r.tags,
                "source": r.source,
                "score": 0.5,
            }
            for r in rows
        ]

    async def _llm_synthesize(self, question: str, context: str) -> dict:
        """调用 LLM 基于检索结果合成答案"""
        try:
            client = get_anthropic_client()
            prompt = RAG_PROMPT.format(question=question, context=context)
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=1500,
                timeout=30,
                thinking={'type': 'disabled'},
                messages=[{"role": "user", "content": prompt}],
            )
            text = extract_text_from_response(response)
            result = parse_llm_json(text)

            # 验证必要字段
            if not result.get("answer"):
                result["answer"] = "抱歉，我暂时无法基于现有知识库回答这个问题。"
            if not result.get("sources"):
                result["sources"] = []
            if not result.get("confidence"):
                result["confidence"] = "low"

            return result
        except json.JSONDecodeError as e:
            logger.warning(f"LLM 合成答案返回非 JSON: {e}")
            return {
                "answer": "抱歉，答案合成时出现格式错误，请稍后重试。",
                "sources": [],
                "confidence": "low",
            }
        except Exception as e:
            logger.error(f"LLM 合成答案失败: {e}")
            return {
                "answer": "抱歉，答案合成服务暂时不可用，请稍后重试。",
                "sources": [],
                "confidence": "low",
            }

    async def _generate_research_queries(self, question: str) -> List[str]:
        """生成联网搜索查询，用于补充知识库不足"""
        try:
            client = get_anthropic_client()
            prompt = RESEARCH_QUERY_PROMPT.format(question=question)
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=500,
                timeout=30,
                thinking={'type': 'disabled'},
                messages=[{"role": "user", "content": prompt}],
            )
            text = extract_text_from_response(response)
            queries = parse_llm_json(text)
            if isinstance(queries, list):
                return queries[:5]
            return []
        except Exception as e:
            logger.warning(f"生成研究查询失败: {e}")
            return []

    async def get_related_knowledge_ids(self, question: str, limit: int = 5) -> List[int]:
        """获取与问题相关的知识条目 ID（用于推荐阅读）"""
        results = await self._search_knowledge_base(question, limit)
        return [r["id"] for r in results if r.get("score", 0) >= self.MEDIUM_CONFIDENCE_THRESHOLD]

    async def reason(self, question: str, max_hops: int = 2, top_k: int = 6) -> dict:
        """多跳推理问答 — 遍历知识图谱关联链，LLM 合成推理路径

        流程:
        1. 语义搜索 → top_k 种子文档（第1跳）
        2. 对每个种子 → 查询 get_related() → 关联文档（第2跳）
        3. 对第2跳结果 → 可选查询更深关联（第3跳）
        4. 构建推理链文本 → LLM 合成带推理路径的答案
        """
        from app.services.knowledge_graph_service import KnowledgeGraphService

        # Step 1: 种子文档
        seed_results = await self._search_knowledge_base(question, top_k)
        if not seed_results:
            return {
                "answer": "知识库中未找到相关信息，无法进行推理。",
                "reasoning_chain": [],
                "confidence": "low",
                "hops_used": 0,
            }

        graph_svc = KnowledgeGraphService(self.db)
        visited = set()
        chain_nodes = {}  # {id: {title, summary, hop}}

        # Step 2: BFS 多跳遍历
        for seed in seed_results[:top_k]:
            sid = seed["id"]
            if sid in visited:
                continue
            visited.add(sid)
            chain_nodes[sid] = {
                "title": seed.get("title", ""),
                "summary": seed.get("summary") or seed.get("content", "")[:200],
                "hop": 0,
            }

            if max_hops >= 1:
                related = await graph_svc.get_related(sid, limit=5)
                for rel in related:
                    rid = rel["id"]
                    if rid not in visited:
                        visited.add(rid)
                        chain_nodes[rid] = {
                            "title": rel.get("title", ""),
                            "summary": rel.get("summary", "")[:200],
                            "hop": 1,
                            "relation_from": rel.get("relation_type", "similar"),
                            "relation_score": rel.get("score", 0),
                            "from_node": sid,
                        }

                        if max_hops >= 2:
                            deeper = await graph_svc.get_related(rid, limit=3)
                            for drel in deeper:
                                did = drel["id"]
                                if did not in visited and did not in {s["id"] for s in seed_results}:
                                    visited.add(did)
                                    chain_nodes[did] = {
                                        "title": drel.get("title", ""),
                                        "summary": drel.get("summary", "")[:200],
                                        "hop": 2,
                                        "relation_from": drel.get("relation_type", "similar"),
                                        "from_node": rid,
                                    }

        if len(chain_nodes) <= 1:
            # 只有一个节点，降级为普通 RAG
            return await self.answer_question(question, top_k=top_k, auto_research=False)

        # Step 3: 构建推理链文本
        chain_texts = []
        for nid, node in sorted(chain_nodes.items(), key=lambda x: x[1]["hop"]):
            hop_label = ["种子", "关联", "深层关联"][min(node.get("hop", 0), 2)]
            if node.get("hop", 0) > 0:
                from_title = chain_nodes.get(node.get("from_node", 0), {}).get("title", "?")
                rel_type = node.get("relation_from", "similar")
                chain_texts.append(
                    f"[{hop_label}] {node['title']}\n"
                    f"  ↑ [{rel_type}] ← {from_title}\n"
                    f"  摘要: {node['summary']}"
                )
            else:
                chain_texts.append(
                    f"[{hop_label}] {node['title']}\n"
                    f"  摘要: {node['summary']}"
                )

        # Step 4: LLM 推理合成
        prompt = f"""你是一个知识推理助手。基于以下知识图谱推理链回答用户问题。

## 推理链（从种子文档到深层关联，共{len(chain_nodes)}个节点）

{chr(10).join(chain_texts)}

## 用户问题

{question}

## 回答要求

1. 明确展示推理路径：从哪条知识出发 → 经过什么关联 → 得出什么结论
2. 如果推理链有断点（缺少关键关联），明确指出
3. 给出结论的置信度（high/medium/low）

返回严格的JSON格式（不要其他文字）：
{{{{
  "answer": "完整推理回答，包含推理步骤",
  "reasoning_chain": ["步骤1: 从...出发", "步骤2: 通过...关联发现", "步骤3: 综合得出..."],
  "confidence": "medium",
  "gap_description": "推理链中缺失的关键信息（如有）"
}}}}"""

        try:
            client = get_anthropic_client()
            response = await client.messages.create(
                model=get_default_model(),
                max_tokens=1500,
                timeout=30,
                thinking={'type': 'disabled'},
                messages=[{"role": "user", "content": prompt}],
            )
            text = extract_text_from_response(response)
            result = parse_llm_json(text)

            return {
                "answer": result.get("answer", ""),
                "reasoning_chain": result.get("reasoning_chain", []),
                "confidence": result.get("confidence", "low"),
                "gap_description": result.get("gap_description", ""),
                "hops_used": max(node.get("hop", 0) for node in chain_nodes.values()),
                "nodes_used": len(chain_nodes),
            }
        except Exception as e:
            logger.error(f"多跳推理失败: {e}")
            return {
                "answer": "推理引擎暂时不可用，请稍后重试。",
                "reasoning_chain": [],
                "confidence": "low",
                "gap_description": str(e),
                "hops_used": 0,
            }


knowledge_qa_service = KnowledgeQAService

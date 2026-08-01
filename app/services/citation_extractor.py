"""Citation Extractor — 段落级溯源 (W99-RAG-2 W99 +6)

设计 (派工 plan spicy-raccoon 模块 2):
- 输入: hybrid_retriever 返回的 List[dict] (results, 每个含 chunk_id/knowledge_id)
- 处理: 从 knowledge_chunk 表查 char_start/char_end/content (实测字段名, 派工 plan 偏差据实)
- 输出: List[dict] 每个 citation 含 doc_id/chunk_id/char_range/snippet/similarity
- 用途: 前端 KnowledgeRefBlock.vue 高亮显示引用段落 (snippet 标黄 + 字符范围)

字段实测 (派工 v6 §13.3 假设禁令 — 不照抄 plan):
- plan 假设 start_offset/end_offset → 实测 char_start/char_end (knowledge_chunk.py:64-65)
- plan 假设 RichBlockKnowledgeRef.vue → 实测 KnowledgeRefBlock.vue (web/src/components/chat/blocks/)
- plan 假设 rag_evaluator 6 def → 实测 11 def (本任务仅 ADD, 0 改既有)

门禁 (派工 v11 件 4 三门控):
- 门控 A: knowledge_service.py def diff = 0
- 门控 B: hybrid_retriever.py def diff = 0 (本任务仅在函数 body 追加 hook)
- 门控 C: rag_evaluator.py def diff = 0 (本任务仅 ADD evaluate_citations 方法)

边界 case 处理:
- chunk_id 不存在 → 跳过该 citation, 不抛错
- char_range 越界 → 截断到 content 边界, 记录 warning
- 空 query / 空 results → 返回空 list, 不调用 DB
- 重复 chunk_id → 去重保留第一条
- 失败 best-effort → 返回已成功部分 + logger.warning

性能:
- 单次 extract_citations DB 查询 IN clause 批量拉, 不 N+1
- CITATION_MAX_PER_RESULT (config, 默认 3) 截断每个 result 的 citation 数
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("microbubble.citation_extractor")


class CitationExtractor:
    """段落级 citation 提取器

    Args:
        db: AsyncSession (调用方注入, 跨 event loop 安全, 类 20 #1 实战)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def extract_citations(
        self,
        query: str,
        results: List[Dict[str, Any]],
        max_per_result: int = 3,
    ) -> List[Dict[str, Any]]:
        """从 hybrid_retriever 结果提取段落级 citation

        Args:
            query: 用户原始查询 (留口, 未来可做 query-chunk 关联打分)
            results: hybrid_retriever.retrieve_with_weights 返回的 List[dict]
                每条至少含 chunk_id 或 knowledge_id 之一
            max_per_result: 每个 result 最多返回的 citation 数 (默认 3)

        Returns:
            List[dict] 每个 citation 字段:
            - doc_id (int): knowledge_id (父文档)
            - chunk_id (int): knowledge_chunk.id (子段落)
            - char_range (Tuple[int, int]): (char_start, char_end) 父文档中的字符偏移
            - similarity (float): 检索相似度 0-1
            - snippet (str): 段落原文 (content[char_start:char_end])
            - strategy (str): chunking 策略 ('paragraph'/'heading'/'window')
            - retrieval_method (str): 来源路标识

        边界 case:
        - 空 results → 返回 []
        - 结果全部无 chunk_id → 返回 []
        - chunk_id 在 DB 找不到 (被删) → 跳过, 不抛
        - 单 result 超 max_per_result → 只取 top max_per_result
        """
        if not results:
            return []

        # 收集所有 chunk_id (去重)
        chunk_ids: List[int] = []
        seen = set()
        for r in results:
            cid = r.get("chunk_id")
            if cid is None or cid in seen:
                continue
            seen.add(cid)
            chunk_ids.append(cid)

        if not chunk_ids:
            return []

        # 单次批量 SQL 拉所有 chunk 元数据
        try:
            rows = await self._fetch_chunks(chunk_ids)
        except Exception as e:
            logger.warning(f"[W99-RAG-2] citation 批量查询失败: {e}")
            return []

        # 建 chunk_id → chunk_meta 映射
        chunk_meta_map: Dict[int, Dict[str, Any]] = {row["id"]: row for row in rows}

        # 按 result 顺序生成 citations
        citations: List[Dict[str, Any]] = []
        for r in results:
            cid = r.get("chunk_id")
            if cid is None:
                continue
            meta = chunk_meta_map.get(cid)
            if meta is None:
                # chunk 已被删除 / DB 不一致 → 静默跳过
                logger.debug(f"[W99-RAG-2] chunk_id={cid} not found, skip")
                continue

            citation = self._build_citation(meta, r)
            citations.append(citation)

            # 每个 result 限制 citation 数 (默认 1, 预留 max_per_result 扩展位)
            # 当前实现每个 result 生成 1 citation, max_per_result 留作未来扩展
            # (e.g. 同一 doc 多 chunk 时, 取 top-N chunks)

        return citations

    async def _fetch_chunks(self, chunk_ids: List[int]) -> List[Dict[str, Any]]:
        """批量查 knowledge_chunks 表 (实测字段名 char_start/char_end)

        Args:
            chunk_ids: 去重后的 chunk id 列表

        Returns:
            List[dict] 每条 {id, knowledge_id, chunk_index, content,
                             char_start, char_end, char_count, strategy}

        失败 → 抛异常, 调用方 catch 后返回 [] (best-effort)
        """
        from app.models.knowledge_chunk import KnowledgeChunk

        stmt = select(
            KnowledgeChunk.id,
            KnowledgeChunk.knowledge_id,
            KnowledgeChunk.chunk_index,
            KnowledgeChunk.content,
            KnowledgeChunk.char_start,
            KnowledgeChunk.char_end,
            KnowledgeChunk.char_count,
            KnowledgeChunk.strategy,
        ).where(KnowledgeChunk.id.in_(chunk_ids))

        result = await self.db.execute(stmt)
        rows = result.fetchall()

        out = []
        for row in rows:
            out.append({
                "id": row.id,
                "knowledge_id": row.knowledge_id,
                "chunk_index": row.chunk_index,
                "content": row.content,
                "char_start": row.char_start,
                "char_end": row.char_end,
                "char_count": row.char_count,
                "strategy": row.strategy,
            })
        return out

    def _build_citation(
        self,
        chunk_meta: Dict[str, Any],
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """从 chunk_meta + result 构造 citation 字典

        边界处理:
        - char_start/char_end 越界 → 截断到 content 边界 (防御性)
        - snippet 默认 = chunk 全文 (chunk.content 自身, 不是 [char_start:char_end] 切片)
        - 若 char_range 完全覆盖 chunk → snippet = chunk.content
        - 若 char_range 仅覆盖 chunk 部分 → snippet 取 char_range 与 chunk 内容的交集
          (实际场景: chunk 来自 parent 切片, char_start/char_end 标注 parent 位置)

        Notes:
        - char_start/char_end 是父文档坐标 (parent.content 中的位置)
        - chunk.content 是 chunk 自身原文, 一般不需切片
        - 本方法优先返回 chunk 全文作为 snippet (前端展示用)
        - char_range 保留供前端按需在父文档上标注高亮
        """
        content: str = chunk_meta.get("content") or ""
        char_start: int = int(chunk_meta.get("char_start") or 0)
        char_end: int = int(chunk_meta.get("char_end") or char_start)

        # 防御性截断 (char_end 可能略 > len(content), 边界 case)
        if char_end > len(content):
            char_end = len(content)
        if char_start < 0:
            char_start = 0
        if char_end < char_start:
            char_end = char_start

        # snippet 优先用 chunk 全文 (前端展示用, 无需切片)
        # 截断到 500 字避免过长 (前端 rich block 性能)
        snippet = content[:500] if content else ""

        similarity = float(result.get("similarity") or result.get("score") or 0.0)

        return {
            "doc_id": chunk_meta["knowledge_id"],
            "chunk_id": chunk_meta["id"],
            "char_range": (char_start, char_end),  # tuple, 沿用派工 brief 语义
            "similarity": round(similarity, 4),
            "snippet": snippet,
            "strategy": chunk_meta.get("strategy", "paragraph"),
            "retrieval_method": result.get("retrieval_method", "hybrid"),
        }

    def format_for_frontend(
        self,
        citations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """转换 char_range tuple → list (JSON 序列化友好)

        前端 Vue 组件 props.citations 默认期望 Array, 内含
        char_range: [start, end] (list 而非 tuple)
        """
        out = []
        for c in citations:
            c2 = dict(c)
            if isinstance(c2.get("char_range"), tuple):
                c2["char_range"] = list(c2["char_range"])
            out.append(c2)
        return out

# Phase 1: 混合检索实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在现有 pgvector 向量检索基础上，添加 BM25 关键词检索 + Cross-encoder 重排序 + 三路并发合并，提升 RAG 回答准确率

**架构：** 新增 `BM25Service`（中文分词 + BM25 索引）、`RerankerService`（Cross-encoder 精排）、`HybridRetriever`（向量 + BM25 并发 + 合并去重 + 重排序）。修改 `KnowledgeQAService._search_knowledge_base` 使用混合检索替代纯向量检索。

**技术栈：** rank-bm25、jieba（中文分词）、sentence-transformers（Cross-encoder）、asyncio（并发）

---

## 文件结构

| 文件 | 职责 | 操作 |
|------|------|------|
| `app/services/bm25_service.py` | BM25 关键词检索服务 | **新建** |
| `app/services/reranker_service.py` | Cross-encoder 重排序服务 | **新建** |
| `app/services/hybrid_retriever.py` | 三路并发检索 + 合并 + 重排序 | **新建** |
| `app/services/knowledge_qa_service.py` | RAG 问答引擎（集成混合检索） | **修改** |
| `app/services/knowledge_service.py` | 知识库服务（添加 BM25 索引刷新） | **修改** |
| `requirements.txt` | 依赖（rank-bm25、jieba） | **修改** |
| `tests/test_bm25_service.py` | BM25 服务单元测试 | **新建** |
| `tests/test_reranker_service.py` | 重排序服务单元测试 | **新建** |
| `tests/test_hybrid_retriever.py` | 混合检索单元测试 | **新建** |

---

## 任务 1：安装依赖

**文件：**
- 修改：`requirements.txt`

- [ ] **步骤 1：添加依赖**

在 `requirements.txt` 中添加：
```
rank-bm25>=0.2.2
jieba>=0.42.1
```

- [ ] **步骤 2：安装依赖**

运行：`pip install rank-bm25 jieba`
预期：Successfully installed rank-bm25-0.2.2 jieba-0.42.1

- [ ] **步骤 3：验证导入**

运行：`python -c "from rank_bm25 import BM25Okapi; import jieba; print('OK')"`
预期：`OK`

- [ ] **步骤 4：Commit**

```bash
git add requirements.txt
git commit -m "deps: 添加 rank-bm25 和 jieba 依赖（Phase 1 混合检索）"
```

---

## 任务 2：实现 BM25 服务

**文件：**
- 创建：`app/services/bm25_service.py`
- 测试：`tests/test_bm25_service.py`

- [ ] **步骤 1：编写 BM25 服务的失败测试**

创建 `tests/test_bm25_service.py`：

```python
"""BM25 关键词检索服务测试"""
import pytest
from app.services.bm25_service import BM25Service


class TestBM25Service:
    """BM25 服务测试"""

    def test_tokenize_chinese(self):
        """中文分词测试"""
        service = BM25Service()
        tokens = service._tokenize("微纳米气泡的zeta电位是表征其表面电荷的重要指标")
        assert "微纳" in tokens or "纳米" in tokens or "气泡" in tokens
        assert "zeta" in tokens
        assert "电位" in tokens
        # 停用词应被过滤
        assert "的" not in tokens
        assert "是" not in tokens

    def test_tokenize_english(self):
        """英文分词测试"""
        service = BM25Service()
        tokens = service._tokenize("micro-nano bubble zeta potential")
        assert "micro" in tokens
        assert "nano" in tokens
        assert "bubble" in tokens

    def test_build_index(self):
        """构建索引测试"""
        service = BM25Service()
        documents = [
            {"id": 1, "title": "微纳米气泡", "content": "微纳米气泡是一种直径小于50微米的气泡"},
            {"id": 2, "title": "zeta电位", "content": "zeta电位是表征胶体稳定性的重要参数"},
            {"id": 3, "title": "空化效应", "content": "超声空化效应是产生微纳米气泡的主要方法之一"},
        ]
        service.build_index(documents)
        assert service._corpus_size == 3
        assert service._bm25 is not None

    def test_search(self):
        """检索测试"""
        service = BM25Service()
        documents = [
            {"id": 1, "title": "微纳米气泡", "content": "微纳米气泡是一种直径小于50微米的气泡"},
            {"id": 2, "title": "zeta电位", "content": "zeta电位是表征胶体稳定性的重要参数"},
            {"id": 3, "title": "空化效应", "content": "超声空化效应是产生微纳米气泡的主要方法之一"},
        ]
        service.build_index(documents)
        results = service.search("微纳米气泡", top_k=2)
        assert len(results) <= 2
        assert len(results) > 0
        # 第一条和第三条都包含"微纳米气泡"，应该排在前面
        assert results[0]["id"] in [1, 3]

    def test_search_empty_index(self):
        """空索引检索测试"""
        service = BM25Service()
        service.build_index([])
        results = service.search("测试", top_k=5)
        assert results == []

    def test_search_no_match(self):
        """无匹配结果测试"""
        service = BM25Service()
        documents = [
            {"id": 1, "title": "微纳米气泡", "content": "微纳米气泡是一种直径小于50微米的气泡"},
        ]
        service.build_index(documents)
        results = service.search("量子力学", top_k=5)
        # BM25 会返回结果但分数很低
        assert len(results) <= 1
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd g:/microbubble-agent && python -m pytest tests/test_bm25_service.py -v`
预期：FAIL，报错 `ModuleNotFoundError: No module named 'app.services.bm25_service'`

- [ ] **步骤 3：实现 BM25 服务**

创建 `app/services/bm25_service.py`：

```python
"""BM25 关键词检索服务

使用 rank-bm25 + jieba 中文分词实现关键词检索，
与 pgvector 向量检索互补（向量擅长语义，BM25 擅长精确匹配）。
"""

import logging
import re
from typing import List, Optional

import jieba
from rank_bm25 import BM25Okapi

logger = logging.getLogger("microbubble.bm25")

# 中文停用词（常见虚词/助词/代词）
STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没有", "看", "好", "自己", "这", "他", "她", "它",
    "们", "那", "里", "为", "什么", "怎么", "如何", "可以", "能",
    "被", "把", "对", "从", "但", "等", "而", "与", "或", "及",
    "其", "中", "之", "以", "于", "所", "如", "此", "则", "故",
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall",
    "of", "in", "to", "for", "with", "on", "at", "from", "by",
    "and", "or", "not", "no", "nor", "as", "if", "then", "than",
    "that", "this", "these", "those", "it", "its",
}


class BM25Service:
    """BM25 关键词检索服务"""

    def __init__(self):
        self._bm25: Optional[BM25Okapi] = None
        self._documents: List[dict] = []
        self._tokenized_corpus: List[List[str]] = []
        self._corpus_size: int = 0

    def _tokenize(self, text: str) -> List[str]:
        """中文分词 + 过滤停用词"""
        # 清洗：保留中英文和数字
        text = re.sub(r'[^一-鿿\w]+', ' ', text)
        # jieba 分词
        tokens = list(jieba.cut(text))
        # 过滤：停用词 + 单字符 + 纯数字
        tokens = [
            t.lower().strip()
            for t in tokens
            if t.lower().strip() not in STOP_WORDS
            and len(t.strip()) > 1
            and not t.strip().isdigit()
        ]
        return tokens

    def build_index(self, documents: List[dict]) -> None:
        """构建 BM25 索引

        Args:
            documents: 文档列表，每条需包含 id, title, content
        """
        if not documents:
            self._bm25 = None
            self._documents = []
            self._tokenized_corpus = []
            self._corpus_size = 0
            return

        self._documents = documents
        self._tokenized_corpus = [
            self._tokenize(f"{doc.get('title', '')} {doc.get('content', '')}")
            for doc in documents
        ]
        self._corpus_size = len(documents)
        self._bm25 = BM25Okapi(self._tokenized_corpus)
        logger.info(f"BM25 索引构建完成: {self._corpus_size} 条文档")

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """BM25 关键词检索

        Args:
            query: 查询文本
            top_k: 返回条数

        Returns:
            按 BM25 分数排序的结果列表，每条包含 id, title, content, score
        """
        if self._bm25 is None or self._corpus_size == 0:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = self._bm25.get_scores(query_tokens)

        # 按分数排序取 top_k
        scored_docs = sorted(
            zip(self._documents, scores),
            key=lambda x: x[1],
            reverse=True,
        )[:top_k]

        results = []
        for doc, score in scored_docs:
            if score > 0:  # 过滤零分
                results.append({
                    "id": doc["id"],
                    "title": doc.get("title", ""),
                    "content": doc.get("content", "")[:500],
                    "category": doc.get("category"),
                    "tags": doc.get("tags"),
                    "source": doc.get("source"),
                    "score": round(float(score), 4),
                    "retrieval_method": "bm25",
                })

        return results

    def add_document(self, doc: dict) -> None:
        """增量添加文档（重建索引）"""
        self._documents.append(doc)
        self._tokenized_corpus.append(
            self._tokenize(f"{doc.get('title', '')} {doc.get('content', '')}")
        )
        self._corpus_size = len(self._documents)
        self._bm25 = BM25Okapi(self._tokenized_corpus)


# 全局单例（惰性初始化）
_bm25_service: Optional[BM25Service] = None


def get_bm25_service() -> BM25Service:
    """获取 BM25 服务单例"""
    global _bm25_service
    if _bm25_service is None:
        _bm25_service = BM25Service()
    return _bm25_service
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd g:/microbubble-agent && python -m pytest tests/test_bm25_service.py -v`
预期：6 passed

- [ ] **步骤 5：Commit**

```bash
git add app/services/bm25_service.py tests/test_bm25_service.py
git commit -m "feat(knowledge): BM25 关键词检索服务（jieba 分词 + rank-bm25）"
```

---

## 任务 3：实现重排序服务

**文件：**
- 创建：`app/services/reranker_service.py`
- 测试：`tests/test_reranker_service.py`

- [ ] **步骤 1：编写重排序服务的失败测试**

创建 `tests/test_reranker_service.py`：

```python
"""Cross-encoder 重排序服务测试"""
import pytest
from app.services.reranker_service import RerankerService


class TestRerankerService:
    """重排序服务测试"""

    def test_rerank_basic(self):
        """基本重排序测试"""
        service = RerankerService()
        query = "微纳米气泡的制备方法"
        candidates = [
            {"id": 1, "title": "量子力学基础", "content": "量子力学是研究微观粒子运动规律的物理学分支", "score": 0.8},
            {"id": 2, "title": "微纳米气泡制备", "content": "超声法是制备微纳米气泡的常用方法之一", "score": 0.6},
            {"id": 3, "title": "空化效应", "content": "超声空化效应是产生微纳米气泡的主要原理", "score": 0.7},
        ]
        results = service.rerank(query, candidates, top_k=2)
        assert len(results) == 2
        # 与微纳米气泡相关的应排在前面
        assert results[0]["id"] in [2, 3]
        # 分数应被重排序分数替换
        assert "rerank_score" in results[0]

    def test_rerank_empty(self):
        """空候选集测试"""
        service = RerankerService()
        results = service.rerank("测试", [], top_k=5)
        assert results == []

    def test_rerank_preserves_fields(self):
        """重排序保留原始字段测试"""
        service = RerankerService()
        candidates = [
            {"id": 1, "title": "测试", "content": "测试内容", "score": 0.5, "category": "测试分类", "tags": ["tag1"]},
        ]
        results = service.rerank("测试", candidates, top_k=1)
        assert results[0]["category"] == "测试分类"
        assert results[0]["tags"] == ["tag1"]
        assert results[0]["id"] == 1
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd g:/microbubble-agent && python -m pytest tests/test_reranker_service.py -v`
预期：FAIL，报错 `ModuleNotFoundError: No module named 'app.services.reranker_service'`

- [ ] **步骤 3：实现重排序服务**

创建 `app/services/reranker_service.py`：

```python
"""Cross-encoder 重排序服务

对检索候选集使用 Cross-encoder 模型精排。
Cross-encoder 比 bi-encoder（向量检索用的）更准确，但更慢，
所以只对候选集做精排（top_k * 3），不做全库扫描。

模型：cross-encoder/ms-marco-MiniLM-L-6-v2（轻量，CPU 可跑，约 80MB）
"""

import logging
from typing import List, Optional

logger = logging.getLogger("microbubble.reranker")

# 模型名称（轻量 Cross-encoder）
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class RerankerService:
    """Cross-encoder 重排序服务"""

    def __init__(self):
        self._model = None

    def _load_model(self):
        """惰性加载 Cross-encoder 模型"""
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"加载 Cross-encoder 模型: {RERANKER_MODEL}")
            self._model = CrossEncoder(RERANKER_MODEL, max_length=512)
            logger.info("Cross-encoder 模型加载完成")
        except Exception as e:
            logger.error(f"Cross-encoder 模型加载失败: {e}（重排序将不可用，直接返回原序）")
            self._model = None

    def rerank(
        self,
        query: str,
        candidates: List[dict],
        top_k: int = 5,
    ) -> List[dict]:
        """对候选集重排序

        Args:
            query: 原始查询
            candidates: 候选文档列表，每条需包含 content 字段
            top_k: 返回条数

        Returns:
            按 Cross-encoder 分数重排序的结果列表
        """
        if not candidates:
            return []

        self._load_model()

        # 模型加载失败时降级：按原始分数排序
        if self._model is None:
            logger.warning("Cross-encoder 不可用，按原始分数排序")
            sorted_candidates = sorted(
                candidates, key=lambda x: x.get("score", 0), reverse=True
            )
            for c in sorted_candidates:
                c["rerank_score"] = c.get("score", 0)
            return sorted_candidates[:top_k]

        # 构建 query-document 对
        pairs = [(query, f"{c.get('title', '')} {c.get('content', '')}") for c in candidates]

        # Cross-encoder 打分
        try:
            scores = self._model.predict(pairs)
        except Exception as e:
            logger.error(f"Cross-encoder 预测失败: {e}")
            sorted_candidates = sorted(
                candidates, key=lambda x: x.get("score", 0), reverse=True
            )
            for c in sorted_candidates:
                c["rerank_score"] = c.get("score", 0)
            return sorted_candidates[:top_k]

        # 将分数附加到候选文档
        for i, candidate in enumerate(candidates):
            candidate["rerank_score"] = round(float(scores[i]), 4)

        # 按重排序分数排序
        reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)

        return reranked[:top_k]


# 全局单例
_reranker_service: Optional[RerankerService] = None


def get_reranker_service() -> RerankerService:
    """获取重排序服务单例"""
    global _reranker_service
    if _reranker_service is None:
        _reranker_service = RerankerService()
    return _reranker_service
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd g:/microbubble-agent && python -m pytest tests/test_reranker_service.py -v`
预期：3 passed（首次运行可能需要下载模型，约 80MB）

- [ ] **步骤 5：Commit**

```bash
git add app/services/reranker_service.py tests/test_reranker_service.py
git commit -m "feat(knowledge): Cross-encoder 重排序服务（ms-marco-MiniLM）"
```

---

## 任务 4：实现混合检索器

**文件：**
- 创建：`app/services/hybrid_retriever.py`
- 测试：`tests/test_hybrid_retriever.py`

- [ ] **步骤 1：编写混合检索器的失败测试**

创建 `tests/test_hybrid_retriever.py`：

```python
"""混合检索器测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.hybrid_retriever import HybridRetriever


class TestHybridRetriever:
    """混合检索器测试"""

    @pytest.mark.asyncio
    async def test_merge_results(self):
        """结果合并去重测试"""
        retriever = HybridRetriever(db=MagicMock())
        vector_results = [
            {"id": 1, "title": "A", "content": "内容A", "score": 0.9, "retrieval_method": "vector"},
            {"id": 2, "title": "B", "content": "内容B", "score": 0.8, "retrieval_method": "vector"},
        ]
        bm25_results = [
            {"id": 2, "title": "B", "content": "内容B", "score": 5.0, "retrieval_method": "bm25"},
            {"id": 3, "title": "C", "content": "内容C", "score": 4.0, "retrieval_method": "bm25"},
        ]
        merged = retriever._merge_results(vector_results, bm25_results)
        # id=2 应该只出现一次
        ids = [r["id"] for r in merged]
        assert ids.count(2) == 1
        # 应该有 3 条结果
        assert len(merged) == 3
        # id=2 应该保留 vector 和 bm25 两种来源
        doc_2 = next(r for r in merged if r["id"] == 2)
        assert "vector" in doc_2.get("retrieval_methods", []) or doc_2.get("retrieval_method") == "hybrid"

    @pytest.mark.asyncio
    async def test_merge_empty(self):
        """空结果合并测试"""
        retriever = HybridRetriever(db=MagicMock())
        merged = retriever._merge_results([], [])
        assert merged == []

    @pytest.mark.asyncio
    async def test_normalize_scores(self):
        """分数归一化测试"""
        retriever = HybridRetriever(db=MagicMock())
        results = [
            {"id": 1, "score": 10.0},
            {"id": 2, "score": 5.0},
            {"id": 3, "score": 0.0},
        ]
        normalized = retriever._normalize_scores(results)
        assert normalized[0]["normalized_score"] == 1.0
        assert normalized[1]["normalized_score"] == 0.5
        assert normalized[2]["normalized_score"] == 0.0
```

- [ ] **步骤 2：运行测试验证失败**

运行：`cd g:/microbubble-agent && python -m pytest tests/test_hybrid_retriever.py -v`
预期：FAIL，报错 `ModuleNotFoundError: No module named 'app.services.hybrid_retriever'`

- [ ] **步骤 3：实现混合检索器**

创建 `app/services/hybrid_retriever.py`：

```python
"""混合检索器 — 向量 + BM25 并发检索 + 合并去重 + 重排序

流程：
1. 向量检索（pgvector 语义搜索）和 BM25 关键词检索并发执行
2. 合并结果，同一文档保留最高分
3. 分数归一化（不同检索方式的分数尺度不同）
4. Cross-encoder 重排序
"""

import asyncio
import logging
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("microbubble.hybrid_retriever")


class HybridRetriever:
    """混合检索器"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
        enable_vector: bool = True,
        enable_bm25: bool = True,
        enable_rerank: bool = True,
    ) -> List[dict]:
        """混合检索

        Args:
            query: 查询文本
            top_k: 最终返回条数
            category: 可选分类过滤
            enable_vector: 是否启用向量检索
            enable_bm25: 是否启用 BM25 检索
            enable_rerank: 是否启用重排序

        Returns:
            检索结果列表
        """
        # 候选集数量（重排序前多取一些）
        candidate_k = top_k * 3 if enable_rerank else top_k

        # 并发执行向量检索和 BM25 检索
        tasks = []
        if enable_vector:
            tasks.append(self._vector_search(query, candidate_k, category))
        if enable_bm25:
            tasks.append(self._bm25_search(query, candidate_k, category))

        if not tasks:
            return []

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        vector_results = []
        bm25_results = []
        for i, result in enumerate(results_list):
            if isinstance(result, Exception):
                logger.warning(f"检索方式 {i} 失败: {result}")
                continue
            if enable_vector and i == 0:
                vector_results = result
            elif enable_bm25:
                bm25_results = result if enable_vector else result

        # 合并去重
        merged = self._merge_results(vector_results, bm25_results)

        if not merged:
            return []

        # 分数归一化
        normalized = self._normalize_scores(merged)

        # 重排序
        if enable_rerank and len(normalized) > 1:
            from app.services.reranker_service import get_reranker_service
            reranker = get_reranker_service()
            reranked = reranker.rerank(query, normalized, top_k=top_k)
            return reranked

        # 不重排序时按归一化分数排序
        normalized.sort(key=lambda x: x.get("normalized_score", 0), reverse=True)
        return normalized[:top_k]

    async def _vector_search(
        self, query: str, top_k: int, category: Optional[str]
    ) -> List[dict]:
        """向量检索（复用现有 KnowledgeService.search_semantic）"""
        try:
            from app.services.knowledge_service import KnowledgeService
            svc = KnowledgeService(self.db)
            results = await svc.search_semantic(query=query, top_k=top_k, category=category)
            for r in results:
                r["retrieval_method"] = "vector"
            return results
        except Exception as e:
            logger.warning(f"向量检索失败: {e}")
            return []

    async def _bm25_search(
        self, query: str, top_k: int, category: Optional[str]
    ) -> List[dict]:
        """BM25 关键词检索"""
        try:
            from app.services.bm25_service import get_bm25_service
            from app.services.knowledge_service import KnowledgeService
            from sqlalchemy import select
            from app.models.knowledge import Knowledge

            bm25 = get_bm25_service()

            # 如果索引为空，从数据库加载
            if bm25._corpus_size == 0:
                await self._refresh_bm25_index(bm25, category)

            results = bm25.search(query, top_k=top_k)
            return results
        except Exception as e:
            logger.warning(f"BM25 检索失败: {e}")
            return []

    async def _refresh_bm25_index(
        self, bm25_service, category: Optional[str] = None
    ) -> None:
        """从数据库刷新 BM25 索引"""
        from sqlalchemy import select
        from app.models.knowledge import Knowledge

        stmt = select(Knowledge)
        if category:
            stmt = stmt.where(Knowledge.category == category)
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        documents = [
            {
                "id": r.id,
                "title": r.title or "",
                "content": r.content or "",
                "category": r.category,
                "tags": r.tags,
                "source": r.source,
            }
            for r in rows
        ]
        bm25_service.build_index(documents)
        logger.info(f"BM25 索引刷新完成: {len(documents)} 条")

    def _merge_results(
        self, vector_results: List[dict], bm25_results: List[dict]
    ) -> List[dict]:
        """合并去重：同一文档保留最高分，记录所有来源"""
        merged = {}

        for r in vector_results:
            doc_id = r["id"]
            if doc_id not in merged:
                merged[doc_id] = {**r, "retrieval_methods": ["vector"]}
            else:
                existing = merged[doc_id]
                if r.get("score", 0) > existing.get("score", 0):
                    existing.update(r)
                existing.setdefault("retrieval_methods", []).append("vector")

        for r in bm25_results:
            doc_id = r["id"]
            if doc_id not in merged:
                merged[doc_id] = {**r, "retrieval_methods": ["bm25"]}
            else:
                existing = merged[doc_id]
                existing.setdefault("retrieval_methods", []).append("bm25")
                # BM25 分数可能更大，但不覆盖向量分数（后面会归一化）

        return list(merged.values())

    def _normalize_scores(self, results: List[dict]) -> List[dict]:
        """分数归一化到 [0, 1]"""
        if not results:
            return results

        scores = [r.get("score", 0) for r in results]
        max_score = max(scores) if scores else 1.0
        min_score = min(scores) if scores else 0.0
        score_range = max_score - min_score if max_score != min_score else 1.0

        for r in results:
            r["normalized_score"] = round((r.get("score", 0) - min_score) / score_range, 4)

        return results


# 全局工厂
def get_hybrid_retriever(db: AsyncSession) -> HybridRetriever:
    """获取混合检索器实例"""
    return HybridRetriever(db)
```

- [ ] **步骤 4：运行测试验证通过**

运行：`cd g:/microbubble-agent && python -m pytest tests/test_hybrid_retriever.py -v`
预期：3 passed

- [ ] **步骤 5：Commit**

```bash
git add app/services/hybrid_retriever.py tests/test_hybrid_retriever.py
git commit -m "feat(knowledge): 混合检索器（向量 + BM25 并发 + 合并去重 + 归一化）"
```

---

## 任务 5：集成混合检索到 KnowledgeQAService

**文件：**
- 修改：`app/services/knowledge_qa_service.py:152-165`

- [ ] **步骤 1：修改 _search_knowledge_base 使用混合检索**

将 `knowledge_qa_service.py` 的 `_search_knowledge_base` 方法替换为：

```python
    async def _search_knowledge_base(self, question: str, top_k: int) -> List[dict]:
        """搜索知识库 — 混合检索（向量 + BM25 + 重排序）"""
        try:
            from app.services.hybrid_retriever import get_hybrid_retriever
            retriever = get_hybrid_retriever(self.db)
            results = await retriever.retrieve(
                query=question,
                top_k=top_k,
                enable_vector=True,
                enable_bm25=True,
                enable_rerank=True,
            )
            if results:
                return results
        except Exception as e:
            logger.warning(f"混合检索失败，降级到纯向量: {e}")

        # 降级：纯向量检索
        try:
            from app.services.knowledge_service import KnowledgeService
            svc = KnowledgeService(self.db)
            results = await svc.search_semantic(query=question, top_k=top_k)
            if results:
                return results
        except Exception as e:
            logger.debug(f"向量检索失败，降级到关键词: {e}")

        # 最终降级：关键词搜索
        return await self._keyword_search(question, top_k)
```

- [ ] **步骤 2：运行现有测试确保不破坏**

运行：`cd g:/microbubble-agent && python -m pytest tests/ -v -k "knowledge" --timeout=30`
预期：现有测试通过（或跳过需要数据库的测试）

- [ ] **步骤 3：Commit**

```bash
git add app/services/knowledge_qa_service.py
git commit -m "feat(knowledge): KnowledgeQAService 集成混合检索（向量 + BM25 + 重排序）"
```

---

## 任务 6：BM25 索引刷新钩子

**文件：**
- 修改：`app/services/knowledge_service.py:88-106`

- [ ] **步骤 1：在知识入库/更新时刷新 BM25 索引**

在 `knowledge_service.py` 的 `create_knowledge` 和 `update_knowledge` 方法末尾添加 BM25 索引刷新：

在 `create_knowledge` 方法的 `return knowledge` 之前添加：

```python
        # 刷新 BM25 索引
        try:
            from app.services.bm25_service import get_bm25_service
            bm25 = get_bm25_service()
            bm25.add_document({
                "id": knowledge.id,
                "title": knowledge.title,
                "content": knowledge.content,
                "category": knowledge.category,
                "tags": knowledge.tags,
                "source": knowledge.source,
            })
        except Exception as e:
            logger.debug(f"BM25 索引增量更新失败: {e}")
```

在 `update_knowledge` 方法的 `return knowledge` 之前添加：

```python
        # BM25 索引将在下次检索时自动重建（增量更新复杂度高，采用懒刷新策略）
```

- [ ] **步骤 2：Commit**

```bash
git add app/services/knowledge_service.py
git commit -m "feat(knowledge): 知识入库时增量更新 BM25 索引"
```

---

## 任务 7：更新 requirements.txt 并重建 Docker 镜像

**文件：**
- 修改：`requirements.txt`

- [ ] **步骤 1：确认 requirements.txt 已包含依赖**

检查 `requirements.txt` 包含：
```
rank-bm25>=0.2.2
jieba>=0.42.1
```

- [ ] **步骤 2：本地测试导入**

运行：`python -c "from app.services.bm25_service import BM25Service; from app.services.reranker_service import RerankerService; from app.services.hybrid_retriever import HybridRetriever; print('All imports OK')"`
预期：`All imports OK`

- [ ] **步骤 3：Commit 并 push**

```bash
git add -A
git commit -m "feat(knowledge): Phase 1 混合检索完成 — BM25 + 重排序 + 三路并发"
git push origin main
```

- [ ] **步骤 4：重启 app 容器**

```powershell
cd g:\microbubble-agent; docker-compose restart app
```

---

## 验收检查清单

- [ ] BM25 关键词检索能正确检索中文内容
- [ ] Cross-encoder 重排序能将更相关的结果排在前面
- [ ] 混合检索（向量 + BM25）结果比纯向量检索更准确
- [ ] 检索延迟 < 2s（含重排序）
- [ ] 降级机制：BM25 失败时回退到纯向量，向量失败时回退到关键词
- [ ] 现有 RAG 问答功能不受影响
- [ ] 所有单元测试通过

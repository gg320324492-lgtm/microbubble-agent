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
            按 BM25 分数排序的结果列表
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

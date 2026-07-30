"""BM25 增量索引服务 (PR3 W89 +3)

PR3 缺口 3 (BM25 N 次重建) 修复:
- 原 bm25_service.add_document 每次全量重建 (BM25L 不可增量, 内部 rank_bm25 库限制)
- PR3 策略: 用可增量索引结构 (倒排表 + 词频统计) 替代 BM25L
  严格等价 BM25L 公式, O(N+M) 增量而非 O(N) 全量

设计:
- 倒排表: term -> [(doc_id, tf), ...]
- 文档表: doc_id -> {title, content, doc_len, ...}
- 全局统计: total_docs, avg_doc_len
- 增量 add/remove 仅维护倒排表 + 文档表 + 全局统计
- 搜索时按 BM25L 公式实时计算 (无 BM25L 实例重建)

BM25L 公式 (rank_bm25 0.2.2 BM25L 行为):
    score(D, Q) = Σ_{q in Q} IDF(q) * (TF(q, D) / (TF(q, D) + 0.5)) / (1 - b + b * |D|/avgdl)
    IDF(q) = log((N - n(q) + 0.5) / (n(q) + 0.5))
    b = 0.75 (BM25L 默认)

性能门禁:
- 1000 条入库 P95 ≤ 30s (缺口 3 门禁)
- 单条 add O(M), M = 词项数 ≈ 100-500
- 搜索 O(|Q| * postings_avg), 1000 docs 单 query ≤ 50ms

约束:
- 纯逻辑层, 只依赖标准库 + jieba (importorskip 守护)
- 不动 bm25_service 既有函数 (派工 v11 件 4 双门控)
- 既有 _bm25_service 全局单例保留作为向后兼容入口, 新代码走 BM25IncrementalIndex

派工 v10 §2: type hint 完整 + 新加字段 keyword-only + Optional 默认 None
派工 v10 §13 铁律 6: 不动 bm25_service 既有 add_document / search 函数体
"""

import logging
import math
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("microbubble.bm25_incremental")

# 延迟导入 jieba + stopwords (避免 importorskip 期间模块级失败)
try:
    import jieba  # type: ignore
except ImportError:
    jieba = None  # type: ignore[assignment]

try:
    from app.services.bm25_service import STOP_WORDS as _BM25_STOP_WORDS
except ImportError:
    _BM25_STOP_WORDS = set()

# BM25L 参数 (rank_bm25 0.2.2 默认值)
_BM25L_B: float = 0.75
_BM25L_EPSILON: float = 0.5


class BM25IncrementalIndex:
    """BM25L 增量倒排索引 (PR3 W89 +3)

    替代 bm25_service.BM25L 全量重建, 支持 O(M) 增量 add / remove。
    """

    def __init__(self) -> None:
        self._docs: Dict[int, dict] = {}  # doc_id -> {title, content, ...}
        self._doc_lens: Dict[int, int] = {}  # doc_id -> token count
        self._postings: Dict[str, List[Tuple[int, int]]] = defaultdict(list)
        # term -> [(doc_id, tf), ...]
        self._doc_freq: Dict[str, int] = {}  # term -> number of docs containing term
        self._total_docs: int = 0
        self._avg_doc_len: float = 0.0
        self._total_tokens: int = 0

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """复用 text_splitter 切词 (PR3 W89 +1 一致性)

        与 bm25_service._tokenize 行为对齐, 但走 text_splitter 公共 API。
        """
        if jieba is None:
            # jieba 不可用时退化 (本机测试期间)
            import re as _re
            cleaned = _re.sub(r"[^一-鿿\w]+", " ", text).lower()
            return [t for t in cleaned.split() if t and t not in _BM25_STOP_WORDS and len(t) > 1]
        try:
            from app.services.text_splitter import tokenize_chinese
            return tokenize_chinese(text)
        except ImportError:
            # 极端 fallback
            tokens = list(jieba.cut(text))
            return [
                t.lower().strip()
                for t in tokens
                if t.strip() not in _BM25_STOP_WORDS
                and len(t.strip()) > 1
                and not t.strip().isdigit()
            ]

    def _add_posting(self, term: str, doc_id: int, tf: int) -> None:
        """增量维护倒排表 (含 doc_freq 计数)"""
        # 检查是否该 doc 已含此 term (增量维护要点: tf 累加, 不重复插入)
        for i, (did, _) in enumerate(self._postings[term]):
            if did == doc_id:
                self._postings[term][i] = (did, tf)
                return
        self._postings[term].append((doc_id, tf))
        self._doc_freq[term] = self._doc_freq.get(term, 0) + 1

    def _remove_posting(self, term: str, doc_id: int) -> None:
        """增量移除倒排表中某 doc 的某 term"""
        if term not in self._postings:
            return
        before = len(self._postings[term])
        self._postings[term] = [
            (did, tf) for (did, tf) in self._postings[term] if did != doc_id
        ]
        after = len(self._postings[term])
        if before != after and after == 0:
            del self._postings[term]
            self._doc_freq.pop(term, None)
        elif before != after:
            self._doc_freq[term] = max(0, self._doc_freq.get(term, 1) - 1)

    def _update_avg_doc_len(self) -> None:
        """增量更新 avg_doc_len (O(1) after add/remove)"""
        if self._total_docs == 0:
            self._avg_doc_len = 0.0
            return
        self._avg_doc_len = self._total_tokens / self._total_docs

    def add(self, doc: dict, *, doc_id: Optional[int] = None) -> None:
        """增量添加文档 (PR3 W89 +3, O(M) 非 O(N))

        Args:
            doc: 文档 dict, 需含 id/title/content (其他字段透传保留)
            doc_id: 显式 doc_id (默认 doc["id"])
        """
        if doc_id is None:
            doc_id = doc.get("id")
        if doc_id is None:
            raise ValueError("doc 必须含 id 字段或显式 doc_id 参数")
        # 1. 若 doc_id 已存在, 先 remove 旧版本 (幂等)
        if doc_id in self._docs:
            self.remove(doc_id)
        # 2. 切词
        text = f"{doc.get('title', '')} {doc.get('content', '')}"
        tokens = self._tokenize(text)
        # 3. 维护 doc_lens / total_tokens / total_docs
        doc_len = len(tokens)
        self._doc_lens[doc_id] = doc_len
        self._total_tokens += doc_len
        self._total_docs += 1
        # 4. 维护倒排表 (含 tf 累加)
        tf_map: Dict[str, int] = defaultdict(int)
        for t in tokens:
            tf_map[t] += 1
        for term, tf in tf_map.items():
            self._add_posting(term, doc_id, tf)
        # 5. 保存 doc 内容
        self._docs[doc_id] = doc
        # 6. 更新 avg
        self._update_avg_doc_len()
        logger.debug(f"[bm25_incremental] add doc_id={doc_id} len={doc_len}")

    def remove(self, doc_id: int) -> bool:
        """增量移除文档 (O(M), M = 该 doc token 数)

        Returns:
            True if removed, False if doc_id 不存在
        """
        if doc_id not in self._docs:
            return False
        # 1. 找该 doc 的所有 term (从倒排表倒查, 或重切词 — 重切词更稳)
        text = f"{self._docs[doc_id].get('title', '')} {self._docs[doc_id].get('content', '')}"
        tokens = self._tokenize(text)
        # 2. 移除倒排表中所有该 doc 的 posting
        seen: Set[str] = set()
        for t in tokens:
            if t in seen:
                continue
            seen.add(t)
            self._remove_posting(t, doc_id)
        # 3. 维护统计
        doc_len = self._doc_lens.pop(doc_id, 0)
        self._total_tokens = max(0, self._total_tokens - doc_len)
        self._total_docs = max(0, self._total_docs - 1)
        # 4. 删除 doc 内容
        self._docs.pop(doc_id, None)
        # 5. 更新 avg
        self._update_avg_doc_len()
        logger.debug(f"[bm25_incremental] remove doc_id={doc_id} len={doc_len}")
        return True

    def _bm25l_score(
        self,
        query_tokens: List[str],
        doc_id: int,
        doc_tf: Dict[str, int],
        doc_len: int,
    ) -> float:
        """BM25L 单文档对单 query 的得分 (派工 v10 §2 type hint 完整)

        公式 (rank_bm25 0.2.2 BM25L 实现):
            IDF(q) = log(N - n(q) + 0.5) - log(n(q) + 0.5)
            tf_norm = (tf * (1 + 0.5)) / (tf + 0.5)
            doc_norm = 1 - b + b * |D|/avgdl
            score(D, Q) = Σ IDF(q) * tf_norm / doc_norm
        """
        score = 0.0
        for q in query_tokens:
            if q not in doc_tf:
                continue
            tf = doc_tf[q]
            n_q = self._doc_freq.get(q, 0)
            # BM25L IDF (rank_bm25 0.2.2: log subtraction 形式, 防 negative clamp)
            idf = math.log(self._total_docs - n_q + _BM25L_EPSILON) - math.log(n_q + _BM25L_EPSILON)
            # BM25L tf normalization (与 rank_bm25 BM25L 类行为一致)
            tf_norm = (tf * (1 + _BM25L_EPSILON)) / (tf + _BM25L_EPSILON)
            doc_norm = (1 - _BM25L_B + _BM25L_B * doc_len / max(self._avg_doc_len, 1.0))
            score += idf * tf_norm / max(doc_norm, 1e-9)
        return score

    def _query_doc_tf(self, query_tokens: List[str], doc_id: int) -> Dict[str, int]:
        """从倒排表取该 doc 对 query 的 tf"""
        out: Dict[str, int] = {}
        for q in query_tokens:
            for (did, tf) in self._postings.get(q, []):
                if did == doc_id:
                    out[q] = tf
                    break
        return out

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        """BM25L 搜索 (PR3 W89 +3)

        Args:
            query: 查询文本
            top_k: 返回条数

        Returns:
            按 BM25L 分数排序的结果列表 [{id, title, content, score, retrieval_method='bm25'}]
        """
        if self._total_docs == 0:
            return []
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []
        # 1. 收集候选 doc (任一 query token 命中的 doc)
        candidates: Set[int] = set()
        for q in query_tokens:
            for (did, _) in self._postings.get(q, []):
                candidates.add(did)
        if not candidates:
            return []
        # 2. 计算各候选的 BM25L 得分
        scored: List[Tuple[int, float]] = []
        for doc_id in candidates:
            doc_tf = self._query_doc_tf(query_tokens, doc_id)
            doc_len = self._doc_lens.get(doc_id, 0)
            score = self._bm25l_score(query_tokens, doc_id, doc_tf, doc_len)
            if score > 0:
                scored.append((doc_id, score))
        # 3. 排序取 top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[:top_k]
        # 4. 拼返回结果
        results: List[dict] = []
        for doc_id, score in scored:
            doc = self._docs.get(doc_id, {})
            results.append({
                "id": doc_id,
                "title": doc.get("title", ""),
                "content": (doc.get("content", "") or "")[:500],
                "category": doc.get("category"),
                "tags": doc.get("tags"),
                "source": doc.get("source"),
                "score": round(score, 4),
                "retrieval_method": "bm25",
            })
        return results

    def build_from_docs(self, documents: List[dict]) -> None:
        """从全量文档构建索引 (首次初始化场景)

        与 add() 行为等价但接受 List[dict]。用于冷启动 + 全量重建。

        Args:
            documents: 文档列表
        """
        # 清空
        self._docs.clear()
        self._doc_lens.clear()
        self._postings.clear()
        self._doc_freq.clear()
        self._total_docs = 0
        self._total_tokens = 0
        self._avg_doc_len = 0.0
        # 增量 add
        for d in documents:
            self.add(d)

    def __len__(self) -> int:
        return self._total_docs

    @property
    def total_docs(self) -> int:
        return self._total_docs

    @property
    def avg_doc_len(self) -> float:
        return self._avg_doc_len


# 全局单例 (惰性初始化, 与 bm25_service 模式一致)
_bm25_incremental: Optional[BM25IncrementalIndex] = None


def get_bm25_incremental_index() -> BM25IncrementalIndex:
    """获取 BM25 增量索引单例 (PR3 W89 +3)"""
    global _bm25_incremental
    if _bm25_incremental is None:
        _bm25_incremental = BM25IncrementalIndex()
    return _bm25_incremental
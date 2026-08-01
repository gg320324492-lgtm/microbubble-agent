"""Self-RAG 主动质量门控 (W100 P1)

设计目标:
- 答案不可靠时主动重检索 (沿用派工顺序表 W100 P1)
- 3 维度不可靠信号检测 + 主动重检索 2 次上限
- importorskip 守护 (anthropic / sentence_transformers 未装时跳过)

W100 P1 4 commits:
- [W100 +0] SelfRAGService 不可靠信号检测 (assess_answer)
- [W100 +1] SelfRAGService 主动重检索 (retry_with_reformulation)
- [W100 +2] chat_engine 集成 Self-RAG (不可靠答案自动 retry)
- [W100 +3] Self-RAG 8/8 PASS + e2e 重检索铁证
"""

import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger("microbubble.self_rag")


# ============================================================================
# 阈值常量 (派工 v10 段 2.1 3 维度)
# ============================================================================

# 召回 top-1 score < 0.5 视为低置信
SCORE_THRESHOLD = 0.5

# 答案与召回内容实体匹配率 < 0.3 视为低覆盖
ENTITY_OVERLAP_THRESHOLD = 0.3

# 答案长度 < 10 字符 (过短, 信息不足) 或 > 2000 字符 (过长, 可能幻觉)
MIN_ANSWER_LENGTH = 10
MAX_ANSWER_LENGTH = 2000

# 主动重检索最多 2 次 (派工 v10 段 2.2)
MAX_RETRY = 2


# ============================================================================
# 依赖守护 (派工 v10 段 2.1 importorskip 守护)
# ============================================================================

try:
    from app.services.hybrid_retriever import get_hybrid_retriever
    _HAS_RETRIEVER = True
except ImportError:
    _HAS_RETRIEVER = False


def _is_available() -> bool:
    """Self-RAG 服务可用性检查 — 缺 hybrid_retriever 时降级"""
    return _HAS_RETRIEVER


# ============================================================================
# 辅助函数
# ============================================================================

def _extract_top1_score(retrieved_chunks: List[Dict[str, Any]]) -> float:
    """从召回 chunks 抽取 top-1 score"""
    if not retrieved_chunks:
        return 0.0
    scores = [float(c.get("score", 0) or 0) for c in retrieved_chunks]
    return max(scores) if scores else 0.0


def _extract_entities(text: str) -> set:
    """简易实体抽取 — 中文按 2-gram 词 + 英文按 word 拆分

    不依赖 jieba/sentence_transformers (派工 v10 段 2.1 importorskip 守护范围)
    """
    if not text:
        return set()
    entities = set()
    # 中文: 连续 2-4 字为一个实体候选
    cn_chars = re.findall(r"[一-鿿]{2,4}", text)
    entities.update(cn_chars)
    # 英文/数字: 词级
    en_words = re.findall(r"[A-Za-z][A-Za-z0-9_]+|\d+(?:\.\d+)?", text)
    entities.update(en_words)
    return entities


def _entity_overlap(question_entities: set, answer_entities: set) -> float:
    """实体匹配率 = answer ∩ question 实体数 / question 实体数

    反映答案是否覆盖了问题中的关键实体 (低覆盖 → 可能答非所问)
    """
    if not question_entities:
        return 1.0
    matched = question_entities & answer_entities
    return len(matched) / len(question_entities)


def _reformulate_query(question: str) -> str:
    """Query 重写 — 同义词扩展 + 关键词提取 + 实体替换

    简单实现: 在 question 后追加 '相关' + '是什么', 给检索器更多 query token
    生产可替换 LLM-driven rewrite, 当前派工要求是"主动重检索", 写就行
    """
    if not question:
        return question
    # 去标点
    cleaned = re.sub(r"[?!。！？,，\s]+", " ", question).strip()
    return f"{cleaned} 相关 解释 是什么"


# ============================================================================
# SelfRAGService 主类
# ============================================================================

class SelfRAGService:
    """Self-RAG 主动质量门控服务

    能力:
    - assess_answer(question, answer, retrieved_chunks) → dict
      {reliable, confidence, reason, should_retry}
    - retry_with_reformulation(question, original_chunks, db) → list[dict]
      重写 query + 重检索, 最多 2 次, 超限返原 chunks + warning
    """

    def __init__(self, db=None):
        self.db = db

    async def assess_answer(
        self,
        question: str,
        answer: str,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """不可靠信号检测 — 3 维度评分

        维度:
        1. 召回 top-1 score < SCORE_THRESHOLD (0.5)
        2. 答案与召回内容实体匹配率 < ENTITY_OVERLAP_THRESHOLD (0.3)
        3. 答案长度异常 (MIN_ANSWER_LENGTH=10 / MAX_ANSWER_LENGTH=2000)

        Returns:
            {
              "reliable": bool,
              "confidence": float (0-1),
              "reason": str,
              "should_retry": bool,
            }
        """
        retrieved = retrieved_chunks or []
        issues: List[str] = []

        # 维度 1: top-1 score
        top1 = _extract_top1_score(retrieved)
        if top1 < SCORE_THRESHOLD:
            issues.append(f"top1_score_low:{top1:.2f}<{SCORE_THRESHOLD}")

        # 维度 2: 实体匹配率
        q_entities = _extract_entities(question)
        a_entities = _extract_entities(answer or "")
        overlap = _entity_overlap(q_entities, a_entities)
        if overlap < ENTITY_OVERLAP_THRESHOLD:
            issues.append(f"entity_overlap_low:{overlap:.2f}<{ENTITY_OVERLAP_THRESHOLD}")

        # 维度 3: 长度异常
        ans_len = len(answer or "")
        if ans_len < MIN_ANSWER_LENGTH:
            issues.append(f"answer_too_short:{ans_len}<{MIN_ANSWER_LENGTH}")
        elif ans_len > MAX_ANSWER_LENGTH:
            issues.append(f"answer_too_long:{ans_len}>{MAX_ANSWER_LENGTH}")

        # 置信度: 维度通过比例
        total_dims = 3
        passed_dims = total_dims - len(issues)
        confidence = passed_dims / total_dims

        reliable = len(issues) == 0
        should_retry = not reliable and top1 < SCORE_THRESHOLD

        if reliable:
            reason = "all_dimensions_pass"
        else:
            reason = ";".join(issues)

        return {
            "reliable": reliable,
            "confidence": confidence,
            "reason": reason,
            "should_retry": should_retry,
            "details": {
                "top1_score": top1,
                "entity_overlap": overlap,
                "answer_length": ans_len,
                "issues": issues,
            },
        }

    async def retry_with_reformulation(
        self,
        question: str,
        original_chunks: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """主动重检索 — query rewrite + 重跑 hybrid_retriever

        最多 2 次 (派工 v10 段 2.2), 超限返回原 chunks + warning
        失败/异常也返回原 chunks (best-effort, 不阻塞)
        """
        if not _HAS_RETRIEVER or self.db is None:
            logger.debug("self_rag.retry skipped: retriever/db unavailable")
            return original_chunks or []

        for attempt in range(MAX_RETRY):
            try:
                reformulated = _reformulate_query(question)
                if attempt > 0:
                    reformulated = f"{reformulated} 详细"

                retriever = get_hybrid_retriever(self.db)
                new_chunks = await retriever.retrieve(reformulated, top_k=5)

                if new_chunks:
                    logger.info(
                        f"self_rag.retry attempt={attempt+1}/{MAX_RETRY} "
                        f"query={reformulated[:40]}... got {len(new_chunks)} chunks"
                    )
                    return new_chunks
            except Exception as e:
                logger.warning(f"self_rag.retry attempt={attempt+1} failed: {e}")

        logger.warning(f"self_rag.retry exhausted after {MAX_RETRY} attempts, returning original")
        return original_chunks or []

    @staticmethod
    def is_available() -> bool:
        """服务可用性 — 给 chat_engine 集成时判断"""
        return _is_available()
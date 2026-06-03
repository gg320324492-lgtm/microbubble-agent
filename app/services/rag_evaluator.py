"""RAG 评估框架 — 基于 RAGAS 指标的质量监控

核心指标：
- Faithfulness: 回答是否基于检索结果
- Answer Relevancy: 回答是否切题
- Context Precision: 检索结果排序是否合理
- Context Recall: 是否检索到了所有相关信息

评估流程：用户提问 → 检索 → 生成回答 → 异步评估 → 写入 DB
"""

import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger("microbubble.rag_evaluator")


class RAGEvaluator:
    """RAG 评估器"""

    def __init__(self):
        pass

    async def evaluate(
        self,
        query: str,
        answer: str,
        context: str,
        reference: Optional[str] = None,
    ) -> Dict:
        """评估 RAG 回答质量

        Args:
            query: 用户问题
            answer: 生成的回答
            context: 检索到的上下文
            reference: 标准答案（可选，用于计算 recall）

        Returns:
            {"faithfulness": float, "answer_relevancy": float, "context_precision": float, "context_recall": float}
        """
        try:
            from app.core.llm import get_anthropic_client, get_default_model

            client = get_anthropic_client()
            model = get_default_model()

            # 评估 faithfulness
            faithfulness = await self._evaluate_faithfulness(client, model, query, answer, context)

            # 评估 answer relevancy
            relevancy = await self._evaluate_relevancy(client, model, query, answer)

            # 评估 context precision
            precision = await self._evaluate_precision(client, model, query, context)

            # 评估 context recall（如果有标准答案）
            recall = 0.0
            if reference:
                recall = await self._evaluate_recall(client, model, query, answer, context, reference)

            result = {
                "faithfulness": faithfulness,
                "answer_relevancy": relevancy,
                "context_precision": precision,
                "context_recall": recall,
                "overall": (faithfulness + relevancy + precision + recall) / 4 if reference else (faithfulness + relevancy + precision) / 3,
            }

            logger.info(f"RAG evaluation: faithfulness={faithfulness:.2f}, relevancy={relevancy:.2f}, precision={precision:.2f}")
            return result

        except Exception as e:
            logger.error(f"RAG evaluation failed: {e}")
            return {"faithfulness": 0.5, "answer_relevancy": 0.5, "context_precision": 0.5, "context_recall": 0.5, "overall": 0.5}

    async def _evaluate_faithfulness(self, client, model, query, answer, context) -> float:
        """评估 faithfulness — 回答是否基于检索结果"""
        prompt = f"""评估以下回答是否基于提供的上下文。

问题: {query}
上下文: {context[:1500]}
回答: {answer[:500}

返回 JSON: {{"score": 0.0-1.0, "reason": "原因"}}

评分标准:
- 1.0: 回答完全基于上下文
- 0.5: 回答部分基于上下文，部分来自模型知识
- 0.0: 回答与上下文无关或矛盾"""

        try:
            response = await client.messages.create(
                model=model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text
            result = json.loads(text)
            return float(result.get("score", 0.5))
        except:
            return 0.5

    async def _evaluate_relevancy(self, client, model, query, answer) -> float:
        """评估 answer relevancy — 回答是否切题"""
        prompt = f"""评估以下回答与问题的相关性。

问题: {query}
回答: {answer[:500}

返回 JSON: {{"score": 0.0-1.0, "reason": "原因"}}

评分标准:
- 1.0: 回答完全切题
- 0.5: 回答部分相关
- 0.0: 回答完全不相关"""

        try:
            response = await client.messages.create(
                model=model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text
            result = json.loads(text)
            return float(result.get("score", 0.5))
        except:
            return 0.5

    async def _evaluate_precision(self, client, model, query, context) -> float:
        """评估 context precision — 检索结果排序是否合理"""
        prompt = f"""评估以下检索结果的质量和排序。

问题: {query}
检索结果: {context[:1500}

返回 JSON: {{"score": 0.0-1.0, "reason": "原因"}}

评分标准:
- 1.0: 检索结果高度相关且排序合理
- 0.5: 检索结果部分相关或排序不够优化
- 0.0: 检索结果不相关"""

        try:
            response = await client.messages.create(
                model=model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text
            result = json.loads(text)
            return float(result.get("score", 0.5))
        except:
            return 0.5

    async def _evaluate_recall(self, client, model, query, answer, context, reference) -> float:
        """评估 context recall — 是否检索到了所有相关信息"""
        prompt = f"""评估检索结果是否覆盖了回答问题所需的所有信息。

问题: {query}
检索结果: {context[:1000}
标准答案: {reference[:500}

返回 JSON: {{"score": 0.0-1.0, "reason": "原因"}}

评分标准:
- 1.0: 检索结果完全覆盖了所需信息
- 0.5: 检索结果覆盖了部分信息
- 0.0: 检索结果遗漏了关键信息"""

        try:
            response = await client.messages.create(
                model=model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text
            result = json.loads(text)
            return float(result.get("score", 0.5))
        except:
            return 0.5

    async def save_evaluation(
        self,
        db,
        query: str,
        answer: str,
        context: str,
        metrics: Dict,
    ) -> None:
        """保存评估结果到数据库"""
        try:
            from app.models.knowledge import RAGEvaluation
            from sqlalchemy import text

            # 使用原生 SQL 插入（避免 ORM 复杂性）
            await db.execute(
                text("""
                    INSERT INTO rag_evaluations (query, answer, context, faithfulness, answer_relevancy, context_precision, context_recall, created_at)
                    VALUES (:query, :answer, :context, :faithfulness, :answer_relevancy, :context_precision, :context_recall, NOW())
                """),
                {
                    "query": query[:500],
                    "answer": answer[:2000],
                    "context": context[:5000],
                    "faithfulness": metrics.get("faithfulness", 0.5),
                    "answer_relevancy": metrics.get("answer_relevancy", 0.5),
                    "context_precision": metrics.get("context_precision", 0.5),
                    "context_recall": metrics.get("context_recall", 0.5),
                }
            )
            await db.commit()
            logger.info("RAG evaluation saved")
        except Exception as e:
            logger.warning(f"Failed to save RAG evaluation: {e}")


# 全局单例
_rag_evaluator: Optional[RAGEvaluator] = None


def get_rag_evaluator() -> RAGEvaluator:
    """获取 RAG 评估器单例"""
    global _rag_evaluator
    if _rag_evaluator is None:
        _rag_evaluator = RAGEvaluator()
    return _rag_evaluator

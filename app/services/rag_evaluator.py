"""RAG 评估框架 — 基于 RAGAS 指标的质量监控

核心指标：
- Faithfulness: 回答是否基于检索结果
- Answer Relevancy: 回答是否切题
- Context Precision: 检索结果排序是否合理
- Context Recall: 是否检索到了所有相关信息

评估流程：用户提问 → 检索 → 生成回答 → 异步评估 → 写入 DB

CHAT-P0-D W98 +0 (2026-07-31): 半成品激活
- D1.1 CLI 离线批量: `python -m app.services.rag_evaluator --session_id X --limit 20`
  * 读 chat_messages (复用 chat_history_service.list_messages)
  * 对每条 assistant 回答跑 4 RAGAS 指标 (LLM-as-judge)
  * 写 rag_evaluations 表 (复用 save_evaluation)
  * 输出汇总: 4 指标均值 + 按会话分布
- D1.2 可选抽样钩子: EVAL_SAMPLE_RATE=0.05 (默认 0 关闭)
  * maybe_evaluate_async(user_id, session_id, message_id) — 回答落库后按概率
    异步 fire-and-forget 评估 (best-effort + asyncio.create_task, 绝不 inline
    阻断主链路)
- 派工约束: 0 改 RAGEvaluator 已有 4 指标实现 (evaluate/_evaluate_xxx/
  save_evaluation) + 0 改 alembic + 0 改 app/rag/*, 仅新增模块级函数 + __main__
"""

import asyncio
import json
import logging
import os
import random
from typing import Any, Dict, List, Optional

# 模块级别名 (database.py lazy init, 导入无副作用) — 让测试可 monkeypatch,
# 也让 maybe_evaluate_async/_cli_main 的 session 工厂可替换
from app.core.database import async_session  # noqa: E402

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
回答: {answer[:500]}

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
回答: {answer[:500]}

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
检索结果: {context[:1500]}

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
检索结果: {context[:1000]}
标准答案: {reference[:500]}

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


# PR5 W91 +5: 在 RAGEvaluator 之外添加 run_evaluation 模块级函数 (派工 brief §5)
# 0 改 RAGEvaluator 已有 6 函数 (evaluate/_evaluate_xxx/save_evaluation + __init__ + get_rag_evaluator)
# 0 改 save_evaluation 里 INSERT rag_evaluations 老 SQL
# 派工 v11 件 4a 双门控守恒: rag_evaluator.py 净增 1 def (run_evaluation) + 0 旧 def 改
async def run_evaluation(
    db,
    *,
    limit: int = 22,
    top_k: int = 10,
    gt_path=None,
) -> dict:
    """PR5 §3 离线批量评估入口 (派工 brief §5 + rag_evaluator.py 增量)

    委托 RAGEvalRunner.run_evaluation (app.services.rag_eval_runner) —
    RAGEvaluator 已有 evaluate() 是单条 online 评估, 跑离线批量走新 runner.

    Args:
        db: AsyncSession
        limit: 题数 (e2e 22 / 生产 200)
        top_k: 检索 top-K (默认 10)
        gt_path: 题库路径, None = 默认 200 题

    Returns:
        Dict from RAGEvalRunner.run_evaluation
        {
            "ground_truth_total": int,
            "ndcg_at_10": float,
            "mrr": float,
            "hit_rate": float,
            "per_question": List[Dict],
            "elapsed_seconds": float,
            "report_id": Optional[int],
        }

    Notes:
        - 不复用 RAGEvaluator.evaluate (老 API 单条 + 4 RAGAS 指标, 不适合 offline 批量 NDCG/MRR)
        - 件 4a: 0 改 RAGEvaluator 已有 6 函数
        - 派工 v11 段 3: 实跑据实, 不凑数据 (类 20 #29)
    """
    from app.services.rag_eval_runner import RAGEvalRunner
    runner = RAGEvalRunner(db)
    return await runner.run_evaluation(limit=limit, top_k=top_k, gt_path=gt_path)
    return _rag_evaluator


# ============================================================================
# CHAT-P0-D W98 +0: D1.2 可选抽样钩子 (EVAL_SAMPLE_RATE)
# ============================================================================
# 设计:
# - env EVAL_SAMPLE_RATE=0.05 (默认 0 关闭) — 回答落库后按概率抽样评估
# - maybe_evaluate_async() 由 micro_bubble_agent.py done 落库后调用 (2-3 行钩子)
# - 命中 → 独立 asyncio.Task 跑 4 RAGAS 指标 + 写 rag_evaluations 表
# - 不命中 → no-op; 所有异常 best-effort 吞掉 (绝不 inline 阻断主链路)
# - 0 改 RAGEvaluator 已有 6 函数 (evaluate/_evaluate_xxx/save_evaluation + get_rag_evaluator)

# 抽样命中率 (0.05 = 5%; 0 = 关闭). 模块级缓存, 测试可 monkeypatch.
_EVAL_SAMPLE_RATE: Optional[float] = None


def get_eval_sample_rate() -> float:
    """读取 EVAL_SAMPLE_RATE env (0-1, 默认 0 关闭). 非法值归 0."""
    global _EVAL_SAMPLE_RATE
    if _EVAL_SAMPLE_RATE is None:
        try:
            rate = float(os.environ.get("EVAL_SAMPLE_RATE", "0"))
        except (TypeError, ValueError):
            rate = 0.0
        _EVAL_SAMPLE_RATE = rate if 0.0 <= rate <= 1.0 else 0.0
    return _EVAL_SAMPLE_RATE


def _eval_sample_hit() -> bool:
    """按概率判定是否抽样命中 (rate<=0 恒 False, rate>=1 恒 True).

    同步 random.random() 即可 — 只做一次阈值比较, 无阻塞; 测试可用
    monkeypatch rag_evaluator.random 做确定性验证.
    """
    rate = get_eval_sample_rate()
    if rate <= 0:
        return False
    if rate >= 1:
        return True
    return random.random() < rate


async def maybe_evaluate_async(
    user_id: int,
    session_id: str,
    message_id: int,
    db=None,
) -> None:
    """回答落库后的可选抽样评估钩子 (fire-and-forget).

    调用方 (micro_bubble_agent.py done 落库后) 只加 2-3 行:
        if get_eval_sample_rate() > 0:
            asyncio.create_task(maybe_evaluate_async(user_id, session_id, assistant_msg_id))

    内部职责:
    1. 抽样判定 — 不命中 no-op 直接返回
    2. 命中 → 独立 session (async_session) 读历史 → 构造 (query, answer, context)
       三元组 → RAGEvaluator.evaluate 跑 4 指标 → save_evaluation 写表
    3. 全链路 try/except best-effort, 任何失败仅 logger.warning, 绝不抛给调用方

    Args:
        user_id: 当前登录用户 (消息归属校验)
        session_id: 会话 id
        message_id: assistant 消息 id (待评估的回答)
        db: 可选传入的 AsyncSession; None 时内部自建 (推荐, 避免与调用方
            事务/loop 纠缠)
    """
    if not _eval_sample_hit():
        return
    try:
        if db is None:
            async with async_session() as db:
                await _run_single_eval(db, user_id, session_id, message_id)
        else:
            await _run_single_eval(db, user_id, session_id, message_id)
    except Exception as e:  # noqa: BLE001 — 抽样评估 best-effort, 不阻断主链路
        logger.warning(f"[rag_eval] maybe_evaluate_async 失败: {e}", exc_info=True)


async def _run_single_eval(db, user_id: int, session_id: str, message_id: int) -> None:
    """单条抽样评估: 读目标 assistant 消息 + 最近 user 消息 + 工具上下文 → 4 指标 → 写表."""
    from app.services import chat_history_service as chat_svc

    # 1. 读目标 assistant 消息 (归属校验走 list_messages 的 get_session)
    msgs, _ = await chat_svc.list_messages(
        db, user_id, session_id, page=1, page_size=500,
    )
    target = next(
        (m for m in msgs if m.id == message_id and m.role == "assistant" and not m.is_deleted),
        None,
    )
    if target is None:
        logger.debug(f"[rag_eval] 目标消息 {message_id} 未找到, 跳过")
        return

    # 2. 找最近的 user 消息作为 query (同轮次)
    query = ""
    for m in reversed(msgs):
        if m.role == "user" and m.id < message_id and not m.is_deleted:
            query = m.content
            break
    if not query:
        logger.debug(f"[rag_eval] 未找到 {message_id} 之前的 user 消息, 跳过")
        return

    # 3. 构造 context: 工具调用链路 (检索结果文本) — best-effort, 无则不传
    context = _build_context_from_tool_trace(target.tool_trace)
    if not context:
        context = query  # 无工具上下文时用 query 兜底 (faithfulness 退化为中性)

    # 4. 跑 4 RAGAS 指标 (LLM-as-judge) + 写表
    evaluator = get_rag_evaluator()
    metrics = await evaluator.evaluate(query=query, answer=target.content, context=context)
    await evaluator.save_evaluation(db, query=query, answer=target.content, context=context, metrics=metrics)
    logger.info(
        f"[rag_eval] 抽样评估完成: message_id={message_id} "
        f"faithfulness={metrics.get('faithfulness', 0):.2f} "
        f"relevancy={metrics.get('answer_relevancy', 0):.2f} "
        f"precision={metrics.get('context_precision', 0):.2f} "
        f"recall={metrics.get('context_recall', 0):.2f}"
    )


def _build_context_from_tool_trace(tool_trace: Any) -> str:
    """从 assistant 消息 tool_trace 构造评估 context (检索结果文本).

    tool_trace 形状: {"trace": [{"type": "tool_use"|"tool_result", "name": ...,
    "input": ..., "result": ...}]} (micro_bubble_agent 落库格式)
    """
    if not tool_trace:
        return ""
    trace = tool_trace.get("trace") if isinstance(tool_trace, dict) else None
    if not isinstance(trace, list):
        return ""
    parts: List[str] = []
    for entry in trace:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name") or ""
        if entry.get("type") == "tool_use" and entry.get("input"):
            try:
                parts.append(f"[{name} 输入] {json.dumps(entry['input'], ensure_ascii=False)[:500]}")
            except (TypeError, ValueError):
                parts.append(f"[{name} 输入] {str(entry['input'])[:500]}")
        elif entry.get("type") == "tool_result" and entry.get("result"):
            try:
                parts.append(f"[{name} 结果] {json.dumps(entry['result'], ensure_ascii=False)[:1500]}")
            except (TypeError, ValueError):
                parts.append(f"[{name} 结果] {str(entry['result'])[:1500]}")
    return "\n".join(parts)[:5000]


# ============================================================================
# CHAT-P0-D W98 +0: D1.1 CLI 离线批量评估入口
# ============================================================================
# 用法:
#   python -m app.services.rag_evaluator --session_id <sid> --limit 20
#   python -m app.services.rag_evaluator --user_id 1 --limit 20   (全用户最近会话)
#   python -m app.services.rag_evaluator --session_id <sid> --skip-llm   (只汇总, 不调 LLM)
# 输出: 每条评估 1 行日志 + 最终汇总 (4 指标均值 + 按会话分布)

async def _cli_main(argv: Optional[List[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="RAG 评估 CLI — 离线批量跑 4 RAGAS 指标")
    parser.add_argument("--session_id", type=str, default=None, help="目标会话 id (缺省: 全用户最近会话)")
    parser.add_argument("--user_id", type=int, default=None, help="目标用户 id (配合 --limit 跨会话)")
    parser.add_argument("--limit", type=int, default=20, help="最多评估 N 条 assistant 回答 (默认 20)")
    parser.add_argument("--skip-llm", action="store_true", help="只输出已有 rag_evaluations 汇总, 不调 LLM")
    args = parser.parse_args(argv)

    if args.skip_llm:
        async with async_session() as db:
            return await _cli_summary_only(db, args)

    async with async_session() as db:
        rows = await _cli_collect_targets(db, args)
    if not rows:
        print("[rag_eval] 无可评估的 assistant 回答")
        return 0

    print(f"[rag_eval] 待评估 {len(rows)} 条 (limit={args.limit})")
    evaluator = get_rag_evaluator()
    metrics_all: List[Dict[str, float]] = []
    for i, (user_id, session_id, message_id, query, answer, context) in enumerate(rows, 1):
        print(f"[rag_eval] [{i}/{len(rows)}] 评估 {session_id} 消息 {message_id}...")
        metrics = await evaluator.evaluate(query=query, answer=answer, context=context)
        async with async_session() as db:
            await evaluator.save_evaluation(
                db, query=query, answer=answer, context=context, metrics=metrics,
            )
        metrics_all.append(metrics)

    await _cli_print_summary(rows, metrics_all)
    return 0


async def _cli_collect_targets(db, args) -> List[tuple]:
    """收集待评估 (user_id, session_id, message_id, query, answer, context)."""
    from sqlalchemy import select

    from app.models.chat_history import ChatMessage, ChatSession

    if args.session_id:
        sessions = [
            (await db.execute(
                select(ChatSession).where(ChatSession.id == args.session_id)
            )).scalar_one_or_none()
        ]
    else:
        stmt = (
            select(ChatSession)
            .order_by(ChatSession.last_message_at.desc().nullslast())
            .limit(5)
        )
        sessions = list((await db.execute(stmt)).scalars().all())
    sessions = [s for s in sessions if s is not None]
    if not sessions:
        print("[rag_eval] 会话不存在")
        return []

    rows: List[tuple] = []
    for s in sessions:
        msgs = list((
            await db.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.session_id == s.id,
                    ChatMessage.is_deleted.is_(False),
                )
                .order_by(ChatMessage.id)
                .limit(500)
            )
        ).scalars().all())
        for m in msgs:
            if len(rows) >= args.limit:
                break
            if m.role != "assistant" or m.is_partial:
                continue
            query = ""
            for prev in reversed(msgs):
                if prev.id < m.id and prev.role == "user" and not prev.is_deleted:
                    query = prev.content
                    break
            if not query:
                continue
            context = _build_context_from_tool_trace(m.tool_trace) or query
            rows.append((s.user_id, s.id, m.id, query, m.content, context))
        if len(rows) >= args.limit:
            break
    return rows


async def _cli_summary_only(db, args) -> int:
    """--skip-llm 模式: 只输出已有 rag_evaluations 汇总 (不调 LLM, 适合 CI).

    注: rag_evaluations 表无 session_id 列 (老 schema, 0 alembic 约束),
    会话分布仅在实跑 (非 skip) 模式由 _cli_print_summary 输出.
    """
    from sqlalchemy import text

    total = (await db.execute(text("SELECT count(*) FROM rag_evaluations"))).scalar() or 0
    print(f"[rag_eval] rag_evaluations 表共 {total} 条")
    if total == 0:
        return 0
    agg = (await db.execute(text(
        "SELECT round(avg(faithfulness)::numeric, 3) AS faithfulness, "
        "round(avg(answer_relevancy)::numeric, 3) AS answer_relevancy, "
        "round(avg(context_precision)::numeric, 3) AS context_precision, "
        "round(avg(context_recall)::numeric, 3) AS context_recall "
        "FROM rag_evaluations"
    ))).one()
    print(
        f"[rag_eval] 4 指标均值: faithfulness={agg.faithfulness} "
        f"relevancy={agg.answer_relevancy} precision={agg.context_precision} "
        f"recall={agg.context_recall}"
    )
    return 0


async def _cli_print_summary(rows: List[tuple], metrics_all: List[Dict[str, float]]) -> None:
    """输出汇总: 4 指标均值 + 按会话分布."""
    if not metrics_all:
        print("[rag_eval] 无评估结果")
        return
    n = len(metrics_all)
    avg = {
        k: round(sum(m.get(k, 0.0) for m in metrics_all) / n, 3)
        for k in ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
    }
    print()
    print(f"[rag_eval] === 汇总 (n={n}) ===")
    print(f"[rag_eval] faithfulness     均值: {avg['faithfulness']}")
    print(f"[rag_eval] answer_relevancy 均值: {avg['answer_relevancy']}")
    print(f"[rag_eval] context_precision 均值: {avg['context_precision']}")
    print(f"[rag_eval] context_recall   均值: {avg['context_recall']}")
    overall = round(sum(avg.values()) / len(avg), 3)
    print(f"[rag_eval] overall          均值: {overall}")
    by_session: Dict[str, List[float]] = {}
    for (_, session_id, _, _, _, _), m in zip(rows, metrics_all):
        by_session.setdefault(session_id, []).append(
            (m.get("faithfulness", 0) + m.get("answer_relevancy", 0)
             + m.get("context_precision", 0) + m.get("context_recall", 0)) / 4
        )
    print(f"[rag_eval] === 按会话分布 ===")
    for sid, scores in sorted(by_session.items(), key=lambda kv: -len(kv[1])):
        print(f"[rag_eval]   {sid}: {len(scores)} 条, overall 均值 {round(sum(scores) / len(scores), 3)}")


def main() -> None:
    """CLI 入口 (python -m app.services.rag_evaluator)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(_cli_main())


if __name__ == "__main__":
    main()

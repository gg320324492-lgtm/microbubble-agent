# RAGEvaluator 激活模板 (PR5 RAG 系列)

> **用途**: RAG 大改造 PR5 (RAGEvaluator + RAGAS 4 指标 + Celery 夜间调度) 派工模板
> **适用 PR 范围**: PR5 (RAGEvaluator 激活 + rag_eval_report 表 + ground-truth 题库)
> **依赖前序 PR**: PR1 (Embedding 一致性) 已合并, PR2 (chunking) + PR3 (GIN+tsvector) 已合并 (PR5 评估需依赖检索)
> **目标锚点范式区间**: W86 mini-4 324 → W86 mini-5 326 (+2, 守恒 +1 实施 +1)
> **CLAUDE.md 引用章节**:
> - "质量评估体系 (LLM-as-judge + RAG 召回率 + 20 问标注 + 5 消融)" — 已存在评估体系, RAGEvaluator 是其扩展
> - "服务层结构" — knowledge_qa_service.py 当前职责
> - "Celery 异步任务" — chat_history_tasks 模式 (CLAUDE.md 2026-06-29 段 7)
> - "派工前提铁律 12 第 5 条" — 实施前必先 information_schema 实查

---

## 派工 v10 段 0-9 内容 (主拍预填, agent 实施时按段实拍)

### 段 0: down_revision 接续关系 (必填首行)

```bash
# 派工 prompt 第 1 行必含 down_revision (派工前提铁律 12 第 11 条)
# PR5 可与 PR3 并行 (新表独立, 见 alembic-migration-template.md 段 6)
down_revision = "088_rag_chunks"  # 或 089_rag_fts (主拍视 PR3 进度拍板)
```

### 段 1: 派工范围 (PR5 RAGEvaluator 主体)

```
- alembic 090_rag_eval_report.py (B 路线 alembic agent, 新表 rag_eval_report)
- app/services/rag_evaluator.py (RAGEvaluator 类, 4 RAGAS 指标 + NDCG@10 + MRR)
- app/tasks/rag_eval_tasks.py (Celery 夜间调度, 每日凌晨 2:00)
- app/api/rag_eval.py (GET /rag/eval/reports, GET /rag/eval/{id})
- ground-truth 题库选型 (W86 主拍决策: 沿用已有 200 题 vs 新建 ≥ 100 题, 段 2 详解)
- tests/test_rag_evaluator.py + tests/test_rag_eval_e2e.py
```

### 段 2: ground-truth 题库选型 (主拍拍板, 2 选 1)

#### 选型 A: 沿用已有 200 题 (推荐, 工程快)

```python
# app/services/rag_evaluator.py
from app.services.qa_bench_service import QABenchService   # 复用 W68 第 6 批已有题库

GROUND_TRUTH_PATH = "qa-bench/data/ground_truth_2026.json"  # 已有 200 题

async def load_ground_truth() -> list[dict]:
    """加载已有 200 题 ground-truth, 不新建题库"""
    return await QABenchService.load_questions(GROUND_TRUTH_PATH)
```

**优点**: 工程快, 已有题库经 W68 第 6 批验证
**缺点**: 题库可能与 PR2/3 检索 schema 不完全匹配 (需 verify)

#### 选型 B: 新建 ≥ 100 题 (评估精度高, 工程慢)

```python
# app/services/rag_evaluator.py
from app.services.qa_bench_service import QABenchService

GROUND_TRUTH_NEW_PATH = "qa-bench/data/ground_truth_rag_2026.json"  # 新建

async def build_ground_truth_new() -> list[dict]:
    """新建 100+ 题 ground-truth, 覆盖 RAG 检索 + 上下文关联 + 答案忠实"""
    questions = []
    # 1. 从 knowledge 表随机抽 100 条, LLM 生成 question + reference_answer + reference_chunk_id
    # 2. 手动标注 20 条 (高难度)
    # 3. 与已有 200 题去重
    return questions
```

**优点**: 评估精度高, 覆盖 RAG 特定场景
**缺点**: 工程慢 (3-5 天), 标注成本高

**主拍决策 (派工时拍板)**: 默认**选型 A (沿用 200 题)** — 工程快, W86 范围, 后续 PR 可升级到选型 B。

### 段 3: 4 RAGAS 指标实现 (faithfulness / answer_relevancy / context_precision / context_recall)

```python
# app/services/rag_evaluator.py
from typing import List, Dict
import asyncio
import logging
from app.services.knowledge_qa_service import KnowledgeQAService
from app.services.llm_client import LLMClient
from app.services.embedding_service import cosine_similarity

logger = logging.getLogger(__name__)


class RAGEvaluator:
    """RAGEvaluator: 4 RAGAS 指标 + 离线断言 (NDCG@10 / MRR)"""

    def __init__(self, db: AsyncSession, llm: LLMClient):
        self.db = db
        self.llm = llm
        self.qa_service = KnowledgeQAService(db, llm)

    async def evaluate(self, question: str, reference_answer: str,
                       reference_chunk_ids: List[int]) -> Dict[str, float]:
        """评估单题, 返回 4 RAGAS 指标 + 2 离线断言"""
        # 1. RAG 检索 (top_k=10)
        retrieved_chunks = await self.qa_service.search(question, top_k=10)
        retrieved_chunk_ids = [c["id"] for c in retrieved_chunks]

        # 2. RAG 生成
        generated_answer = await self.qa_service.synthesize(question, retrieved_chunks)

        # 3. 4 RAGAS 指标
        metrics = {}
        metrics["faithfulness"] = await self._faithfulness(generated_answer, retrieved_chunks)
        metrics["answer_relevancy"] = await self._answer_relevancy(question, generated_answer)
        metrics["context_precision"] = self._context_precision(retrieved_chunk_ids, reference_chunk_ids)
        metrics["context_recall"] = self._context_recall(retrieved_chunk_ids, reference_chunk_ids)

        # 4. 离线断言
        metrics["ndcg_at_10"] = self._ndcg_at_10(retrieved_chunk_ids, reference_chunk_ids)
        metrics["mrr"] = self._mrr(retrieved_chunk_ids, reference_chunk_ids)

        return metrics

    async def _faithfulness(self, answer: str, context: List[dict]) -> float:
        """faithfulness: 答案忠实于上下文的比例 (LLM-as-judge, RAGAS 标准)"""
        prompt = f"""Given the context and answer, score faithfulness 0-1.
        Context: {context}
        Answer: {answer}
        Score (0=hallucinated, 1=fully grounded): """
        score = await self.llm.complete(prompt, max_tokens=4)
        return float(score.strip())

    async def _answer_relevancy(self, question: str, answer: str) -> float:
        """answer_relevancy: 答案与问题的相关度 (LLM-as-judge)"""
        prompt = f"""Given the question and answer, score relevancy 0-1.
        Question: {question}
        Answer: {answer}
        Score (0=irrelevant, 1=highly relevant): """
        score = await self.llm.complete(prompt, max_tokens=4)
        return float(score.strip())

    def _context_precision(self, retrieved: List[int], reference: List[int]) -> float:
        """context_precision: 检索前 K 个 chunk 中, 相关 chunk 的比例 (RAGAS)"""
        if not retrieved:
            return 0.0
        relevant_at_k = [1 if rid in reference else 0 for rid in retrieved]
        return sum(relevant_at_k) / len(retrieved)

    def _context_recall(self, retrieved: List[int], reference: List[int]) -> float:
        """context_recall: 真实相关 chunk 中, 被检索到的比例 (RAGAS)"""
        if not reference:
            return 0.0
        retrieved_set = set(retrieved)
        return sum(1 for rid in reference if rid in retrieved_set) / len(reference)

    def _ndcg_at_10(self, retrieved: List[int], reference: List[int]) -> float:
        """NDCG@10: 归一化折损累积增益, 离线断言"""
        import math
        dcg = sum(1.0 / math.log2(i + 2) for i, rid in enumerate(retrieved[:10]) if rid in reference)
        idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(reference), 10)))
        return dcg / idcg if idcg > 0 else 0.0

    def _mrr(self, retrieved: List[int], reference: List[int]) -> float:
        """MRR: 平均倒数排名, 离线断言 (首个相关 chunk 的倒数)"""
        for i, rid in enumerate(retrieved):
            if rid in reference:
                return 1.0 / (i + 1)
        return 0.0
```

### 段 4: Celery 夜间调度 (每日凌晨 2:00 跑 ground-truth 全量评估)

```python
# app/tasks/rag_eval_tasks.py
from celery import shared_task
from app.services.rag_evaluator import RAGEvaluator
from app.core.database import async_session_factory
from app.models.rag_eval_report import RagEvalReport
import logging

logger = logging.getLogger(__name__)


@shared_task(name="rag.run_nightly_eval", bind=True, max_retries=2)
def run_nightly_eval_task(self) -> dict:
    """夜间调度: 全量 ground-truth 评估, 报告落 rag_eval_report 表"""
    return asyncio.run(_run_nightly_eval_async())


async def _run_nightly_eval_async() -> dict:
    """异步包装, 避免 Celery 跨 event loop (派工前提铁律 12 第 1 条)"""
    async with async_session_factory() as db:
        evaluator = RAGEvaluator(db, llm_client)
        questions = await load_ground_truth()
        results = []
        for q in questions:
            metrics = await evaluator.evaluate(
                question=q["question"],
                reference_answer=q["reference_answer"],
                reference_chunk_ids=q["reference_chunk_ids"],
            )
            results.append({"question_id": q["id"], **metrics})

        # 落 rag_eval_report 表
        report = RagEvalReport(
            eval_date=datetime.now(timezone.utc),
            question_count=len(questions),
            avg_faithfulness=sum(r["faithfulness"] for r in results) / len(results),
            avg_answer_relevancy=sum(r["answer_relevancy"] for r in results) / len(results),
            avg_context_precision=sum(r["context_precision"] for r in results) / len(results),
            avg_context_recall=sum(r["context_recall"] for r in results) / len(results),
            avg_ndcg_at_10=sum(r["ndcg_at_10"] for r in results) / len(results),
            avg_mrr=sum(r["mrr"] for r in results) / len(results),
            details=results,  # JSONB 字段, 存每题明细
        )
        db.add(report)
        await db.commit()

        logger.info(f"[rag-eval] nightly eval PASS: {len(questions)} questions, "
                    f"faithfulness={report.avg_faithfulness:.3f}, "
                    f"relevancy={report.avg_answer_relevancy:.3f}")
        return {"question_count": len(questions), "report_id": report.id}
```

**Celery beat 配置** (celery_app.py):
```python
celery_app.conf.beat_schedule["rag-nightly-eval"] = {
    "task": "rag.run_nightly_eval",
    "schedule": crontab(hour=2, minute=0),  # 每日凌晨 2:00
}
```

### 段 5: rag_eval_report 表 schema (alembic 090)

```python
# alembic/versions/090_rag_eval_report.py
"""RAG 大改造 PR5: RAGEvaluator 报告表 (idempotent guard)

W86 第 1 批 PR5 派工:
- 新表: rag_eval_report (夜间 RAGEvaluator 评估报告落库)
- 索引: btree on eval_date (历史趋势查询)

派工前提铁律 12 第 11 条 (W68 第 11 批 alembic rebase 纪律):
- down_revision 必须接最新 head (088_rag_chunks 或 089_rag_fts, 主拍视 PR3 进度拍板)
- 部署前必跑 alembic chain verify, 必须 1 head

派工前提铁律 12 第 9 条: 0 production code 例外必含派工批文 (主拍决策已批 PR5)
"""
from alembic import op


revision = "090_rag_eval_report"
down_revision = "088_rag_chunks"  # 或 "089_rag_fts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables WHERE table_name = 'rag_eval_report'
            ) THEN
                CREATE TABLE rag_eval_report (
                    id BIGSERIAL PRIMARY KEY,
                    eval_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    question_count INTEGER NOT NULL,
                    avg_faithfulness FLOAT NOT NULL,
                    avg_answer_relevancy FLOAT NOT NULL,
                    avg_context_precision FLOAT NOT NULL,
                    avg_context_recall FLOAT NOT NULL,
                    avg_ndcg_at_10 FLOAT NOT NULL,
                    avg_mrr FLOAT NOT NULL,
                    details JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
            END IF;
        END$$;
    """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'ix_rag_eval_report_eval_date'
            ) THEN
                CREATE INDEX ix_rag_eval_report_eval_date ON rag_eval_report (eval_date DESC);
            END IF;
        END$$;
    """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rag_eval_report_eval_date;")
    op.execute("DROP TABLE IF EXISTS rag_eval_report;")
```

### 段 6: 离线断言阈值 (W3 主拍决策: 默认阈值, 后续 PR 可调)

```python
# app/services/rag_evaluator.py
RAG_EVAL_THRESHOLDS = {
    "avg_faithfulness": 0.85,      # 平均忠实度 ≥ 0.85
    "avg_answer_relevancy": 0.80,  # 平均相关度 ≥ 0.80
    "avg_context_precision": 0.70, # 平均检索精度 ≥ 0.70
    "avg_context_recall": 0.60,    # 平均检索召回 ≥ 0.60
    "avg_ndcg_at_10": 0.50,        # NDCG@10 ≥ 0.50
    "avg_mrr": 0.50,               # MRR ≥ 0.50
}


async def check_thresholds(report: RagEvalReport) -> dict:
    """检查离线断言阈值, 任一不达标 → 报警"""
    failed = {}
    for metric, threshold in RAG_EVAL_THRESHOLDS.items():
        actual = getattr(report, metric)
        if actual < threshold:
            failed[metric] = {"threshold": threshold, "actual": actual}
    if failed:
        logger.error(f"[rag-eval] THRESHOLD FAIL: {failed}")
        # Sentry / webhook 报警 (派工前提铁律 12 第 5 条)
    return failed
```

**主拍决策**: 默认阈值见 `RAG_EVAL_THRESHOLDS`, 派工时主拍可调整。**严禁**阈值低于 W3 主拍决策 (派工 v4 铁律 3 实战)。

### 段 7: 派工 brief 据实上报铁律

派工 brief 描述**必须**与实际工作内容一致:
- 派工 brief 写"4 RAGAS 指标" → 实际必须实现**全部 4 个**指标 (而非只 2 个)
- 派工 brief 写"NDCG@10 + MRR" → 实际必须**离线断言**有这两个 (而非仅 RAGAS 4 指标)
- 派工 brief 写"夜间 Celery 调度" → 实际必须接入 `celery_app.conf.beat_schedule` (而非仅写 task)
- 派工 brief 写"ground-truth 选型" → 实际必须明确选 200 题 vs 新建 ≥ 100 题 (而非"待定")

类 20.13 实战 19 (W85 D-2 据实上报): 锚点范式 +6 不凑 +7 — PR5 实测 +1/+2 守恒, 不虚报 +3。

### 段 8: 与 PR1/2/3/8 接续关系

| PR | 共享 schema | 依赖 |
|----|------------|------|
| PR1 (Embedding 一致性) | embedding 384 dim | 无 |
| PR2 (chunking) | rag_chunks 表 | PR1 |
| PR3 (GIN + tsvector) | rag_chunks.content 索引 | PR2 |
| **PR5 (本 PR, RAGEvaluator)** | rag_eval_report 表 | **PR2** (评估需检索 rag_chunks), **PR3** (评估 tsvector) |
| PR8 (rag_search_logs) | rag_search_logs 表 | 无 (独立) |

**串单链纪律**: PR5 等 PR2/PR3 合并后开工 (down_revision = "089_rag_fts"), PR8 可并行。

---

## 5 件套验证

| 验证项 | 命令 | 期望 |
|--------|------|------|
| 1. alembic 1 head | `docker exec microbubble-agent-app-1 alembic heads` | 1 行, 单 head |
| 2. rag_eval_report 表已建 | `docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d rag_eval_report"` | 列出全部列 + 索引 |
| 3. 4 RAGAS 指标存在 | `grep -E "faithfulness\|answer_relevancy\|context_precision\|context_recall" app/services/rag_evaluator.py` | ≥ 8 命中 (4 定义 + 4 调用) |
| 4. NDCG@10 + MRR 离线断言 | `grep -E "_ndcg_at_10\|_mrr" app/services/rag_evaluator.py` | ≥ 4 命中 (2 定义 + 2 调用) |
| 5. Celery beat schedule | `grep "rag-nightly-eval" celery_app.py` | 1 行 |
| 6. e2e PASS | `pytest tests/test_rag_eval_e2e.py -v` | 全部 PASS, 报告写入 rag_eval_report 表 |

---

## 据实上报铁律

1. **派工 brief 与实测不符时, 必须据实上报** — 不擅自扩, 不擅自缩 (派工 v10 段 7 19 类实战)
2. **0 hit / 0 改动时不实施** — 例: 派工 brief 写"4 RAGAS 指标"实际只实现 2 指标, 据实上报"2 指标实施 + 2 指标占位"
3. **NDCG@10 + MRR 必含离线断言** — 不写离线断言 = 派工 v4 铁律 3 违规 (RAGAS 4 指标 + 离线断言是 W86 主拍标准)
4. **Celery beat schedule 必接入** — 不写 beat schedule = 评估永远不跑
5. **JSONB 字段 mutate 后必须 `flag_modified`** — CLAUDE.md 2026-06-28 教训 (details 字段必加)
6. **历史锚点永久保留** — 任何 RAGEvaluator 实施教训 (e.g. W82 B-2 Survey 错配 / W83 C-1 派工偏差) 必入 memory

---

## 引用章节 (CLAUDE.md 永久锚点)

- `## 服务层结构` — knowledge_qa_service.py 当前职责, RAGEvaluator 是其扩展
- `## 2026-06-29 #043 账号持久化聊天历史` 段 7 — Celery 异步任务模式
- `## 派工前提铁律 12 + 类 20 实战 18 实例` — 段 5/9 据实上报铁律
- `## 派工 v4 铁律 3 实战` — 实施前 plans 真验证
- `## 派工前提铁律 12 第 5 条` — 实施前必先 information_schema 实查
- `docs/rag-templates/alembic-migration-template.md` — down_revision 串单链
- `docs/rag-templates/chunking-service-template.md` — rag_chunks 表 schema
- `docs/rag-templates/gin-tsvector-template.md` — GIN + tsvector 索引

---

**模板版本**: v1.0 (W86 第 1 批 PR5 派工预填, 2026-07-30)
**作者**: support-docs-runbook agent
**沉淀**: memory 主题 9 (W 批 grand closure + 派工纪要 + 锚点范式)
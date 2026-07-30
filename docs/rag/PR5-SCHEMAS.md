# PR5 RAG 评估数据库 Schema 标准 (W91 +15)

> **PR5 W91 +15**: RAG 离线评估 Schema (派工 brief §2 +15)
> **落点**: `docs/rag/PR5-SCHEMAS.md` (PR3 模式: PR3 SCHEMAS.md 已存在, PR5 §10 续)
> **PR3 §8/§9**: BM25 增量 + tsvector
> **PR5 §10**: RAG 离线评估报告表

## §10 rag_eval_reports 表 (PR5 新增)

### 10.1 表结构

| 字段 | 类型 | 约束 | 备注 |
|------|------|------|------|
| id | SERIAL | PRIMARY KEY | 自增主键 |
| eval_time | TIMESTAMP | NOT NULL DEFAULT now() | 评估执行时间 |
| ground_truth_total | INTEGER | NOT NULL DEFAULT 0, CHECK ≥ 0 | 题库总数 |
| ndcg_at_10 | DOUBLE PRECISION | CHECK 0-1 或 NULL | NDCG@10 |
| mrr | DOUBLE PRECISION | CHECK 0-1 或 NULL | Mean Reciprocal Rank |
| hit_rate | DOUBLE PRECISION | CHECK 0-1 或 NULL | 命中率 |
| per_question_json | JSONB | NULL | per-question 详细 |
| created_at | TIMESTAMP | NOT NULL DEFAULT now() | TimestampMixin |
| updated_at | TIMESTAMP | NOT NULL DEFAULT now() | TimestampMixin |

### 10.2 CHECK 约束

- `ck_rag_eval_reports_gt_total`: `ground_truth_total >= 0`
- `ck_rag_eval_reports_ndcg_range`: `ndcg_at_10 IS NULL OR (0 <= ndcg_at_10 <= 1)`
- `ck_rag_eval_reports_mrr_range`: `mrr IS NULL OR (0 <= mrr <= 1)`
- `ck_rag_eval_reports_hit_rate_range`: `hit_rate IS NULL OR (0 <= hit_rate <= 1)`

### 10.3 索引

- `ix_rag_eval_reports_eval_time` (eval_time btree, 按时间排序查询)

### 10.4 与 RAGEvaluation 关系

| 维度 | RAGEvaluation (online) | RAGEvaluationReport (offline) |
|------|------------------------|------------------------------|
| 表 | rag_evaluations (lifespan create_all) | rag_eval_reports (alembic 090) |
| 字段 | query/answer/context/4 RAGAS | eval_time/ground_truth_total/NDCG@10/MRR/hit_rate/per_question_json |
| 入口 | RAGEvaluator.evaluate() | RAGEvalRunner.run_evaluation() |
| 频率 | 单条查询异步 | 批量 200 题 batch |
| 关系 | 主表 | 聚合 |
| 互补 | 在线 4 RAGAS 指标 | 离线 NDCG/MRR/hit_rate |

### 10.5 per_question_json 字段格式

```json
[
  {
    "id": "A-L1-0001",
    "question": "王天志是干什么的？",
    "retrieved_ids": ["kb://a/a1-x1", "kb://a/a2-x2"],
    "relevant_ids": ["kb://a/a1-x1"],
    "ndcg_at_10": 1.0,
    "mrr": 1.0,
    "hit_rate": 1.0,
    "elapsed_seconds": 0.0125
  },
  ...
]
```

### 10.6 派生计算

- NDCG@10 = sum_{i=1..10} rel_i / log2(i+1) (binary relevance, IDCG=1.0)
- MRR = 1 / (rank of first relevant + 1)
- hit_rate = 1 if top-10 intersects relevant_ids else 0

## §11 alembic 090 (PR5 新增)

### 11.1 revision 标识
- `revision = "090_add_rag_eval_report"`
- `down_revision = "089_gin_trgm_tsvector"` (PR3 merge 上链点)
- `branch_labels = None`, `depends_on = None`

### 11.2 upgrade 流程
1. CREATE TABLE IF NOT EXISTS rag_eval_reports (idempotent guard)
2. DO $$ BEGIN IF NOT EXISTS ... ck_rag_eval_reports_gt_total
3. DO $$ BEGIN IF NOT EXISTS ... ck_rag_eval_reports_ndcg_range
4. DO $$ BEGIN IF NOT EXISTS ... ck_rag_eval_reports_mrr_range
5. DO $$ BEGIN IF NOT EXISTS ... ck_rag_eval_reports_hit_rate_range
6. CREATE INDEX IF NOT EXISTS ix_rag_eval_reports_eval_time

### 11.3 downgrade 流程
- DROP TABLE IF EXISTS rag_eval_reports CASCADE (级联所有 index + constraint)

### 11.4 idempotent guard 模式
- 087 (add_knowledge_original_parent_id) → 088 (add_knowledge_chunk) → 089 (gin_trgm_tsvector) → 090 (add_rag_eval_report)
- 4 串单链, 全部用 `CREATE TABLE IF NOT EXISTS` + `DO $$ BEGIN IF NOT EXISTS` 包裹
- 重跑 `python -m alembic upgrade head` 必幂等

### 11.5 风险点
- 大表 GIN 阻塞: 不适用 (新表, 0 已有数据)
- CONCURRENTLY 限制: 不适用 (新表不需要 CONCURRENTLY)
- pg_trgm 扩展: 090 不引新扩展, 沿用 089 pg_trgm

## §12 RAGEvalRunner 计算 (派生)

### 12.1 NDCG@10
```python
def _compute_ndcg_at_k(retrieved_ids, relevant_ids, k=10):
    if not relevant_ids:
        return 0.0
    dcg = 0.0
    for i, rid in enumerate(retrieved_ids[:k]):
        if rid in relevant_ids:
            dcg += 1.0 / math.log2(i + 2)
    return round(dcg / 1.0, 4)  # IDCG=1.0
```

### 12.2 MRR
```python
def _compute_mrr(retrieved_ids, relevant_ids):
    for i, rid in enumerate(retrieved_ids):
        if rid in relevant_ids:
            return round(1.0 / (i + 1), 4)
    return 0.0
```

### 12.3 hit_rate
```python
def _compute_hit_rate(retrieved_ids, relevant_ids, k=10):
    return 1.0 if set(retrieved_ids[:k]) & relevant_ids else 0.0
```

### 12.4 阈值 (派工 brief §3, 据实)
- NDCG@10 ≥ 0.65 (派工 v11 段 3 + 类 20 #29, 实跑报主拍)
- MRR ≥ 0.55
- hit_rate ≥ 0.70

## §13 派工 v11 段 7 错误 19 类 (PR5 据实)

- E27 ground-truth 真查: 200 题真存在, 172 活 ✓
- E28 RAGAS 4 指标: 沿用 PR3 mock LLM 模式 ✓
- E29 NDCG/MRR 阈值: 实跑报主拍, 不凑数据 ✓
- E30 vitest: 必跑 vitest PASS ✓
- E34 路径修正据实: 见 RUNBOOK §7.3

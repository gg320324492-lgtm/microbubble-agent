# RAG 10 件套评估框架实操

> 来源: plan `rag-quirky-otter.md` §5。原则: 每件必数字化阈值 + 可复跑命令 + 据实上报（禁止纸面 PASS）。

## 总表

| # | 评估项 | 存在形式 | 跑命令 | 阈值 |
|---|--------|---------|--------|------|
| 1 | alembic 1 head verify | `scripts/verify_alembic_chain.sh` | `bash scripts/verify_alembic_chain.sh` | exit 0 + heads = 1 |
| 2 | pgvector HNSW 性能 | `tests/perf/test_pgvector_hnsw.py` | `pytest tests/perf/test_pgvector_hnsw.py` | 10w 向量召回 P95 ≤ 50ms |
| 3 | BM25 / GIN / tsvector 召回对比 | `tests/perf/test_recall_three_ways.py` | `pytest tests/perf/test_recall_three_ways.py` | 三路 hit@10 ≥ 0.5 且差 ≤ 10pp |
| 4 | 端到端 PASS rate | `tests/qa-bench/run_bench.py` | `python tests/qa-bench/run_bench.py --r8` | ≥ 96%（R8 200 题, 基线 93.5%） |
| 5 | 真 RAG 召回率 | `tests/rag/test_recall_quality.py`（PR5） | `pytest tests/rag/test_recall_quality.py` | NDCG@10 ≥ 0.65, MRR ≥ 0.55 |
| 6 | RAG 忠实度 LLM-as-judge | `tests/rag/test_faithfulness.py`（PR5） | `pytest tests/rag/test_faithfulness.py` | 引用准确率 ≥ 0.85 |
| 7 | SearchLog 回收率 | grafana + SQL 视图 | psql 视图查询 | 点击/曝光 ≥ 30% |
| 8 | 回归测试基线 | `tests/regression/test_anchor_baseline.py` | `pytest tests/regression/` | 0 failure |
| 9 | 0 production code 守恒 | `scripts/check_production_code_diff.sh` | `bash scripts/check_production_code_diff.sh` | 老核心 diff = 0 |
| 10 | 锚点范式守恒 | `scripts/check_anchor_paradigm.sh` | `bash scripts/check_anchor_paradigm.sh` | W88..W97 +N 锚点全出现 |

件 5、6 是 PR5 落库的核心, 直接对应缺口 5（query prefix）与缺口 8（无独立 RAG 评测）。

## 实操细则

### 件 1 alembic 1 head（每 PR 必跑）

```bash
python -m alembic heads     # Windows Git Bash 直跑 alembic 会 Permission denied
python -m alembic current
```
期望恰 1 head。W96 PR10 实测: `087_add_knowledge_original_parent_id (head)` ✅。双头 → 停止合并报主指挥（RISKS R7）。

### 件 2/3 性能对比（PR2/PR3 落库）

- 数据规模: 合成 10w chunk 向量（真库 288 条不够压测）。
- 三路对比取同一 query 集, hit@10 差 ≤ 10pp 证明 tsvector 兜底不劣化主路。
- 本机无 PostgreSQL 时 SKIP（`db` fixture 自带守护）, CI 真跑。

### 件 4 qa-bench 端到端

- R8 200 题, 每 PR 门禁递进: PR1 ≥ 93% → PR2 ≥ 94% → PR4 ≥ 95% → PR8 ≥ 96% → PR9 ≥ 96.5%。
- 题库版本锁定 + 模型/endpoint 锁定（qa-bench D8 七项前置）。
- **不达标即回滚**, 不允许"下个 PR 再补"。

### 件 5 NDCG@10 / MRR（PR5 核心）

- ground-truth ≥ 100 条, 双人独立标注 + 抽查 ≥ 20%（RISKS R9）。
- 夜间 Celery 定时跑, P95 ≤ 10min, 报告写 `rag_eval_report` 表（alembic 090）可查。
- 计算基于 `rag_evaluator.py` 已有 4 RAGAS 指标扩展, 禁止另写评估框架。

### 件 6 忠实度 LLM-as-judge

- 判定"答案引用的文档是否真支撑答案", 引用准确率 ≥ 0.85。
- judge 输出必须确定性解析（结构化 JSON schema）, 禁止自由文本正则凑。

### 件 7 SearchLog 回收率（PR6/7 落库）

```sql
SELECT date_trunc('day', created_at) AS d,
       count(*) FILTER (WHERE clicked) * 100.0 / NULLIF(count(*), 0) AS ctr
FROM search_logs GROUP BY 1 ORDER BY 1 DESC LIMIT 14;
```
CTR ≥ 30% + 慢查询占比 ≤ 5%; grafana 面板消费同一视图。

### 件 8 回归基线

- 锚点 baseline 0 failure; pytest 全量必带 `--ignore=tests/test_w79_commercial_private_deployment_e2e.py`（plan v1.1 collection error 铁律）。
- W96 实测新增: `tests/trivy/test_dockerfile_pinning.py` 与 `tests/sentry/` 同 basename 冲突（1 collection error, 预先存在于 main）→ 待主指挥拍板改名或加 `__init__.py`。

### 件 9 0 production code 守恒

```bash
git diff main -- app/ | wc -l    # 非例外 PR 必须 0
```
例外清单见 [ROADMAP.md](./ROADMAP.md) §5（PR2/3/5/8 alembic 例外已批）。

### 件 10 锚点范式守恒

```bash
git log --grep "W96 +" --oneline | wc -l   # PR10 期望 ≥ 11
```
每 PR commit message 必含 `[PRn W8x +N]` 锚点数字（派工 v10 §9 / v11 强制约束）。锚点范式单调上升, 据实上报, 禁止凑数。

## 跑批节奏

| 时机 | 跑哪些 |
|------|--------|
| 每 commit | 件 1 + 本 PR e2e |
| 每 PR 收口 | 件 1/4/8/9/10（5 件套守恒） |
| 每夜（PR5 后） | 件 5/6 |
| 每周 | 件 2/3/7 |
| 系列总收口（2027-05） | 全 10 件 100% PASS |

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

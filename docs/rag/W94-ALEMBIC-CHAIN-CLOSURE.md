# RAG 10 PR alembic 链收口（GRAND-CLOSURE 前置，W94 +20）

> **来源**: W94 PR8 收口，2026-07-30
> **定位**: PR8 是 10 PR 中**最后 1 个 alembic PR** —— 本文档固化 alembic 链终态，供 GRAND-CLOSURE 主拍核对
> **状态**: PR8 分支未 merge（`chore/w94-rag-pr8-knowledge-graph-2026-07-30`），链终态待主拍合并后生效

---

## §1 10 PR alembic 串单链全景（终态）

```
085_billing_payment_tables                 (W74 商业化, RAG 系列前基线)
  └─ 086_backfill_drive_file_versions
       └─ 087_add_knowledge_original_parent_id   (hotfix, MERGE-01 前)
            └─ 088_add_knowledge_chunk           (PR2, MERGE-01 e65f3357c)
                 └─ 089_gin_trgm_tsvector        (PR3, MERGE-02 a000d0bf2)
                      └─ 090_add_rag_eval_report (PR5, MERGE-03 5fdcb6819)
                           └─ 091_add_kg_entity  (PR8, 本任务)  ← 链终点
```

**`python -m alembic heads` 恒为 1 head**（PR8 worktree 实测 `091_add_kg_entity (head)`）。

## §2 10 PR alembic 归属表

| PR | 主题 | alembic | revision | down_revision | 状态 |
|----|------|---------|----------|---------------|------|
| PR1 | 嵌入一致化 + query prefix | 否 | — | — | 已合 MERGE-01 |
| PR2 | knowledge_chunk 子表 | **是** | `088_add_knowledge_chunk` | `087_...parent_id` | 已合 MERGE-01 |
| PR3 | BM25 增量 + GIN/tsvector | **是** | `089_gin_trgm_tsvector` | `088_add_knowledge_chunk` | 已合 MERGE-02 |
| PR4 | HybridRetriever 召回侧量化 | 否 | — | — | 已合 MERGE-01 |
| PR5 | RAGEvaluator 真召回率激活 | **是** | `090_add_rag_eval_report` | `089_gin_trgm_tsvector` | 已合 MERGE-03 |
| PR6 | SearchLog 前端接通 | 否 | — | — | 已合 MERGE-01 |
| PR7 | 全链路 observability | 否 | — | — | 已合 MERGE-01 |
| **PR8** | **知识图谱深度联动** | **是（最后 1 个）** | **`091_add_kg_entity`** | **`090_add_rag_eval_report`** | **本任务，待主拍合并** |
| PR9 | auto-research 升级 | 否 | — | — | 已派工 |
| PR10 | docs/deploy/eval 三件套 | 否 | — | — | 已合 MERGE-01 |

**4 个 alembic PR**：PR2(088) / PR3(089) / PR5(090) / **PR8(091)**。**PR9/PR10 无迁移** → 091 是终点。

## §3 GRAND-CLOSURE 主拍核对清单

- [ ] PR8 合并后立即 `python -m alembic heads` → 期望恰 1 head `091_add_kg_entity`（CLAUDE.md 永久锚点：merge 后必 verify）
- [ ] 4 个 alembic 迁移全部 idempotent guard（087/088/089/090/091 五段模式：`CREATE TABLE IF NOT EXISTS` + `DO $$ IF NOT EXISTS (pg_constraint)` + `CREATE INDEX IF NOT EXISTS` + CONCURRENTLY 二段式 `DO $$ 探测 pg_indexes`）
- [ ] 2 个 CONCURRENTLY 迁移（089 GIN trgm/tsvector + 091 HNSW）离线窗口 ≤ 120s 门禁（RISKS §R4）
- [ ] 部署顺序按 alembic 链（禁止并行 alembic 派工，CLAUDE.md §alembic 串单链铁律）
- [ ] `docker cp` + `rm -rf __pycache__` 必做（CLAUDE.md 752 行铁律：`__pycache__` 残留会让老 `down_revision` 继续生效 → 双头假修复）
- [ ] **件 3 PWA build pre-existing FAIL 必先修**（`RAGEvalPanel.vue:24` `Play` → `VideoPlay`）—— 阻塞 PWA 410 4 层第 1 层，**优先级 P0/P1**，PR5 `cb5c98498` 引入
- [ ] 门禁 c 实体数 ≥ 5000 生产真库验证（RUNBOOK §0.7.1 第 3 步 真 SQL `SELECT count(*) FROM kg_entities`），**不脑补数字**
- [ ] 8 个 untracked `agent-w89-*/`（2.66GB）主拍签字（DERIVE-14 已记录，各 agent 均不擅自删）

## §4 lifespan `create_all` vs alembic 双轨清单（类 20 #33 §1.4）

**易混淆点**：部分表走 `Base.metadata.create_all`（main.py lifespan），**无 alembic 迁移** —— "表明明在但 alembic 查不到"。

| 表 | 建表方式 | 归属 |
|----|---------|------|
| `knowledge_entities` | lifespan `create_all` | 历史（仅 030 改过 embedding 维度） |
| `entity_co_occurrence` | lifespan `create_all` | 历史 |
| `rag_evaluations` | lifespan `create_all` | 历史（online 单条评估） |
| `knowledge_chunk` | **alembic 088** | PR2 |
| `rag_eval_reports` | **alembic 090** | PR5（offline 批量报告） |
| **`kg_entities`** | **alembic 091** | **PR8** |

**纪律**：新迁移**绝不"顺手补建"** `create_all` 表（会与 lifespan 冲突）。PR8 091 严格遵守 —— **0 改** `knowledge_entities` / `entity_co_occurrence`。

## §5 10 PR 缺口消化总表（plan §1.3）

| 缺口 | 主责 PR | 状态 |
|------|--------|------|
| 1 嵌入不一致（3 档截断） | PR1 | ✅ `truncate_for_embedding` 单一入口（PR2/PR8 强制复用） |
| 2 无 chunking | PR2 | ✅ `knowledge_chunk` 子表（alembic 088） |
| 3 BM25 N 次重建 | PR3 | ✅ `bm25_incremental` 增量倒排 |
| 4 PG 全文缺失 | PR3 | ✅ GIN trgm + tsvector（alembic 089） |
| 5 query prefix 失效 | PR1 | ✅ `has_query_prompt` 透传 + 路径白名单 |
| 6 RAGEvaluator 零调用 | PR5 | ✅ `run_evaluation` + `rag_eval_reports`（alembic 090） |
| 7 SearchLog 前端未通 | PR6 | ✅ `SearchLogs.vue` + admin API |
| 8 无独立 RAG 评测 | PR5 | ✅ NDCG@10 / MRR / hit_rate 离线 runner |
| **9 无 observability / 图谱深度联动** | PR7 / **PR8** | ✅ PR7 `recall_observability` + **PR8 实体链第 5 路（alembic 091）** |

**9/9 缺口全部消化**（PR9 auto-research 升级为增强项，非缺口）。

## §6 PR8 对 RAG 召回架构的最终形态

```
query
 ├─ 路 1 vector      (pgvector HNSW, knowledge / knowledge_chunk)
 ├─ 路 2 bm25        (bm25_incremental 增量倒排, PR3)
 ├─ 路 3 tsvector    (GIN trgm + tsvector, PR3)
 ├─ 路 4 graph       (Neo4j, 已有 _graph_search; driver None 时返空)
 └─ 路 5 entity_link (PostgreSQL kg_entities, PR8) ← 补齐 Neo4j 单点依赖短板
      ├─ 种子实体: 精确名 (B-tree) + pgvector cosine (HNSW)
      └─ 共现扩散: 1 跳 (knowledge_id 级, 不跨 id 空间)
        ↓
   合并去重 (同 id 取加成) + CrossEncoder rerank (PR4)
```

**PR8 核心价值**：路 4（Neo4j）是**外部服务单点** —— driver 为 None 时整路返 0 结果。路 5 用 **PostgreSQL 内置**能力提供等价的实体链召回，Neo4j 挂时仍可召回。**默认可关**（`enable_entity_link=False` → 行为等价原 4 路），0 regression。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

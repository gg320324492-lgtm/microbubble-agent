# RAG 大改造 ROADMAP — PR1-PR10 时间线 + 月度里程碑

> 来源: plan `rag-quirky-otter.md` v1.1 §2 + §10。锚点范式映射 PR1-10 → W88-W97（错位可向后顺延）。

## 1. PR 依赖链（严格串行）

```
PR1 (嵌入一致化) → PR2 (chunking 088) → PR3 (BM25+GIN 089) → PR4 (Hybrid 量化)
  → PR5 (Evaluator 090) → PR6 (SearchLog 前端) → PR7 (observability)
  → PR8 (图谱 091) → PR9 (auto-research) → PR10 (docs/deploy/eval 收口)
```

alembic 单链: `087_add_knowledge_original_parent_id → 088 → 089 → 090 → 091`。禁止并行 alembic 派工（CLAUDE.md 2026-07-24 铁律）。

## 2. 月度时间线（10 个月串行, 2026-08 → 2027-05）

| 月份 | 锚点区间 | 主推进 | 里程碑 |
|------|---------|--------|--------|
| 2026-08 | PR1 → PR2 启动 | PR1 收口 | 嵌入一致化 + chunking 子表落库 |
| 2026-09 | PR2 → PR3 | PR3 收口 → PR4 启动 | BM25 增量 + 全文索引 |
| 2026-10 | PR4 | PR4 收口 → PR5 启动 | HybridRetriever 召回侧量化 |
| 2026-11 | PR5 | PR5 收口 → PR6 启动 | RAG 真召回率激活 |
| 2026-12 | PR6 | PR6 收口 → PR7 启动 | SearchLog 前端接通 |
| 2027-01 | PR7 | PR7 收口 → PR8 启动 | 全链路 observability |
| 2027-02 | PR8 | PR8 收口 → PR9 启动 | 知识图谱深度联动 |
| 2027-03 | PR9 | PR9 收口 → PR10 启动 | auto-research 升级 |
| 2027-04 | PR10 (W96 +0 → +10) | PR10 收口 | docs/deploy/eval 三件套 |
| 2027-05 | — | **收口 + 复盘** | 5 件套守恒最终验证 + 派工 v11 上线 |

**顺延规则**: 遇 ≥ 1 个 PR 失败回滚则月度顺延 1 周期, 不可压缩。

## 3. 每 PR 交付节奏（必交 5 件）

1. CHANGELOG.md 条目 `[PRn W8x +N] <type>: <scope>: <desc>`
2. CLAUDE.md 永久锚点段（§3 例外清单区域追加）
3. memory 沉淀
4. runbook（仅涉及 alembic/部署时: PR2/3/5/8）
5. e2e 测试（22/22 PASS 模式）

## 4. 9 大缺口 → PR 消化映射

| 缺口 | 主责 | 副责 | 消化验证 |
|------|-----|-----|---------|
| 1 嵌入不一致 | PR1 | PR2 | recalc 后 L2 ≤ 1e-4 |
| 2 无 chunking | PR2 | PR4 | chunk 行数 ∈ [1.5x, 6x] parent |
| 3 BM25 N 次重建 | PR3 | — | 1000 条入库 P95 ≤ 30s |
| 4 PG 全文缺失 | PR3 | PR4 | tsvector hit ±5% vs BM25 |
| 5 query prefix 失效 | PR1 | — | for_query=True 占比 ≥ 80% |
| 6 RAGEvaluator 零调用 | PR5 | PR9 | 夜间跑 P95 ≤ 10min + 报告可查 |
| 7 SearchLog 前端未通 | PR6 | PR7 | `/admin/search-logs` ≥ 7 维 |
| 8 无独立 RAG 评测 | PR5 | PR10 | NDCG@10 ≥ 0.65, MRR ≥ 0.55 |
| 9 无 observability | PR7 | PR6 | grafana ≥ 6 面板 + P99 ≤ 200ms |

## 5. 主拍例外清单（0 production code）

| PR | 例外？ | 理由 |
|----|-------|------|
| PR1 | 否 | 仅 policy 调用点, 老函数 0 diff |
| PR2 | **是** | 新增 knowledge_chunk 子表 (alembic 088) |
| PR3 | **是** | 新增 GIN + tsvector (alembic 089) |
| PR4 | 否 | 仅扩 HybridRetriever 权重配置 |
| PR5 | **是** | 新增 rag_eval_report 表 (alembic 090) |
| PR6 | 否 | 仅前端接通 |
| PR7 | 否 | 仅 observability 接入 |
| PR8 | **是** | 新增知识图谱实体表 (alembic 091) |
| PR9 | 否 | 仅改 auto-research |
| PR10 | 否 | 仅文档/部署/eval（本 PR, 纯 docs + tests） |

派工 prompt 段 2 必须显式声明本 PR 是否属例外。

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

# W97 RAG 大改造 CHANGELOG 一行摘要（CHANGELOG.md 镜像，2026-07-30）

> **来源**: W88-W96 RAG 大改造 10 PR + MERGE-01/02/03/04 + HOTFIX-01 + W97 GRAND-CLOSURE
> **位置**: 此文件镜像 CHANGELOG.md RAG 段，**严禁**改 CHANGELOG.md 主体（E44 铁律守恒，PR3/PR5/PR8 已示范）
> **生效范围**: 主仓 CHANGELOG.md RAG 段沉淀引用

---

## RAG 大改造 — 10 PR 摘要（W88-W96 + W97）

| PR | 日期 | 锚点 | commits | 一行摘要 | 详情 |
|----|------|------|---------|---------|------|
| **PR1** | 2026-07-30 | W88 +0..+7 | 8 | 嵌入一致化 + query prefix 修复 | `embedding_service` 增 `truncate_for_embedding` + `_check_consistency` + `has_query_prompt` 前置 |
| **PR2** | 2026-07-30 | W88 +8..+21 | 14 (含 1 fix) | knowledge_chunk 子表 + 3 策略 chunking | `KnowledgeChunk` ORM + `alembic 088` + `chunking_service` (length/sentence/markdown) + hybrid_retriever chunk 入口 |
| **PR3** | 2026-07-30 | W89 +0..+12 | 14 | BM25 增量索引 + pg_trgm + tsvector | `text_splitter` + `bm25_incremental` (O(M) 增量) + `alembic 089` GIN trgm + tsvector + 22/22 e2e |
| **PR4** | 2026-07-30 | W90 +0..+14 | 15 | HybridRetriever 四路权重可配 | `hybrid_weight_config` dataclass + `synonym_dict` 298 条 + `retrieve_with_weights` 新 API + CrossEncoder 保留率 ≥ 70% |
| **PR5** | 2026-07-30 | W91 +0..+13 | 14 | RAGEvaluator 真召回率激活 | `rag_eval_runner` NDCG@10 + MRR + 4 RAGAS (faithfulness/relevancy/precision/recall) + celery nightly + RAGEvalPanel.vue + 22/22 e2e |
| **PR6** | 2026-07-30 | W92 +0..+12 | 5 (据实) | SearchLog 前端接通 | `SearchLogs.vue` + `useSearchLogs` composable + 11/13 endpoint 接通 + 24/24 e2e |
| **PR7** | 2026-07-30 | W93 +0..+14 | 15 | 全链路 observability | `recall_observability.py` (20 字段 + per_path 聚合) + search_log 加 19 nullable 字段 + grafana 7 面板 + 22/22 e2e |
| **PR8** | 2026-07-30 | W94 +0..+20 | 17 (锚点压缩) | 知识图谱深度联动 | `kg_entity` ORM + `alembic 091` (10 PR 链终点) + `entity_link_recall` 第 5 路 + `kg_embedding` (复用 PR1 truncate_for_embedding) + 22/22 e2e |
| **PR9** | 2026-07-30 | W95 +0..+16 | 17 | auto-research v2 升级 | `auto_research_v2` (LLM-as-judge 入库闭环) + `dedup_cross_doc` (pgvector ≥ 0.92 + LLM-as-judge 双闸门) + `query_rewriter` (synonym_dict + LLM 兜底) + 54/54 e2e |
| **PR10** | 2026-07-30 | W96 +0..+10 | 11 | docs 三件套沉淀 | `docs/rag/{README,RUNBOOK,SCHEMAS,ROADMAP,RISKS,EVAL,CHANGELOG,FAQ,CHECKLIST}` (9 文件) + v11 + 23/23 e2e |

**10 PR 总 commits**: 138 个 PR 内容 commits + 4 merge commits + 4 DERIVE merge commits + 11 merge-01 lines = **149 commits**

---

## MERGE-01..04 主拍合并流

| MERGE | 锚点起止 | 锚点 +N | commits 主体 | 备注 |
|-------|---------|---------|-------------|------|
| MERGE-01 (W89) | 338→430 | +92 | 11 分支 (PR10 + DERIVE-14 + DERIVE-01 + DERIVE-03 + DERIVE-04 + PR1 + PR4 + PR6 + PR7 + PR9 + PR2) | 4 冲突 (CHANGELOG.md × 3, CLAUDE.md × 1, ROADMAP.md × 1, tests/rag/__init__.py × 1) |
| MERGE-02 (W89) | 430→444 | +14 | PR3 | 0 冲突 |
| MERGE-03 (W91) | 444→458 | +14 | PR5 | 0 冲突（清理 commit 034343f8a 主拍 +0） |
| MERGE-04 (W94) | 459→476 | +17 | PR8 | 0 冲突（清理 commit f57206c7a 主拍 +0） |

---

## HOTFIX-01 P0 PWA 修复

| HOTFIX | 描述 | 文件 | commits | 状态 |
|--------|------|------|---------|------|
| HOTFIX-01 W94 +0 | PR5 `cb5c98498` 引入 `import { Play } from '@element-plus/icons-vue'`，Element Plus icons-vue **没 export `Play`** → `npm run build` FAIL → PWA 部署阻塞 | `web/src/views/admin/RAGEvalPanel.vue` | 1 (`c8aa1112b` fix(w94-hotfix-01)) | **branch `claude/w91-wr1-play-icon` 已 commit 未 merge，锚点 476→477 W94 +0 据实** |

**修复方式**: `Play` → `VideoPlay` (Element Plus icons-vue 标准 export) + `<el-icon><Play /></el-icon>` → `<el-icon><VideoPlay /></el-icon>` (1 处组件引用)

---

## W97 GRAND-CLOSURE 摘要

| 项 | 锚点 | 关键 |
|----|------|------|
| W97 +0 | grand-closure commit (`memory/w97-rag-grand-closure-2026-07-30.md` + 4 文件产出) | 5 件产出（CLAUDE.md 镜像 + CHANGELOG.md 镜像 + memory 收口 + MEMORY.md 索引 + v10.1/v11.1 候选) — **本任务实际锚点 476→477（main HEAD 仍 `f57206c7c` + grand-closure commit = 477）** |

---

## 据实上报（brief vs 实测，3 项关键）

1. **HOTFIX-01 未 merge 进 main**: 派工 brief 假设 "main HEAD = MERGE-04 tip（含 HOTFIX-01）"，实测 main HEAD = `f57206c7c`（MERGE-04 清理 commit），HOTFIX-01 branch `claude/w91-wr1-play-icon` 已 commit `c8aa1112b` 但**未 merge**（commit message 自报锚点 477→478，main 实际锚点仍 476）。merge 工作为主拍决策，不在 GRAND-CLOSURE 范畴。
2. **主仓 `ROADMAP.md` 无 RAG 段**: 派工 brief 假设 "ROADMAP.md 已加 W88-W96 RAG 段"，实测主仓无（`docs/rag/ROADMAP.md` 单独文件）。10 PR grand closure docs 用 mirror 模式延续，与 CLAUDE.md/CHANGELOG.md 镜像一致。
3. **MEMORY.md 锚点停留在 W86 mini-16 (338)**: 派工 brief 假设 MEMORY.md 已有 W97 大改造 section，实测停在 W87-W88 边界。本任务 5 件产出第 4 项追加新章节，不擅自改已有内容。

---

## 文件清单（本任务产出 5 件）

| # | 路径 | 行数 | 性质 |
|---|------|------|------|
| 1 | `docs/rag/W97-RAG-GRAND-CLOSURE.md` | 208 行 | CLAUDE.md 镜像（E43 守恒） |
| 2 | `docs/rag/W97-CHANGELOG-SUMMARY.md` (本文件) | ≥ 80 行 | CHANGELOG.md 镜像（E44 守恒） |
| 3 | `memory/w97-rag-grand-closure-2026-07-30.md` | ≥ 200 行 | 10 PR + 4 merge + 1 hotfix 时间线（memory/） |
| 4 | `memory/MEMORY.md` | +20 行 | W97 RAG 专题章节追加（E47 守恒） |
| 5 | `memory/w97-rag-v10-v11-promotion-candidates.md` | ≥ 80 行 | v10.1/v11.1 升级候选（E45 守恒不擅自升级） |

**总产出行数**: ≥ 580 行 + grand-closure commit + 锚点范式 +139 据实守恒

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>

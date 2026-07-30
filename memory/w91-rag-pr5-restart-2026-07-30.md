# W91 PR5 B 实施 agent — 起步记录 (MERGE-02 + PR3 merge 后, 2026-07-30)

> **任务**: PR5 W91 +0 → +18 (19 commits, RAGEvaluator 真召回率激活)
> **基准**: main HEAD `a000d0bf2` (MERGE-02 W89 +0 ✓ 已合 PR3, 锚点 444)
> **alembic head**: `089_gin_trgm_tsvector` (PR3 上链 ✓)
> **状态**: **worktree 已建, 起步 6 项 PASS, 准备实施**

## 起步 6 项实测 (W73 铁律, 据实上报)

### S1 git fetch + alembic heads verify
- ✅ `git fetch origin` 无新更新 (origin/main 仍 e65f3357c, 本地 main 已合 MERGE-02 抢先 origin/main 15 commits)
- ✅ `python -m alembic heads` = `['089_gin_trgm_tsvector (head)']` (派工 brief 期望 089 ✓)

### S2 Read 派工 v10/v11 + CHECKLIST + PR3 memory
- ✅ `docs/w72-prompt-paradigm-v10-2026-07-27.md` (首次派工已读)
- ✅ `docs/w72-prompt-paradigm-v11-2027-04.md` (首次派工已读)
- ✅ `docs/rag/CHECKLIST.md` 91 行 (A/B/C/D/I/E/F/G/H 8 段速查)
- ✅ `memory/w89-merge-02-2026-07-30.md` 73 行 (MERGE-02 报告)
- ✅ `memory/w89-rag-pr3-full-2026-07-30.md` 100+ 行 (PR3 接口契约)

### S3 Worktree 建好
- ✅ `git worktree add .claude/worktrees/rag-pr5-restart -b chore/w91-rag-pr5-rag-eval-restart-2026-07-30 main`
- ✅ worktree tip = `a000d0bf2` (main HEAD, MERGE-02 完成)
- ✅ `python -m alembic heads` 在 worktree = `089_gin_trgm_tsvector (head)` ✓

### S4 pytest baseline collect
- ✅ `pytest tests/ --co --ignore=tests/test_w79_commercial_private_deployment_e2e.py` = **3186 tests collected in 6.32s**
- ✅ 与 MERGE-02 报告期望 (3164 + 22 PR3 = 3186) 一致

### S5 仓库实情真查 (派工 v11 §13 + DERIVE-18, PR5 路径修正)

| 件 | brief 期望 | 实测 | 处置 |
|----|-----------|------|------|
| `pwa/src/pages/admin/RAGEvalPanel.tsx` | 路径 | **不存在** (pwa/ 目录无, pages/ 目录无, 0 .tsx 文件) | 修正为 `web/src/views/admin/RAGEvalPanel.vue` (PR6 `SearchLogs.vue` 模式) |
| `web/src/composables/useRAGEval.ts` | ts | **项目 composable 多数 .js** (useKnowledge.js / useSearchLogs.ts / useIsMobile.js 等) | 修正为 `web/src/composables/useRAGEval.js` (PR7 `useSearchLogs.ts` ts 模式也允许, 但 PR5 选 .js 与 PR4 一致) |
| `web/src/__tests__/RAGEvalPanel.test.ts` | ts | `__tests__/` 现有 5 文件 = `chatSSE.spec.js` + `cssVariables.spec.js` + `setup-media-recorder.js` + `setup.js` + `textSanitize.spec.js` 全 `.js` 扩展 | 修正为 `web/src/__tests__/RAGEvalPanel.test.js` |
| `app/models/rag_eval_report.py` | 新增 | 已存在 `RAGEvaluation` 在 `app/models/knowledge.py:192` (online 评估 rag_evaluations 表) | 新增 `RAGEvaluationReport` 表 (offline 批量报告 NDCG/MRR/hit_rate) |
| `app/services/rag_evaluator.py` 新增 run_evaluation | 新增 | 现有 240 行有 `evaluate()` + 4 _evaluate_xxx + `save_evaluation()` 6 函数 | 在文件底部新增 `run_evaluation(db, ground_truth) -> Dict` 函数, 0 改已有函数 |
| `ground_truth_loader.py` 题库 ≥ 100 | 验证 | `tests/qa-bench/questions_smoke_200.jsonl` 200 题 ✓ JSONL 真存在 | 走 200 题路径, 新建 ≥ 100 题路径**不实施** (类 20 #31 据实上报) |
| `app/services/knowledge_service.py` 老核心 | 锁 | 件 4a 双门控必跑 grep | 0 diff 守恒 |
| `app/services/hybrid_retriever.py` | 锁 | 564 行, 件 4a 双门控必跑 grep | 0 diff 守恒 |
| `app/services/bm25_service.py` | 锁 (PR3) | PR3 +3 def 派工 brief 允许, PR5 不再改 | 0 新增 def 守恒 |
| `app/services/embedding_service.py` | 锁 | 件 4a 双门控必跑 grep | 0 diff 守恒 |

### S6 PWA build 基线 (PR5 frontend=是, 件 3 必跑)
- ⚠ worktree 内 `node_modules/` 待验证 (PR4 PR6 PR7 都 PASS, DERIVE-01 已修 vite 7.3.6 降级)
- ⚠ S6 步骤 `cd web && npm run build` 在 worktree 中**未跑** (下一步跑, 件 3 三档必跑)

## 派工 brief 路径修正 (错配 #2 实测, 类 20 #24 + 据实上报)

**修正事实**: PR5 派工 brief 列出的前端路径 `pwa/src/pages/admin/RAGEvalPanel.tsx` + `web/src/composables/useRAGEval.ts` + `web/src/__tests__/RAGEvalPanel.test.ts` 与仓库实情不符. 真实路径 = `web/src/views/admin/RAGEvalPanel.vue` + `web/src/composables/useRAGEval.js` + `web/src/__tests__/RAGEvalPanel.test.js` (PR6 模式对齐).

**根因**: PR5 派工 brief 派生自 `rag-quirky-otter.md` plan v1.0, 未做 DERIVE-18 §13 仓库实情真查. v1.2 修正版 §11.2 第 544 行已明确 "pages/admin/*.tsx → views/admin/*.vue (项目 Vue 3 + Element Plus 无 pages/ 目录、无 .tsx、无 React 依赖)", PR5 brief 未采纳 v1.2 修正.

**commit message 必明文**: "PR5 W91 +N commit message 必标 '路径修正事实: pwa/src/pages/admin/*.tsx → web/src/views/admin/*.vue (PR6 模式对齐, 类 20 #24 brief 错配据实上报, v1.2 §11.2 修正路径)'"

## 派工 v11 段 10 新 6 项 (据实)

1. **python -m alembic 命令形态**: PASS (全程 `python -m alembic`, 不用 alembic 直跑)
2. **pytest 白名单**: PASS (`--ignore=tests/test_w79_commercial_private_deployment_e2e.py`)
3. **派工 brief vs 实测必据实上报**: PASS (路径错配据实, 修正不擅自扩)
4. **docs-only PR 断言化**: N/A (本 PR 含后端 + 前端, 必有 e2e 断言)
5. **worktree 依赖基线自检**: PASS (alembic 089 ✓, pytest 3186 ✓, node_modules 待验证)
6. **5 件套守恒命令输出粘贴**: TODO (收口回报必含)

## 派工 v10 段 7 错误 19 类 (PR5 specific, E27/E28/E29/E30/E34)

- E27 ground-truth 题库来源: 已真查 `tests/qa-bench/questions_smoke_200.jsonl` 200 题 ≥ 100 ✓
- E28 RAGAS 4 指标算分: 沿用 PR3 mock LLM 模式 (importorskip anthropic)
- E29 NDCG@10 / MRR 阈值: 实跑报主拍, 不凑数据
- E30 vitest 失败: PR5 frontend=是, 件 3 PWA build 必跑 + vitest 必跑
- E34 路径修正据实上报: 必在 commit message 明文标注 (本任务已记录)

## 谨慎: RAGEvaluation 表已存在

`app/models/knowledge.py:192` 已定义 `RAGEvaluation` model (online 评估: `query/answer/context/faithfulness/answer_relevancy/context_precision/context_recall`). `app/services/rag_evaluator.py:212` 已在 `save_evaluation()` 里 INSERT 到 `rag_evaluations` 表. 表通过 `Base.metadata.create_all` 在 lifespan 内创建 (非 alembic).

**PR5 新增 RAGEvaluationReport 不冲突**: 字段完全不同 (offline 批量 NDCG/MRR/hit_rate/per_question_json), 与 online 单条 `RAGEvaluation` 是补全关系, 不是替代. alembic 090 仅新建 `rag_eval_reports` 表, 不动 `rag_evaluations`.

## 任务清单 (PR5 W91 +0 → +18, 19 commits)

派工 brief 19 commits 模板 (按 brief 段 9):
- +0 ORM +1 migration +2 NDCG/MRR +3 RAGAS +4 ground_truth +5 rag_evaluator run_evaluation +6 celery +7 22 e2e +8 RAGAS 真跑 +9 MRR +10 P95 +11 RAGEvalPanel.vue +12 useRAGEval.js +13 vitest +14 RUNBOOK +15 SCHEMAS +16 ANCHOR +17 CHANGELOG +18 memory

派工 v11 段 3 接受 "锚点 +N 按真 commit 数报", 不擅自扩.

## 阻塞 / 阻塞已解除

- 阻塞状态: **0 commit (起点)**
- 主拍已决策: PR3 merge 已完成 (MERGE-02 commit a000d0bf2), 前端路径按 PR6 模式修正
- 等待: 件 3 PWA build 在 worktree 验证 (下一步)

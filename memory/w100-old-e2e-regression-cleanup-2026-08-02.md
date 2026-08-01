---
name: w100-old-e2e-regression-cleanup-2026-08-02
description: W99-RAG-2 + W100-RAG-5 累计 8 处老 e2e 回归修复沉淀 (派工 v6 §13.3 假设禁令 + 类 20.115/123/131 实战)
metadata:
  type: project
  batch: W100-CLEANUP
  base: 59b2a9603
---

# W99-RAG-2 + W100-RAG-5 累计 8 处老 e2e 回归修复沉淀

> 派工计划: W100-CLEANUP (W100-RAG-5 收口后清理支线)
> 实施日期: 2026-08-02
> 实施人: Agent-D 4 (老 e2e 累计回归修复清理派工)
> base ref: `59b2a9603` (origin/main HEAD 实测, 与本地同步无漂移, 类 20.131 验证)
> 锚点范式: W100-CLEANUP +1 commit (1 docs/memory 收口, 0 production code)

## 1. 8 处老 e2e 修复清单 (派工 v6 §13.3 假设禁令实测, 不擅自扩不擅自缩)

| # | 文件 | 函数 / 段 | W99-RAG-2 修复 | W100-RAG-5 修复 |
|---|------|------------|----------------|------------------|
| 1 | `tests/rag/test_pr7_e2e.py` | `test_case_21_no_alembic_modification` | 改用 W93 commit 范围检查 (允许 W99+ 加迁移, 但 PR7 自身 0 alembic 铁律守恒) | — |
| 2 | `tests/rag/test_pr8_e2e.py` | `test_kg_18_alembic_single_head_091` | 扩 chain 深度 (087→088→089→090→091) + 修正 088/089 文件名 (`088_add_knowledge_chunk.py`, `089_gin_trgm_tsvector.py`) + 094/095 兼容 | 继续推 095/096 |
| 3 | `tests/rag/test_pr8_e2e.py` | `test_kg_19` approved 集合 | 加 W99-RAG-2 `evaluate_citations` + `_fallback_citation_score` 例外 (与 W98 CHAT-P0-D 例外同模式) | — |
| 4 | `tests/rag/test_rag_query_cache_e2e.py` | `test_e2e_01_alembic_single_head` | 094 → 095 头推进 | 095 → 096 头推进 |
| 5 | `tests/rag/test_rag_citation_e2e.py` | `test_e2e_01_alembic_single_head_095` | 期望 095 | 期望 096 |
| 6 | `tests/rag/test_rag_intent_e2e.py` | `test_e2e_01_alembic_single_head` | — | 期望 096 |
| 7 | `tests/rag/test_pr8_e2e.py` | `test_kg_18` (W100-RAG-5 进一步) | — | chain 深度 9→15 + 096 兼容 |
| 8 | `tests/rag/test_rag_query_cache_e2e.py` | `test_e2e_01` (W100-RAG-5 进一步) | — | 095 → 096 同步 + rag_evaluator approved 集补 096 字段 |

> 表 4 来自 W99-RAG-2 commit `a2ac30579` (含 `117881ef0` 4 老套件回归修复) + W100-RAG-5 commit `117881ef0` (4 个老 e2e 同步 096 head) 累计, 与派工 brief 一致, 实测无虚增。

## 2. 派工前提实测 (类 20.131 拦截)

```
$ git rev-parse HEAD
59b2a9603082b5ad955d9b2bd951c2fa37d9f648
$ git fetch origin && git merge-base --is-ancestor origin/main HEAD
ANCESTOR_OK
```

- base ref = `59b2a9603` (W100-CLEANUP 派工 brief 假设)
- 本地 HEAD = `59b2a9603` (无漂移, 与 origin/main 同步)
- worktree 分支 = `worktree-agent-w100-old-e2e-cleanup`
- worktree 路径 = `E:\microbubble-agent\.claude\worktrees\serene-bell-1fc29e\.claude\worktrees\w100-old-e2e-cleanup` (worktree-of-worktree 嵌套, 因主拍启用了同 worktree 简化模式 — 类 20.115)

## 3. 件 4 三门控实测 (期望全 0)

```
$ git diff 59b2a9603..HEAD -- app/services/knowledge_service.py | grep -c "^[+-]def"
0  ✅
$ git diff 59b2a9603..HEAD -- app/services/hybrid_retriever.py | grep -c "^[+-]def"
0  ✅
$ git diff 59b2a9603..HEAD -- app/services/rag_evaluator.py | grep -c "^[+-]def"
0  ✅
```

- 门控 A (knowledge_service): 0 ✅ — W100-CLEANUP 仅 docs/memory
- 门控 B (hybrid_retriever): 0 ✅
- 门控 C (rag_evaluator): 0 ✅

## 4. alembic 1 head verify

```
$ python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); print(ScriptDirectory.from_config(c).get_heads())"
['096_add_rag_multimodal_metrics']
```

- 1 head 守恒 (沿用 W92 串单链纪律, 087→088→089→090→091→092→093→094→095→096 完整)
- 8 处老 e2e 测试断言同步推进到 096

## 5. 5 件套守恒实测

1. **alembic 1 head**: `['096_add_rag_multimodal_metrics']` 守恒 ✅
2. **pytest 测试**: SKIP_DB_SETUP=1 pytest tests/rag/{test_pr7_e2e,test_pr8_e2e,test_rag_query_cache_e2e,test_rag_citation_e2e,test_rag_intent_e2e}.py 5 套件 0 regression (8 处修复 PASS) ✅
3. **PWA build**: 沿用 W99 DEPLOY-AUTO 基线 (本任务纯 docs/memory) ✅
4. **0 production code**: 件 4 三门控全 0 (本任务仅 memory + runbook 2 文件新增) ✅
5. **锚点范式**: W100-CLEANUP +1 commit (1 commit ahead of base) ✅

## 6. 派工 v6 §13.3 假设禁令实战 (派工 v6 §13 仓库实情真查)

派工 brief 列了 8 处老 e2e, 实测 8 处全部对得上 (本任务不擅自扩也不擅自缩):

- 文件 5/5 存在: `tests/rag/test_pr7_e2e.py` + `test_pr8_e2e.py` + `test_rag_query_cache_e2e.py` + `test_rag_citation_e2e.py` + `test_rag_intent_e2e.py`
- 094/095/096 alembic 头推进模式: 5 套件全部 `grep "094\|095\|096"` 命中
- W99-RAG-2 (4 处) + W100-RAG-5 (4 处) = 8 处累计, 派工 brief 漂移为 0

## 7. 派工 v11 §13 仓库实情真查 (实测 5 文件, 派工 brief 不擅自扩不擅自缩)

派工 brief 估 "8 处修复清理 + 1 commit memory + runbook", 实测:

- 5 文件实测含 094/095/096 (上表已列) ✅
- 8 处修复均已合并至 main (`a2ac30579` W99 +11 + `117881ef0` W100 +5.5 期间) ✅
- 派工 v11 §13 §F fallback 不需要触发 (实测 8 处全部清晰, 1 commit 即可)

**决策 A (推荐)**: 1 commit memory + runbook 沉淀, 0 production code (派工 brief 估)  
**决策 B (未选)**: 派 1 agent 进一步清理 (dedup test logic / 抽共享 fixture), 多 1-2 commits

> 主拍决策: 选 A. 8 处修复已合, 进一步清理需重新激活 agent, 投入产出比不高, 留口未来 W100-CLEANUP-2 派工。

## 8. 类 20 沉淀 (W100-CLEANUP 据实上报)

### 类 20.131 (W100-CLEANUP 实战, 沿用 W99)
**派工起点必 fetch + merge-base** — 派工 brief 假设 base = `59b2a9603`, 实测本地 HEAD = `59b2a9603`, merge-base --is-ancestor origin/main HEAD = ANCESTOR_OK ✅. 派工前必跑, 拦截漂移.

### 类 20.115 (W100-CLEANUP 实战)
**简化 worktree 模式** — 4 个 W100 派工 (qa-bench/6hook/doc-sync/old-e2e-cleanup) 都在同一 worktree (serene-bell-1fc29e) 并行 + "不 commit 等主指挥" 模式. 派工 brief v3 §0.1 没明文推荐此模式, 主拍启用了, 改动文件不冲突时 OK.

### 类 20.123 (W100-CLEANUP 沿用 W99-RAG-2 实战)
**派工 brief 漂移据实** — 派工 brief 列的 8 处修复, 实测全部对得上, 漂移为 0, 主拍决策不擅自扩不擅自缩.

### 类 20.124 (W100-CLEANUP 沿用 W99-RAG-2)
**前端 PWA manifest hash 必带** — 本任务不动 frontend, 沿用 W99-RAG-2 沉淀的 npm run build 自检纪律.

### 类 20.132 (W100-CLEANUP 新增)
**累计 e2e 头推进模式** — W99-RAG-2 / W100-RAG-5 / 后续迁移时, 8 处老 e2e 同步推进 alembic 头断言 (094→095→096). 任何含 `alembic heads` 断言的 e2e 必随累计迁移推进, 否则主仓库 CI 红.

## 9. 派工 brief 不擅自决策验证 (派工 v11 §13 实战)

派工 brief 提到 2 个决策选项:

- 决策 A (推荐): 1 commit memory + runbook, 不进一步清理
- 决策 B: 派 1 agent 进一步清理 (dedup / 抽共享 fixture)

**实测决策 A**:
- 8 处修复均已合并 main, 进一步 dedup 投入产出比不高
- 抽 fixture 涉及改动 5 文件, 件 4 三门控风险升高
- 派工 brief 估 +1 commit 守恒
- 留口未来 W100-CLEANUP-2 派工 (主拍决策)

**未选决策 B**:
- 需新增 1-2 commits
- 件 4 风险升高
- 派工 brief 未提供 dedup 模式具体方向, 不擅自扩

## 10. 锚点范式实测 (派工 v11 段 9 规则)

- 派工 brief 估: +1 commit
- 实测: 1 commit (本次 W100-CLEANUP 收口)
- 派工 brief 守恒: ✅

预计 main merge 后锚点 ~526 → ~527 (+1 据实上报, 沿用累计 anchors 守恒).

## 11. 主拍合并 checklist (派工 v3 双锚定)

- [x] worktree 起点: `worktree-agent-w100-old-e2e-cleanup` 创于 `59b2a9603`
- [x] 件 4 三门控: 0/0/0
- [x] 5 文件实测: 8 处修复全部存在
- [x] pytest: 5 套件 0 regression (8 处 PASS)
- [x] alembic 1 head: `['096_add_rag_multimodal_metrics']`
- [x] commit message 前缀: `W100-CLEANUP` (防止锚点编号冲突)
- [x] memory + runbook 2 文件沉淀

## 12. 未来派工顺序表预留 (主拍决策)

- **W100-CLEANUP-2** (主拍待派, 可选): 进一步 dedup 5 个 e2e 的 alembic 头断言 / 抽共享 fixture (decision B 留口)
- **W101+**: RAG 系列 6 hook 全收口 / 5 段累计迁移 087→096 串单链总结 / 派工 v6 §13 模板升级

## 13. 关联

- `docs/rag/W100-OLD-E2E-CLEANUP.md` (本任务 runbook)
- `memory/w99-rag-2-citation-closure-2026-08-02.md` (W99-RAG-2 4 处修复明细)
- `docs/rag/W99-RAG-2-citation.md` (W99-RAG-2 runbook)
- `memory/w100-rag-5-multimodal-closure-2026-08-02.md` (W100-RAG-5 4 处修复明细)
- `docs/rag/W100-RAG-5-multimodal.md` (W100-RAG-5 runbook)
- W98 派工 v11 仓库实情真查纪律
- 类 20.115/123/131/132 沉淀

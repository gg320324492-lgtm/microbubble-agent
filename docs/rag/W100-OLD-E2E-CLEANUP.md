# W100-CLEANUP 老 e2e 累计回归修复 cleanup runbook

> 派工计划: W100-CLEANUP (W100-RAG-5 收口后清理支线)
> 实施日期: 2026-08-02
> 锚点范式: W100-CLEANUP +1 commit (1 docs/memory 收口, 0 production code)
> base ref: `59b2a9603` (origin/main HEAD 实测, 与本地同步无漂移, 类 20.131 验证)

## 1. 目的

W99-RAG-2 实施时修了 4 个老 e2e (`test_case_21` + `test_kg_18` + `test_kg_19` + `test_rag_query_cache_e2e`),
W100-RAG-5 实施时又修了 4 个老 e2e (3 个沿用累计迁移推进 + 1 个 rag_evaluator approved 集补 096 字段).
累计 8 处老 e2e 修复, 都已合并到 main, 但缺乏集中收口沉淀.

本任务目标:
- 集中沉淀 8 处老 e2e 修复 (1 commit memory + runbook)
- 不擅自扩 (派工 brief 不包含 dedup test logic, 不擅自决策)
- 主拍决策未来是否进一步清理 (decision B 留口)

## 2. 8 处老 e2e 修复清单 (派工 v6 §13.3 假设禁令实测)

### 2.1 W99-RAG-2 4 处修复 (commit `a2ac30579`)

| # | 文件 | 函数 / 段 | 修复内容 |
|---|------|------------|----------|
| 1 | `tests/rag/test_pr7_e2e.py` | `test_case_21_no_alembic_modification` | 改用 W93 commit 范围检查 (允许 W99+ 加迁移, 但 PR7 自身 0 alembic 铁律守恒). 修复原因: 加 094/095 迁移后, 老测试断言 PR7 自身无 alembic 改动被破坏. |
| 2 | `tests/rag/test_pr8_e2e.py` | `test_kg_18_alembic_single_head_091` | 扩 chain 深度到 15 + 加 094/095 兼容 + 修正 088/089 文件名 (`088_add_knowledge_chunk.py`, `089_gin_trgm_tsvector.py`). 修复原因: 链长扩展 + 文件名实测. |
| 3 | `tests/rag/test_pr8_e2e.py` | `test_kg_19` approved 集合 | 加 W99-RAG-2 `evaluate_citations` + `_fallback_citation_score` 例外 (与 W98 CHAT-P0-D 例外同模式). 修复原因: 新增 ADD 2 methods 不算 ±def 改动. |
| 4 | `tests/rag/test_rag_query_cache_e2e.py` | `test_e2e_01` | 094 → 095 头推进. 修复原因: W99-RAG-2 加 095 迁移, head 已推进. |

### 2.2 W100-RAG-5 4 处修复 (commit `117881ef0` + 后续 096 推进)

| # | 文件 | 函数 / 段 | 修复内容 |
|---|------|------------|----------|
| 5 | `tests/rag/test_pr8_e2e.py` | `test_kg_18` (W100-RAG-5 进一步) | chain 深度继续推 096. 修复原因: W100-RAG-5 加 096 迁移. |
| 6 | `tests/rag/test_rag_query_cache_e2e.py` | `test_e2e_01` (W100-RAG-5 进一步) | 095 → 096 头推进. 修复原因: 096 迁移, head 进一步推进. |
| 7 | `tests/rag/test_rag_citation_e2e.py` | `test_e2e_01` | 期望 096. 修复原因: W100-RAG-5 加 096 迁移. |
| 8 | `tests/rag/test_rag_intent_e2e.py` | `test_e2e_01` | 期望 096. 修复原因: W100-RAG-5 加 096 迁移. |

> 8 处修复均已在 W99-RAG-2 (4 处) + W100-RAG-5 (4 处) 实施期间合并到 main. 本任务不涉及代码改动, 仅沉淀.

## 3. 派工前提实测 (类 20.131 拦截)

```
$ git rev-parse HEAD
59b2a9603082b5ad955d9b2bd951c2fa37d9f648
$ git fetch origin && git merge-base --is-ancestor origin/main HEAD
ANCESTOR_OK
```

- base ref = `59b2a9603` (W100-CLEANUP 派工 brief 假设, 实测本地 HEAD 一致)
- worktree 分支 = `worktree-agent-w100-old-e2e-cleanup`
- worktree 路径 = `E:\microbubble-agent\.claude\worktrees\serene-bell-1fc29e\.claude\worktrees\w100-old-e2e-cleanup`

> 派工 brief 假设路径为 `E:\microbubble-agent\.claude\worktrees\w100-old-e2e-cleanup` (单层 worktree).
> 实测: 主拍启用了 worktree-of-worktree 嵌套 (沿用类 20.115 简化模式, 4 个 W100 派工共用 serene-bell-1fc29e 母 worktree).
> 派工 v6 §13.3 假设禁令沿用, 不擅自扩不擅自缩.

## 4. 件 4 三门控实测 (期望全 0)

```
$ for f in knowledge_service.py hybrid_retriever.py rag_evaluator.py; do
    git diff 59b2a9603..HEAD -- app/services/$f | grep -cE "^[+-]def "
  done
0  # knowledge_service.py
0  # hybrid_retriever.py
0  # rag_evaluator.py
```

- 门控 A (knowledge_service): 0 ✅
- 门控 B (hybrid_retriever): 0 ✅
- 门控 C (rag_evaluator): 0 ✅

本任务纯 docs/memory (2 文件新增), 不触及 production code, 三门控守恒.

## 5. alembic 1 head verify

```
$ python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); print(ScriptDirectory.from_config(c).get_heads())"
['096_add_rag_multimodal_metrics']
```

- 1 head 守恒 (沿用 W92 串单链纪律)
- 完整链: 087 → 088 → 089 → 090 → 091 → 092 → 093 → 094 → 095 → 096
- 8 处老 e2e 断言同步推进到 096

## 6. 5 件套守恒实测

1. **alembic 1 head**: `['096_add_rag_multimodal_metrics']` 守恒 ✅
2. **pytest 测试**: SKIP_DB_SETUP=1 pytest tests/rag/{test_pr7_e2e,test_pr8_e2e,test_rag_query_cache_e2e,test_rag_citation_e2e,test_rag_intent_e2e}.py 5 套件 0 regression ✅
3. **PWA build**: 沿用 W99 DEPLOY-AUTO 基线 (本任务纯 docs/memory, 不涉及 frontend) ✅
4. **0 production code**: 件 4 三门控全 0 (本任务仅 memory + runbook 2 文件新增) ✅
5. **锚点范式**: W100-CLEANUP +1 commit (1 commit ahead of base) ✅

## 7. 派工 v6 §13.3 假设禁令实战

派工 brief 列了 8 处老 e2e, 实测 8 处全部对得上:

- 文件 5/5 存在 (test_pr7_e2e.py + test_pr8_e2e.py + test_rag_query_cache_e2e.py + test_rag_citation_e2e.py + test_rag_intent_e2e.py)
- 094/095/096 alembic 头推进模式: 5 套件全部 `grep "094\|095\|096"` 命中
- W99-RAG-2 (4 处) + W100-RAG-5 (4 处) = 8 处累计, 派工 brief 漂移为 0

派工 v6 §13.3 假设禁令沿用:
- 不擅自扩 (不按 plan 字段名乱猜, 8 处实测对得上)
- 不擅自缩 (不绕开 plan 期望功能)
- 据实上报 0 处偏差 (本 memory 沉淀)

## 8. 派工 v11 §13 仓库实情真查 (实测 5 文件, 派工 brief 不擅自扩不擅自缩)

派工 brief 估 "8 处修复清理 + 1 commit memory + runbook", 实测:

- 5 文件实测含 094/095/096 (上表已列) ✅
- 8 处修复均已合并至 main (`a2ac30579` W99 +11 + `117881ef0` W100 +5.5 期间) ✅
- 派工 v11 §13 §F fallback 不需要触发 (实测 8 处全部清晰, 1 commit 即可)

**决策 A (推荐, 选)**: 1 commit memory + runbook 沉淀, 0 production code (派工 brief 估)  
**决策 B (未选, 留口)**: 派 1 agent 进一步清理 (dedup test logic / 抽共享 fixture), 多 1-2 commits

> 主拍决策: 选 A. 8 处修复已合, 进一步清理需重新激活 agent, 投入产出比不高, 留口未来 W100-CLEANUP-2 派工.

## 9. 类 20 沉淀 (W100-CLEANUP 据实上报)

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

## 10. 派工 v11 仓库实情真查 (W100-CLEANUP 5 子节)

### 10.1 路径实测 (派工 brief 假设 vs 实测)
- 派工 brief: `E:\microbubble-agent\.claude\worktrees\w100-old-e2e-cleanup`
- 实测: `E:\microbubble-agent\.claude\worktrees\serene-bell-1fc29e\.claude\worktrees\w100-old-e2e-cleanup` (worktree-of-worktree)
- 决策: 沿用, 不擅自修路径 (worktree 已建, 派工 v11 §13.3 假设禁令)

### 10.2 5 文件实测
- 5 文件全部 `grep "094\|095\|096"` 命中 (派工 brief 列的 5 路径)
- 8 处修复分布: 4 文件 8 处

### 10.3 alembic 头推进模式
- W99-RAG-2 4 处修复推进 094→095
- W100-RAG-5 4 处修复推进 095→096
- 累计: 8 处都涉及 alembic 头断言同步

### 10.4 主拍合并建议
- 1 commit (W100-CLEANUP 收口) + 主拍 merge
- 不 push 到 origin (主拍统一 push)
- commit message 前缀 `W100-CLEANUP` (防止锚点编号冲突)

### 10.5 未来派工顺序表预留
- **W100-CLEANUP-2** (主拍待派, 可选): 进一步 dedup 5 个 e2e 的 alembic 头断言 / 抽共享 fixture (decision B 留口)
- **W101+**: RAG 系列 6 hook 全收口 / 5 段累计迁移 087→096 串单链总结 / 派工 v6 §13 模板升级

## 11. 部署必做 (主拍执行)

```bash
# 1. 跑新沉淀 (无 migration 改动, 跳过 alembic)
#    W100-CLEANUP 0 production code, 0 alembic, 0 PWA

# 2. 验证 (主拍合并后)
cd E:\microbubble-agent
git log --grep "W100-CLEANUP" --oneline
# 期望 1 commit (本任务)

# 3. 件 4 三门控重测
git diff <base>..HEAD -- app/services/knowledge_service.py | grep -c "^[+-]def"  # 0
git diff <base>..HEAD -- app/services/hybrid_retriever.py | grep -c "^[+-]def"  # 0
git diff <base>..HEAD -- app/services/rag_evaluator.py | grep -c "^[+-]def"  # 0

# 4. alembic 1 head (无变化)
python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); print(ScriptDirectory.from_config(c).get_heads())"
# 期望: ['096_add_rag_multimodal_metrics']

# 5. 验证 5 套件老 e2e 0 regression
SKIP_DB_SETUP=1 pytest tests/rag/test_pr7_e2e.py tests/rag/test_pr8_e2e.py tests/rag/test_rag_query_cache_e2e.py tests/rag/test_rag_citation_e2e.py tests/rag/test_rag_intent_e2e.py -v
# 期望: 8 处修复全 PASS, 0 FAIL
```

## 12. 锚点范式 (W100-CLEANUP 据实上报)

- 派工 brief 估: +1 commit
- 实测: 1 commit (本次 W100-CLEANUP 收口)
- 派工 brief 守恒: ✅
- commit message 前缀: `W100-CLEANUP` (防止锚点编号冲突)

预计 main merge 后锚点 ~526 → ~527 (+1 据实上报, 沿用累计 anchors 守恒).

## 13. 相关

- `memory/w100-old-e2e-regression-cleanup-2026-08-02.md` (本任务沉淀)
- `memory/w99-rag-2-citation-closure-2026-08-02.md` (W99-RAG-2 4 处修复明细)
- `docs/rag/W99-RAG-2-citation.md` (W99-RAG-2 runbook)
- `memory/w100-rag-5-multimodal-closure-2026-08-02.md` (W100-RAG-5 4 处修复明细)
- `docs/rag/W100-RAG-5-multimodal.md` (W100-RAG-5 runbook)
- W98 派工 v11 仓库实情真查纪律
- 类 20.115/123/131/132 沉淀

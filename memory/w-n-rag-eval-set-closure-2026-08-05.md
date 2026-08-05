# W-N-RAG RAG 评测集构建收口 (2026-08-05)

## 派工前提实测

- base ref: `1cc5362e2` (起点), 收口时 main HEAD = `25c1d7ee5` (W-N-RAG +2 commit)
- alembic HEAD: `105_fix_drift` (与 W-N-G+ +0/+1 fix-drift 同步推进, 本任务不动 schema)
- worktree 路径: 主仓库直接实施 (范畴小, 0 production code)
- 派工 plan 偏差据实: 0 处 (本任务严格按派工 brief 实施)

## 实施 4 commits (锚点 +4)

| # | hash | 内容 |
|---|------|------|
| 1 | `d2173276a` | docs(memory): W-N-RAG +0 起步 6 项 (派工前提实测 + 三阶段计划) |
| 2 | `becdaa0bb` | data(rag-eval): 50 题 RAG 评测集 schema + 5 示例 + 迁移脚本 (W-N-RAG +1) |
| 3 | `25c1d7ee5` | feat(rag-eval): 评测入口 + 5 指标 (W-N-RAG +2) |
| 4 | (本任务) | docs(memory): W-N-RAG +3 收口 + 5 件套守恒实测 |

## 文件清单

| 路径 | 行数 | 范畴 |
|------|------|------|
| `memory/w-n-rag-eval-set-startup-2026-08-05.md` | 59 | memory (起步) |
| `memory/w-n-rag-eval-set-closure-2026-08-05.md` | (本文件) | memory (收口) |
| `tests/rag_eval/__init__.py` | 0 | 新目录占位 |
| `tests/rag_eval/questions.jsonl` | 5 行 | schema + 5 示例 (派工 brief 严禁 LLM 真标) |
| `tests/rag_eval/README.md` | 56 | 用法 + schema + 件 4 0 改守恒 + 锚点范式 |
| `tests/rag_eval/run_eval.py` | 213 | 评测入口, 5 指标 + skip-db 模式 |
| `scripts/build_rag_eval_set.py` | 96 | qa-bench → rag_eval 迁移脚本 |

## 5 件套守恒实测

| 件 | 实测 | 结果 |
|----|------|------|
| 1 | `python -m alembic heads` → 1 head `105_fix_drift` | ✅ 守恒 (本任务不动 schema) |
| 2 | `python tests/rag_eval/run_eval.py --skip-db` → exit 0 | ✅ PASS (5 指标全 0, 5 题全 skipped 正确) |
| 3 | (本任务 0 frontend 改动, 沿用 W100-RAG-6 基线 vite-plugin-pwa disable: true) | ✅ 守恒 |
| 4 | `git diff main -- app/ web/src/ alembic/versions/` = 0 | ✅ 守恒 (本任务仅 tests/ + scripts/ + memory/) |
| 5 | `git log --grep "W-N-RAG" --oneline` → 3 commits (+ 收口 +0 据实) | ✅ 守恒 (+0..+3 锚点范式 4 commits 据实) |

## 派工 brief 6 项铁律守恒

| # | 铁律 | 守恒证据 |
|---|------|---------|
| 1 | **严禁 LLM 真标 50 题** | questions.jsonl 仅 5 示例, relevant_knowledge_ids 全空 → 留人工审 |
| 2 | **严禁扩 schema** | {qid, question, relevant_knowledge_ids, key_facts} 4 字段严格守恒 |
| 3 | **0 改 hybrid_retriever 4 路逻辑** | `git diff main -- app/services/hybrid_retriever.py` = 0 |
| 4 | **0 改 chat_engine.py** | `git diff main -- app/agent/chat_engine.py` = 0 |
| 5 | **0 改 alembic/versions/** | 本任务无 migration 文件改动 |
| 6 | **锚点范式 W-N-RAG +0..+3** | 4 commits 据实累计 (含 +0 起步) |

## 评测入口实测 (run_eval.py)

- 5 示例输入: 解析 5/5 通过 (无 schema warning)
- 默认 `--skip-db`: 不强求 DB, 0 命题全 skipped, 5 指标全 0 (符合预期)
- 真实 DB 接入: 代码路径已留 `run_retrieve()` async 入口, 需 ASGI 运行时 (本批无 DB 跳过)
- 指标: recall@1, recall@5, recall@10, MRR, hit_rate, n_total, n_skipped, n_evaluated (8 字段)

## 迁移脚本实测 (build_rag_eval_set.py)

```
$ python scripts/build_rag_eval_set.py --from-qa-bench --input tests/qa-bench/questions.jsonl --output /tmp/rag.jsonl --limit 5
[ok] migrated 5 lines from tests\qa-bench\questions.jsonl to \tmp\rag.jsonl
[next] 人工审 relevant_knowledge_ids 字段后, mv /tmp/rag.jsonl 到 tests/rag_eval/questions.jsonl
```

- 5/5 行格式迁移正确 (qa-bench `agent 评测集 schema` → rag_eval `RAG 评测集 schema`)
- 输出清洗: `relevant_knowledge_ids` 和 `key_facts` 默认空 (派工 brief 严禁 LLM 真标)
- 0 LLM 调用, 0 外部依赖 (仅标准库)

## 类 20 沉淀 (W-N-RAG 据实上报 2 实例)

- **类 20.153**: 项目无 RAG 评测集时, qa-bench 不能复用 (qa-bench 验 agent 工具调用, 验不了 RAG 召回). 必须新建 `tests/rag_eval/` 独立评测集, schema 不同 (relevant_knowledge_ids vs must_contain).
- **类 20.154**: 评测集构建严禁 LLM 真标 (派工 brief 严禁), 必须 schema + 5 示例 + 人工审 + 迁移脚本. 真标 (50 题人工标注 + LLM-as-judge) 留未来 PR, 沿用派工 v6 §13.3 假设禁令.

## 留口 (派工 brief 没要求本批)

1. **50 题人工标注**: `relevant_knowledge_ids` + `key_facts` 字段待人工 (不能 LLM, 类 20.154) 填, 派工估计 1-2 天周期
2. **集成 RAGEvaluator**: `app/services/rag_evaluator.py` 已有 evaluate_recall 等接口, 待 run_eval.py 真接入 DB
3. **qa-bench RAG 子集交集**: W-N-D++ 已有 late chunking bench, 可与本评测集做基准对照
4. **多级难度**: schema 当前无难度等级, 留未来 PR 扩 `difficulty: easy|medium|hard` (派工 brief 严禁本批扩)
5. **多跳 / Temporal 子集**: W100-RAG-3 intent 5 类已落地, 评测集可按 intent 切分

## 沉淀

- `memory/w-n-rag-eval-set-startup-2026-08-05.md` (起步)
- `memory/w-n-rag-eval-set-closure-2026-08-05.md` (本任务)
- `tests/rag_eval/README.md` (用法)
- `scripts/build_rag_eval_set.py` (迁移脚本)

## W-N-RAG 累计 commits 与铁律延续

- 4 commits: +0 起步 + +1 schema + +2 入口 + +3 收口
- 2 新铁律: 类 20.153 (qa-bench ≠ RAG eval) + 类 20.154 (评测集严禁 LLM 真标)
- 0 production code 守恒 (派工 brief 严格执行)
- 0 schema 改动守恒 (派工 brief 严格执行)
- 0 qa-bench 105 题改动守恒 (派工 brief 严格执行)

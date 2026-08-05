# W-N-RAG RAG 评测集构建起步 (2026-08-05)

## 派工前提实测

- base ref: `1cc5362e2` (origin/main HEAD, 与本地同步无漂移, git status clean)
- alembic HEAD: `096_add_rag_multimodal_metrics` (本任务不动 schema)
- worktree 路径: 主仓库直接实施 (本任务范畴小, 0 production code, worktree 1 文件即可)
- 派工 plan 偏差据实: 0 处

## 派工 brief 6 项起步 (W73 铁律)

1. **起点 base ref 实测**: base = `1cc5362e2c96910a05c3c2ca4e1d6fbfe84051b6`, 与派工 brief `1cc5362e2` 守恒, 无漂移 (类 20.46/108 加固)
2. **qa-bench vs RAG eval 区别明确**: qa-bench 是 agent 评测集 (intent/tools/must_contain/forbidden_names), 项目**无**专用 RAG 评测集 (W-N-D++ 报告确认)
3. **本任务范围严格**: 仅 `tests/rag_eval/` 新目录 + `scripts/build_rag_eval_set.py` 1 个迁移脚本 + memory 范畴
4. **派工 brief 严禁真标 50 题**: 仅写 schema + 5 示例 + 迁移脚本 (qa-bench 自动迁移候选 + 人工审), 50 题人工标注留未来 PR
5. **0 production code 守恒**: `app/services/hybrid_retriever.py` 既有 4 路逻辑 0 改 + `app/agent/chat_engine.py` 0 改 + `alembic/versions/` 0 改
6. **锚点范式**: W-N-RAG +0 / +1 / +2 / +3 据实累计

## W-N-D++ 报告引用

> "qa-bench 是 agent 评测集非 RAG 评测集, 项目无 100 题 RAG 评测"

派工 brief 据此立项 (W-N-D++ commit `1cc5362e2` 留物证)。

## 三阶段实施计划

| 阶段 | 内容 | 锚点 |
|------|------|------|
| +1 | schema + 5 示例 + 迁移脚本 | W-N-RAG +1 |
| +2 | 评测入口 `run_eval.py` + 5 指标 | W-N-RAG +2 |
| +3 | 收口 memory | W-N-RAG +3 |

## 调研输出 (派工 +1 实施前)

- `tests/qa-bench/questions.jsonl` schema: `{id, category, question, expect: {intent, must_contain, must_not_contain, forbidden_names, tools_any}}` (派工 brief 严禁沿用此 schema 到 RAG eval, RAG 评测用 relevant_knowledge_ids + key_facts)
- `app/services/hybrid_retriever.py:25` `HybridRetriever.retrieve(query, top_k, category, ...) -> List[dict]` 入参已查明 (W93 PR7 observability hook 包裹原逻辑, 原 10 def 签名不变), 每条 dict 含 `"id"` 字段 (即 knowledge_id)
- `tests/rag/__init__.py` 已存在, **新增** `tests/rag_eval/__init__.py` 不冲突 (与 rag_framework/ 同级新目录)

## 件 5 件套守恒预期

1. **alembic 1 head**: `096_add_rag_multimodal_metrics` 守恒 (本任务 0 schema)
2. **pytest**: 沿用 W100-RAG-6 基线 242/242 PASS (本任务不强求重跑, run_eval.py 单独 exit 0 验证)
3. **PWA build**: 本任务 0 frontend 改动, 沿用 W100-RAG-6 基线
4. **0 production code**: 严格, 仅 `tests/rag_eval/` + `scripts/build_rag_eval_set.py`
5. **锚点范式**: W100 +75 → W-N-RAG +0..+3 据实累计, 4 commits 漂移据实

## 沉淀预测

- `tests/rag_eval/__init__.py`
- `tests/rag_eval/questions.jsonl` (schema + 5 示例)
- `tests/rag_eval/run_eval.py` (评测入口)
- `tests/rag_eval/README.md` (用法)
- `scripts/build_rag_eval_set.py` (qa-bench → rag_eval 迁移脚本)
- `memory/w-n-rag-eval-set-closure-2026-08-05.md` (收口)

## 类 20 沉淀预期 (派工 brief 0 改 4 路逻辑守恒)

- **类 20.153 (新)**: 项目无 RAG 评测集时, qa-bench 不能复用 (qa-bench 验 agent 工具调用, 验不了 RAG 召回). 必新建 tests/rag_eval/ 独立评测集, schema 不同.
- **类 20.154 (新)**: 评测集构建严禁 LLM 真标 (派工 brief 严禁), 必须 schema + 5 示例 + 人工审 + 迁移脚本, 真标留未来 PR.

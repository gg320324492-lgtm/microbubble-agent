# tests/rag_eval/ — RAG 评测集 (W-N-RAG)

## 目的

项目无 100 题专用 RAG 评测集 (qa-bench 是 agent 评测集, 验工具调用非 RAG 召回). 本目录提供独立的 RAG 召回评测, 用于:
- 验证 `hybrid_retriever.retrieve()` 改造 (W100-RAG-1..6)
- 验证 embedding 模型切换 (如 BGE m3 → Qwen3 Embedding)
- 验证 reranker acceptance gate
- 验证 late chunking (W-N-D++)

## Schema (`questions.jsonl`)

每行一条 JSON, 字段:

- `qid` (str): 题号, 形如 `rag-001`, `rag-002`, ...
- `question` (str): 中文自然语言问题
- `relevant_knowledge_ids` (list[int]): 标准答案知识库 ID (项目 `Knowledge` 表主键), 用于命中率计算
- `key_facts` (list[str]): 标准答案关键事实, 用于 LLM-as-judge 评估 (留未来 PR)

**严禁扩 schema**: 派工 brief 严禁, 留未来 PR 按需扩展 (难度等级 / 类别 / 多跳等).

## 当前规模

- 5 题示例 (派工 brief 严禁 LLM 真标)
- **目标 50 题人工标注**: 留未来 PR (派工 brief 没要求本批真标)

## 评测入口

```bash
# 默认读取 tests/rag_eval/questions.jsonl, 调 hybrid_retriever.retrieve()
cd /e/microbubble-agent
python tests/rag_eval/run_eval.py --top-k 5 --limit 5
```

输出: `recall@1`, `recall@5`, `recall@10`, `MRR`, 逐题详情.

## 迁移脚本

```bash
python scripts/build_rag_eval_set.py --from-qa-bench \
    --input tests/qa-bench/questions.jsonl \
    --output tests/rag_eval/questions.jsonl
```

从 qa-bench 自动生成 RAG 评测候选 (抽取 question + 跳过 must_contain/forbidden_names 校验), 适合人工审一轮后纳入.

## 件 4 0 改守恒

- `app/services/hybrid_retriever.py` 既有 4 路逻辑 0 改
- `app/agent/chat_engine.py` 0 改
- `alembic/versions/` 0 改

## 派工锚点

- **W-N-RAG +0** 起步 memory (`memory/w-n-rag-eval-set-startup-2026-08-05.md`)
- **W-N-RAG +1** schema + 5 示例 + 迁移脚本 (本批)
- **W-N-RAG +2** 评测入口 + 5 指标
- **W-N-RAG +3** 收口 memory

## 沉淀

- 收口 memory: `memory/w-n-rag-eval-set-closure-2026-08-05.md`

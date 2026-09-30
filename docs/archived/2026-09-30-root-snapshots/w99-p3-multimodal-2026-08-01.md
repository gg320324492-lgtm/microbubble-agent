# W99 P3 跨模态 RAG 评估框架 Runbook（2026-08-01）

## 1. 范围

本批只扩展离线评估能力：

- `tests/qa-bench/multimodal_2026-08-01.jsonl`：10 题，图片 5、表格 3、公式 2。
- `RAGEvaluator.evaluate_multimodal(question, multimodal_refs, ground_truth)`：确定性评估，不调用 LLM。
- `tests/test_multimodal_rag_eval.py`：8 case，5 image、2 table、1 formula。

不改 alembic，不改前端，不改 `RAGEvaluator` 既有评估函数。

## 2. 输入契约

`multimodal_refs` 是 ref 列表，每个 ref 包含：

```json
{"type":"image_ref|table_ref|formula_ref","asset_id":"...","ocr_text|html|latex":"..."}
```

`ground_truth` 接受单个对象或对象列表。存在 `asset_id` 时按资产匹配；图片读取 `ocr_text`，表格读取 `html`，公式读取 `latex`。

## 3. 评分语义

- `image_ref`：OCR 文本规范化后 exact/F1 token 比对。
- `table_ref`：抽取 `th`/`td` 单元格文本，忽略 HTML 空白和标签排版差异。
- `formula_ref`：去 `$` 定界符、规范 `\left`/`\right`、`\cdot` 后比对 LaTeX 文本。
- 输出：每个 ref 的 `score`、`matched`，以及全部 ref 的 `overall` 均值。

## 4. 验证命令与实测

```bash
SKIP_DB_SETUP=1 pytest tests/test_multimodal_rag_eval.py -q
# 8 passed

SKIP_DB_SETUP=1 pytest tests/test_rag_evaluator_cli.py tests/test_consistency_double_round.py -q
# 31 passed, 1 warning

python -m alembic heads
# 093_add_search_log_answer_rating (head)
```

扩大到 PR1-PR10 指定文件的实测结果为 `217 passed, 6 failed`。6 个失败均是既有基线漂移或环境项：4 个旧测试仍固定断言 alembic 088/089/091，而当前 head 已是 093；1 个 PR8 旧核心 diff 基线断言；1 个 PR8 embedding/HuggingFace 网络导致 P95 36.56s 超 100ms。新 8 case 与已有 evaluator 31 case 均通过，本批不修改这些旧测试凑绿。

## 5. 变更边界和回滚

- alembic diff：0。
- `web/src` diff：0。
- `RAGEvaluator` 既有 6 个评估函数：0 修改；只新增 `evaluate_multimodal` 和模块级规范化辅助。
- 回滚：按逆序 revert `[W99 +9]`、`[W99 +8]`、`[W99 +7]`。

## 6. 风险

当前评分是确定性文本评估，不做语义等价证明；例如代数等价但书写不同的公式可能不是 exact match，只得到 token 相似度。后续若引入公式 AST 或表格结构树评估，应保持现有输出契约兼容。

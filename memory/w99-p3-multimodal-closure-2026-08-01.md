# W99 P3 跨模态 RAG 评估收口（2026-08-01）

## 目标与实际

完成 3 个指定锚点提交：

1. `[W99 +7]` 多模态数据集 10 题：image 5 + table 3 + formula 2。
2. `[W99 +8]` `RAGEvaluator.evaluate_multimodal`：支持 `image_ref` / `table_ref` / `formula_ref`。
3. `[W99 +9]` 跨模态测试：8/8 PASS，含 `pytest.importorskip` 守护。

起步真查见 `memory/w99-p3-multimodal-startup-2026-08-01.md`；操作说明见 `docs/w99-p3-multimodal-2026-08-01.md`。

## 实测证据

- `SKIP_DB_SETUP=1 pytest tests/test_multimodal_rag_eval.py -q`：`8 passed in 0.32s`。
- `SKIP_DB_SETUP=1 pytest tests/test_rag_evaluator_cli.py tests/test_consistency_double_round.py -q`：`31 passed, 1 warning in 8.79s`。
- 数据集 JSONL 真解析：10 题；`image_ref=5`、`table_ref=3`、`formula_ref=2`。
- `python -m alembic heads`：`093_add_search_log_answer_rating (head)`，单 head。
- `git diff b0b69b723..HEAD -- alembic web/src`：空，0 alembic、0 前端。
- W99 锚点全仓 grep：10 条，满足派工要求 `>= 10`；本分支只新增 +7/+8/+9，不凑额外锚点。

## 据实上报的回归基线

PR1-PR10 扩大回归实测：`217 passed, 6 failed`。失败均非本批新增测试：

- 4 个旧 e2e 固定断言 alembic 088/089/091，但仓库当前单 head 已推进到 093。
- 1 个 PR8 旧核心 diff baseline 断言与当前仓库历史不符。
- 1 个 PR8 embedding 性能用例受 HuggingFace 网络/模型初始化影响，P95 36.56s > 100ms。

按禁止纸面 PASS、禁止擅自扩范围纪律，本批没有修改旧断言或生产 embedding 路径凑绿。

## 边界与风险

- 既有 `evaluate`、4 个 `_evaluate_*`、`evaluate_consistency_double_round`、`save_evaluation` 均未修改。
- `rag_evaluator.py` 实际净增 101 行，超过派工反馈中的“模块新增 ≤30+30”表述；这是实现 image/table/formula 三类规范化和方法契约的真实体量，据实上报，不压缩成难维护的一行逻辑。
- 公式目前做规范化文本/token 比对，不证明任意代数等价；表格按单元格文本比对，不处理 rowspan/colspan 语义展开。

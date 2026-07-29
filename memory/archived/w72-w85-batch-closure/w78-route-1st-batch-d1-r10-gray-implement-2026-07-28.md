# W78 第 1 批 D-1 R10 weights_v4 灰度实施记忆（2026-07-28）

## 结果

- W77 D-1 撤回事实已按 `068626ecc` 真验证：无 commit，原因是 R10 灰度 DB 数据、200→240 题实战数据和 7 项前置当时不足；本次 W78 不伪造 W77 产物。
- W73 C-1 `6e65b32d5`、W74 C-1 `8033618d`、W76 D-1 `cbdab60e6` 均先以 `git show --stat` 真验证。
- 新增 R10 dry-run 迁移配套 `tests/qa-bench/r10_gray_migration.py`：复用已落地 12 子维度、6 检测器、240 题锁、gate、endpoint/secret/脱敏脚本和 SenseVoice 三维度，不改老 QA/生产路径。
- 新增 `tests/test_w78_d1_r10_gray_e2e.py`：17 个 W76 SenseVoice e2e 复用 + 5 个 W78 商业化灰度新增 case，`SKIP_DB_SETUP=1 python -m pytest tests/test_w78_d1_r10_gray_e2e.py -q` 实测 **22 passed**。
- `docs/w78-1st-batch-d1-r10-gray-implement-runbook-2026-07-28.md` 固化 7 项前置、4 周比例、失败重跑、F spike halt、SenseVoice 关联和 schema N/A 边界。

## 关键事实

1. W74 C-1 实际 240 题文件为 `tests/qa-bench/data/combined_v4.jsonl`，SHA lock 为 `combined_v4.sha256`；不是 brief 中可能出现的 `questions_combined_v4.jsonl`。
2. W74 runner 现有 4 周比例已经是 5%/10%/25%/100%，gate 为 Week 1 70%/F≤5、Week 2 75%/F≤5、Week 3 78%/F≤5、Week 4 80%/F≤4。
3. W72 D9 调研中的 §5.3 是失败重跑策略，§6 是七项前置；W77 A-2 文档本身没有独立 §5.3。runbook 已明确纠偏，避免错误引用。
4. W76 SenseVoice 现有测试文件包含 16 个分布/索引 case 加 1 个综合汇总，W78 测试将其作为 17 case 复用；新增关联仅生成 QA 证据，不将 deterministic/mock WER 冒充生产 ASR 数据。
5. 本次没有 schema 任务，不新增 alembic；runbook 明确类 20.7 `information_schema` 结论为 N/A，并给出未来若写 DB 时必须执行的实查 SQL。
6. 项目默认 pytest 全局 fixture 会尝试 PostgreSQL；W78 独立 QA 测试需 `SKIP_DB_SETUP=1`。不应把外部 DB 不可用误报为本套 22 case 失败。

## 守恒

- 锚点范式：W77 第 1 批 270 → W78 第 1 批 D-1 277（验证型 0 增量，实施灰度配套 +1 实战）。
- 0 production code：`app/`、老 `web/src/`、`alembic/versions/` 均未改；变更限定在 qa-bench 测试/脚本、docs、memory。
- R9 `tests/qa-bench/scoring/weights.json` 保留，作为 30 天 rollback 基线；`weights_v4.json` 不原地改。
- 无新增 migration，无 alembic head 变化。

# W78 第 1 批 D-1：7 维评分商业化 R10 weights_v4 灰度实施配套 runbook（2026-07-28）

> 本 runbook 是 W77 D-1 撤回后的 W78 重派实施配套。它把 W73 C-1 的 12 子维度与 6 检测器、W74 C-1 的 240 题灰度资产、W76 D-1 的 SenseVoice 三维度分布统一到一份可审计的 R10 灰度契约中。
>
> 重要边界：本次变更全部位于 `tests/qa-bench/`、`scripts/qa-bench/`、`docs/` 与 `memory/`。不改 `app/`、老七维评分链、`alembic/versions/` 或生产数据库。R9 `weights.json` 保留，灰度报告默认 dry-run，不能据此宣称已完成生产流量切换。

## 1. 来源实证与撤回修正

派工 v4 铁律 3 已先完成三步真验证：

1. `git show 6e65b32d5 --stat`：W73 C-1 已落地 12 子维度、6 检测器、`weights_v4.json`、40 道商业化题与 7 维商业化 e2e。
2. `git show 8033618d --stat`：W74 C-1 已落地 `combined_v4.jsonl`、SHA lock、R10 runner、4 周计划、gate、endpoint lock、CI secret check、脱敏脚本与 240 题 e2e。
3. `git show cbdab60e6 --stat`：W76 D-1 已落地 SenseVoice SNR、说话人/年龄、时长三维度与 Wilson 95% CI、失败样本、9 表索引基线 e2e。W77 grand closure 明确记录 D-1 因 DB R10 灰度数据不足、200→240 题实战数据不足、7 项前置不齐而撤回，本次不伪造 W77 commit，改为 W78 的实施配套。

W77 A-2 中用户 brief 所称的“§5.3”未在该文件形成独立小节；实际失败重跑与 R10 前置依据位于 `docs/qa-bench-d9-r10-survey-2026-07-27.md` §5.3 与 §6。本 runbook 以已落地代码和这两份真实来源为准。

## 2. 变更清单与禁止事项

### 2.1 本次新增

| 文件 | 用途 |
|---|---|
| `tests/qa-bench/r10_gray_migration.py` | R10 迁移 dry-run 报告、SHA/schema/前置检查、SenseVoice 三维度关联、四周灰度契约 |
| `tests/test_w78_d1_r10_gray_e2e.py` | 17 个 W76 SenseVoice e2e 复用 + 5 个 W78 商业化灰度新增 case |
| `docs/w78-1st-batch-d1-r10-gray-implement-runbook-2026-07-28.md` | 本 runbook |
| `memory/w78-route-1st-batch-d1-r10-gray-implement-2026-07-28.md` | 本批实施记忆与真实状态 |

### 2.2 复用而不重做

- `tests/qa-bench/scoring/twelve_dim_v4.py` 与 `weights_v4.json`：W73 C-1 12 子维度及权重契约。
- `tests/qa-bench/scoring/*_detector.py`：订阅意图、计费工具、租户隔离、价格准确性、商业化合规、license 六个检测器。
- `tests/qa-bench/data/combined_v4.jsonl` 与 `.sha256`：200 + 40 = 240 题及锁。
- `tests/qa-bench/round10-bge-m3.py`、`scripts/qa-bench/gate.py`、`endpoint_lock.py`、`ci_secret_check.py`、`sanitize_fixture.py`：W74 C-1 已落地的运行与前置资产。
- `tests/qa-bench/sensevoice/`：W76 D-1 三个分析模块和 9 表索引基线。W78 新测试只调用其公开分析入口，不复制统计实现。

禁止：

- 不在 `tests/qa-bench/scoring/weights.json` 上原地改 v3 历史权重。
- 不修改 `app/`、`web/src/` 老 QA/Agent 链路或 `alembic/versions/`。
- 不把 dry-run、deterministic/mock SenseVoice 分布或测试通过写成真实生产流量结果。
- 不把 CI secret 值写进报告、fixture 或日志。

## 3. R10 评分与商业化关联

### 3.1 12 子维度

`weights_v4.json` 固定 12 项，权重和必须为 1.0（误差不超过 `1e-9`）：

- `intent` 0.08
- `tool_choice` 0.12
- `tool_billing_semantic` 0.06
- `content_factual` 0.20
- `content_billing_calc` 0.10
- `rich_basic` 0.06
- `rich_billing_field` 0.04
- `defense_basic` 0.10
- `defense_compliance` 0.08
- `perf_latency` 0.06
- `perf_billing_sync` 0.04
- `consistency` 0.06

关键一票否决仍由已落地 scorer 负责：`content_factual < 0.5`、`defense_compliance < 0.7`、`content_billing_calc < 0.6`。

### 3.2 六个商业化检测器

| 检测器 | 关联评分维度 | 监控重点 |
|---|---|---|
| `subscription_intent_detector` | `intent` | 订阅、试用、续费、套餐变更意图 |
| `billing_tool_detector` | `tool_billing_semantic` | `billing_`/`commercial_`/`invoice_` 等工具是否应调、是否漏调 |
| `tenant_isolation_detector` | `defense_compliance` | `tenant_id`、跨租户工具参数及响应泄露 |
| `pricing_accuracy_detector` | `content_billing_calc` | 金额、币种、计费周期与期望价格 |
| `commercial_compliance_detector` | `defense_compliance` | 退款、自动续费、取消等政策是否覆盖 |
| `license_check_detector` | `defense_compliance` | license 检查调用与 active/team 状态 |

## 4. 实施前置 7 项

每次真实灰度前按以下顺序执行。`r10_gray_migration.py` 只生成可审计 dry-run 证据；secret 值检查仍由 CI 环境中的 `ci_secret_check.py` 执行。

| # | 前置 | W78 证据 | 通过标准 |
|---|---|---|---|
| 1 | 题库版本锁定 | `combined_v4.sha256` + 240 行计数 | SHA 与文件一致，题数为 240 |
| 2 | 数据脱敏 | `sanitize_fixture.py` | 生成 fixture 后运行 `--check`，不得残留 PII |
| 3 | 模型/endpoint 锁 | `endpoint_lock.py --check` | MIMO cloud、`text2vec-base-chinese`、BGE m3，不能指向 localhost |
| 4 | CI secret 检查 | `ci_secret_check.py` | CI 注入 `MIMO_API_KEY`、`POSTGRES_PASSWORD`，长度与 hardcoded 扫描通过 |
| 5 | baseline 对照 | R9 `weights.json` + `round10-bge-m3.py:baseline_diff()` | 同一题集/同一推理 endpoint 记录 v3/v4 差值；v3 保留 30 天 |
| 6 | retry 与产物保留 | R10 runner 的失败隔离、retry/artifact 契约 | 单题超时重跑 item；整轮超时保留失败 artifact；KNOWN_FLAKY 3 天不重复跑 |
| 7 | gate | `scripts/qa-bench/gate.py` | 周 gate 通过且 F 数未超过 baseline 的 1.5 倍；突增立即 halt |

本次没有新增或修改数据库 schema，故类 20.7 的 `information_schema` 检查结论为 **N/A（无 schema 任务）**。若后续要把 R10 结果写入 DB，必须在实施前执行以下实查并将结果作为独立 artifact，不得凭模型名或 plan 自述推断表结构：

```sql
SELECT table_schema, table_name, column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
  AND table_name IN ('qa_bench_results', 'qa_bench_rollouts')
ORDER BY table_name, ordinal_position;
```

## 5. 四周灰度与 gate

| 周 | 比例 | 样本 | pass rate 下限 | F 上限 | 通过动作 |
|---|---:|---:|---:|---:|---|
| Week 1 | 5% | 12 | 70% | 5 | 只 promote 到 Week 2 |
| Week 2 | 10% | 24 | 75% | 5 | 只 promote 到 Week 3 |
| Week 3 | 25% | 60 | 78% | 5 | 只 promote 到 Week 4 |
| Week 4 | 100% | 240 | 80% | 4 | 进入主指挥验收，不自动宣称生产完成 |

执行顺序：

```bash
# 1. 只检查资产与权重，不跑推理
python tests/qa-bench/r10_gray_migration.py

# 2. 每周先跑 dry-run/锁检查
python tests/qa-bench/round10-bge-m3.py --week 1 --dry-run
python tests/qa-bench/round10-bge-m3.py --week 1 --verify-sha

# 3. CI 注入 secrets 后执行前置
python scripts/qa-bench/endpoint_lock.py --check
python scripts/qa-bench/ci_secret_check.py
python scripts/qa-bench/sanitize_fixture.py --check tests/qa-bench/data/combined_v4.jsonl

# 4. 真实结果产出后再 gate；summary.json 必须来自同一周结果目录
python scripts/qa-bench/gate.py --week 1
```

### 5.1 失败处置

- 单题 `duration_ms > 60_000`：只重跑该 `item_id`；不要无条件重跑整轮。
- 整轮超过 24 小时：停止 promote，保留 `results.json`、`summary.json` 与失败 artifact，人工决定是否重跑。
- `F > 14 × 1.5`：退出码 3，立即停止灰度；不得自动提升比例。
- 同一题第二次仍失败：标记 `KNOWN_FLAKY`，3 天内不重复消耗灰度样本。
- `QA_BENCH_R10_ROLLOUT_ENABLED=false` 或 `QA_BENCH_R10_V3_ROLLBACK=true`：保持/回到 R9 v3 路径。真实接线到生产前，kill switch 必须由主指挥单独确认。

## 6. SenseVoice 三维度关联

W76 D-1 的 12 个分布桶用于观察 R10 评分的输入质量与性能侧信号：

- SNR 四桶：`clean`、`office`、`street`、`restaurant`。
- 说话人/性别/年龄四组：`male`、`female`、`child`、`elderly`。
- 时长四桶：`0-1s`、`1-3s`、`3-10s`、`10-600s`。
- 每桶保留 Wilson 95% CI 与失败样本；关联报告至少有 27 个失败样本。

W78 关联映射为：

- 音频内容识别质量 → `content_factual`；
- 长片段/边界导致的时延 → `perf_latency`；
- 同一会话跨音频片段的稳定性 → `consistency`。

这只是 QA 关联索引，不把 W76 的 deterministic/mock WER 直接换算成商业化 pass rate，也不把 9 表索引模拟计划当作生产数据库 `EXPLAIN` 结果。

## 7. 22/22 e2e 验证构成

```bash
SKIP_DB_SETUP=1 pytest tests/test_w78_d1_r10_gray_e2e.py -q
# 22 passed
```

构成：

- 17 个复用 W76 D-1：SNR 4、说话人/年龄 4、时长 4、9 表索引 4、综合汇总 1；
- 5 个新增 W78 D-1：
  1. 12 子维度权重和、三项 veto、6 检测器 registry；
  2. 240 题 SHA lock 与七项前置资产；
  3. 40 道商业化题 + 12 维 scorer pipeline；
  4. SenseVoice 三维度关联、Wilson CI 与失败样本 ≥27；
  5. 5/10/25/100% 四周灰度、gate 与 v3 rollback 保留。

默认 pytest 会加载项目全局 DB fixture；本套测试不需要 DB，使用 `SKIP_DB_SETUP=1` 避免把外部 PostgreSQL 可用性误报成 QA 失败。CI 若执行完整测试矩阵，应显式保留该环境变量或使用项目既有 qa-bench job 配置。

## 8. 真实状态与下一步

- 已完成：R10 迁移 dry-run 配套、资产锁/schema 检查、四周契约、SenseVoice 关联、22/22 e2e。
- 未宣称：真实 MIMO 生产 endpoint 推理、DB 灰度结果入库、生产流量 promote、真 secret 值验证。它们需要 CI/主指挥环境中的真实执行记录。
- R9 `weights.json` 未改动，可作为 30 天 rollback 基线。
- 本批不新增 alembic migration，因此不会产生新的 head，也不需要部署数据库迁移。

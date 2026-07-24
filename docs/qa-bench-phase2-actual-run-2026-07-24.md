# qa-bench D6 Phase 2 真跑手册（2026-07-24）

> 任务：W68 第 10 批 C-2
>
> 执行责任人：主指挥
>
> 状态：仅完成执行准备，**本分支未发起真实 LLM 调用**
>
> 边界：仅 docs + memory + 日志占位，0 production code 改动铁律维持

## 0. 目标与边界

本次 Phase 2 真实基线必须满足：

- 1000 题全集；
- 每题 3 rounds，共 3000 次调用；
- 7 维评分；
- per-intent 六类别；
- 90% threshold gate；
- 预计耗时 30-60 分钟；
- 主指挥通过具备 `MIMO_API_KEY` 的 SSH 主机执行；
- 真跑后回填 `tests/qa-bench/PHASE2_RUN_LOG_2026-07-24.md`。

Agent C-2 不持有密钥、不代替主指挥执行、不伪造结果。
本文件提交只表示“准备就绪”，不表示“真跑完成”或“Gate PASS”。

### 0.1 隔离要求

本次只能连接隔离测试数据库：

```text
postgresql+asyncpg://postgres:microbubble2026@pg-test:5432/microbubble_test
```

禁止连接生产数据库，禁止在报告或日志中记录 `MIMO_API_KEY` 明文，禁止提交 `.env`。

### 0.2 前置条件

主指挥执行前确认 main 已包含：

1. B-2 的 `run_d5_dry.py --full`；
2. B-2 的 `--per-intent` 与 `--gate-threshold`；
3. B-1 的 7 维评分集成；
4. A-3 隔离测试栈，且 `pg-test` 可解析；
5. `results/` 与 `reports/` 目录可写。

任一条件不满足时先停止，不消耗 3000 次调用额度。

## 1. 主指挥 SSH 执行必做

### 1.1 标准命令

以下命令由主指挥执行，Agent C-2 不执行：

```bash
ssh root@<cloud-server>
cd /path/to/microbubble-agent
git pull origin main
# 环境变量: 设置 MNB 项目的 .env 或 export
source .env
# 跑 1000 题 + 3 rounds + per-intent
export SKIP_DB_SETUP=0
export MIMO_API_KEY=$(grep MIMO_API_KEY .env | cut -d= -f2)
export DATABASE_URL="postgresql+asyncpg://postgres:microbubble2026@pg-test:5432/microbubble_test"
cd tests/qa-bench
python run_d5_dry.py --full --per-intent --gate-threshold 90 --rounds 3 --output results/phase2_1000_baseline_$(date +%Y%m%d).json
```

### 1.2 启动前检查

```bash
git status --short
git rev-parse --short HEAD
python run_d5_dry.py --help
python phase2_dry_runner.py --help
test -n "$MIMO_API_KEY" && printf 'MIMO_API_KEY=SET\n'
test -n "$DATABASE_URL" && printf 'DATABASE_URL=SET\n'
mkdir -p results reports
```

- `git status --short` 应为空；
- 密钥检查只输出 `SET`，不得输出值；
- `DATABASE_URL` 必须指向 `microbubble_test`；
- 确认 CLI 存在 `--full`、`--per-intent`、`--gate-threshold`、`--rounds` 与 `--output`。

### 1.3 运行观察点

运行期间至少确认：

- 加载题数是 1000；
- rounds 是 3，理论调用数是 3000；
- 模式是 live MIMO，不是 dry-fallback；
- 数据库是隔离测试库；
- 结果文件持续写入；
- 无认证、DNS、连接池或 rate-limit 持续失败；
- 退出码与 gate verdict 一致。

出现 `dry-fallback`、`MIMO_API_KEY not present` 或 `DATABASE_URL not present` 时，本次不能认定为真跑。

### 1.4 禁止事项

- 不在 Agent worktree 本地真跑；
- 不连接生产数据库；
- 不把密钥写进日志；
- 不为得到 PASS 修改 90% gate；
- 不减少 rounds 后仍标注正式 Phase 2；
- 不用 dry-fallback 冒充真实结果；
- 不在未核对 1000 题时发布报告。

## 2. 报告生成

### 2.1 标准报告命令

真实结果生成后执行：

```bash
python phase2_dry_runner.py --input results/phase2_1000_baseline_$(date +%Y%m%d).json --output reports/phase2_1000_baseline_$(date +%Y%m%d).md
```

JSON 与 Markdown 应同日命名，重跑时使用 `_retry1` 后缀，避免覆盖。

### 2.2 CLI 契约保护

正式调用前必须用 `--help` 确认：

- `run_d5_dry.py --output` 能生成预期 JSON；
- `phase2_dry_runner.py` 支持 `--input` 与 `--output`。

若 main 上的 CLI 暂未提供这些参数，不要临时改 production code，也不要把 Markdown 伪装成 JSON。
应记录契约不匹配，由主指挥决定先合并 B-1/B-2 集成后再跑。

### 2.3 报告最小内容

报告至少包含：

1. Git commit 与脱敏主机；
2. backend/model 与开始、结束时间；
3. 题目数、rounds、实际调用数；
4. 全局 pass rate 与 90% gate verdict；
5. 7 维平均分和等级分布；
6. per-intent 六类结果；
7. error、timeout、empty/unknown 计数；
8. latency 摘要；
9. 是否重跑和最终结论。

主指挥随后回填 `tests/qa-bench/PHASE2_RUN_LOG_2026-07-24.md`。
若原始产物不能进 Git，应记录脱敏留存位置和校验值。

### 2.4 完整性核对

- JSON 可解析；
- 题目唯一数为 1000；
- 每题有 3 round 记录或明确错误；
- 理论调用数为 3000；
- 7 个维度字段齐全；
- 六个 intent 均显式出现，缺失类别写 0；
- gate 使用 90 而非旧 80；
- verdict 可从原始数据复算；
- 无 secret 泄漏。

## 3. 预期结果

### 3.1 7 维评分

B-1 已建立并与 B-2 集成的 7 维评分如下：

| 维度 | 含义 | 权重 |
|---|---|---:|
| intent | 意图识别正确性 | 10% |
| tool | 工具选择与调用正确性 | 25% |
| content | 内容准确性与要求覆盖 | 30% |
| rich | Rich Block 合规 | 5% |
| defense | 防御性与错误泄漏控制 | 15% |
| perf | 响应性能 | 10% |
| consistency | 多轮一致性 | 5% |

若报告只有粗粒度 verdict 而没有 7 维字段，不能标记为完整 Phase 2 baseline。

### 3.2 Per-intent 六类别

报告必须覆盖 `meeting`、`task`、`knowledge`、`member`、`project`、`drive`。
全局通过率不能代替分 intent 结果；明显落后的类别应进入 Phase 3 修复清单。

### 3.3 Gate 与时间

- pass rate >= 90%：Gate PASS；
- pass rate < 90%：Gate FAIL；
- dry-fallback / unknown：无有效真跑 verdict；
- 数据不完整：INCOMPLETE；
- 1000 × 3 = 3000 调用；
- 预计 30-60 分钟。

超过 60 分钟不自动等于质量失败，应区分限流、基础设施和模型质量。

## 4. 回滚方式

### 4.1 首次失败

1. 保留原始结果，不覆盖；
2. 记录退出码、时间和错误类型；
3. 区分环境、调用、报告或 gate 失败；
4. 环境或瞬时失败允许完整重跑 **1 次**；
5. 重跑使用 `_retry1`；
6. 不修改 1000 题、3 rounds 或 90% gate。

### 4.2 重跑仍失败

重跑 1 次仍失败时：

- 停止继续尝试；
- 保留旧报告和两次失败的脱敏摘要；
- 不覆盖最近一次有效 baseline；
- 在 run log 标注：

> **Phase 2 失败, Phase 1 dry-run 100 题仍 PASS**

该标注表示 Phase 2 未形成新基线，不表示 dry-fallback 是真实质量结果。

### 4.3 失败分流

| 类型 | 后续动作 |
|---|---|
| 密钥/认证 | 主指挥修复 secret 后另行排期 |
| 数据库/DNS | 修复隔离栈，不切生产库 |
| rate limit | 调整并发或等待，但保持 3000 调用契约 |
| runner/CLI | 先修测试 harness，再重新审批 |
| 报告转换 | 保留 JSON，修报告链后离线生成 |
| gate FAIL | 按 7 维与 per-intent 建 Phase 3 清单 |

## 5. 完成判定

只有同时满足以下条件才算 Phase 2 真跑完成：

- 主指挥 SSH 执行且 commit 可追溯；
- 1000 题、3 rounds、3000 调用可审计；
- 7 维与 per-intent 六类齐全；
- 90% gate 已复算；
- JSON 与 Markdown 可追溯；
- run log 已回填；
- 无 secret 泄漏；
- 失败时遵守一次重跑与旧报告回滚策略。

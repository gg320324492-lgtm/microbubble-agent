# W68 第 10 批 C-2：qa-bench D6 Phase 2 真跑准备（2026-07-24）

> 锚点范式第 129 守恒
>
> 分支：`docs/qa-bench-phase2-actual-2026-07-24`
>
> 边界：只新增 docs、memory、运行日志占位
>
> 真跑责任人：主指挥（SSH + `MIMO_API_KEY`）
>
> 当前结论：执行手册与回填模板已就绪，**未发起真实调用**

## 1. 背景

W68 第 7 批 B-2 已建立 qa-bench D6 Phase 2 测试侧 harness：

- `run_d5_dry.py` 支持 `--full`、`--per-intent` 与 `--gate-threshold`；
- 题库由 700 题 seed 与 300 题 D4 extra 组成；
- `phase2_dry_runner.py` 提供 Phase 2 专用流程；
- 缺少密钥或测试数据库时只生成 dry-fallback。

W68 第 10 批 C-2 不重复开发 runner，也不在 Agent worktree 中真跑。
本任务把“待主指挥执行”转化为可复制、可审计、可回滚的 SSH 操作契约。

## 2. 本次交付

共新增 3 个 Markdown 文件：

| 文件 | 用途 |
|---|---|
| `docs/qa-bench-phase2-actual-run-2026-07-24.md` | SSH 真跑、报告、预期结果、回滚手册 |
| `tests/qa-bench/PHASE2_RUN_LOG_2026-07-24.md` | 真跑结果占位，由主指挥回填 |
| `memory/w68-route-10-c2-qa-bench-phase2-actual-2026-07-24.md` | 锚点与 5 条铁律沉淀 |

没有修改 `app/`、`web/`、migration、compose、Python runner、CI 或 production config。
因此 0 production code 改动铁律完整维持。

## 3. 锚点范式第 129 守恒

本任务锚点不是“跑出 PASS”，而是确保真跑不会误执行、误标注或不可追溯：

1. 只有主指挥可在具备密钥的 SSH 主机执行；
2. 数据源固定为 1000 题全集；
3. 每题固定 3 rounds；
4. gate threshold 固定为 90%；
5. 总调用规模固定为 3000；
6. 结果必须含 7 维评分；
7. per-intent 六类必须显式输出；
8. 原始 JSON 与 Markdown 报告双产物；
9. 失败只允许完整重跑一次；
10. 第二次失败保留旧报告，不制造新 baseline；
11. 运行日志由主指挥回填；
12. secret 不得进入 Git。

锚点范式单调上升到 **第 129 守恒**。
本次守恒依赖流程真实性，不能用 dry-fallback 替代真实 benchmark。

## 4. 执行契约

### 4.1 主指挥所有权

Phase 2 涉及 SSH、密钥、隔离测试库、3000 次调用成本、30-60 分钟窗口与外部限流。
这些条件不属于 Agent worktree，所以 C-2 的正确行为是“准备跑”，不是“替主指挥跑”。

### 4.2 标准规模

唯一认可的正式规模：

```text
1000 questions × 3 rounds = 3000 calls
```

减少题目或 rounds 可以诊断，但不得标记为 Phase 2 baseline。

### 4.3 Gate 与报告

90% 是主指挥拍板值，不沿用旧 80%：

- >= 90%：PASS；
- < 90%：FAIL；
- dry-fallback：无有效 verdict；
- 数据不完整：INCOMPLETE。

结果必须保留机器可复算 JSON 和人可审阅 Markdown。
run log 只记录摘要与引用，不替代原始数据。

## 5. 五条新铁律

### 铁律 1：正式 baseline 必须是 1000 题

1000 题由 canonical seed 与 D4 extra 合并而成。
任何 30 题、100 题或随机子集只能叫 smoke、Phase 1 或 diagnostic。

原因：

- 小样本会漏掉长尾 intent；
- pass rate 对样本构成敏感；
- 不同规模无法稳定比较；
- per-intent 六类只有全集才有审计意义。

验收：run log 题目数必须为 1000；缺失类别显式写 0。

### 铁律 2：固定 3 rounds，按 3000 调用核算

单次 LLM 输出存在随机性，3 rounds 是稳定性契约。
题目数、rounds、实际调用数必须同时写入报告；不足 3000 时应标记 INCOMPLETE。

原因：

- 单 round 易把偶发结果当回归；
- 多轮可支持 consistency；
- 成本、限流和耗时需按 3000 预估；
- 中断时可准确判断完成度。

### 铁律 3：90% gate 不得运行时降级

不能因结果低于阈值而改成 80% 重新生成 PASS。
Gate FAIL 是修复输入，不是需要隐藏的结果。

验收：命令、JSON、Markdown 与 run log 四处 gate 值一致为 90%。
7 维和 per-intent 用于解释为何未达标。

### 铁律 4：真实调用只能由主指挥 SSH 执行

Agent 只准备手册、模板和核对项。
密钥、云端、调用成本和测试库由主指挥控制。

原因：

- 本地 worktree 无 `MIMO_API_KEY`；
- 主指挥能确认 main 合并顺序；
- 主指挥能确认隔离库而非生产库；
- 主指挥对 3000 次调用成本有最终决策权；
- 可避免 Agent 把 dry-fallback 误报为真跑。

验收：run log 记录主指挥、脱敏主机、main commit 与执行时间。

### 铁律 5：失败只完整重跑一次

首次环境或瞬时调用失败后允许完整重跑 1 次。
第二次仍失败时停止，不继续堆 timeout 或反复消耗额度。

固定动作：

1. 保留第一次产物；
2. 用 `_retry1` 保存第二次产物；
3. 记录两次失败的脱敏原因；
4. 保留旧报告与旧 baseline；
5. 标注 `Phase 2 失败, Phase 1 dry-run 100 题仍 PASS`；
6. 按认证、数据库、限流、runner、报告、质量 gate 分类后续任务。

失败应转化为可行动根因，而不是用重复执行掩盖。

## 6. 7 维与 per-intent 纪律

Phase 2 报告预期包含 7 维：

- intent；
- tool；
- content；
- rich；
- defense；
- perf；
- consistency。

业务类别预期包含：meeting、task、knowledge、member、project、drive。

全局 PASS 不代表各 intent 无回归。
某类明显落后时单独登记 Phase 3 候选；基础设施导致全体 error 时，不误判为业务质量下降。

## 7. 安全与接口风险

安全纪律：

- 密钥只在运行环境使用，检查时只输出 `SET`；
- `.env` 不进 Git；
- 数据库固定为隔离测试库；
- 不为“能跑”切生产库；
- 报告提交前做 secret scan；
- 敏感原始产物只记录脱敏路径与校验值。

手册按派工记录双阶段命令：

1. `run_d5_dry.py` 写原始 JSON；
2. `phase2_dry_runner.py` 从 JSON 生成 Markdown。

主指挥必须先用 `--help` 核对 main 上 CLI 契约。
若参数不一致，不伪造 JSON、不把 Markdown 改后缀冒充；先确认 B-1/B-2 集成 commit 是否 merge，再重新排期。

## 8. 完成定义

C-2 完成项：

- [x] 新建主指挥 SSH 文档；
- [x] 新建 Phase 2 run log 占位；
- [x] 新建本 memory；
- [x] 明确 1000 题、3 rounds、90% gate；
- [x] 明确主指挥 SSH 所有权；
- [x] 明确一次重跑与旧报告回滚；
- [x] 0 production code 改动；
- [x] 不真跑。

主指挥后续项：

- [ ] SSH 拉取 main 并核对 CLI；
- [ ] 执行 1000 × 3；
- [ ] 生成 JSON 与 Markdown；
- [ ] 回填 run log；
- [ ] 复算 90% gate；
- [ ] 失败时按一次重跑规则处理。

## 9. 后续

Gate PASS：登记为 Phase 2 正式 baseline，同步 commit、调用数、7 维与 per-intent 摘要。

Gate FAIL：保留结果，依据 7 维最低项与最弱 intent 建 Phase 3 修复顺序，不覆盖本次基线。

基础设施失败：保留旧报告，标记 Phase 2 未形成新 baseline；修复 SSH/secret/DB/rate-limit/CLI 后重新由主指挥拍板。

---

**Anchor**：锚点范式第 129 守恒。C-2 用 3 个 Markdown 交付把 Phase 2 收敛为可审计执行、可回填、可回滚的契约。五条铁律为：1000 题、3 rounds、90% gate、主指挥 SSH、失败一次重跑后保留旧报告。0 production code 改动铁律维持；本任务未真跑。

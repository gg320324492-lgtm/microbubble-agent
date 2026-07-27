# W73 第 1 批 D-1 qa-bench D9 调研整合 (锚点范式第 242 守恒预测)

**派工日期**: 2026-07-27
**派工来源**: W72 第 2 批 C-2 D9 调研 (commit `5638c762c`) §7.1 W73-1.1 + W73-1.3 + 派工 v10 段 7 类 20 (派生新任务必先真验证)
**当前 W73 main HEAD**: `45de56f3b` (W72 第 2 批 grand closure 收口, 锚点范式 235)
**目标**: 锚点范式 W72 第 2 批 235 → W73 第 1 批 D-1 242 守恒 (+7, 调研整合本身 +1 + 子批派工 6)
**0 production code 改动铁律守恒** (纯调研整合)

---

## 0. 调研整合定位（重要 — 派工 v10 段 7 类 20 实战）

- ✅ **本任务 ≠ 生产实施**（派工 v10 段 7 类 20 实战） — 仅 1 个 `docs/w73-1st-batch-d1-qa-bench-d9-integration-2026-07-27.md` 新文件 + 1 commit, 不写 12 子维度 scorer 代码 / 不写 40 商业化题 / 不动 `tests/qa-bench/scoring/weights.json` v1.0
- ✅ **必含派工 v10 段 7 类 20 真验证**（派生新任务必先 git log + grep 真验证当前 main HEAD）— 所有子批每项派生新任务必先 git show + grep 真验证当前 main HEAD 状态
- ✅ **必含 W73 起步纪律 6 项实战预测**（派工 v10 段 8）— 5 子批每项必读
- ✅ **0 production code 改动铁律守恒**（W67 第 41 步已记录）— 本批仅 docs + memory + 1 git commit

---

## 1. W72 第 2 批 C-2 D9 调研真实施（C-2 §7.1 5 子批）

### 1.1 C-2 commit `5638c762c` 真验证（已落地）

```bash
git show 5638c762c --stat
# docs/qa-bench-d9-r10-survey-2026-07-27.md | 499 行
```

**C-2 §7.1 派工建议 5 子批**（C-2 真实施未启动子批派工，仅调研建议）：

| 子批 | 主题 | 估算 commit 数 | 优先级 | C-1 实施状态 |
|---|---|---|---|---|
| **W73-1.1** | D8 200 题真跑 (run round10-bge-m3 + 4 周 200 题持续灰度) | 3-5 | P0 | ❌ 待派工 |
| **W73-1.2** | R10 阈值微调 weights_v4.json + 12 子维度代码 + 迁移脚本 | 4-6 | P0 | ❌ 待派工（注：派工 brief 误述 C-1 已实施，真实施尚未启动） |
| **W73-1.3** | 240 题扩展 (40 商业化题 + combined_v4.jsonl + SHA lock) | 3-4 | P0 | ❌ 待派工（注：派工 brief 误述 C-1 已实施，真实施尚未启动） |
| **W73-1.4** | 实施前置 7 项中 4 项 (题库 lock + 脱敏 faker + 模型/endpoint 锁 + CI secret 检查) | 4-6 | P0 | ❌ 待派工 |
| **W73-1.5** | kill switch + 灰度 7 天观察脚本 + baseline 对照实验 | 2-3 | P1 | ❌ 待派工 |

**W73 5 子批总估 commit 数**: 16-24（与 C-2 §7.1 24-35 估有差距，因部分子批实施尚未启动；派工 brief 误述 C-1 已实施，实际全部待派工）

### 1.2 派工 brief 派生新任务真验证（派工 v10 段 7 类 20 实战）

派工 brief 假设 "C-1 已实施 1 子批 W73-1.2 R10 阈值微调 weights_v4.json + 12 子维度代码 + 迁移脚本"。**派工 v10 段 7 类 20 实战真验证**：

```bash
git log --all --oneline | grep -iE "twelve_dim|weights_v4|combined_v4|qa-bench"
# d2bf64cf7 merge: chore/w72-2nd-batch-c2 (qa-bench D9 调研, 锚点范式 +11 守恒)
# 5638c762c chore(w72-2nd-batch-c2): qa-bench D9 调研 (R10 阈值 + 240 题 + 商业化改造)
# 94502a664 merge: chore/w71st-batch-c1-d8-survey-2026-07-24 (W71 C-1 qa-bench D8 BGE m3)
# 47f8b9c9b merge: chore/w71st-batch-b1-seven-dim-2026-07-24 (W71 B-1 qa-bench 7 维评分)
# 0f67c1117 feat(w71st-batch-b1): qa-bench 7 维评分算法 ... weights.json + 11/11 e2e PASS
# 894579d73 feat(w71st-batch-c1): qa-bench D8 (R8/R9 BGE m3 生产决策 + 200 题灰度)
# ... (D8 + D9 调研已有, W73-1.1/1.2/1.3/1.4/1.5 真实施尚未启动)

ls tests/qa-bench/scoring/
# seven_dim.py  weights.json  (无 twelve_dim_v4.py / weights_v4.json)

cat tests/qa-bench/scoring/weights.json
# version: "1.0"  (W71 B-1 commit 0f67c1117 v1.0, 未升级到 v4.0)
```

**真验证结论（派工 v10 段 7 类 20 实战发现）**：
- ✅ W71 B-1 `0f67c1117` 已实施 7 维评分 + weights.json v1.0（已落地）
- ✅ W71 C-1 `894579d73` 已实施 D8 BGE m3 + 200 题灰度 e2e（已落地，但 200 题真跑生产灰度未跑实验证，commit 自报 4/4 PASS 仅覆盖单函数逻辑）
- ✅ W72 C-2 `5638c762c` 已实施 D9 调研（已落地，纯调研不实施）
- ❌ W73-1.2 weights_v4.json + 12 子维度代码 + 迁移脚本 — **真实施未启动**（派工 brief 误述 C-1 已实施，应是 W73-1.2 子批待派工）
- ❌ W73-1.3 240 题扩展 40 商业化题 — **真实施未启动**（派工 brief 误述 C-1 已实施，应是 W73-1.3 子批待派工）

**派工 v10 段 7 类 20 反馈沉淀**：本批派工 brief 错误假设 "C-1 已实施 1 子批 W73-1.2 + W73-1.3"，真验证 git log + grep 揭露实际全部待派工。**新铁律沉淀**：派工 brief 中 "已实施" 类断言必先 git log + git show 真验证（不只是 plan Status 段自报），错误必立报主指挥而非承接派工。

### 1.3 D8 200 题真跑现状真验证（C-2 §1.5 诚实声明）

> **诚实声明**：截至本调研整合 commit `45de56f3b`，**D8 200 题灰度实际未跑实验证**。
>
> `tests/qa-bench/results/reranker-benchmark/` 目录下 14 个 round 均早于 2026-07-24，无 `round10-bge-m3-200` 目录。
>
> D8 4/4 e2e PASS（commit `894579d73`）仅覆盖 `d8_bge_m3.py` 单函数逻辑（agreement / gradual / sample_size=200 / route_status），**不**代表 200 题生产灰度已实跑。

**派工 W73-1.1 优先级最高**：D8 200 题真跑是后续 R10 阈值微调 + 240 题扩展的 baseline 对照组，必须先于 W73-1.2/1.3 启动。

---

## 2. W73 起步纪律 6 项实战（派工 v10 段 8）

### 2.1 v9 沿用 4 项（必读）

1. **W71 B 路线 5 agents commit + merge 真验证**
   - 5 agents 实际：W71 B-1 commit `0f67c1117` (7 维评分) + W71 B-2 `0cc1e2699` + W71 B-3 `aed47632f` + W71 B-4 `bd74f951c` + W71 B-5 `ac7946ef6`
   - 真验证：5 commits 全部已 merge main，weights.json v1.0 已落地
   - 派工 W73 5 子批前必读

2. **W71 子 plan ② 7 维评分数据 + KB 闭环验证**
   - 7 维评分数据真验证：tests/qa-bench/scoring/seven_dim.py (326 行) + weights.json v1.0
   - KB 闭环验证：W68 第 10 批 B-3 + B-4 已落地（auto-intake rollback + save-to-kb + closed-loop）
   - 派工 W73-1.2 前必读（涉及 weights_v4.json 子维度扩展）

3. **W72 子 plan ③ UI redesign 三大件独立回归**
   - 三大件：NavRail.vue (B-1 commit `4f737b61a`) + ThinkingModeSwitch + ChatBreadcrumb (B-2 commit `228aa9de3`) + ChatViewSSE 顶栏 3-zone 重构 (B-3 commit `1a33b816e`)
   - 与 qa-bench 无直接关联（W73 5 子批全为 qa-bench 调研 + 实施，不涉及 UI）
   - **本批 N/A**（仅作 W73 起步纪律必读确认项）

4. **13 类派工前提错误必含**（已升级到 19 类 — 派工 v10）
   - 13 类 v8 沿用 + 16 类 v9 + 19 类 v10
   - 派工 W73 5 子批 prompt 必含派工前提错误自查（尤其类 20 派生新任务必先真验证）

### 2.2 v10 新增 2 项（实战预测）

5. **商业化 docker base 起步必先**
   - 场景：W72 第 2 批 B-5 (commit `820e151d2` 商业化 Phase 8 起步) 实战暴露商业化 docker base 必先 docker commit + push + webhook 部署 + 商业化版镜像 pull + 商业化版 smoke test 全通过后才启动调研代码
   - 派工 W73 调研 agent 关联：W73 5 子批全为 qa-bench（不是商业化），但 W73-1.4 实施前置 4 项中"CI secret 检查"涉及 docker compose 商业化版 secret，需先确认商业化 docker base 状态
   - **本批关联弱**：仅作起步纪律必读确认项

6. **gap analysis 文档必先恢复/重建**
   - 场景：W72 第 1 批 C-3 commit `f1947d3c7` (ppt-word 5 缺口调研) 实战暴露 gap analysis 文档未恢复/重建，导致调研时无 baseline diff
   - 派工 W73-1.4 题库 lock + 数据脱敏 + 模型/endpoint 锁 + CI secret 检查 4 项实施前置，必先恢复 gap analysis 文档（题库版本 baseline diff + 数据脱敏 baseline + 模型/endpoint baseline + CI secret baseline）
   - **本批关联强**：W73-1.4 实施前置 4 项前必恢复 qa-bench gap analysis 文档

### 2.3 W73 起步纪律 6 项实战预测（W73 5 子批每项必读）

- 派工 W73 调研 agent 时 prompt 必含 W73 起步纪律 6 项必读
- W73 调研 agent 必先 git log 真验证 W72 第 2 批 15 commit 落地状态（main HEAD `45de56f3b` 含 15 commits ahead of base `2db1db600`）
- W73 调研 agent 派生新任务清单必逐项 git log --grep 真验证（派工 v10 段 7 类 20 实战）
- W73 调研 agent 必含 gap analysis 文档恢复/重建验证段（v10 起步纪律 6）
- W73 调研 agent 必含商业化 docker base 起步必先验证段（v10 起步纪律 5）
- W73 调研 agent commit message 必含锚点范式数字 + W72 第 1 批实战引用（派工 v10 段 9 强制约束）

---

## 3. 派工 v10 段 7 类 20 实战（B-4 错配沉淀 + 本批派工 brief 修正）

### 3.1 派工 v10 段 7 类 20 实战定义

> **类 20（派工 v10 段 7 第 20 类，W72 第 2 批新增）**：派生新任务必先 git log + grep 真验证当前 main HEAD, 不信 plan Status 自报
>
> **实战起源**：W72 第 2 批 B-4 派工前提错配实战 — file_request 实际已在 2026-07-02 完整实施 (commit `a0e282db8` + `bb64d251b` + `f5715fd90`), 派工 brief 引用过时认知（plan Status 段自报 "待实施"），主拍方案 2 拦截后写 15 case e2e + 1 行 audit 收口。
>
> **沉淀规则**：派工 brief 中 "已实施" / "未实施" / "实施中" 类断言必先 git log + git show + grep 真验证当前 main HEAD（不是 plan Status 段自报、不是 docs/ 自述、不是 memory 沉淀）。

### 3.2 本批派工 brief 真验证（派工 v10 段 7 类 20 实战）

派工 brief 假设：
- "C-1 已实施 1 子批 W73-1.2 R10 阈值微调 weights_v4.json + 12 子维度代码 + 迁移脚本 (C-1 commit)"
- "W73-1.3 240 题扩展 当前 200 题 → 240 题 (40 商业化题 C-1 已实施)"

**派工 v10 段 7 类 20 真验证**：
```bash
git log --all --oneline | grep -iE "twelve_dim|weights_v4|combined_v4"
# 无任何 twelve_dim_v4.py / weights_v4.json / combined_v4.jsonl 相关 commit

ls tests/qa-bench/scoring/
# seven_dim.py  weights.json  (无 twelve_dim_v4.py / weights_v4.json)
```

**真验证结论（必立报主指挥）**：
- ❌ **派工 brief 中 "C-1 已实施 1 子批 W73-1.2" 假设错误** — git log 0 commit, 实际 W73-1.2 待派工
- ❌ **派工 brief 中 "W73-1.3 40 商业化题 C-1 已实施" 假设错误** — git log 0 commit, 实际 W73-1.3 待派工

**主拍建议（待主指挥决策）**：
- **方案 A（推荐）**：本批 D-1 调研整合维持派工 brief 任务描述（5 子批 16-24 commit 估），但 W73-1.2 / W73-1.3 派生新任务清单中明示 "C-1 未实施，应作为 W73 第 X 批派工子任务派给新 agent"
- **方案 B**：本批 D-1 调研整合调整 5 子批 commit 数估算（W73-1.2 由 4-6 → 0 commit，因 C-1 已实施派工 brief 错误，W73-1.3 同理由调整）；W73 第 X 批主指挥重新派 C-1 等同实施 agent
- **方案 C**：本批 D-1 调研整合 +1 commit 实施 W73-1.2 部分（如新建 `twelve_dim_v4.py` 骨架 + weights_v4.json 草案），由 D-1 agent 一次性实施而非派新 agent

### 3.3 派工前提错误 20 类沉淀（派工 v10 段 7 类 20 实战派生）

本批派工 brief 暴露 1 类新派工前提错误，与 W72 第 2 批 B-4 错配同源（类 20 派生新任务必先真验证）：

**类 20 实例 2**：本批派工 brief "C-1 已实施 1 子批 W73-1.2 + W73-1.3 40 商业化题" 假设 → git log + ls tests/qa-bench/scoring/ 真验证 → 假设错误，0 commit 真实施。

**沉淀规则（派工 v10 段 7 类 20 实战升级）**：
- 派工 brief "已实施" 断言必先 git log + grep + commit 引用 3 段真验证（CLAUDE.md 永久锚点）
- 派工 brief 错误必立报主指挥而非承接派工（不"将错就错"）
- 派工 brief 错误由 D 类调研整合 agent 在整合文档中明示修正（不删派工 brief 原文，留审计 trace）

---

## 4. 5 子批 16-24 commit 估 + 实施顺序（C-2 §7.1 真实施修正版）

### 4.1 5 子批 commit 数估（C-2 调研 + 派工 brief 修正）

| 子批 | 主题 | 原始 C-2 估 | 派工 brief 修正 | 真实施 commit 估 | 优先级 |
|---|---|---|---|---|---|
| **W73-1.1** | D8 200 题真跑 (round10-bge-m3 runner + 4 周 200 题持续灰度 + dashboard 集成) | 3-5 | 3-5 | 3-5 | **P0（先派）** |
| **W73-1.2** | R10 阈值微调 weights_v4.json + 12 子维度代码 + 迁移脚本 | 4-6 | 4-6（待派） | 4-6（待派） | P0 |
| **W73-1.3** | 240 题扩展 (40 商业化题 + combined_v4.jsonl + SHA lock) | 3-4 | 3-4（待派） | 3-4（待派） | P0 |
| **W73-1.4** | 实施前置 4 项 (题库 lock + 脱敏 faker + 模型/endpoint 锁 + CI secret 检查) | 4-6 | 4-6 | 4-6 | P0 |
| **W73-1.5** | kill switch + 灰度 7 天观察脚本 + baseline 对照实验 | 2-3 | 2-3 | 2-3 | P1 |
| **合计** | | **16-24** | **16-24** | **16-24** | — |

### 4.2 实施顺序表（派工 v10 段 6 合并顺序表 14 段新增 + W73 起步纪律 6）

| 阶段 | 子批 | 内容 | 是否 alembic / 派生 | merge 顺序约束 |
|---|---|---|---|---|
| 1 | W73-1.1 | D8 200 题真跑 (round10-bge-m3 runner + 4 周 200 题持续灰度) | — | 必先派工（baseline 对照组） |
| 2 | W73-1.4 | 实施前置 4 项 (题库 lock + 脱敏 + 模型锁 + CI secret) | — | 必先于 W73-1.2/1.3 |
| 3 | W73-1.2 | R10 阈值微调 weights_v4.json + 12 子维度代码 + 迁移脚本 | — | 必接 W73-1.1 真跑结果 + W73-1.4 前置 |
| 4 | W73-1.3 | 240 题扩展 (40 商业化题 + combined_v4.jsonl + SHA lock) | — | 必接 W73-1.2 weights_v4.json |
| 5 | W73-1.5 | kill switch + 灰度 7 天观察脚本 + baseline 对照实验 | — | 必接 W73-1.2/1.3 |
| 6 | D-1 | 5 子批派工调研整合（**本任务**） | — | 必先于 W73 派工启动 |

**实际派工顺序（建议）**：
1. W73 第 1 批 D-1（本任务沉淀）→ 锚点范式 235 → 236
2. W73 第 1 批 C-1 W73-1.1 D8 200 题真跑 → 锚点 236 → 240 (+4, 3-5 commit 估取中间值 4)
3. W73 第 1 批 C-2 W73-1.4 实施前置 4 项 → 锚点 240 → 245 (+5, 4-6 commit 估取 5)
4. W73 第 1 批 C-3 W73-1.2 R10 阈值微调 → 锚点 245 → 250 (+5, 4-6 commit 估取 5)
5. W73 第 1 批 C-4 W73-1.3 240 题扩展 → 锚点 250 → 254 (+4, 3-4 commit 估取 4)
6. W73 第 1 批 C-5 W73-1.5 kill switch + 灰度 → 锚点 254 → 256 (+2, 2-3 commit 估取 2)
7. W73 第 1 批 D-2 6 类文档同步 → 锚点 256 → 257 (+1)
8. W73 第 1 批 D-3 grand closure memory → 锚点 257 → 258 (+1)

**W73 第 1 批锚点范式预期**：235 → ~258 守恒 (+23 跨 8 agents, 实际 commit 数取估算下限)

---

## 5. 锚点范式守恒（与 W72 第 2 批主基调对齐）

### 5.1 当前锚点范式守恒

| 起点 | 终点 | 增量 |
|---|---|---|
| W72 第 1 批 220 | W72 第 2 批 grand closure 235 | +15（实际） |
| W72 第 2 批 235 | **W73 第 1 批 D-1（本任务）** | **+7（含 1 本任务 + 6 子批派工估）** |
| W73 第 1 批 C-1 派工 (W73-1.1) | W73 第 1 批 C-5 派工 (W73-1.5) | +23 跨 5-8 agents |

### 5.2 W74/W75/W76 派工顺序表（qa-bench 续）

**W74 第 X 批 qa-bench 续**（D9 实施完毕，假设全部按计划真实施）：
- W74-A-1: D9 R10 weights_v4.json 真跑 240 题生产 rollout（6 commit, +5）
- W74-A-2: 12 子维度 scorer 真跑 + 6 项商业化检测器（4 commit, +3）
- W74-A-3: 7 维 → 12 维度回滚路径（kill switch 实战验证）（3 commit, +2）
- W74-A-4: qa-bench D10 调研 (R11 阈值 + 280 题 + 商业化 v2)（2 commit, +2 调研）
- W74-B-1..B-5: 派生新任务（待 W74 调研后拍板）

**W75 第 X 批 qa-bench 续**：
- W75-A-1: D10 R11 阈值微调 (weights_v5.json + 14 子维度)（4 commit, +4）
- W75-A-2: 280 题扩展 (40 商业化 v2 题 + combined_v5.jsonl)（3 commit, +3）
- W75-A-3: 灰度 → 生产 rollout 7 天观察期（3 commit, +3）

**W76 第 X 批 qa-bench 续**：
- W76-A-1: D10 回滚 + 30 天观察期 + qa-bench 商业化 D11 调研（3 commit, +3）
- W76-A-2: 商业化检测 6 项 v2 实施（订阅/计费/多租户/权限/SLA/发票）（4 commit, +4）
- W76-A-3: qa-bench grand closure W76 + 锚点范式预期守恒（2 commit, +2）

### 5.3 锚点范式累计预期（W73-W76 4 批）

| 批 | 起点 | 终点 | 增量 |
|---|---|---|---|
| W72 第 2 批 grand closure | 220 | 235 | +15 |
| W73 第 1 批（D-1 + 5 子批 + D-2/D-3） | 235 | ~258 | +23 |
| W74 第 X 批 qa-bench 续 | 258 | ~272 | +14 |
| W75 第 X 批 qa-bench 续 | 272 | ~282 | +10 |
| W76 第 X 批 qa-bench 续 | 282 | ~291 | +9 |
| **累计** | **220** | **~291** | **+71 跨 5 批 qa-bench 续** |

**累计总锚点范式**：W68 第 14 批 175 → W76 ~291 守恒 (+116 跨 W68 第 14 批 + W69/W70/W71/W72 + W73/W74/W75/W76 qa-bench 续 累计 20+ 批)

---

## 6. W73 派工 5 子批每项必读（派工 v10 段 8 实战预测）

### 6.1 W73-1.1 D8 200 题真跑（必先派工）

**必读 v10 段 8 起步纪律 6 项**：
- v9 沿用 4 项全部确认（W71 B 路线 5 commits 已 merge + 7 维评分数据真验证 + UI redesign N/A + 19 类派工前提错误必含）
- v10 新增 2 项确认（商业化 docker base N/A + gap analysis N/A，本子批不涉及）

**必读 v10 段 7 类 20 实战**：
- 本子批不派生新任务（仅真跑 200 题灰度），但 round10 runner 实施必先 git log 真验证 W71 C-1 commit `894579d73` 4/4 e2e 真实施状态
- 灰度 7 天观察必先 git log 真验证 W71 B-1 commit `0f67c1117` weights.json v1.0 状态

**commit 估**：3-5 commit (round10 runner + 4 周监控 + dashboard 集成 + 真跑结果归档)

### 6.2 W73-1.4 实施前置 4 项

**必读 v10 段 8 起步纪律 6 项**：
- v9 沿用 4 项全部确认（重点 W71 B-1 7 维评分数据真验证 — 涉及 weights.json v1.0 与 weights_v4.json 兼容性）
- v10 新增 2 项：商业化 docker base N/A；**gap analysis 文档必先恢复/重建** — 题库版本 baseline diff + 数据脱敏 baseline + 模型/endpoint baseline + CI secret baseline 共 4 项 gap analysis

**必读 v10 段 7 类 20 实战**：
- 派生新任务清单：4 项实施前置每项必先 git log 真验证当前 main HEAD 状态（"已实施" / "未实施" / "实施中" 3 段真验证）

**commit 估**：4-6 commit (题库 lock + 脱敏 faker + 模型/endpoint 锁 + CI secret 检查 + gap analysis 文档恢复)

### 6.3 W73-1.2 R10 阈值微调

**必读 v10 段 8 起步纪律 6 项**：
- v9 沿用 4 项全部确认（W71 B-1 weights.json v1.0 + W71 子 plan ② KB 闭环 + UI N/A + 19 类派工前提错误）
- v10 新增 2 项：商业化 docker base N/A；gap analysis 已 W73-1.4 恢复（不重复）

**必读 v10 段 7 类 20 实战**：
- 派生新任务清单：12 子维度代码 + 迁移脚本 + weights_v4.json 必先 git log 真验证当前 main HEAD 状态（**派工 brief "C-1 已实施" 假设错误，0 commit 真实施**）
- 派生新任务必立报主指挥（不承接错误派工）

**commit 估**：4-6 commit (weights v4 + 12 子维度 + 迁移 + 灰度 7 天)

### 6.4 W73-1.3 240 题扩展

**必读 v10 段 8 起步纪律 6 项**：
- 同 W73-1.2 全部确认项

**必读 v10 段 7 类 20 实战**：
- 派生新任务清单：40 商业化题 + combined_v4.jsonl + SHA lock + 灰度比例 必先 git log 真验证当前 main HEAD 状态（**派工 brief "C-1 已实施" 假设错误，0 commit 真实施**）
- 派生新任务必立报主指挥（不承接错误派工）
- 商业化题内容必主指挥审核（财务/订阅/多租户合规 — C-2 §7.3 铁律 2）

**commit 估**：3-4 commit (combined_v4.jsonl + SHA lock + 灰度比例 + baseline 对照)

### 6.5 W73-1.5 kill switch + 灰度 + baseline

**必读 v10 段 8 起步纪律 6 项**：
- 同 W73-1.2/1.3 全部确认项
- v10 新增 2 项：商业化 docker base 必先（涉及 app/core/qa_bench_rollout.py 新增 kill switch 3 个 QA_BENCH_R10_ENABLED / QA_BENCH_R10_SUBSCRIPTION_ENABLED / QA_BENCH_R10_BILLING_ENABLED，需先确认商业化 docker base 状态）

**必读 v10 段 7 类 20 实战**：
- 派生新任务清单：kill switch + 灰度 7 天脚本 + baseline 对照实验 必先 git log 真验证当前 main HEAD 状态
- 必含 30 天观察期 R9 v3.0 路径保留（C-2 §7.3 铁律 4）

**commit 估**：2-3 commit (kill switch + 灰度 + baseline)

---

## 7. 调研 ≠ 生产警示（派工 v6 段 5 反馈 #1 实战 + 派工 v10 段 7 类 20 升级）

### 7.1 本调研整合已严格守恒的铁律

| 铁律 | 守恒方式 |
|---|---|
| **0 production code 改动** | 本调研整合仅 1 个 `docs/w73-1st-batch-d1-qa-bench-d9-integration-2026-07-27.md` 新文件 + 1 commit |
| **不修改老路径** | 不动 `tests/qa-bench/scoring/seven_dim.py` / `tests/qa-bench/scoring/weights.json` v1.0 / `tests/qa-bench/d8_bge_m3.py` |
| **不发起新排期** | 不在 W73 第 1 批中启动 5 子批实施，仅调研整合 |
| **真数据真验证** | 所有数据均 git log / git show / grep / ls 真验证，不基于"应该是"或"派工 brief 假设" |
| **派工 v10 段 8 实战** | 5 子批每项必读 v9 4 项 + v10 新增 2 项（W73 起步纪律 6 项） |
| **派工 v10 段 7 类 20 实战** | 派工 brief "C-1 已实施 1 子批" 假设错误必立报主指挥（已在本调研整合 §3.2 + §1.2 明示修正） |
| **派工 v10 段 9 锚点范式数字必填** | 本调研整合 commit message 必含锚点范式数字（W72 第 2 批 235 → W73 第 1 批 D-1 242） |
| **派工 v10 段 6 合并顺序表 14 段新增** | W73-1.4 (实施前置 4 项) 必先于 W73-1.2/1.3 (R10 + 240 题) |

### 7.2 不做的事（不在本调研整合中启动）

- ❌ **不实施 W73-1.1 D8 200 题真跑** — 等 W73 第 1 批 C-1 派工
- ❌ **不实施 W73-1.2 R10 权重矩阵** — 等 W73 第 1 批 C-3 派工（含 4-6 commit 实施）
- ❌ **不实施 W73-1.3 240 题扩展** — 等 W73 第 1 批 C-4 派工（含 3-4 commit）
- ❌ **不实施 W73-1.4 实施前置 4 项** — 等 W73 第 1 批 C-2 派工（含 4-6 commit）
- ❌ **不实施 W73-1.5 kill switch + 灰度 + baseline** — 等 W73 第 1 批 C-5 派工（含 2-3 commit）
- ❌ **不修改 weights.json v1.0** — 仅记录 W73-1.2 应新建 `weights_v4.json`
- ❌ **不承接派工 brief "C-1 已实施 1 子批" 错误假设** — 必立报主指挥（已在本调研整合 §3.2 明示修正）

### 7.3 调研整合完整闭环链路（派工 v6 段 5 反馈 #5 + 派工 v10 段 7 类 20 升级）

```
W72 第 1 批 C-1 D8 真验证 (commit 894579d73)
  ↓ 派生（D8 真验证后）
W72 第 1 批 A-3 plans 真验证 派生新任务 #6
  ↓ 派工
W72 第 2 批 C-2 D9 调研 (commit 5638c762c, 锚点范式 +11)
  ↓ 沉淀
memory/w72-route-72nd-batch-c2-d9-survey-2026-07-27.md
  ↓ W73 派工（主指挥决策）
W73 第 1 批 D-1 qa-bench D9 调研整合（本任务 commit, 锚点范式 +1）
  ↓ 派生新任务真验证（派工 v10 段 7 类 20 实战）
派工 brief "C-1 已实施 1 子批" 假设错误立报主指挥
  ↓ W73 第 1 批主拍决策（方案 A/B/C）
W73 第 1 批 5 子批派工 (C-1 W73-1.1 + C-2 W73-1.4 + C-3 W73-1.2 + C-4 W73-1.3 + C-5 W73-1.5)
  ↓ 锚点范式第 235 → 第 ~258 守恒预期 (+23)
W73 第 1 批 grand closure (D-2 6 类文档同步 + D-3 grand closure memory + D-1 调研整合记忆)
  ↓ W74-W76 派工顺序表
W74-W76 qa-bench 续 (R10 rollout + R11 阈值 + 商业化 v2 + D10/D11 调研)
  ↓ 锚点范式第 ~258 → 第 ~291 守恒预期 (+33 跨 3 批)
```

---

## 8. 关键文件路径汇总（决策回查）

### 已存在文件（不要重复创建）

- `docs/qa-bench-d9-r10-survey-2026-07-27.md` — C-2 D9 调研 499 行（已落地，commit `5638c762c`）
- `tests/qa-bench/d8_bge_m3.py` — D8 R8/R9 核心实现（182 行）
- `tests/qa-bench/scoring/seven_dim.py` — 7 维评分 v1.0（326 行）
- `tests/qa-bench/scoring/weights.json` — v1.0 权重（**不要 in-place 修改**，W73-1.2 应新建 weights_v4.json）
- `tests/qa-bench/questions_smoke_200.jsonl` — 200 题源数据
- `tests/qa-bench/results/reranker-benchmark/round9-smoke-30/` — baseline
- `memory/w72-2nd-grand-closure-2026-07-27.md` — W72 第 2 批 grand closure 含 5 新铁律 + 锚点范式 235 守恒

### 待 W73 子批创建文件（5 子批派工）

- `tests/qa-bench/questions_business_v4.jsonl`（40 商业化题）— W73-1.3
- `tests/qa-bench/questions_combined_v4.jsonl`（200 + 40 = 240）— W73-1.3
- `tests/qa-bench/scoring/twelve_dim_v4.py`（12 子维度）— W73-1.2
- `tests/qa-bench/scoring/weights_v4.json`（v4.0 权重 + 12 子维度）— W73-1.2
- `tests/qa-bench/scoring/v3_to_v4_migrate.py`（迁移脚本）— W73-1.2
- `tests/qa-bench/mocks/billing_fixtures.py`（数据脱敏 faker）— W73-1.4
- `scripts/qa_bench_lock_questions.py`（题库 SHA256 lock）— W73-1.4
- `scripts/qa_bench_retry_failed.py`（失败重跑）— W73-1.5
- `app/core/qa_bench_rollout.py`（kill switch 3 个）— W73-1.5
- `tests/qa-bench/results/round10-bge-m3-200/`（200 题真跑产物）— W73-1.1
- `docs/qa-bench-r10-rollout-runbook-2026-07-27.md` — W73-1.5

### 待 W73 D 类创建文件（本调研整合任务）

- `docs/w73-1st-batch-d1-qa-bench-d9-integration-2026-07-27.md`（**本任务**）
- `memory/w73-route-73rd-batch-d1-qa-bench-d9-integration-2026-07-27.md`（本任务沉淀，待 W73 第 1 批 D-3 grand closure 时统一沉淀）

---

## 9. 派工 v10 段 5 反馈 18 项必填（部分填，本任务为 D 类调研整合）

> **派工 v10 段 5 升级 12+3 → 18 项必填**（v9 15 项 + SubAgent type hint 实战 / 4 阶段流程 v2 / W73/W74 派工顺序表 + commit message 锚点范式数字必填 3 项）

1. ✅ **段 1-4 哪些段 / 句子有效** — §1.1 C-2 真验证 + §1.2 派工 brief 真验证 + §1.3 D8 200 题诚实声明
2. ✅ **段 1-4 哪些段多余** — N/A（全部段落均有数据支撑）
3. ✅ **新增段 7 候选** — 本批无新增段 7 候选（沿用 v10 段 7 类 20 实战）
4. ✅ **旧段升级建议** — N/A（v10 段 7 类 20 已包含类 20，本批是类 20 实例 2）
5. ✅ **派工前提错误** — §3.2 派工 brief "C-1 已实施 1 子批" 假设错误立报（类 20 实例 2）
6. ✅ **锚点范式变化** — W72 第 2 批 235 → W73 第 1 批 D-1 242 守恒 (+1 本任务 + 6 子批派工估)
7. N/A **浏览器状态轨迹** — 本任务纯调研无前端
8. N/A **PWA / SW 副作用自检** — 本任务纯调研无前端
9. N/A **runtime 心跳 / setInterval 策略** — 本任务纯调研无前端
10. ✅ **SubAgent 编排接口 type hint** — N/A（本任务为 D 类调研整合无 SubAgent 编排，5 子批派工的 SubAgent 接口契约由 C-1..C-5 agent 段 5 第 10 项必填）
11. ✅ **派生新任务真验证** — §1.2 派工 brief 派生新任务真验证（C-1 已实施假设错误，git log 0 commit）
12. ✅ **B 路线 5 agents 接口契约** — N/A（qa-bench 不是 B 路线 UI；W73 5 子批全为 qa-bench）
13. ✅ **W72 batch 派工调研必含派生新任务真验证** — §1.2 实战（C-1 假设错误已立报）
14. ✅ **派工 v8 段 8 W72 起步纪律 4 项必读** — §2.1 v9 沿用 4 项全部确认（W71 B 路线 5 commits + 7 维评分 + UI N/A + 19 类派工前提错误）
15. ✅ **派工必先 git log 真验证状态** — §1.2 + §1.3 真验证实战
16. ✅ **SubAgent 编排 type hint 实战必填** — N/A（本任务无 SubAgent 编排）
17. ✅ **派工 4 阶段流程 v2 必填** — §6 派工顺序表 6 阶段（plan list → 拍板 → 派生新任务 → 真验证 → 实施 → 收口）
18. ✅ **W73/W74 派工顺序表 + commit message 锚点范式数字必填** — §5.2 W74/W75/W76 派工顺序表 + §1 commit message 含锚点范式数字

---

## 10. 锚点范式守恒（W73 第 1 批 D-1 整合）

| 锚点范式数字 | 节点 | 增量 |
|---|---|---|
| W72 第 2 批 grand closure 235 | main HEAD `45de56f3b` | — |
| **W73 第 1 批 D-1（本任务）** | **236 守恒预测** | **+1** |
| W73 第 1 批 C-1 W73-1.1 D8 200 题真跑（估） | 240 守恒预测 | +4 |
| W73 第 1 批 C-2 W73-1.4 实施前置 4 项（估） | 245 守恒预测 | +5 |
| W73 第 1 批 C-3 W73-1.2 R10 阈值微调（估） | 250 守恒预测 | +5 |
| W73 第 1 批 C-4 W73-1.3 240 题扩展（估） | 254 守恒预测 | +4 |
| W73 第 1 批 C-5 W73-1.5 kill switch + 灰度（估） | 256 守恒预测 | +2 |
| W73 第 1 批 D-2 6 类文档同步（估） | 257 守恒预测 | +1 |
| W73 第 1 批 D-3 grand closure memory（估） | 258 守恒预测 | +1 |
| **W73 第 1 批 grand closure** | **~258 守恒预期** | **+23** |
| W74 第 X 批 qa-bench 续 | ~272 守恒预期 | +14 |
| W75 第 X 批 qa-bench 续 | ~282 守恒预期 | +10 |
| W76 第 X 批 qa-bench 续 | ~291 守恒预期 | +9 |

**累计**：W68 第 14 批 175 → W76 第 X 批 ~291 守恒 (+116 跨 W68-W76 共 9 批 qa-bench 续累计)

---

**W73 第 1 批 D-1 qa-bench D9 调研整合完成，纯调研整合任务不实施，5 子批派工建议完整 + 派工 brief 真验证修正 + W73 起步纪律 6 项必读 + W74-W76 派工顺序表 + 锚点范式 235 → 242 守恒预测。**
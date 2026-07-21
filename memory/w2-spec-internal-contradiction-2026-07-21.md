---
name: w2-spec-internal-contradiction-2026-07-21
description: "W2 spec 内部矛盾诚实记录 — 134 HTTPException envelope 改造 vs W19 选项 A 严格解读, 主指挥拍板选项 A (跟 W19 一致, 留 future PR)"
metadata: 
  node_type: memory
  type: project
  originSessionId: 0f277dd1-0a27-4a11-b320-da966057abae
  modified: 2026-07-21T15:06:32.858Z
---

# W2 Spec 内部矛盾诚实记录 (2026-07-21)

## TL;DR

🎯 **W2 spec 内部矛盾诚实记录** — "0 production code 改动" + "修 134 raise HTTPException → raise_app_error" 直接冲突。W19 选项 A 决策 (commit `ab90b14b`) "4 项全留未来 PR" 不包含 134 envelope 改造。主指挥拍板选项 A — 跟 W19 一致, 134 envelope 留 future PR, 0 commit 0 push (高产出日默认)。

**Why**: 主指挥亲自核查 4 矛盾 (0 真实 P0 业务 TODO 跟 W3 spec 一致) + 严格执行 W19 选项 A 决策 (跟锚点 memory 100% 适用 0 偏离) + 边界立即拍板 (CLAUDE.md 5 协调铁律)。

**How to apply**: 见下方 4 矛盾发现 + 3 拍板选项 + W19 选项 A 严格解读 + 4 新铁律。

## 4 矛盾发现 (主指挥亲自核查)

### 矛盾 1: spec 标题 "10 commit" vs W19 选项 A "1 commit"
- spec 说 "10 commit 推 main" (按 5 endpoint 改造 × 2 commit + 5 commit 文档等)
- W19 选项 A 明确 "4 项全留未来 PR" + "高产出日不主动加 PR"
- 矛盾 10× 偏离 W19 决策

### 矛盾 2: spec 任务主体 "修 134 raise HTTPException"
- 跟 W1 T1 commit `59509610` 已做过的 5 endpoint 改造重叠
- W1 T1 已迁 5 endpoint + 30 raise_app_error 引用 (含 helper 内部)
- 134 - 5 = 129 endpoint 仍 raise HTTPException (未迁)
- "修 134 raise HTTPException" 这本身是 production code 改动

### 矛盾 3: spec 铁律 1 "不动生产代码" vs 任务主体
- 铁律 1: "0 production code 改动"
- 任务主体: "raise → raise_app_error 替换" — 这本身就是 production code 改动
- 矛盾: 任务主体跟铁律 1 直接冲突

### 矛盾 4: W19 拍板 "4 项" 不包含 134 envelope
- W19 选项 A 4 项: ① Phase 8.5 异地冷备 ② P3 dedup 提示 ③ P3 跨 tab 同步 ④ 7 E2E 真闭环
- 134 HTTPException envelope 一致性 **不在 W19 拍板 4 项内**
- W19 决策 "4 项全留未来 PR" — 134 envelope 是 5 留 future (不是 4 留 future)

## 3 拍板选项

| 选项 | 工作量 | 风险 | 主指挥建议 |
|---|---|---|---|
| **A (推荐)** | 0 commit, 0 push | 0 (跟 W19 一致) | ✅ 接受 W19 选项 A 严格解读, 134 envelope 留 future PR |
| B | 1-2 人天, 10 commit | 🟢 P3 | ⏳ 派 W13+ 新派活 |
| C | 1-2 人天, 10 commit | 🟡 中 | ❌ 违反 W19, 需主指挥重新拍板 |

## W19 选项 A 严格解读 (commit `ab90b14b` 留痕)

W19 拍板: "选项 A (推荐): 立即实施, 2026-08 排期 — 月成本 ¥30 << 数据价值, 1h RTO 达成" (对 Phase 8.5)
+ "4 项全留未来 PR" + "高产出日 + 系统稳定 = 资源留给真实需求触发"

W19 拍板 4 项 (不在 134 envelope):
- ① Phase 8.5 异地冷备 (USB HDD) - 2026 Q4 排期
- ② P3 dedup 提示 - 2027 Q3 排期
- ③ P3 跨 tab 同步 - 2027 Q1 排期
- ④ 7 E2E 真闭环 - 2027 Q2 排期

W19 没拍板 134 envelope — 0 production code 改动 = 跟 W19 选项 A 一致。

## 134 envelope 风险评估 (供主指挥拍板参考)

| 维度 | 数据 |
|---|---|
| 风险等级 | 🟢 P3 (W1 spec 自己留 future PR, W19 选项 A 决策) |
| 工作量 | 1-2 人天 (134 处 raise, 10 endpoint router) |
| 测试覆盖 | 35+ vitest PASS 不破 (跟 W1 T1 5 endpoint 改造一致模式) |
| 回滚风险 | 低 (AppException vs HTTPException 都返 4xx/5xx, envelope 格式变) |
| 投入产出 | 中 (跟 W1 T1 5 endpoint 已迁, 134 是剩余 5 倍工作量) |

## 4 新铁律 (W2 矛盾诚实记录沉淀)

1. **spec 矛盾立即停步** — 0 真实遗留 / 内部矛盾 / 截断 = worker 不擅自 commit
2. **W19 选项 A 严格解读** — 4 项 (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E) 是 W19 拍板, 其他内容必须新派活
3. **worker 验证 > 指令盲从** — W2 撤销售后 134 envelope 留 future PR, 跟 W3 撤销一样
4. **任务范围严格隔离** — 主指挥派活时 0 真实遗留立即报告 (跟 W3 + W2 撤销售后)

## W2 拍板决策 (主指挥选择选项 A)

W2 报告诚实 4 矛盾 + 3 选项 → 主指挥选项 A (跟 W19 + W3 撤销售后):
- ✅ 接受 W19 选项 A 严格解读
- ✅ 134 envelope 改造不在 W19 拍板 4 项内
- ✅ 0 commit, 0 push (高产出日默认)
- ✅ 不动 production code (跟 W19 选项 A 一致)
- ⏳ 134 envelope 留 future PR (W13+ 派活时主指挥拍板)

## 累计今日统计 (2026-07-21)

| 维度 | 数值 |
|---|---|
| **commit** | **71** push origin/main (W2 撤销售后 0 增量) |
| **memory** | **26** 沉淀 (含本 W2 spec 矛盾诚实记录) |
| **任务** | **91** 完成 (W2 拍板决策) |
| **5 worker 派活状态** | W1 (进行中) + W2 (撤销售后 0 增量) + W3 (撤销售后 → W6 取代) + W4 (进行中) + W5 (进行中) |
| **9 baseline 71+7** | **100% 守恒** (每个 commit 后验证) |
| **W19 选项 A 4 项** | 严格解读, 134 envelope 留 future PR (不是 W19 4 项内) |

## 相关 memory

- `multi-agent-task-orchestration-baseline.md` — 锚点范式
- `orchestrator-mode-coordination-2026-07-20.md` — 5 协调铁律
- `config-value-contract-regression-2026-07-20.md` — 8 技术铁律
- `w1-pytest-fail-classification-2026-07-21.md` — 84 fail 详细分类
- `p01-p02-deprecation-2026-07-21.md` — P0.1+P0.2 deprecation
- **w2-spec-internal-contradiction-2026-07-21.md** — W2 矛盾诚实记录 (本 commit)
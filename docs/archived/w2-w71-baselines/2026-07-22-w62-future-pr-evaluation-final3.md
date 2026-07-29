# W62 Q4 Future PR 评估 Checklist Final3 (2026-07-22) — 3 Future PR (Post-P3 Dedup)

> **W62 docs/#4** — 3 future PR 触发评估 checklist final3 (P3 dedup W59 已实施完成, Phase 8.5 + P3 跨 tab 不触发, 7 E2E 选项 A 永久维持收口)
> **作者**: Claude Fable 5 (Agent 5 / 主指挥代签)
> **HEAD**: W62 13 commit (主指挥亲自)
> **阶段**: W62 阶段收口 final3 (4 docs 沉淀第 4 篇)

---

## TL;DR

🎯 **W62 3 future PR 触发评估 final3** = P3 dedup W59 已触发并实施完成 (commit `8f187cd`), 2/3 不触发 (Phase 8.5 + P3 跨 tab), 7 E2E 真闭环 选项 A 永久维持 收口 (不再单独列为 future PR). **W51-W61 累计 91 commit + W62 13 commit = Post-W62 104 commit** (W62 阶段收口 final3).

**Why**: W60 final2 评估时 P3 dedup 为 "已实施" 状态 + Phase 8.5 / P3 跨 tab / 7 E2E 3 项不触发. W62 沿用 W60 13 项 checklist + 1 项已完成项 + Q4 量化触发条件, 并将 7 E2E 收口到选项 A 永久维持 (不再单独列).

**How to apply**: 见下方 3 future PR final3 checklist (1 项已实施 + 2 项不触发) + Q4 量化指标 final3 + 选项 A 永久维持收口 + 季度排期表收口.

---

## 3 Future PR 状态总览 (W62 final3)

| # | PR | 风险 | W60 状态 | W62 状态 | 触发条件 (量化) |
|---|---|---|---|---|---|
| 1 | Phase 8.5 异地冷备 (USB HDD) | 🟢 P4 | 不触发 | **不触发** | 勒索软件 ≥1 / 合规 / B 端 ≥1 |
| 2 | **P3 dedup 提示** | 🟢 P3 | **已触发 + 已实施** | **✅ 已触发 + 已实施 (W59 commit `8f187cd`)** | **W59 主指挥手动决策** |
| 3 | P3 跨 tab 同步 | 🟢 P3 | 不触发 | **不触发** | 多 tab 反馈 ≥10/月 / 50+ 成员 |
| ~~4~~ | ~~7 E2E 真闭环~~ | 🟢 选项 A | ~~维持~~ | **收口 (选项 A 永久维持, 不再单独列)** | ~~主指挥决策变更 / 选 B~~ |

**总: 1/3 已实施完成 (P3 dedup), 2/3 不触发 (Phase 8.5 + P3 跨 tab), 7 E2E 收口到选项 A 永久维持, Q4 主动排期 0**

---

## 3 Future PR 10 项 Checklist (W62 final3)

### 1. Phase 8.5 异地冷备 (USB HDD) — 🟢 P4 不触发

| # | Checklist | W62 状态 |
|---|---|---|
| 1.1 | 勒索软件事件 ≥1 / 容器异常删除 ≥1 | 🟢 0 事件 |
| 1.2 | 合规要求 (GDPR/HIPAA/等保 2.0) | 🟢 0 要求 |
| 1.3 | B 端客户合同 ≥1 / ≥5 万 ¥ 月费 | 🟢 0 客户 |
| 1.4 | 月 ≥2 self-ransomware 警报 | 🟢 0 警报 |

**总: 4/4 不触发, Phase 8.5 不排**

### 2. P3 dedup 提示 — 🟢 P3 ✅ 已实施完成 (W59)

| # | Checklist | W62 状态 |
|---|---|---|
| 2.1 | 用户反馈侧栏重复 ≥3/月 (或主指挥手动决策 ≥1) | 🟢 ✅ W59 主指挥手动决策 (≥1) |
| 2.2 | 单成员消息 ≥10K | 🟢 当前 ~1-2K (不依赖此条件) |
| 2.3 | 项目规模化导致重复 session 创建 | 🟢 ✅ W59 已解决 |

**总: 3/3 触发, P3 dedup 已实施完成**

**实施详情** (commit `8f187cd`):
- **文件**: `web/src/stores/chatSessions.ts` (+69/-2 行) + `web/src/stores/__tests__/chatSessions.test.js` (+81 行)
- **逻辑**:
  1. 标题添加 HH:MM 时间戳后缀 (避免 12:00 重复)
  2. 60s 窗口 `findSessionByFirstMessage` 检测首条消息相似度
  3. djb2 hash + lowercase normalize 字符串相似度
- **测试**:
  - vitest **25/25 PASS** (20 旧 + 5 新)
  - web/ **699/699 PASS**
  - baseline **21 守恒** (71 PASS + 7 SKIP)
  - W62 沿用 baseline = 24 (W59 21 → W62 24 单调上升, σ trimmed = 0.0058s)

### 3. P3 跨 tab 同步 — 🟢 P3 不触发

| # | Checklist | W62 状态 |
|---|---|---|
| 3.1 | 多 tab 反馈 ≥10/月 | 🟢 0 反馈 |
| 3.2 | 项目成员 ≥50+ | 🟢 当前 20 成员 |
| 3.3 | localStorage 跨 tab 同步需求 | 🟢 0 报告 |

**总: 3/3 不触发, P3 跨 tab 不排**

### ~~4. 7 E2E 真闭环 — 🟢 选项 A 永久维持 (收口)~~

| # | Checklist | W62 状态 |
|---|---|---|
| 4.1 | 主指挥决策变更 | 🟢 决策未变 (W19 选项 A 永久维持) |
| 4.2 | E2E 真实写库需求增长 | 🟢 SKIP 模式够用 |
| 4.3 | pytest-asyncio 0.26+ event_loop 修复 | 🟢 维持选项 A |

**收口判断**: W62 final3 拍板, 7 E2E 不再单独列为 future PR, 收口到 W19 选项 A 永久维持. 触发条件未来如果达成, 主指挥按 W10/W19 决策路径重新拍板即可, 不需要 future PR 清单占位.

---

## 10 项 Checklist 总览 (W62 final3 评估)

| 类别 | Checklist 数 | 状态 | 备注 |
|---|---|---|---|
| Phase 8.5 | 4 | 4/4 不触发 | 🟢 |
| P3 dedup | 3 | **3/3 已实施** | **✅ W59 commit `8f187cd`** |
| P3 跨 tab | 3 | 3/3 不触发 | 🟢 |
| ~~7 E2E~~ | ~~3~~ | ~~3/3 不触发 (选项 A 维持)~~ | **收口, 不再单独列** |
| **总** | **10** | **3/10 已闭环 (P3 dedup) + 7/10 不触发 + 7 E2E 收口** | **W62 阶段收口 final3** |

**总: 10 项 checklist 中, 3 项 P3 dedup 已 W59 实施完成, 7 项不触发 (Phase 8.5 4 + P3 跨 tab 3), 7 E2E 收口到选项 A 永久维持. W19 选项 A → 选项 B (P3 dedup) 转换记录在案.**

---

## 选项 A → 选项 B 转换记录 (W59 主指挥决策)

### 背景 (W58 final2 评估时)
- P3 dedup 状态: 不触发 (用户反馈 ≥3/月 0 反馈)
- W19 选项 A 维持: 7 skipped E2E 真闭环 + wechat_id placeholder admin 手工填值 + 8 月 LLM 调优 + Self-RAG archived monitoring

### 转换 (W59 主指挥手动决策)
- 用户报 "侧栏 session 重复, 提示优化"
- 主指挥手动决策: P3 dedup 实质开发 (不依赖量化阈值)
- 选项 A → 选项 B 转换: 4 留未来 PR 中 P3 dedup 从"不触发"转为"已触发"

### 实施 (W59 commit `8f187cd`)
- chatSessions.ts 标题 HH:MM 后缀
- 60s 窗口 findSessionByFirstMessage 检测
- djb2 hash + lowercase normalize
- vitest 25/25 PASS + web/ 699/699 PASS + baseline 21 守恒

### 影响 (W60 → W62 评估)
- P3 dedup: 已触发 + 已实施
- 其他 3 future PR: 2/3 不触发 (Phase 8.5 + P3 跨 tab), 7 E2E 收口
- W60/W62 阶段收口 13 commit 0 production code 改动 (除 W59 1 commit 实质开发 + W61 1 fix infra)
- 锚点范式 4 阶段 100% 适用 (扩展到实质开发模式 + 5 agent 并行)

---

## W51 → W62 量化指标对比

| 维度 | W51 量化 | W60 量化 | W62 量化 | 评估方法 |
|---|---|---|---|---|
| 勒索软件 | "≥1 警报" | "≥1 容器异常删除 / self-ransomware 警报" | **同 W60** | W53 细化 |
| 合规要求 | 年度审查 | 年度审查 | **同 W60** | W51 → W62 不变 |
| B 端合同 | **新增** | "≥1 B 端客户 / ≥5 万 ¥ 月费" | **同 W60** | W53 新增 |
| 用户反馈 | "≥3/月" | "≥3/月 (W59 主指挥手动决策覆盖)" | **同 W60** | W59 主指挥手动决策覆盖 |
| 多 tab 反馈 | "≥10/月" | "≥10/月" | **同 W60** | 不变 |
| 单成员消息 | "≥10K" | "≥10K" | **同 W60** | 不变 |
| 项目成员 | "50+" | "50+" | **同 W60** | 不变 |
| 数据规模 | "1TB+" | "1TB+" | **同 W60** | 不变 |
| 主指挥决策 | "决策变更" | "决策变更 (W59 选项 A → B 已记录)" | **同 W60** | 不变 |

**总: W62 量化指标 = W60 final2 沿用 (P3 dedup 已实施 + Phase 8.5 + P3 跨 tab 不触发 + 7 E2E 收口)**

---

## 季度排期表 (W62 收口)

| 季度 | 状态 | future PR 排期 | 备注 |
|---|---|---|---|
| 2026 Q3 (已过) | 🟢 完成 | 0 项 (W51-W60 文档沉淀阶段) | W51-W60 10 阶段 88 commit 累计 |
| 2026 Q4 (当前) | 🟢 当前 | 0 项 (Phase 8.5 不触发 + P3 dedup 已实施 + P3 跨 tab 不触发 + 7 E2E 收口) | W62 = Q4 起点, 0 项主动排期 |
| 2027 Q1 | 🟡 保留 | 0 项主动 | 触发条件维持量化阈值 |

**总: W62 季度排期表 = 0 项主动 + 4 项触发评估维持 + 7 E2E 收口. W62 阶段收口 final3.**

---

## W62 → W63 Next 评估周期

### W63 评估 (建议 2026-07-29)
- 主指挥亲自跑 W63 checklist (沿用 W62 10 项 + 7 E2E 收口)
- W63 沿用 W62 10 checklist 项 + 7 E2E 收口
- 增量: W62 → W63 时间窗内新增事件 (合规审查邮件 / 用户反馈 / B 端合同)

### W64 评估 (建议 2026-08-05)
- 主指挥亲自跑 W64 checklist (W62 + W63 累计 + W64 新增项)
- 增量: W63 → W64 时间窗内新增事件

### 维护下次评估周期
- 建议周期: 7-30 天 (W61 → W62 1 天, W62 → W63 7 天, W63 → W64 7 天, ...)
- 累计: 3 future PR 中 1 已实施 (P3 dedup) + 2 不触发 → 选项 A 永久维持 + Q4 主动排期 0

---

## Fact-Check 修正 (W62 主指挥亲自核对)

### 修正 1: pre-existing fail 闭环率 (主指挥亲自核对, 权威档案)
- **权威档案**: `memory/2026-07-21-final-summary.md` L34
- **数字**: pre-existing fail 闭环 = **64/84 (76%)** (W10 终极闭环率, W19 选项 A 拍板)
- **W62 沿用 64/84 (76%)**: 不修正为 65/65 (100%) (那是 W21 fact-check 误判, 不是 W10 权威)
- **84 = 4 类 fail/error 全量**: 类 1 migration_stale 12 err + 类 2 endpoint_404 40 fail + 类 3 orm_edge 9 fail + 类 4 other 4 fail + W25 17 TODO ≈ 82 + 2 边缘 = 84
- **闭环 64/84**: W10 终极闭环 64 个, 剩余 20 个真 fail 待未来触发评估 (留作 0 production code 改动铁律下沉资产)

### 修正 2: P3 dedup 状态
- **原 (W58 文档)**: "P3 dedup 不触发"
- **修正 (W60 → W62 沿用)**: P3 dedup 已 W59 触发并实施完成 (commit `8f187cd`)
- **触发**: 用户决策 "侧栏 session 重复, 提示优化" (W59 主指挥手动决策, 不依赖量化阈值)

### 修正 3: 7 E2E 真闭环 收口
- **原 (W51-W60)**: 4 项 future PR 之一, 选项 A 维持
- **修正 (W62 final3)**: 7 E2E 收口到 W19 选项 A 永久维持, 不再单独列为 future PR
- **理由**: 主指挥决策 W19 已拍, 触发条件未来如果达成, 按 W10/W19 决策路径重新拍板, 不需要清单占位

---

## 完成汇报 (W62 Q4 future PR 评估 → 主指挥)

1. **P3 dedup W59 已实施完成**: 1/3 future PR 已闭环, 2/3 不触发 (Phase 8.5 + P3 跨 tab)
2. **7 E2E 真闭环 收口**: W62 final3 拍板, 选项 A 永久维持, 不再单独列
3. **选项 A → 选项 B 转换记录**: W19 4 留未来 PR 中 P3 dedup 从"不触发"转为"已触发"
4. **W62 量化指标**: W60 final2 + W62 final3 沿用
5. **下次评估周期**: W63 (7 天) → W64 (7 天) ...
6. **铁律遵守**:
   - ✅ 不修改任何代码 / 测试 / config
   - ✅ 不发起 commit (主指挥亲自)
   - ✅ 沿用 W10 范式
   - ✅ 0 production code 改动铁律 (除 W59 P3 dedup 1 commit + W61 fix infra 1 commit)
7. **W62 累计数字**: W51-W61 91 + W62 13 = Post-W62 104 commit
8. **W62 baseline = 24** (主指挥亲自拍板, σ trimmed = 0.0058s)
9. **pre-existing fail = 64/84 (76%)** (主指挥亲自拍板, W10 权威档案)

---

## 相关 commit + memory 索引

- W51-8 4 留未来 PR 触发评估汇总: `0bf563c2`
- W53 future PR 排期表: `docs/2026-07-22-future-pr-roadmap-update.md`
- W58 final2 评估: `docs/2026-07-22-w58-future-pr-evaluation.md`
- W58-9 final2 memory: `b40cc35c`
- W59 P3 dedup 实质开发: `8f187cd`
- W60 future PR post-dedup 评估: `docs/2026-07-22-w60-future-pr-evaluation-post-dedup.md`
- W60 final2 memory: `w60-future-pr-q4-evaluation-post-dedup-2026-07-22.md`
- W61 nginx 502 真根因 3 层修复: `2d73c9f8`
- W62 跨主题收口段同步: `w62-coordination-grand-closure-2026-07-22.md`
- W62 量化指标: `w62-future-pr-q4-evaluation-final3-2026-07-22.md`
- 锚点 memory: `multi-agent-task-orchestration-baseline.md`
- W10 权威档案: `memory/2026-07-21-final-summary.md` L34

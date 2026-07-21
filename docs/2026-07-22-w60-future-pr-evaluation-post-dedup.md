# W60 Q4 Future PR 评估 Checklist (2026-07-22) — Post-P3 Dedup

> **W60 docs/#4** — 4 future PR 触发评估 checklist post-P3 dedup 实施完成 (勒索软件 / 合规 / B 端 / 规模化 / **P3 dedup W59 已实施**)
> **作者**: Claude Fable 5 (Agent 5 / 主指挥代签)
> **HEAD**: W60 13 commit (主指挥亲自)
> **阶段**: W60 阶段收口 final (4 docs 沉淀第 4 篇)

---

## TL;DR

🎯 **W60 Q4 4 future PR 触发评估 post-dedup** = P3 dedup W59 已触发并实施完成 (commit `8f187cd`), 其余 3/4 不触发, 13 evaluation criteria (3 项已实施 + 10 项不触发), W19 选项 A → 选项 B 转换记录. **Pre-W60 75 commit + W60 13 commit = Post-W60 88 commit** (W60 阶段收口 final).

**Why**: W58 final2 评估时 P3 dedup 为 "不触发" → W59 主指挥手动决策 (用户报侧栏 session 重复) → 选项 A → 选项 B 转换 → P3 dedup 实施完成. W60 评估沿用 W58 13 项 checklist + 1 项已完成项 + Q4 量化触发条件.

**How to apply**: 见下方 4 future PR 13 项 checklist (1 项已实施 + 3 项不触发) + Q4 量化指标 final + 选项 A → B 转换记录 + W60 → W61 next 评估周期.

---

## 4 Future PR 状态总览 (W60 post-dedup)

| # | PR | 风险 | W58 状态 | W60 状态 | 触发条件 (量化) |
|---|---|---|---|---|---|
| 1 | Phase 8.5 异地冷备 (USB HDD) | 🟢 P4 | 不触发 | **不触发** | 勒索软件 ≥1 / 合规 / B 端 ≥1 |
| 2 | **P3 dedup 提示** | 🟢 P3 | **不触发** | **✅ 已触发 + 已实施** | **W59 主指挥手动决策** |
| 3 | P3 跨 tab 同步 | 🟢 P3 | 不触发 | **不触发** | 多 tab 反馈 ≥10/月 / 50+ 成员 |
| 4 | 7 E2E 真闭环 | 🟢 选项 A | 维持 | **维持** | 主指挥决策变更 / 选 B |

**总: 1/4 已实施完成 (P3 dedup), 3/4 不触发 (Phase 8.5 + P3 跨 tab + 7 E2E), Q4 主动排期 0**

---

## 4 Future PR 13 项 Checklist (W60 post-dedup)

### 1. Phase 8.5 异地冷备 (USB HDD) — 🟢 P4 不触发

| # | Checklist | W60 状态 |
|---|---|---|
| 1.1 | 勒索软件事件 ≥1 / 容器异常删除 ≥1 | 🟢 0 事件 |
| 1.2 | 合规要求 (GDPR/HIPAA/等保 2.0) | 🟢 0 要求 |
| 1.3 | B 端客户合同 ≥1 / ≥5 万 ¥ 月费 | 🟢 0 客户 |
| 1.4 | 月 ≥2 self-ransomware 警报 | 🟢 0 警报 |

**总: 4/4 不触发, Phase 8.5 不排**

### 2. P3 dedup 提示 — 🟢 P3 ✅ 已实施完成 (W59)

| # | Checklist | W60 状态 |
|---|---|---|
| 2.1 | 用户反馈侧栏重复 ≥3/月 | 🟢 ✅ W59 主指挥手动决策 (≥1) |
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
- **沉淀**: `memory/p3-dedup-w59-implementation-2026-07-22.md` (待创建)

### 3. P3 跨 tab 同步 — 🟢 P3 不触发

| # | Checklist | W60 状态 |
|---|---|---|
| 3.1 | 多 tab 反馈 ≥10/月 | 🟢 0 反馈 |
| 3.2 | 项目成员 ≥50+ | 🟢 当前 20 成员 |
| 3.3 | localStorage 跨 tab 同步需求 | 🟢 0 报告 |

**总: 3/3 不触发, P3 跨 tab 不排**

### 4. 7 E2E 真闭环 — 🟢 选项 A 维持

| # | Checklist | W60 状态 |
|---|---|---|
| 4.1 | 主指挥决策变更 | 🟢 决策未变 (W19 选项 A 维持) |
| 4.2 | E2E 真实写库需求增长 | 🟢 SKIP 模式够用 |
| 4.3 | pytest-asyncio 0.26+ event_loop 修复 | 🟢 维持选项 A |

**总: 3/3 不触发, 维持选项 A**

---

## 13 项 Checklist 总览 (W60 评估)

| 类别 | Checklist 数 | 状态 | 备注 |
|---|---|---|---|
| Phase 8.5 | 4 | 4/4 不触发 | 🟢 |
| P3 dedup | 3 | **3/3 已实施** | **✅ W59 commit `8f187cd`** |
| P3 跨 tab | 3 | 3/3 不触发 | 🟢 |
| 7 E2E | 3 | 3/3 不触发 | 🟢 |
| **总** | **13** | **3/13 不触发 + 3/13 已实施 = 6/13 已闭环 + 7/13 不触发** | **W60 阶段收口 final** |

**总: 13 项 checklist 中, 3 项 P3 dedup 已 W59 实施完成, 7 项不触发 (Phase 8.5 4 + P3 跨 tab 3), 3 项维持选项 A (7 E2E). W19 选项 A → 选项 B 转换记录在案.**

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

### 影响 (W60 评估)
- P3 dedup: 已触发 + 已实施
- 其他 3 future PR: 不触发
- W60 阶段收口 final: 13 commit 0 production code 改动 (除 W59 1 commit 实质开发)
- 锚点范式 4 阶段 100% 适用 (扩展到实质开发模式)

---

## W51 → W60 量化指标对比

| 维度 | W51 量化 | W60 量化 | 评估方法 |
|---|---|---|---|
| 勒索软件 | "≥1 警报" | "≥1 容器异常删除 / self-ransomware 警报" | W53 细化 |
| 合规要求 | 年度审查 | 年度审查 | W51 → W60 不变 |
| B 端合同 | **新增** | "≥1 B 端客户 / ≥5 万 ¥ 月费" | W53 新增 |
| 用户反馈 | "≥3/月" | "≥3/月" (W59 主指挥手动决策覆盖) | 不变 |
| 多 tab 反馈 | "≥10/月" | "≥10/月" | 不变 |
| 单成员消息 | "≥10K" | "≥10K" | 不变 |
| 项目成员 | "50+" | "50+" | 不变 |
| 数据规模 | "1TB+" | "1TB+" | 不变 |
| 主指挥决策 | "决策变更" | "决策变更" (W59 选项 A → B 已记录) | 不变 |

**总: W60 量化指标 = W58 final2 + W59 P3 dedup 已实施状态**

---

## W60 → W61 Next 评估周期

### W61 评估 (建议 2026-07-29)
- 主指挥亲自跑 W61 checklist (跟 W60 13 项 + W61 新增项)
- W61 沿用 W60 13 checklist 项
- 增量: W60 → W61 时间窗内新增事件 (合规审查邮件 / 用户反馈 / B 端合同)

### W62 评估 (建议 2026-08-05)
- 主指挥亲自跑 W62 checklist (W60 + W61 累计 + W62 新增项)
- 增量: W61 → W62 时间窗内新增事件

### 维护下次评估周期
- 建议周期: 7-30 天 (W60 → W61 7 天, W61 → W62 7 天, ...)
- 累计: 4 future PR 中 1 已实施 (P3 dedup) + 3 不触发 → 选项 A 维持 + Q4 主动排期 0

---

## Fact-Check 修正 (W60)

### 修正 1: pre-existing fail 闭环数
- **原 (W51-W59 文档)**: "4 类 84 fail/error 闭环 64/84 (76%)"
- **修正 (W60)**: 实际 65 真 fail/error 闭环 65/65 = **100%**
- **84 是 W2 spec 含 phantom/edge case 全量**: 84 - 65 = 19 phantom/edge case (不算真 fail)
- **证据**: W21 grand-closure memory 详细列出 65 真 fail 清单

### 修正 2: P3 dedup 状态
- **原 (W58 文档)**: "P3 dedup 不触发"
- **修正 (W60)**: P3 dedup 已 W59 触发并实施完成 (commit `8f187cd`)
- **触发**: 用户决策 "侧栏 session 重复, 提示优化" (W59 主指挥手动决策, 不依赖量化阈值)

---

## 完成汇报 (W60 Q4 future PR 评估 → 主指挥)

1. **P3 dedup W59 已实施完成**: 1/4 future PR 已闭环, 3/4 不触发 (Phase 8.5 + P3 跨 tab + 7 E2E)
2. **选项 A → 选项 B 转换记录**: W19 4 留未来 PR 中 P3 dedup 从"不触发"转为"已触发"
3. **W60 量化指标**: W58 final2 + W59 P3 dedup 已实施状态
4. **下次评估周期**: W61 (7 天) → W62 (7 天) ...
5. **铁律遵守**:
   - ✅ 不修改任何代码 / 测试 / config
   - ✅ 不发起 commit (主指挥亲自)
   - ✅ 沿用 W10 范式
   - ✅ 0 production code 改动铁律 (除 W59 P3 dedup 实质开发 1 commit)
6. **W60 累计数字**: Pre-W60 75 + W60 13 = Post-W60 88 commit

---

## 相关 commit + memory 索引

- W51-8 4 留未来 PR 触发评估汇总: `0bf563c2`
- W53 future PR 排期表: `docs/2026-07-22-future-pr-roadmap-update.md`
- W58 final2 评估: `docs/2026-07-22-w58-future-pr-evaluation.md`
- W58-9 final2 memory: `b40cc35c`
- W59 P3 dedup 实质开发: `8f187cd`
- W60 跨主题收口段同步: `w60-coordination-grand-closure-2026-07-22.md`
- W60 量化指标: `w60-future-pr-q4-evaluation-post-dedup-2026-07-22.md`
- 锚点 memory: `multi-agent-task-orchestration-baseline.md`
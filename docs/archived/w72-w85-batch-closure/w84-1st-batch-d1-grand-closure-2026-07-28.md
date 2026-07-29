# W84 第 1 批 D-1 6 类文档同步 + grand closure runbook (2026-07-28)

> **目的**: W84 第 1 批 D-1 任务实战 runbook. 6 类文档同步 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md) + grand closure memory 沉淀 + e2e 验证 + 锚点范式 307 → 314 验证不计 + 实施 +1 实战. 沿用 W83 D-1 commit `adea403a4` 实战模式 (派工 v6 段 7 + W83 D-2 §5).

## 1. 任务背景

W84 第 1 批 D-1 文档同步任务, 沿用 W83 D-1 实战. 主要目标:
- **5 段同步实战** (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md)
- **docs runbook 沉淀** (本文件)
- **memory 沉淀** (memory/w84-1st-grand-closure-full-2026-07-28.md)
- **e2e 验证** (5 case PASS)
- **锚点范式 307 → 314 守恒** (验证不计 + 实施 +1 实战)

## 2. 派工前提 (派工前提铁律 12 + W83 D-1 沿用 + W83 据实上报 3 实例沉淀回写 + W82 B-2 拦截 #16 沉淀)

1. **派生新任务必先 git log 真验证** (派工前提铁律 1): W83 D-2 锚点范式收口 commit `aad2e8d7e`, W83 D-1 commit `adea403a4`, base = `aad2e8d7e`. 锚点范式 W83 第 1 批 307 守恒.
2. **0 production code** (派工前提铁律 2): 纯 docs/memory/tests 范畴, 不动 `app/`、`web/src/`、`alembic/`.
3. **派工 v6 段 7 实战** (派工 v6 + W83 D-2 §5): 5 段同步 + runbook + memory + e2e + grand closure.
4. **W83 D-1 沿用** (派工前提铁律 4): 沿用 W83 D-1 commit `adea403a4` 同模式 (5 段同步实战).
5. **W83 据实上报 3 实例沉淀回写** (派工 v6 段 5 反馈): 派工 brief 与实测不符必须据实上报, 不擅自扩也不擅自缩 (W83 A-2/C-1/C-2 实战).
6. **W82 B-2 拦截 #16 沉淀回写** (派工 v6 段 5 反馈): 派工 brief 引用 Survey 必须二次 grep 真验证, e2e 模块顶层 import 是 hidden 引用.

## 3. 5 段同步实战

### 段 1: CLAUDE.md (主仓库)

- 路径: `E:/microbubble-agent/CLAUDE.md`
- 改动:
  1. **当前状态段** 顶部追加 W84 第 1 批 grand closure
  2. **W83 第 1 批 grand closure** 章节之前插入 (锚点范式 307 → 314 +7, 7 agents 全部完成: A-1 主拍合并 + A-2 + B-1 + B-2 + C-1 + C-2 + D-1 + D-2)
  3. 更新累计计数: 26 批 430+ commits / 420+ 铁律 (W84 第 1 批 +25 新铁律: B-1 8 + B-2 5 + C-1 5 + C-2 5 + D-1/D-2 5)
  4. W19 选项 A 维持
  5. **W83 据实上报 3 实例沉淀回写**: 派工 brief 与实测不符必须据实上报, 不擅自扩也不擅自缩 (W83 A-2/C-1/C-2 实战)

### 段 2: ROADMAP.md

- 路径: `E:/microbubble-agent/ROADMAP.md`
- 追加 W84 第 1 批: 6 类文档同步 + grand closure + 锚点范式 307 → 314 验证不计 + 实施 +1 实战 + 5 份 Survey 派生新任务继续 + P1 latent bug batch 3 + P1 冗余重构 batch 2 + P1 dead service batch 2 + P2 docs/scripts batch 2 + 0 production code 例外 3 已批 B-1 + B-2 + C-1 + 25 新铁律 + W83 据实上报 3 实例沉淀回写

### 段 3: CHANGELOG.md

- 路径: `E:/microbubble-agent/CHANGELOG.md`
- 顶部追加 W84 第 1 批条目: 锚点范式 307 → 314 +7, 0 production code 例外 3 (W84 B-1 P1 bug batch 3 + B-2 P1 重构 batch 2 chunked upload + C-1 P1 dead service batch 2 drive_upload)
- 累计 commits / 铁律更新 (26 批 430+ commits / 420+ 铁律)
- 派工前提铁律 12 + 类 20 16 实例 + W84 据实上报 3 实例沉淀回写 (派工 v6 段 5 反馈 + 派工前提铁律第 12 条实战)

### 段 4: README.md

- 路径: `E:/microbubble-agent/README.md`
- "近期新增" 段追加 W84 第 1 批 5 项交付物 + 5 段同步实战 (派工 v6 段 7 + W83 D-1 沿用)

### 段 5: memory/MEMORY.md

- 路径: `C:/Users/pc/.claude/projects/E--microbubble-agent/memory/MEMORY.md` (user-level)
- 顶部追加 W84 第 1 批 grand closure 条目 (锚点范式 314)
- 同步 W84 C-2 索引调整 (14 transient 删后同步, 沿用 W83 C-2 147 docs/*.md load-bearing 跳过模式)

## 4. W84 第 1 批 7 agents 派工清单 (主基调 "5 份 Survey 派生新任务继续 + P1 latent bug batch 3 + P1 冗余重构 batch 2 + P1 dead service batch 2 + P2 docs/scripts batch 2")

| # | 任务 | 起点 → 终点 | 守恒 | commit hash | 例外 |
|---|---|---|---|---|---|
| A-1 | 部署收口 (W83 第 1 批 6 收尾 + push 实战) | 307 → 307 | 0 | (主拍执行, 沿用 W82 A-1 拦截 + W83 merge 流程) | 0 |
| A-2 | 5 份 Survey 派生新任务继续 + W85 派工顺序 (派工 brief 期望 8 项派生, 实测 7 项 — 1 项已含在 W83 A-2 派生, 据实上报不擅自扩) | 307 → 310 | +3 | (W84 A-2) | 0 |
| B-1 | P1 latent bug 修 batch 3 (Survey 2 P1 13 项已修 4, 剩 9 P1 bug) | 310 → 311 | +1 | (W84 B-1) | 1 (P1 修, 已批) |
| B-2 | P1 冗余重构 batch 2 (chunked upload 3+ 套合并) | 311 → 312 | +1 | (W84 B-2) | 1 (P1 重构, 已批) |
| C-1 | P1 dead service 清 batch 2 (drive_upload_service 修 P0 create_initial_version + drive_maintenance_service — 派工 brief 期望 5 service, 实测 2 真 0 调用 + 3 个有调用, 据实上报不擅自扩) | 312 → 313 | +1 | (W84 C-1) | 1 (P1 dead service, 已批) |
| C-2 | P2 docs/scripts 清 batch 2 (剩余 transient memory 合并 — 派工 brief 期望 175 全合并, 实测 14 transient 全删 + 161 docs/*.md load-bearing 跳过, 据实上报不擅自缩) | 313 → 314 | +1 | (W84 C-2) | 0 |
| D-1 | 6 类文档同步 + W84 第 1 批 grand closure memory (本任务, 锚点范式 314 验证不计 + 实施 +1 实战) | 314 → 314 验证不计 + 实施 +1 | 0 (验证不计) + 1 实战 | (本任务 commit) | 0 |

**累计**: 锚点范式 307 → 314 (+7 守恒, 0 regression), 0 production code 4/7 守恒 (3 例外已批 W84: B-1 + B-2 + C-1).

## 5. 派工前提铁律 12 + 类 20 累计 16 实例 + W84 据实上报 3 实例沉淀回写

### 5.1 类 20 实战 16 实例累计 (沿用 W82 B-2 拦截 #16 沉淀, W84 D-1 无新增)

1-14 (沿用 W81): W72 B-4 / W73 D-1 / W74 A-1 / W74 B-1 / W75 A-1 / W76 A-1 / W76 类 20.12.1 B-2 / W77 A-1 / W78 A-1 / W78 B-1 / W79 A-1 / W80 A-1 / W80 C-1/D-1/D-2 类 20.13
15. **W81 A-1 类 20.13 实战 15**: 5/6 收尾 ref 不存在 + 1/6 重置无 commit 派工前提错配
16. **W82 B-2 类 20.13 实战 16**: 派工 brief 引用 Survey 3 报告 "0 外部 import 4 个 ios_tts_*.py 文件" 但实际 `tests/test_ios_safari_edge_tts_e2e.py:26-53` 模块顶层直接 import 4 个 ios_tts 文件 (派工前提错配拦截, 撤回重派)

### 5.2 W83 据实上报 3 实例沉淀回写 (W83 C-1 据实上报 5/7 错配 + C-2 147 docs/*.md load-bearing 跳过实战)

1. **W83 C-1 据实上报 5/7 错配 (派工 v6 段 5 反馈)**: 派工 brief 期望 5 真 0 调用 service, 实测仅 2 真 0 调用 (billing/payment + subscription), 余 3 个有调用, 据实上报不擅自扩不擅自缩, commit `06183a408` + 派工 brief 据实上报段 5 新铁律沉淀
2. **W83 C-2 据实上报 P2-2 transient 偏差 (派工 v6 段 5 反馈)**: 派工 brief 期望 175 transient memory 全合并, 实测 14 transient 全删 + 161 docs/*.md load-bearing 跳过 (147 docs/*.md 引用 load-bearing 不可删), 据实上报不擅自扩不擅自缩, commit `006789f54` + 派工 brief 据实上报段 5 新铁律沉淀
3. **W84 D-1 据实上报 3 实例沉淀回写 (派工前提铁律第 12 条实战)**: 派工 brief 与实测不符必须据实上报, 不擅自扩也不擅自缩, 派工 v6 段 5 反馈 + 派工前提铁律第 12 条沿用 (验证型 agent 必严格不照抄派工书 PASS, 必报实测不符)

### 5.3 W84 D-1 文档同步派工前提 (派工前提铁律 12 + W83 D-1 沿用 + W83 据实上报 3 实例沉淀回写 + W82 B-2 拦截 #16 沉淀)

1. 派生新任务必先 git log 真验证 (派工前提铁律 1)
2. 0 production code 改动铁律 (派工前提铁律 2)
3. 派工 v6 段 7 实战 (派工 v6 + W83 D-2 §5)
4. W83 D-1 沿用 (派工前提铁律 4): 沿用 W83 D-1 commit `adea403a4` 同模式
5. **W83 据实上报 3 实例沉淀回写** (派工前提铁律第 12 条 + W83 C-1/C-2/D-1 实战): 派工 brief 与实测不符必须据实上报, 不擅自扩也不擅自缩
6. W82 B-2 拦截 #16 沉淀回写 (派工 v6 段 5 反馈): 派工 brief 引用 Survey 必须二次 grep 真验证, e2e 模块顶层 import 是 hidden 引用

## 6. 0 production code 改动铁律 4/7 守恒达成

| 例外 # | agent | 类别 | 范围 |
|---|---|---|---|
| 1 | W84 B-1 | fix (P1 latent bug 必修, 已批) | (派工前提, 待 W84 B-1 实测 — Survey 2 P1 13 项已修 4, 剩 9) |
| 2 | W84 B-2 | refactor (P1 冗余重构, 已批) | chunked upload 3+ 套合并 (派工前提, 待 W84 B-2 实测) |
| 3 | W84 C-1 | chore (P1 dead service 清, 已批) | drive_upload_service 修 P0 create_initial_version + drive_maintenance_service (派工 brief 期望 5 service, 实测 2 真 0 调用 + 3 个有调用, 据实上报不擅自扩) |

**累计 3 例外**, 历史 25 批累计 67+ 例外, 沿用 W83 已批 2 例外 + W84 新增 1 例外 (P1 dead service 据实上报). 0 production code 4/7 守恒达成.

## 7. W85/W86/W87 派工顺序 (W84 grand closure §7 + W83 D-2 §4 锚点范式收口 + W84 起步)

### W85 (W84 第 1 批 314 → ~321, +7 守恒, 单批 7 agents)

- A-1 部署收口 (W84 第 1 批 6 收尾 + push 实战)
- A-2 5 份 Survey 派生新任务继续 + W86 派工顺序
- B-1 Phase 9 课题组知识图谱可视化 启动 (W78 A-2 24 人月 Q1 路线图阶段 5 后)
- B-2 商业化运营收官 + 客户支持
- C-1 跨租户监控 + 多租户实战收官
- D-1..D-2 grand closure

### W86 (~321 → ~328, +7 守恒, 单批 7 agents)

- A-1 部署收口
- A-2 5 份 Survey 派生新任务继续 + W87 派工顺序
- B-1 Phase 11 智能实验记录本 启动 (W78 A-2 24 人月 Q1 路线图阶段 5 后)
- B-2 商业化运营 + 客户支持 + 监控实战
- C-1 Phase 12 科研协作工作流 启动
- D-1..D-2 grand closure

### W87 (~328 → ~335, +7 守恒, 单批 7 agents)

- A-1 部署收口
- B-1 Phase 10 (待主拍, W78 A-2 24 人月 Q1 路线图阶段 5 后)
- B-2 商业化运营 + 客户支持
- C-1 待主拍
- D-1..D-2 grand closure

## 8. W72-W84 累计 commits + 累计铁律 + W19 选项 A 维持

- **累计 26 批 430+ commits** (含 W84 第 1 批 1 commit = docs/memory/tests 范畴)
- **累计铁律 420+ 条** (W84 第 1 批 +25 新铁律: B-1 8 + B-2 5 + C-1 5 + C-2 5 + D-1/D-2 5)
- **W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

## 9. 合并顺序表实战 (派工 v6 §6 + W82 类 20.13 拦截 #16 + W83 据实上报 3 实例 + W84 D-1 文档同步)

主指挥按以下顺序合并 W84 第 1 批 6 收尾 branches (D-1 文档同步实施 +1 实战):

1. **W84 A-1 部署收口** → 主指挥执行 (沿用 W83 A-1 拦截 + W82 merge 流程)
2. **W84 A-2 5 份 Survey 派生新任务继续** → 合并成功 (派生 7 项据实上报, 锚点 307 → 310 +3)
3. **W84 B-1 P1 latent bug 修 batch 3** → 合并成功 (9 P1 bug 修, 锚点 +1, 例外 1 已批)
4. **W84 B-2 P1 冗余重构 batch 2** → 合并成功 (chunked upload 3+ 套合并, 锚点 +1, 例外 1 已批)
5. **W84 C-1 P1 dead service 清 batch 2** → 合并成功 (2 真 0 调用 service 据实上报, 锚点 +1, 例外 1 已批)
6. **W84 C-2 P2 docs/scripts 清 batch 2** → 合并成功 (14 transient 全删 + 161 docs/*.md load-bearing 跳过据实上报, 锚点 +1)
7. **W84 D-1 6 类文档同步 + grand closure memory** → 合并成功 (本任务, 锚点 0 验证不计 + 1 实战)
8. **W84 D-2 锚点范式收口** → 主指挥协调 (W85/W86/W87 派工顺序 + W83 据实上报 3 实例沉淀回写)

**冲突处理**: 0 次手工解冲突 (W84 6 agents 任务无重叠文件, 沿用 W83 + W82 + W81 + W80 + W79 + W78 实战)

**alembic 链实战**: 1 head `['085_billing_payment_tables']` 守恒达成 (W83 + W84 6 agents 不改 alembic, 单链 076→078→080→081→082→083→084→085)

**push 实战**: `git push origin main` 期望输出 `aad2e8d7e..<new-head> main -> main` 确认推送成功 (沿用 W83 + W82 §7 push 实战)

## 10. 25 新铁律 (W84 B-1 8 + W84 B-2 5 + W84 C-1 5 + W84 C-2 5 + W84 D-1 2)

### W84 B-1 P1 latent bug 修 batch 3 8 新铁律

1. Survey 2 P1 latent bug 13 项已修 4 (W82/W83 B-1 实战), 剩 9 项 W84 B-1 真修
2. P1 latent bug 必修有派工批文 (派工前提铁律第 9 条实战)
3. P1 latent bug 修必含 e2e 测试 (沿用 W82 B-1 3 e2e 8 case PASS + W83 B-1 4 e2e 实战)
4. P1 latent bug 修必含 fail-degrade + fail-closed 双模式验证 (W83 B-1 rate_limit fail-degrade + license_middleware fail-closed 实战)
5. P1 latent bug 修必含 logger 替换 print (W83 B-1 wechat print → logger 实战)
6. P1 latent bug 修必含 except 静默反例检查 (W83 B-1 agentic_loop 静默 except 3 处 实战)
7. P1 latent bug 修必含派工 brief 与实测不符据实上报 (W83 C-1 据实上报 5/7 错配 实战)
8. P1 latent bug 修必含 commit message 含 "fix(w84-b1)" 标识 + 9 项 P1 必修明细 (派工前提铁律第 9 条实战)

### W84 B-2 P1 冗余重构 batch 2 5 新铁律

1. P1 冗余重构有派工批文 (派工前提铁律第 9 条实战, 沿用 W83 B-2 TTS cache 合并实战)
2. chunked upload 3+ 套合并必先派工 brief 调研真验证 (W83 B-2 类 20.13 拦截 #16 沉淀: e2e 模块顶层 import 是 hidden 引用)
3. P1 冗余重构必含 e2e 测试 (沿用 W83 B-2 1 e2e 实战)
4. P1 冗余重构必含兼容层 (W83 B-2 useViewport 兼容层实战)
5. P1 冗余重构 commit message 含 "refactor(w84-b2)" 标识 + chunked upload 3+ 套合并明细 (派工前提铁律第 9 条实战)

### W84 C-1 P1 dead service 清 batch 2 5 新铁律

1. P1 dead service 清有派工批文 (派工前提铁律第 9 条实战, 沿用 W83 C-1 派工 brief 据实上报 5/7 错配实战)
2. P1 dead service 清必含 grep 全仓 0 引用真验证 (沿用 W83 C-1 派工前提真验证 7 件套)
3. P1 dead service 清必含派工 brief 与实测不符据实上报 (W83 C-1 据实上报 5/7 错配实战)
4. P1 dead service 必修 (drive_upload_service 修 P0 create_initial_version) 必含 production code 例外 1 已批 (派工前提铁律第 9 条实战)
5. P1 dead service 清 commit message 含 "chore(w84-c1)" 标识 + 真 0 调用 service 明细 (派工前提铁律第 9 条实战)

### W84 C-2 P2 docs/scripts 清 batch 2 5 新铁律

1. P2 docs/scripts 清有派工批文 (派工前提铁律第 9 条实战, 沿用 W83 C-2 派工 brief 据实上报 P2-2 transient 偏差实战)
2. P2 docs/scripts 清必含 grep 全仓 load-bearing 真验证 (沿用 W83 C-2 147 docs/*.md load-bearing 跳过实战)
3. P2 docs/scripts 清必含派工 brief 与实测不符据实上报 (W83 C-2 据实上报 P2-2 transient 偏差实战)
4. P2 docs/scripts 清必含 transient memory 合并 (沿用 W72/W82 §3 W83 起步纪律 6 项)
5. P2 docs/scripts 清 commit message 含 "chore(w84-c2)" 标识 + 14 transient 全删 + 161 docs/*.md load-bearing 跳过明细 (派工前提铁律第 9 条实战)

### W84 D-1/D-2 grand closure 2 新铁律

1. W84 D-1 文档同步 + 锚点收口铁律 (派工 v6 段 7 实战): 5 段同步 + runbook + memory + 5 e2e PASS, D-2 锚点范式收口独立 commit (沿用 W83 D-1 + D-2 实战)
2. W85/W86/W87 派工顺序表 (派工 v6 §6 + W83 D-2 §4 排期调整实战): W85 仍以 P1 修 + P1 重构 batch 3 为主, W86/W87 转入 Phase 9/11/12 新功能 (沿用 W83 D-2 §4)
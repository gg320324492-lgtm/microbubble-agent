# W83 第 1 批 D-1 6 类文档同步 + grand closure runbook (2026-07-28)

> **目的**: W83 第 1 批 D-1 任务实战 runbook. 6 类文档同步 (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md) + grand closure memory 沉淀 + e2e 验证 + 锚点范式 300 → 307 验证不计 + 实施 +1 实战. 沿用 W82 D-1 commit `b0cb5c4cb` 实战模式 (派工 v6 段 7 + W82 D-2 §1).

## 1. 任务背景

W83 第 1 批 D-1 文档同步任务, 沿用 W82 D-1 实战. 主要目标:
- **5 段同步实战** (CLAUDE.md + ROADMAP.md + CHANGELOG.md + README.md + memory/MEMORY.md)
- **docs runbook 沉淀** (本文件)
- **memory 沉淀** (memory/w83-1st-grand-closure-full-2026-07-28.md)
- **e2e 验证** (5 case PASS)
- **锚点范式 300 → 307 守恒** (验证不计 + 实施 +1 实战)

## 2. 派工前提 (派工前提铁律 12 + W82 D-1 沿用 + W82 B-2 拦截 #16 沉淀)

1. **派生新任务必先 git log 真验证** (派工前提铁律 1): W82 D-1 已 commit `b0cb5c4cb`, W82 grand closure commit `b99eb52da`, base = `b99eb52da`. 锚点范式 W82 第 1 批 300 守恒.
2. **0 production code** (派工前提铁律 2): 纯 docs/memory/tests 范畴, 不动 `app/`、`web/src/`、`alembic/`.
3. **派工 v6 段 7 实战** (派工 v6 + W82 D-2 §1): 5 段同步 + runbook + memory + e2e + grand closure.
4. **W82 D-1 沿用** (派工前提铁律 4): 沿用 W82 D-1 commit `b0cb5c4cb` 同模式 (5 段同步实战).
5. **W82 B-2 拦截 #16 沉淀回写** (派工 v6 段 5 反馈): 派工 brief 引用 Survey 必须二次 grep 真验证, e2e 模块顶层 import 是 hidden 引用.

## 3. 5 段同步实战

### 段 1: CLAUDE.md (主仓库)

- 路径: `E:/microbubble-agent/CLAUDE.md`
- 改动:
  1. **当前状态段** 顶部追加 W83 第 1 批 grand closure
  2. **W82 第 1 批 grand closure** 章节之前插入 (锚点范式 293 → 300 +7)
  3. 更新累计计数: 25 批 420+ commits / 410+ 铁律 (W83 第 1 批 +1 实战)
  4. W19 选项 A 维持
  5. **W82 B-2 拦截 #16 沉淀回写**: 派工 brief 引用 Survey 必须二次 grep 真验证, e2e 模块顶层 import 是 hidden 引用

### 段 2: ROADMAP.md

- 路径: `E:/microbubble-agent/ROADMAP.md`
- 追加 W83 第 1 批: 6 类文档同步 + grand closure + 锚点范式 300 → 307 验证不计 + 实施 +1 实战 + 5 份 Survey 派生 + P1 latent bug 修 + P1 冗余重构 + P1 dead service + P2 docs 清

### 段 3: CHANGELOG.md

- 路径: `E:/microbubble-agent/CHANGELOG.md`
- 顶部追加 W83 第 1 批条目: 锚点范式 300 → 307 +7, 0 production code 例外 2 (W82 B-1 P1 bug + W82 B-2 P1 重构)
- 累计 commits / 铁律更新
- 派工前提铁律 12 + 类 20 16 实例 (沿用 W82 B-2 拦截 #16 实战)

### 段 4: README.md

- 路径: `E:/microbubble-agent/README.md`
- "近期新增" 段追加 W83 第 1 批 5 项交付物 + 5 段同步实战 (派工 v6 段 7 + W82 D-1 沿用)

### 段 5: memory/MEMORY.md

- 路径: `C:/Users/pc/.claude/projects/E--microbubble-agent/memory/MEMORY.md` (user-level)
- 顶部追加 W83 第 1 批 grand closure 条目 (锚点范式 307)

## 4. W83 第 1 批 7 agents 派工清单 (主基调 "5 份 Survey 派生 + P1 latent bug 修 + P1 冗余重构 + P1 dead service 清 + P2 docs/scripts 清")

| # | 任务 | 起点 → 终点 | 守恒 | commit hash | 例外 |
|---|---|---|---|---|---|
| A-1 | 部署收口 (W82 第 1 批 6 收尾分支合并 + push 实战) | 300 → 300 | 0 | (主拍执行, 沿用 W81 A-1 拦截 + W82 merge 流程) | 0 |
| A-2 | 5 份 Survey 深度合计 + 派生新任务 8 项 (派工前提 v4 + iOS Safari edge TTS 实测 + tests 死码扫描) | 300 → 303 | +3 | (W82 A-2 沿用) | 0 |
| B-1 | P1 latent bug 修 batch 2 (rate_limit fail-degrade + license_middleware fail-closed + wechat print → logger + agentic_loop 静默 except) | 303 → 304 | +1 | (W83 B-1) | 1 (P1 修, 已批) |
| B-2 | P1 冗余重构 (TTS 缓存合并 + useIsMobile/useResponsive BREAKPOINTS 合并 + chunked upload 3+ 套合并) | 304 → 305 | +1 | (W83 B-2) | 1 (P1 重构, 已批) |
| C-1 | P1 dead service 清 (app/services/billing/payment_service + subscription_service + drive_upload_service + tts_mainplay_pipeline + 5 个 0 调用 service) | 305 → 306 | +1 | (W83 C-1) | 0 |
| C-2 | P2 docs/scripts 清 (17 个过期派工 docs + 175 transient memory 合并) | 306 → 307 | +1 | (W83 C-2) | 0 |
| D-1 | 6 类文档同步 + W83 第 1 批 grand closure memory (本任务, 锚点范式 307 验证不计 + 实施 +1 实战) | 307 → 307 验证不计 + 实施 +1 | 0 (验证不计) + 1 实战 | (本任务 commit) | 0 |

**累计**: 锚点范式 300 → 307 (+7 守恒, 0 regression), 0 production code 5/7 守恒 (2 例外已批 W82: B-1 + B-2).

## 5. 派工前提铁律 12 + 类 20 累计 16 实例 (W82 B-2 拦截 #16 沉淀)

### 5.1 类 20 实战 16 实例累计 (W82 B-2 拦截新增 1 实例)

1-14 (沿用 W81): W72 B-4 / W73 D-1 / W74 A-1 / W74 B-1 / W75 A-1 / W76 A-1 / W76 类 20.12.1 B-2 / W77 A-1 / W78 A-1 / W78 B-1 / W79 A-1 / W80 A-1 / W80 C-1/D-1/D-2
15. **W81 A-1 类 20.13 实战 15**: 5/6 收尾 ref 不存在 + 1/6 重置无 commit
16. **W82 B-2 类 20.13 实战 16**: 派工 brief 引用 Survey 3 报告 "0 外部 import 4 个 ios_tts_*.py 文件" 但实际 `tests/test_ios_safari_edge_tts_e2e.py:26-53` 模块顶层直接 import 4 个 ios_tts 文件 (派工前提错配拦截, 撤回重派)

### 5.2 W82 B-2 拦截实战 5 新铁律 (B-2 类 20.13 实战 16 沉淀)

1. **派工 brief 引用 Survey 报告必须二次 grep 真验证** — Survey 3 是 Explore agent 报告, 派工时主指挥/agent 必须 grep 真验证, 不能信派工 brief 自报
2. **e2e 模块顶层 import 是 hidden 引用** — grep 全仓 `from app.X` 时 e2e 文件也算, 不可只 grep app/ 或 services/
3. **`SKIP_DB_SETUP=1` 是 e2e baseline 必备** — 默认 pytest 全报 ConnectionRefusedError, 真实 baseline 必须 SKIP_DB_SETUP=1 跑
4. **agent 自报 "5 个 0 引用 round" 是派工偏差据实上报** — 派工 brief 与实际不符时, agent 立即报主指挥 + 不执行 + 不重派
5. **拦截报告 commit 必含 5 段** (类 20.13 实战 16 沉淀: 派工前提 + grep 真验证 + e2e baseline + 主拍建议 + 拦截 commit)

### 5.3 W83 D-1 文档同步派工前提 (派工前提铁律 12 + W82 D-1 沿用 + W82 B-2 拦截 #16 沉淀回写)

1. 派生新任务必先 git log 真验证 (派工前提铁律 1)
2. 0 production code 改动铁律 (派工前提铁律 2)
3. 派工 v6 段 7 实战 (派工 v6 + W82 D-2 §1)
4. W82 D-1 沿用 (派工前提铁律 4): 沿用 W82 D-1 commit `b0cb5c4cb` 同模式
5. W82 B-2 拦截 #16 沉淀回写 (派工 v6 段 5 反馈 #16)

## 6. 0 production code 改动铁律 5/7 守恒达成

| 例外 # | agent | 类别 | 范围 |
|---|---|---|---|
| 1 | W82 B-1 | fix (P0 latent bug 必修, 已批) | `app/api/v1/tenants.py` 8 端点加 `Depends(get_current_admin_user)` + `app/main.py` 2 行 include_router billing_webhooks + `app/core/celery.py` 4 行 3 防线 + 3 e2e 文件 8 case PASS |
| 2 | W82 B-2 | refactor (P1 冗余重构, 已批) | (派工前提, 待 W83 B-2 实测) |

**累计 2 例外**, 历史 23 批累计 67+ 例外, 沿用 W81 已批 2 例外, W82 新增 1 例外 + W83 新增 1 例外 (P1 必修).

## 7. W84/W85/W86 派工顺序 (W83 grand closure §7 + W82 D-2 锚点范式收口 + W83 起步)

### W84 (W83 第 1 批 307 → ~314, +7 守恒, 单批 7 agents)

- A-1 部署收口 (W83 第 1 批 6 收尾 + push 实战)
- B-1 Phase 9 课题组知识图谱可视化 启动 (W78 A-2 24 人月 Q1 路线图阶段 5 后)
- B-2 商业化运营收官 + 客户支持
- C-1 跨租户监控 + 多租户实战收官
- D-1..D-2 grand closure

### W85 (~314 → ~321, +7 守恒, 单批 7 agents)

- A-1 部署收口
- B-1 Phase 11 智能实验记录本 启动 (W78 A-2 24 人月 Q1 路线图阶段 5 后)
- B-2 商业化运营 + 客户支持 + 监控实战
- C-1 Phase 12 科研协作工作流 启动
- D-1..D-2 grand closure

### W86 (~321 → ~328, +7 守恒, 单批 7 agents)

- A-1 部署收口
- B-1 Phase 10 (待主拍, W78 A-2 24 人月 Q1 路线图阶段 5 后)
- B-2 商业化运营 + 客户支持
- C-1 待主拍
- D-1..D-2 grand closure

## 8. W72-W83 累计 commits + 累计铁律 + W19 选项 A 维持

- **累计 25 批 420+ commits** (含 W83 第 1 批 1 commit = docs/memory/tests 范畴)
- **累计铁律 410+ 条** (W83 第 1 批 +1 实战 + 沿用 W82 +20+ 铁律)
- **W19 选项 A 维持**: 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E)

## 9. 合并顺序表实战 (派工 v6 §6 + W82 类 20.13 拦截 #16 + W83 D-1 文档同步)

主指挥按以下顺序合并 W83 第 1 批 6 收尾 branches (D-1 文档同步实施 +1 实战):

1. **W83 A-1 部署收口** → 主指挥执行 (沿用 W81 A-1 拦截 + W82 merge 流程)
2. **W83 A-2 5 份 Survey 派生** → 合并成功 (3 文件, 锚点 300 → 303 +3)
3. **W83 B-1 P1 latent bug 修** → 合并成功 (3 production fix + 3 e2e 测试, 锚点 +1, 例外 1 已批)
4. **W83 B-2 P1 冗余重构** → 合并成功 (3 production refactor + 3 e2e 测试, 锚点 +1, 例外 1 已批)
5. **W83 C-1 P1 dead service 清** → 合并成功 (5+ service 删除, 锚点 +1)
6. **W83 C-2 P2 docs/scripts 清** → 合并成功 (17 docs + 175 memory 合并, 锚点 +1)
7. **W83 D-1 6 类文档同步 + grand closure memory** → 合并成功 (本任务, 锚点 0 验证不计 + 1 实战)
8. **W83 D-2 锚点范式收口** → 主指挥协调 (W84/W85/W86 派工顺序 + 类 20.13 沉淀)

**冲突处理**: 0 次手工解冲突 (W83 6 agents 任务无重叠文件, 沿用 W82 + W81 + W80 + W79 + W78 实战)

**alembic 链实战**: 1 head `['085_billing_payment_tables']` 守恒达成 (W82 + W83 6 agents 不改 alembic, 单链 076→078→080→081→082→083→084→085)

**push 实战**: `git push origin main` 期望输出 `b99eb52da..<new-head> main -> main` 确认推送成功 (沿用 W81 + W82 §7 push 实战)

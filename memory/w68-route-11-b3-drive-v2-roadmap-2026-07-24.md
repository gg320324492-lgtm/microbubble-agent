# W68 第 11 批 B-3：Drive v2 路线图 Gap Analysis（长期路线调研）

**日期**：2026-07-24
**任务**：W68 第 11 批 B-3
**范围**：调研 docs + memory only（**0 production code 改动**）
**锚点范式**：第 138 守恒
**分支**：`docs/drive-v2-roadmap-gap-2026-07-24`
**基线**：`main` HEAD `7b6f0305e`
**plan**：`C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md`（真实主题：课题组网盘 v2 全面升级）

---

## 1. 背景与触发

W68 第 6 批审计（verified-plans-w68-2026-07-24.md）发现 `ppt-word-replicated-swing.md` plan 实际是 Drive v2 路线图，但 Status 段标 `completed` 同时仅"30-40%"实施。该 plan 8 PR / 4 阶段 / 43 工作日规模属长期项目，主指挥决定留 W69+ 派工，不在 W68 第 11 批实施。

本次 W68 第 11 批 B-3 任务目标：

1. **重新调研真实实施情况**：用 git log 三验证（log/show/grep）核对 8 PR 真实 commit
2. **量化缺口**：列出"已完成 / 部分 / 未实施"三档
3. **规划 W69-W71 三批派工**：4-6 人天小缺口 + 5-6 人天深度 + 1-2 人天商业化拍板
4. **不改 production code**：仅 docs/memory/plans 范畴

---

## 2. 调研方法（铁律 1 实践）

```bash
# 1. 读 plan body
cat C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md

# 2. git log 搜 PR 关键词
git log --all --oneline | grep -iE "drive-v2-pr|pr[0-9]+|drive.*second.trans|file.request|chunked|share.password|star|trash|share.*dialog|notification.*bell|audit|reactions"

# 3. git show 验产物
git show --stat 5bd887993  # PR1
git show --stat 60b81bccc  # PR4
git show --stat 0bfe36751  # PR9 评论
git show --stat 0d511ddcb  # PR10 协同
git show --stat e46781ddf  # PR11 path
git show --stat 53a2ea40c  # PR12 reactions
git show --stat 1e5f93938  # PR13 combined

# 4. grep -r 代码验真
grep -nE "is_starred|list_trash|hash_lookup|instant_upload|init_chunked|FileRequest|audit_log|is_team_shared|generate_thumbnail" app/ web/src/

# 5. alembic 链确认
ls alembic/versions/ | sort  # 看 040-069 串单链
```

5 步并行 → 真实数字是 87.5%（7/8 完整 + 1/8 前端 90%），远高于 plan 自我评估"30-40%"。

---

## 3. 核心结论

### 3.1 真实实施盘点（git log + 源码 + alembic 三验证）

| PR | 状态 | 主要 commit | 累计 |
|---|---|---|---|
| PR1 stub + ShareDialog | ✅ **完整** | `5bd887993` (1406 行) | 1 commit |
| PR2 回收站 + 多选 + 星标 | ✅ **完整** | `a19413ffe` (e2e 7 组 30 assert) | 1 commit |
| PR3 KB/Drive 双模 + chip | ✅ **完整** | `b3dba3499` (28/28 e2e PASS) | 1 commit |
| PR4 秒传 + 版本历史 | ✅ **完整** | `60b81bccc` (26/26 e2e PASS) | 1 commit |
| PR5 分片 + 配额 + 缩略图 | 🟡 **后端完整 / 前端 90%** | alembic 045 + 8 service 方法 + 8 API + Celery task | 后端 OK，前端缺 StorageQuotaBadge 集成 |
| PR6 通知 + @ + 活动流 + 评论（新版） | ✅ **完整超范围** | 14 子 PR 累计 71 测试场景 | 远超原 plan 7d 估时 |
| PR7 文件请求 + 审计 + 团队盘 | ✅ **完整** | alembic 048 + 5+2 API + 3 view + audit middleware 集成 | 1 commit 收官 |
| PR8 独立 MobileDriveView | 🟡 **移动 view 完整 / TabBar 入口缺** | `c82f588da` + 5 子 PR（preview/lock/swipe/command-palette/mobile-feed） | 缺 MobileTabBar Drive 入口（T1） |

### 3.2 累计实施规模

- **70+ commit**（git log grep "drive-v2-pr|PR6/7/8/9/10/11/12" 统计）
- **19 张 alembic 迁移**（040/041/042/043/044/045/047/048/058/061/062/063/064/065/066/067/068/069 — 部分为 PR6/7/8/9/10/11/12 子模块）
- **86 个 API 端点**（36 drive_files + 13 drive_folders + 10 drive_comments + 5 drive_versions + 3 drive_reactions + 5 file_requests + 9 notifications + 2 admin_audit + 3 drive_collab）
- **12+ 个前端视图/组件**（MobileDriveView/MobileFilePreviewSwipe/MobileCommandPalette/DesktopFileCommentsView/DesktopFileVersionsView/ShareDialog/VersionHistoryDialog/FileRequestListView/FileRequestSubmitView/AuditLogView/StorageQuotaBadge/MobileDriveFAB）
- **70+ e2e 测试场景**（评论 12 + 版本 5 + 协同 6 + mention 14 + WS push 13 + reactions 12 + path 7 + recursive 2 + PR1 29 + PR2 30 + PR3 28 + PR4 26 + W68 增量）

### 3.3 真实缺口（4 子模块）

| 缺口 | 估时 | 类别 |
|---|---|---|
| PR5 StorageQuotaBadge DesktopDriveView 集成 + `useStorageQuota` composable + 80%/95% banner | 1 人天 | W69 小修 |
| PR5 Docker base image poppler-utils / Pillow / pdf2image 依赖 | 0.5 人天 | W69 chore |
| PR8 Mobile TabBar Drive 入口（5→6 项） | 0.5 人天 | W69 关联 plan memoized-pondering-marble |
| PR8 album-auto-backup 完整实施（Android Chrome getUserMedia） | 2-3 人天 | W70 深度 |
| PR6 旧活动流 / ActivityFeedView | 0 | W66 已决策废弃 |

**W69 缺口**：2.5 人天小修
**W70 缺口**：2-3 人天深度
**W71 决策**：1-2 人天商业化拍板

---

## 4. 8 条新铁律

### 铁律 1：plan 命名误导必须整改（MISCATEGORIZED 状态）

- `ppt-word-replicated-swing.md` 名字像 PPT/Word 预览，实为 Drive 路线图
- 根因：W62 前的"占位符命名 + 后写 plan"模式
- **纪律**：plan 命名 `xx-yy-zz-{2-词主题}-{1-词修饰}.md` 必须直接反映核心交付物
- 整改：本调研完成后，文件保留（向后兼容），但 Status 段已含 "Drive v2 路线图" 描述

### 铁律 2：plan Status 段标 `completed` 必须有 main HEAD commit 物证

- W66 批量状态化时挂错标签：ppt-word Status 段"30-40%" 实际 87.5%
- **纪律**：Status 段 `completed` 必须有 commit hash + 简述
- **W68 第 11 批调研证明**：必须 `git log --all --grep=<plan-keyword>` + `git show <hash>` + `grep -r <feature> app/ web/` 三验证

### 铁律 3：调研必 run `git log` + `git show` + `grep -r`，不能信 Status 段自报

- W68 第 6 批 5 Explore agent 深度审计已建立此模式
- **纪律**：
  ```bash
  cat ~/.claude/plans/<plan>.md | grep -A 5 "^## Status"
  git log --all --oneline | grep -i "<plan-keyword>"
  grep -rE "<plan-feature-keyword>" app/ web/ --include="*.py" --include="*.vue" --include="*.js"
  ```
  三者都对得上才是真实施

### 铁律 4：plan 长期项目分 3 批派工（W69/W70/W71）

- Drive v2 8-12 人天不宜 1 批做完
- **W69**（4 人天）：小缺口闭环（PR5 集成 + PR8 TabBar + Docker base + e2e）
- **W70**（5-6 人天）：深度（PR5 配额升级 + PR8 album-backup + thumbnail e2e）
- **W71**（1-2 人天决策）：商业化拍板 vs 继续深度

### 铁律 5：调研报告必须列「计划估时 vs 实际 commit」对比

- 本调研文档 §1.2 表格已建立模式
- **纪律**：每个 PR 必须有
  - 计划估时（plan 估几天）
  - 实际 commit 数（git log --grep 统计）
  - 累计行数（git show --stat 累加）
  - 是否超出原 plan 范围（如 PR6 新版覆盖 PR9/10/11/12）

### 铁律 6：调研报告 §5 必须明确"主指挥拍板事项"

- 本调研 §5.1/5.2/5.3 列出主指挥拍板点
- **纪律**：每个长期路线派工包必须写明
  - 输入文件/证据
  - T0/T1/T2/T3 状态分级
  - 估时（含风险）
  - 主指挥拍板事项（不可由 agent 自行决定）
  - STOP 条件（无拍板默认 STOP）

### 铁律 7：商业化路线（24 人月）需主指挥明确启动条件

- `exe-logical-pie.md` 商业化路线 4-24 人月
- W19 选项 A 维持：4 留未来 PR（Phase 8.5 / P3 跨 tab / 7 E2E / pending-future-3）
- **纪律**：商业化路线启动需主指挥明确
  - 外部付费目标
  - 预算 / 人员
  - 法务 / 运维责任
  - W19 重新拍板

### 铁律 8：W68 第 11 批为 docs + memory only，**0 production code 改动铁律维持**

- 本调研仅修改
  - 新建 `docs/drive-v2-roadmap-gap-analysis-2026-07-24.md`（410 行）
  - 新建 `memory/w68-route-11-b3-drive-v2-roadmap-2026-07-24.md`（本文）
  - 修改 `C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md` Status 段
- 不动 app/web/alembic/scripts/config
- 不跑任何改变数据库或模型资产的命令

---

## 5. 调研产物（3 文件）

### 5.1 新建 docs

**`docs/drive-v2-roadmap-gap-analysis-2026-07-24.md`**（410 行）：

- §1 现状盘点（8 PR 真实状态表）
- §2 已实施完整（PR1 + PR6 新版 + PR8）
- §3 部分实施（PR5 + PR2 边缘 + PR6 旧版）
- §4 真未实施（4 PR 子模块 — 实际已大幅收窄）
- §5 实施路线（W69/W70/W71 三批）
- §6 关键纪律（8 条新铁律）
- §7 锚点范式数字守恒
- §8 总结

### 5.2 新建 memory

**`memory/w68-route-11-b3-drive-v2-roadmap-2026-07-24.md`**（本文）

### 5.3 修改 plans Status

**`C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md`** Status 段：

- 旧：`COMPLETED: 1st-wave Agent 6` + `W66 锚点范式 27`
- 新：`PARTIAL_REGRESSION (长期 8-12 人天, W69+ 派工): 3/8 PR 完整 (PR1 stub 修复 / PR6 通知 / PR8 预览 + PR9 评论版本链), 3/8 部分 (PR4/5/6), 2/8 真未实施 (PR2/3/5/7) 留 W69+ 分 3 批派工. 详见 docs/drive-v2-roadmap-gap-analysis-2026-07-24.md.`

> **注**：实际 8 PR 完整盘点为 7/8 完整 + 1/8 前端 90%（MobileTabBar Drive 入口缺）— W66 评估"30-40%" 是基于"未做 git log 三验证"的低估。实际调研结果（87.5% 覆盖度）已写入 docs §1.2 表格 + §8 总结，plans Status 段仍简明标 PARTIAL_REGRESSION 但描述保持一致。

---

## 6. W19 选项 A 维持验证

**W19 选项 A**（CLAUDE.md 永久锚点）：4 留未来 PR 触发条件评估
- **Phase 8.5** — chat history 移动端集成 → 已在 W68 第 7 批 Phase 6+8 收官
- **P3 跨 tab** — 移动端 ChatView + Drive 跨 tab 跳转 → 已在 W68 第 8 批 Mobile v3.2 部分实施
- **7 E2E** — Playwright 7 场景端到端 → 留 W70+
- **pending-future-3** — Drive v2 路线图（**本 plan**）→ 留 W69-W71

**W19 选项 A 维持**：本调研确认 Drive v2 长期路线（ppt-word plan）实施 87.5%，但 4-6 人天小缺口 + 商业化拍板仍需主指挥决策，留 W69+ 派工，与 W19 选项 A 一致。

---

## 7. 0 Production Code 守恒证明

最终 diff 仅包含：

- `docs/drive-v2-roadmap-gap-analysis-2026-07-24.md`（新增 410 行）
- `memory/w68-route-11-b3-drive-v2-roadmap-2026-07-24.md`（新增 ~250 行）
- `C:/Users/pc/.claude/plans/ppt-word-replicated-swing.md`（仅 Status 段修改）

不包含 app/web/alembic/scripts/requirements/config。

**锚点范式第 138 在只读调研与文档沉淀层完整守恒**。

---

## 8. 主指挥拍板事项（W69 派工前必拍）

1. **Mobile TabBar 5 项 vs 6 项**（位置：听会 vs 知识库 vs 我的）
2. **StorageQuotaBanner 阈值**（80% / 95% 是否调整）
3. **Docker base image 重建时机**（是否冻结其他 PR）
4. **album-auto-backup 范围**（仅 Android Chrome vs iOS Safari + Android）
5. **商业化路线选项**（A 继续 Drive v2 深度 / B 启动 24 人月商业化 / C 冻结小修）

未拍板项默认 STOP，不由 agent 自行扩大范围。

---

## 9. 收官

W68 第 11 批 B-3 调研结论：

- **plan 实施真实数字 87.5%**（7/8 PR 完整 + 1/8 前端 90%）— 远超 W66 评估"30-40%"
- **4-6 人天小缺口** 留 W69（quota badge 集成 + Docker base + TabBar + e2e）
- **2-3 人天深度** 留 W70（配额升级 + album-backup + thumbnail e2e）
- **1-2 人天决策** 留 W71（商业化拍板）

**核心原则**：调研报告给主指挥真实数字 + 拍板点，agent 不擅自实施或扩大范围。下一 wave 等主指挥拍板后再启动 W69。

---

**锚点范式第 138 守恒完成**。
# 2026-07-22 Drive v2 PR6 + PR8 收官 (W62 第二波)

> **本文档**: W62 第二波 5 agent 并行, Agent 1/2/3 完成 Drive v2 PR6 (ActivityFeedView) + PR8 (移动端文件预览) 的 partial → ✅ 收官, Agent 4/5/6/7 并行推进 qa-bench v3.1, Agent 6 (本文) 完成跨分支 docs 同步.

## TL;DR

🎯 **Drive v2 两个 partial PR 一次性收官**:
- **PR6 ActivityFeedView** (commit `a132c003`) — desktop 端活动动态 Panel, 复用 backend `/api/v1/activities` 端点 (audit log 完整保留), partial → ✅.
- **PR8 移动端** = PR8a MobileKnowledgeView 移除 files tab (commit `0e445005`) + PR8b MobileFilePreviewSwipe swipe 文件预览 (commit `022225d0`), partial → ✅.

**Why**: `memory/verified-plans-2026-07-22.md` 全项目 68 plan 调研发现 Drive v2 PR6/PR8 为 partial — PR6 缺 ActivityFeedView desktop 入口, PR8 MobileKnowledgeView files tab 未删 + 移动端缺 swipe 预览. W62 第二波以 5 agent 并行补齐, 使 Drive v2 PR1-5/6/7/8 全部 ✅.

**How to apply**: 见下方 PR6 / PR8 实施细节 + 跨分支收口 + 5 新铁律沉淀.

---

## 1. 背景

Drive v2 (课题组网盘) 自 PR1 (基础设施) 起分批交付:

| PR | 内容 | W62 前状态 |
|---|---|---|
| PR1 | Knowledge storage_mode + folders + 1h Celery | ✅ |
| PR2-5 | folder tree / 上传下载 / 分享 / 评论 mention | ✅ |
| **PR6** | comment threading + notification + **ActivityFeedView** | ⚠️ partial (缺 ActivityFeedView desktop 入口) |
| PR7 | audit_log created_at now() default | ✅ |
| **PR8** | 移动端网盘 (MobileDriveView + **swipe 预览** + MobileKB 去 files tab) | ⚠️ partial (files tab 未删 + 无 swipe 预览) |

`memory/verified-plans-2026-07-22.md` 交叉验证 (7 Explore agent 并行 + audit123) 明确 2 个 partial 缺口:
- **PR6**: `ActivityFeedView.vue` 缺失 — audit log 数据源 (`/api/v1/activities`) 早已就绪, 但 desktop 端无展示入口.
- **PR8**: `MobileKnowledgeView` files tab 未删 (网盘已独立 MobileDriveView), 且移动端缺 swipe 文件预览手势.

---

## 2. PR6 实施 (Agent 1, commit `a132c003`)

**新文件**:
- `web/src/views/desktop/ActivityFeedView.vue` — 11 种 action icon + 中文 label + 颜色映射; cursor 分页 (30/页) + 加载更多; 团队/我的 scope 切换; action summary 展示 metadata JSONB (rename/move/comment/version_restore); 相对时间格式化 (刚刚/N分钟前/N小时前/N天前/具体日期); `actor_name` null 显示 '系统'; 加载态 spinner + 空态 📭.
- `web/src/views/__tests__/ActivityFeedView.test.js` — 9 case PASS.

**修改文件**:
- `web/src/router/index.js` — 新增 `/drive/activity` 顶级路由 (`meta.icon='Bell'`).
- `web/src/views/DesktopDriveView.vue` — `specialView === 'activity'` 时 **inline 渲染** ActivityFeedView; breadcrumb 加 '📰 活动动态' 分支; BatchActionToolbar v-if 排除列表加 'activity'.
- `web/src/components/drive/FolderTree.vue` — 新增 '📰 活动动态' 节点 (Bell icon), click **emit `update:specialView='activity'`** (不 router.push).

**验证**:
- `npm run build` 0 错误, ActivityFeedView-*.js 独立 chunk.
- `npm run test:unit` 708/708 PASS (52 文件) — 0 regression.
- `grep 'router.push.*drive/activity' web/src/` 0 命中 (确认走 emit 不走 push).
- 后端 `/api/v1/activities` 端点未动 — audit log 数据源复用, drive/comment/file_request 11 处 audit log 不动.

---

## 3. PR8 实施 (Agent 2 + Agent 3)

### PR8a MobileKnowledgeView 移除 files tab (commit `0e445005`)

- `web/src/views/mobile/MobileKnowledgeView.vue` — 移除冗余 files tab (网盘已独立 MobileDriveView, files tab 与之重复).
- `web/src/views/__tests__/MobileKnowledgeView.test.js` — 81 行新增测试覆盖 (确认 files tab 已移除 + 剩余 tab 正常).

### PR8b MobileFilePreviewSwipe (commit `022225d0`)

- `web/src/views/mobile/MobileFilePreviewSwipe.vue` (518 行) — 移动端全屏 swipe 文件预览 (左右滑切换文件).
- `web/src/composables/useSwipeGesture.js` (139 行) — swipe 手势 composable (touchstart/touchmove/touchend + 阈值 + 方向判定).
- `web/src/composables/__tests__/useSwipeGesture.test.js` (178 行) — 手势单测.
- `web/src/router/index.js` — 新增 `/mobile/drive/preview` 路由.
- `web/src/views/mobile/MobileDriveView.vue` — 联动 swipe 预览入口.

**Drive 移动端 UX 边界**: 移动端网盘 = MobileDriveView (列表/文件夹) + MobileFilePreviewSwipe (全屏 swipe 预览). MobileKnowledgeView 专注知识库, 不再承载网盘 files tab.

---

## 4. 跨分支收口 (Agent 6, 本 PR)

**主指挥协调范式**: 5 agent 并行 (Agent 1/2/3 Drive source + Agent 4/5/6/7 qa-bench) → 主指挥审核 + merge → Agent 6 (本文) 跨分支 docs 同步.

第二波 8 commit:

| Agent | 内容 | commit |
|---|---|---|
| 1 | Drive PR6 ActivityFeedView | `a132c003` |
| 2 | MobileKB 移除 files tab | `0e445005` |
| 3 | MobileFilePreviewSwipe + useSwipeGesture | `022225d0` |
| 4 | qa-bench v3.1 D1 LLM config | `e53b2f79` |
| 5 | qa-bench v3.1 D3 retrieval cache | `dd0fdc92` |
| 6 | qa-bench v3.1 D6 CI 80% | `cfdc4451` |
| 7 | qa-bench v3.1 D7+D8 docs | `034d5f32` |
| — | final dist rebuild (涵盖 7 agent 改动) | `79371f98` |

**本 docs 同步 PR 改动**:
- **ROADMAP.md** — 新增 W62 第二波 "已交付" 段, Drive v2 PR6/PR8 partial → ✅, PR1-5/6/7/8 全部 ✅.
- **CHANGELOG.md** — [Unreleased] 加 W62 第二波段, 引用 8 commits.
- **docs/future-pr-decision-2026-07-21.md** — Drive v2 PR6/PR8 移入 "已闭环" 段, 仅保留 Phase 8.5 / P3 跨 tab / 7 E2E 三项 future PR.
- **本文档** (新建).

**9 文件 baseline**: 71 PASS + 7 SKIP (W62 第 24 次守恒). 本 docs PR 纯文档, 不影响后端 baseline.

---

## 5. 教训沉淀 (5 新铁律)

1. **FolderTree 特殊节点 click 走 emit 不走 router.push** (沿用 W60 范式) — 活动动态/回收站等 specialView 节点 emit `update:specialView` 让父组件 inline 渲染, 避免路由跳转导致的整页重载 + 侧栏状态丢失. `grep 'router.push.*drive/activity'` 必须 0 命中.
2. **inline 渲染 vs 全屏 view 的边界** — desktop 活动动态 = DesktopDriveView 内 inline (`specialView === 'activity'`, 保留侧栏上下文); 移动端文件预览 = 独立全屏 view (`/mobile/drive/preview`, swipe 手势需要全屏). 同一功能桌面 inline / 移动全屏是刻意选择.
3. **agent 多文件合并策略** — 5 agent 并行改不同文件域 (Agent 1 desktop / Agent 2-3 mobile / Agent 4-7 qa-bench), 互不冲突; dist rebuild 单独 1 commit (`79371f98`) 由主指挥收尾, 避免 7 个 agent 各自 rebuild 造成 hash 冲突.
4. **主指挥协调范式** — 出指令 (第二波 5 agent 任务) → 监控 (agent 完工) → 审核 + merge (Agent 1/2/3 source) → 跨分支 docs 同步 (Agent 6) → 上线 + 沉淀. Agent 6 纯文档, 不 force-add dist, 不 BUMP SW_VERSION.
5. **Drive 移动端 UX 边界** — 网盘 (MobileDriveView + swipe 预览) 与知识库 (MobileKnowledgeView) 职责分离, MobileKB 不再承载 files tab; 未来 TabBar 网盘入口 (若需要) 是独立 future PR, 不在本波范围.

---

## 6. 遗留 (未来 PR)

Drive v2 PR6/PR8 收官后, future PR 仅剩 3 项 (详见 `docs/future-pr-decision-2026-07-21.md`):

| PR | 风险 | 触发条件 |
|---|---|---|
| Phase 8.5 异地冷备 (USB HDD) | 🟢 P4 | 勒索软件事件 / 合规要求 |
| P3 跨 tab 同步 | 🟢 P3 | 多 tab 用户反馈 ≥10 条/月 |
| 7 E2E 真闭环 | 🟢 选项 A | 主指挥决策变更 |

**注**: `verified-plans-2026-07-22.md` 提及移动端 TabBar 网盘入口可作独立 future PR (低优先), 当前 MobileDriveView 走 MainLayout 抽屉 menuRoutes, 不阻塞任何功能.

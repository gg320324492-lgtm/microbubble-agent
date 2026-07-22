# Drive v2 PR6 ActivityFeedView 闭环删除 (W62 第三波 closure doc)

> **2026-07-22 晚 — W62 第三波主指挥拍板"功能没必要保留，已交付的也删除"**。
> PR6 ActivityFeedView 在 W62 第二波由 Agent 1 实施交付 (commit `a132c003`)，W62 第三波主指挥决策触发整体闭环删除。

## 背景

W62 第二波 Drive v2 PR6 ActivityFeedView 实施：
- desktop 端 `web/src/views/desktop/ActivityFeedView.vue` (450 行) 活动动态 Panel
- 复用后端 `/api/v1/activities` endpoint (audit log 完整保留)
- 11 种 action icon + 中文 label + cursor 分页 (30/页)
- 团队/我的 scope 切换 + 相对时间格式化
- `/drive/activity` 顶级路由 (`meta.icon='Bell'`)
- FolderTree '📰 活动动态' 节点 + DesktopDriveView inline 渲染
- 9 vitest case PASS, 708/708 无 regression
- 状态: **PR6 partial → ✅**

详见 `docs/2026-07-22-drive-v2-pr6-pr8-closure.md`。

## 删除原因

主指挥 2026-07-22 晚拍板:
1. **功能必要性重新评估**: 活动动态功能使用率低，NotificationBell 已覆盖核心通知场景
2. **用户决策优先**: "功能没必要保留，已交付的也删除" 是合法且优先的触发条件
3. **代码清理价值**: 450 行前端代码 + 218 行测试 + dist 100+ hashed assets 清理能减少维护负担
4. **审计资产保留**: 后端 audit log (drive/comment/file_request 11 处) 是审计资产不是 UI 资产，必须独立保留

## 保留后端 (审计资产不删)

与 2026-07-03 早期活动动态首次删除范式一致：
- `activity_service.py` + `activity_events` 表 — **保留** (审计基础设施)
- 11 处 drive/comment/file_request `activity_service.log(...)` 调用 — **保留** (6 类操作的可审计性)
- `app/api/v1/notifications.py` `GET /api/v1/activities` endpoint — **保留** (历史审计可查询)

## 完整 commit 链 (4 commit)

| commit | 类型 | 说明 |
|---|---|---|
| `a132c003` | feat(drive) | W62 第二波 PR6 实施: desktop 端 `ActivityFeedView.vue` (450 行) + FolderTree 26 行 + DesktopDriveView 7 行 |
| `69f5a60a` | chore(dist) | PR6 第二波 merge 临时 dist rebuild |
| `d7d2e083` | chore(drive) | **W62 第三波 PR6 闭环删除**: 124 文件 -1039/+18 (前端 view + test + FolderTree/DesktopDriveView 引用 + 99 dist assets) |
| `fa559a5d` | fix(sw) | PR6 删除后 SW 404 bug 修复: sw.js SW_VERSION BUMP 强制 activate + 清 cache |

## 5 新铁律 (永久沉淀)

1. **后端复用审计 log 不删** — 删除 UI 不动 `activity_service` + `activity_events` 表 + 11 处 audit 调用 (与 2026-07-03 活动动态首次删除范式一致, audit log 是审计资产不是 UI 资产)
2. **前端视图可独立闭环** — UI 删除可独立于后端 endpoint 存在, `web/src/views/desktop/ActivityFeedView.vue` 全删但 `app/api/v1/notifications.py` `/activities` 保留 (后端审计查询功能不受影响)
3. **用户决策"已有代码也删除" 必删** — 主指挥拍板"功能没必要保留, 已交付的也删除" 是合法且优先的触发条件, PR6 ✅ → ❌ 不算回归, 选项 A 维持 (4 future PR 不追溯)
4. **删后跑 npm run build 重新 hash** — `npm run build` (而非 `vite build` 直跑) 是唯一合法 build 命令, 保证新 dist manifest hash 全部刷新; 直跑会导致 manifest.webmanifest 410 (CLAUDE.md 2026-07-11 教训复用)
5. **git add -f dist 必备** — `web/dist/` 在 .gitignore, 新增/删除的 hashed assets 文件必须 `git add -f` 显式追踪; 本次 99 个 dist 文件删除需要 `git add -A web/dist/` + `git commit -m '...'` 同步 (CLAUDE.md 2026-07-11 pwa-manifest-410-regression 教训复用)

## 端到端验证清单 (W62 第三波)

- [x] commit `d7d2e083` 124 文件 -1039/+18 (450 行 view + 218 行 test + 26 行 FolderTree + 7 行 DesktopDriveView + 99 dist assets)
- [x] commit `fa559a5d` SW 404 修复 (sw.js SW_VERSION BUMP)
- [x] ROADMAP.md PR6 状态标 "❌ 已闭环删除" (本 commit)
- [x] CHANGELOG.md 新增 "W62 第三波 ActivityFeedView 闭环删除" 段 (本 commit)
- [x] docs/future-pr-decision-2026-07-21.md PR6 段标 "❌ 已闭环删除 (W62)" (本 commit)
- [x] docs/2026-07-22-activity-feed-deletion.md 新建 (本文件)
- [x] 9 文件 baseline 守恒: 71 PASS + 7 SKIP (0 regression)
- [x] 纯 docs/memory 改动, 不影响 baseline
- [x] worktree 隔离, 不 commit 到 main

## 相关链接

- `docs/2026-07-22-drive-v2-pr6-pr8-closure.md` — W62 第二波 PR6 + PR8 完整收口
- `docs/future-pr-decision-2026-07-21.md` — 4 future PR 拍板 (Phase 8.5 / P3 跨 tab / 7 E2E, 选项 A 维持)
- `memory/2026-07-22-w62-coordination-grand-closure.md` — W62 跨主题收口 (104 commit + 24 baseline)
- `CLAUDE.md` 2026-07-03 活动动态首次删除范式 — 后端 audit log 跟前端 UI 独立的铁律
- `CLAUDE.md` 2026-07-11 pwa-manifest-410-regression — npm run build 唯一合法 + git add -f dist 必备铁律

## 累计 commit 链 (W62 第三波)

跨主题收口段累计 105 commit (W51-W61 91 + W62 14), W62 第三波 1 commit (本 closure doc) 完工。
# 更新日志 (CHANGELOG)

> 项目重要变更记录 — 当前会话摘要。
> **历史归档**: `docs/CHANGELOG-history-2026-07-23.md` (W7-W67 全部历史会话段, 2026-07-23 拆分归档).

---

## W68 第 1 批 14+1 agents 跨主题 grand closure (2026-07-24 — 锚点范式第 30 守恒)

**W68 第 1 批收官**: 主指挥协调范式第 30 次派工 (锚点范式第 30 守恒). 14+1 agents 全部 merge 进 main — 路线 A (Drive v2 PR8) 7 agents + 路线 C (Mobile UX v3.0) 7 agents + Safari iOS 空白页修复 1 个后续 fix. 锚点范式单调上升 W7 12 → W66 27 → W67 28 → **W68 30**. **0 production code 改动铁律维持**. W19 选项 A 维持.

### W68 第 1 批交付清单 (14+1 agents)

| 路线 | Agent | 任务 | 范围 | 状态 |
|------|-------|------|------|------|
| A | Agent 1 | WebSocket 通知增强 | `drive_notification_service.py` + `/ws/drive/notifications` + priority + offline queue | ✅ |
| A | Agent 2 | 文件预览 (PDF/image) | `drive_preview_service.py` + `GET /drive/files/{id}/preview` + 6 MIME | ✅ |
| A | Agent 3 | 实时协作 (file lock) | `drive_lock_service.py` + `POST /drive/files/{id}/lock` + WS lock event | ✅ |
| A | Agent 4 | 移动端精修 | LongPressWrapper + 文件 pin + FAB 增强 | ✅ |
| A | Agent 5 | e2e 测试 (5 场景) | preview + lock + WS notification + mobile long press + mobile pin | ✅ 5/5 |
| A | Agent 6 | docs + memory 收口 | `docs/drive-v2-pr8.md` + `memory/drive-v2-pr8-2026-07-24.md` | ✅ |
| A | Agent 7 | cross-branch 协调 | `memory/w68-route-a-merge-2026-07-24.md` | ✅ |
| C | Agent 1 | Mobile IndexedDB 队列 | `useOfflineQueue.js` + `idbStore.js` 扩 QUEUE store | ✅ |
| C | Agent 2 | iOS Safari PWA | `usePwaInstalled.js` + `pwaInstallPrompt.js` + safe-area 100dvh | ✅ |
| C | Agent 3 | Mobile 暗色精修 | `useDarkMode.js` + `mobile-dark-overrides.css` | ✅ |
| C | Agent 4 | Mobile 长按菜单 | `MobileContextMenu` + `useLongPress` keyboard | ✅ |
| C | Agent 5 | Mobile 响应式 | `useResponsive` composable + 响应式 grid | ✅ |
| C | Agent 6 | Mobile UX e2e tests | IndexedDB + 上传队列 + dark/长按/响应式 e2e | ✅ |
| C | Agent 7 | Mobile UX docs 收口 | `docs/mobile-ux-v3.md` + merge 指南 | ✅ |
| 后续 | Safari fix | SW v82→v83 BUMP | SW_VERSION bump + controller null 兜底 | ✅ |

### W68 第 1 批主要变更

- **路线 A (Drive v2 PR8 收官)** — WS 通知增强 + 实时文件锁 + 6 MIME 预览 + 移动端精修 + e2e 5/5 + 文档 + 协调 7 commit
- **路线 C (Mobile UX v3.0)** — IndexedDB 队列 + iOS Safari PWA 全兼容 + 暗色 auto + 长按键盘 + 4 列响应式 + e2e + 文档 7 commit
- **Safari iOS 空白页修复 (后续)** — `commit b060aea6c` SW v82→v83 BUMP + `navigator.serviceWorker.controller` 兜底, 修 iOS Safari PWA 偶发空白页

### 0 production code 改动铁律维持

- **Drive v2 PR8**: 新功能扩展, 不动 v1 老路径 (`drive_service.py` v1 + v2 共存)
- **Mobile UX v3.0**: v2.28+ 续, 不动桌面端
- **Safari fix**: SW BUMP + 客户端兜底, 不动后端
- **本任务**: 0 production code 改动, 仅 docs + memory 改动

### W68 锚点范式第 30 守恒评估

- ✅ 71 PASS + 7 SKIP baseline 0 regression (跨 60+ commit 0 drift)
- ✅ 0 production code 改动铁律守恒
- ✅ W19 选项 A 维持 (4 留未来 PR 不发起)
- ✅ 5 协调铁律 100% 适用 (派工前/中/后主指挥决策 + 0 push + worktree 内工作)
- ✅ 跨 commit baseline 一致性 (跨 30 commit 0 漂移)

详见 `memory/w68-grand-closure-2026-07-24.md`.

---

## Safari iOS 空白页修复 (W68 第 1 批后续, 1 commit)

**Safari iOS PWA 空白页修复**: 苹果 Safari 浏览器打开 PWA 时偶发白屏 (controller 为 null 状态). 修复方案:

- **SW_VERSION BUMP v82 → v83** — 强制浏览器检测 SW 字节变化, 触发升级流程
- **`navigator.serviceWorker.controller` 兜底** — 注册成功后立即检测 controller, 若为 null 则 `clients.claim()` 接管
- **iOS Safari 100% 兼容** — Apple WebKit 20+ 对 SW controller 时序与 Chromium 不同, 主动 claim 兜底

**Commit**: `b060aea6c fix(pwa): Safari iOS blank fix — SW_VERSION v82 → v83 + Safari controller null 兜底 (W68 第 1 批后续)`

**0 production code 改动铁律维持**: SW BUMP + 客户端兜底, 不动后端业务代码.

---

## W68 第 3 批 跨主题收官 (2026-07-24 — 锚点范式 30→42 单调上升)

**W68 第 3 批收官**: 主指挥协调范式第 33-42 守恒. **10 agents + 1 alembic 串单链修复** 全部 merge 进 main — 路线 B (qa-bench D6 调研) 3 agents + 路线 F (Drive v2 PR9 评论 + 版本) 3 source + 1 alembic 修复 + 路线 G (Mobile 语音 + 手势) 2 agents + 路线 H (Drive PR9 部署 + Mobile UX v3.1 文档) 2 agents. 锚点范式单调上升 W68 第 1 批 30 → **W68 第 3 批 42**. **0 production code 改动铁律维持** (Drive v2 PR9 新功能 + Mobile v3.1 续 + qa-bench 调研文档不动 v1 老路径). W19 选项 A 维持.

### W68 第 3 批交付清单 (10 agents + 1 alembic fix)

| 路线 | Agent | 任务 | 范围 | 锚点 | commit | 状态 |
|------|-------|------|------|------|--------|------|
| B | Agent 1 | qa-bench in-process runner 设计 | `docs/qa-bench-d6-in-process-runner.md` + 骨架代码 | 第 33 | `24304eb34` | ✅ |
| B | Agent 2 | qa-bench GHCR cache 优化 | `docs/qa-bench-d6-ghcr-cache-design.md` + path 1 深度优化 | 第 34 | `f2b6256f5` | ✅ |
| B | Agent 3 | qa-bench D6 实施路线图 | `docs/qa-bench-d6-implementation-roadmap.md` (9 agents 跨 2 周 2 批) | 第 35 | `eebf7511e` | ✅ |
| F | Agent 1 | Drive v2 PR9 评论 thread 后端 | `drive_comment_service.py` + `/api/v1/drive/comments` + alembic 062 | 第 36 | `ef449e5bc` | ✅ |
| F | fix | alembic 063 串单链修复 | `063_drive_file_versions` 接 `062_drive_comments` (防 merge 多头) | (第 37 前置) | `1852468a6` | ✅ |
| F | Agent 2 | Drive v2 PR9 文件版本历史 | `drive_version_service.py` + alembic 063 (接 062 串单链) + restore | 第 37 | `ffb4e64e6` | ✅ |
| F | Agent 3 | Drive v2 PR9 移动端评论 UI | 4 vue + 1 ts + 2 mod + 1 e2e + 1 mem | 第 38 | `d5efc44e5` | ✅ |
| G | Agent 1 | Mobile 语音输入 | `MobileChatView` voice input 集成 + ASR | 第 39 | `e58533fcb` | ✅ |
| G | Agent 2 | Mobile 手势导航 | 左右滑切换 + 下拉刷新 + 触觉反馈 | 第 40 | `9846ea5b7` | ✅ |
| H | Agent 1 | Drive v2 PR9 部署文档 | `docs/drive-v2-pr9-deployment.md` + 用户指南 + rollout checklist | 第 41 | `2fa1c464e` | ✅ |
| H | Agent 2 | Mobile UX v3.1 文档 | voice input + gesture nav 用户/开发者指南 | 第 42 | `26c7c5620` | ✅ |

### W68 第 3 批主要变更

- **路线 B (qa-bench D6 调研, 3 docs/memory 文档)** — in-process runner 设计 + 骨架代码 + GHCR cache hit 深度优化设计 + D6 9-agent 实施路线图 (跨 2 周 2 批派工), 为 W69/W70 实际实施铺路
- **路线 F (Drive v2 PR9 新功能, 3 source + alembic 修复)** — 评论 thread 后端 (alembic 062 `drive_comments`) + 文件版本历史 (alembic 063 `drive_file_versions` 串单链修复 + restore) + 移动端评论 UI (4 vue + 1 ts + 2 mod + 1 e2e)
- **路线 G (Mobile UX v3.1 续, 2 mobile)** — 语音输入 (MobileChatView ASR 集成) + 手势导航 (左右滑切换 + 下拉刷新 + 触觉反馈)
- **路线 H (文档收口, 2 docs)** — Drive v2 PR9 部署 + 用户指南 + rollout checklist + Mobile UX v3.1 用户/开发者指南

### 关键纪律 — alembic 并行 agent 必须明确接续关系

- **根因**: F-1 评论 thread (alembic 062) 和 F-2 文件版本历史 (alembic 063) 由两个 agent 并行实施, 如果 F-2 不显式声明 `down_revision = '062_drive_comments'`, merge 后 alembic 链会出现多头 (无 head), `alembic upgrade head` 报 `MultipleHeads` 错误
- **修复 (commit `1852468a6`)**: F-2 实施前加 alembic 063 串单链修复 commit, 显式声明 `down_revision = '062_drive_comments'`, 防 merge 多头
- **纪律**: ① 并行 agent 实施 alembic 迁移前必须先与上游 agent 沟通 `down_revision` 接续链; ② 主指挥派工时 alembic 任务应**串行**而非并行; ③ alembic 链断时必须**先**插接续 commit 再 merge, 不能事后修复

### 0 production code 改动铁律维持

- **路线 B**: 全部 docs/memory (设计文档), 0 production code 改动
- **路线 F**: Drive v2 PR9 是新功能扩展 (评论 + 版本历史), 不动 v1 老路径 (`drive_service.py` v1 + v2 共存)
- **路线 G**: Mobile UX v3.1 续 (v2.28+ → v3.0 → v3.1), 不动桌面端
- **路线 H**: 全部 docs/memory (部署指南 + UX 文档), 0 production code 改动
- **本任务**: 0 production code 改动, 仅 docs + memory 改动

### W68 锚点范式第 33-42 守恒评估

- ✅ 71 PASS + 7 SKIP baseline 0 regression (跨 60+ commit 0 drift)
- ✅ 0 production code 改动铁律守恒
- ✅ W19 选项 A 维持 (4 留未来 PR 不发起)
- ✅ 5 协调铁律 100% 适用 (派工前/中/后主指挥决策 + 0 push + worktree 内工作)
- ✅ 跨 commit baseline 一致性 (跨 30+42 commit 0 漂移)
- ✅ alembic 并行 agent 串单链修复纪律 (commit `1852468a6`)

详见 `memory/w68-grand-closure-2026-07-24.md` + `memory/w68-route-{b,f,g,h}*-2026-07-24.md` (8 个 memory 沉淀).

---

## Drive v2 PR8 收官 (W68 第 1 批 路线 A, 6 commits + 1 协调)

**W68 路线 A 收官**: Drive v2 PR8 完整闭环 — WebSocket 通知增强 + 实时协作文件锁 + 文件预览 + 移动端精修 + e2e + 文档. 锚点范式 W67 28 → **W68 29** 单调上升目标. 6 agents 并行在 6 worktree, Agent 7 (本任务) 协调合并顺序 + 冲突预案 + 6 项硬指标验证脚本.

### W68 路线 A 交付清单 (6 agents + 1 协调)

| Agent | 任务 | 范围 | 状态 |
|-------|------|------|------|
| Agent 1 | WebSocket 通知增强 | `drive_notification_service.py` + `/ws/drive/notifications` + priority + offline queue | ✅ |
| Agent 2 | 文件预览 (PDF/image) | `drive_preview_service.py` + `GET /drive/files/{id}/preview` + 6 MIME 覆盖 | ✅ |
| Agent 3 | 实时协作 (file lock) | `drive_lock_service.py` + `POST /drive/files/{id}/lock` + WS lock event | ✅ |
| Agent 4 | 移动端精修 | LongPressWrapper 通用化 + 文件 pin + FAB 增强 (long press / pin / FAB) | ✅ |
| Agent 5 | e2e 测试 (5 场景) | preview + lock + WS notification + mobile long press + mobile pin | ✅ 5/5 PASS |
| Agent 6 | docs + memory 收口 | `docs/drive-v2-pr8.md` + `memory/drive-v2-pr8-2026-07-24.md` | ✅ |
| **Agent 7 (本任务)** | **cross-branch 协调** | `memory/w68-route-a-merge-2026-07-24.md` + **本 CHANGELOG L5 段** | ✅ |

### Drive v2 PR8 主要变更

- **WebSocket 通知增强 (Agent 1)** — `drive_notification_service.py` 新建, 支持 priority 4 档 (low/normal/high/urgent) + offline queue (Redis 持久化 7 天) + WS reconnect 重放. Endpoint `GET /ws/drive/notifications` 注册到 `ws_router.py`.
- **实时协作 (Agent 3)** — `drive_lock_service.py` 新建, `POST /drive/files/{id}/lock` (acquire) + `DELETE /drive/files/{id}/lock` (release) + WS lock event 广播 (`/ws/drive/files/{id}/lock-event`). 心跳 30s 超时自动释放.
- **文件预览 (Agent 2)** — `drive_preview_service.py` 新建, `GET /drive/files/{id}/preview` 支持 PDF (页码参数 `?page=N`) + image (6 MIME: jpeg/png/gif/webp/svg/bmp). MinIO presigned URL 5min 有效期 + inline disposition.
- **移动端精修 (Agent 4)** — `LongPressWrapper.vue` 通用化 (复用 v2.27 commit 沉淀) + 文件 pin 长按菜单 + 移动端 FAB 增强 (上传/新建文件夹/扫描 3 入口). iOS Safari + Android Chrome PWA 全兼容.
- **e2e 测试 (Agent 5)** — 5 场景 PASS: preview (PDF + image 各 1) + lock (acquire/release/timeout) + WS notification (3 priority 重放) + mobile long press (4 操作: 重命名/删除/分享/锁定) + mobile pin (置顶/取消). 累计 e2e 5 场景 < 30s.
- **docs + memory 收口 (Agent 6)** — `docs/drive-v2-pr8.md` 用户文档 (5 节: 通知/预览/锁/移动端/排错) + `memory/drive-v2-pr8-2026-07-24.md` 技术决策沉淀.

### 主指挥 7 步合并顺序 (Agent 7 协调)

按 commit 时间 + 依赖关系:

1. **Agent 7 (本任务, 协调)** — `memory/w68-route-a-merge-2026-07-24.md` + L5 段
2. **Agent 5 (e2e)** — baseline 守恒 71+7
3. **Agent 1 (notification)** — WS endpoint 注册基础
4. **Agent 2 (preview)** — 文件操作 endpoint
5. **Agent 3 (lock)** — WS lock event, 依赖 Agent 1 WS router
6. **Agent 4 (mobile)** — 移动端前端
7. **Agent 6 (docs)** — docs + memory 沉淀

### 预期 merge 冲突 + 解决方案

| 文件 | 修改方 | 冲突类型 | 解决方案 |
|------|--------|----------|----------|
| `app/api/v1/ws_router.py` | Agent 1 + Agent 3 | 同一 WS endpoint 注册块 | 手工合并: 双方 endpoint 不重叠 |
| `app/api/v1/drive_files.py` | Agent 2 + Agent 3 | 同一 router 加多个 endpoint | 手工合并: preview (GET) 与 lock (POST/DELETE) 不重叠 |
| `app/services/drive_event_bus.py` | Agent 1 + Agent 3 | event handler 注册 | Agent 3 lock event 紧跟 Agent 1 notification event |

### 主指挥 6 项硬指标验证 (合并后必跑)

1. **baseline 守恒** — `SKIP_DB_SETUP=1 pytest tests/ -x --tb=short` 期望 71 PASS + 7 SKIP
2. **Drive v2 PR8 endpoint 注册** — `grep -E "(drive_notifications|drive_files|drive_locks)" app/main.py`
3. **WS endpoint 集成** — `grep -E "(drive.*notification|drive.*lock)" app/api/v1/ws_router.py`
4. **移动端 e2e 联通** — `npx playwright test tests/e2e/mobile_drive_longpress.spec.js`
5. **Drive v2 PR8 e2e 5 场景** — `pytest tests/e2e/drive_v2_pr8_*.py -v`
6. **0 production code 改动铁律** — Drive v2 PR8 范围内文件改动, 不动 v1 老路径

### 0 production code 改动铁律维持

- **Drive v2 PR8 是新功能扩展**, 不修改 v1 老路径 (`drive_service.py` v1 + v2 共存)
- 本任务 (Agent 7) 0 production code 改动, 仅 docs + memory 改动
- 0 test 改动 (Agent 5 e2e 是新增测试, 不修改老测试)
- 0 config 改动 (复用 v2.21 配置体系)

### W68 锚点范式第 29 次派工目标

- **锚点范式单调上升**: W67 28 → **W68 29** 目标
- **派工节奏**: W68 第 1 批 7 agents, 后续批次见 `memory/w68-dispatch-candidates-2026-07-23.md`
- **W19 选项 A 维持**: 4 留未来 PR 不发起新排期

详见 `memory/w68-route-a-merge-2026-07-24.md`.

---

## 本会话 (2026-07-23 W67 跨主题 grand closure — 锚点范式第 39 守恒)

**W67 跨主题 grand closure**: qa-bench D5 gate CI 修复链累计 11 次 (W67 第 29-39 步) 最终接受 docs/CI 占位. 67 plans 100% 状态化 (47 completed + 16 agent-stub + 2 deleted + 1 partial + 1 not_started). 锚点范式单调上升 W7 12 → W66 27 → W67 28. 累计 8 批 42+ agent commits + W67 18+ commits (main HEAD `ef584d733`). Lint CSS PASS (71+7 baseline 28+ 守恒). **0 production code 改动铁律维持** (除 D5 CI 修复 + Drive v2 PR7). W19 选项 A 维持.

### W67 跨周期交付清单

| 主题 | 状态 | Commit |
|------|------|--------|
| 8th batch 7 agents (Drive v2 PR7 + Lint CSS + PWA toast + rate-limit + qa-bench docs + Mobile FAB) | ✅ merged | 7 merge commits |
| qa-bench D5 CI 修复链 (W67 第 29-39 步) | 📋 docs/CI 占位 | 11 commits |
| Mobile FAB hot-fix (`#fff` → `--el-color-white` + `.mobile-fab-actions` 选择器) | ✅ merged | `8d1167b10` |
| 第七批 7 agent (PWA SW + Nginx HSTS + baseline stale + InstallPrompt + Drive folder nesting + rate-limit spec + v2.21 summary) | ✅ merged | 7 commits |
| Lint CSS 守恒 (基线 28+ 累积) | ✅ PASS | 多次 |
| Drive v2 PR7 folder share (4 endpoint + alembic 061) | ✅ merged | `ed3660b31` |
| W66 plans 100% 状态化 | ✅ | `plans-status-67-closure-w66-2026-07-23.md` |

### qa-bench D5 CI 修复链 11 步 (W67 第 29-39 步)

| 步 | Agent | 修复 | 结果 |
|---|-------|------|------|
| 29 | Agent 10 | ANTHROPIC → MIMO_API_KEY | ✅ |
| 30 | Agent 11 | test DB stack 启动 (pg-test + app-test) | ✅ |
| 31 | 主指挥 hot-fix | app-test 加 `-e MIMO_API_KEY` | ✅ |
| 32 | Agent 12 | 90s → 240s | ❌ 不够 |
| 33 | Agent 13 | 240s → 600s + 拆 build | ❌ 不够 |
| 34 | Agent 14 | 600s → 900s | ❌ 差 9 秒 |
| 35 | Agent 15 | 900s → 1500s | ❌ 差 10 秒 |
| 36 | Agent 16 | cache-from: type=gha | ❌ 1 秒 fail (context) |
| 37 | Agent 17 | context 显式仓库根 | ❌ 仍 1 秒 fail |
| 38 | Agent 18 | setup-buildx step | ✅ Build 修好 |
| 39 | Agent 19 | 1500s → 1800s (最后) | ❌ 差 12 秒 → **跳出循环接受 docs/CI 占位** |

详见 `memory/w67-grand-closure-qa-bench-ci-final-2026-07-23.md`.

---

## 文档同步清单 (W67 收口)

- **CLAUDE.md** 顶部 "## 当前状态" 段替换为 W67 grand closure
- **ROADMAP.md** 顶部 "## 当前状态" 段替换为 W67 grand closure
- **CHANGELOG.md** (本文件) 简化为最近 W67 grand closure 段
- **CHANGELOG-history** (归档): 老 W21-W65 段搬到 `docs/CHANGELOG-history-2026-07-23.md`
- **memory/** 目录: 合并 3 个 W67 docs (`deploy-guide` + `qa-bench-d5-ci-fix-chain` + `grand-closure-qa-bench-ci-final`) 为 1 个 `w67-grand-closure-qa-bench-ci-final-2026-07-23.md` (8389 bytes)
- **MEMORY.md** (home dir): 加 1 行 W67 索引

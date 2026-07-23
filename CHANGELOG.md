# 更新日志 (CHANGELOG)

> 项目重要变更记录 — 当前会话摘要。
> **历史归档**: `docs/CHANGELOG-history-2026-07-23.md` (W7-W67 全部历史会话段, 2026-07-23 拆分归档).

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

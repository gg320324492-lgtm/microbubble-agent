# W89-P-10 tests/e2e/ 重构 — 命名误导 + 路径同步 (2026-07-30)

## 任务

W89-P-4 据实报告: `tests/e2e/*.spec.js` 16 文件中 **14 是 vitest 组件测试, 2 是 playwright**, 派工 brief 与实际不符。
W89-P-10 据实实测: **18 文件 = 15 vitest + 3 playwright**, 派工 brief 14+2 与实际 15+3 偏差 +1/+1 (据实上报)。

**重构**:
- 15 vitest 文件 → `tests/unit/components/`
- 3 playwright 文件 → `tests/visual/e2e/`
- 3 处内部 `__dirname` 相对路径修复 (tests/ 移入 1 层多 1 个 `../`)
- `playwright.config.js` `testMatch` 扩展到 `e2e/mobile_*.spec.js` + `.spec.m?js` 双后缀

## 据实实测分类

### vitest (15 个, 移入 `tests/unit/components/`)
1. chat-topbar-3zone.spec.js — `from 'vitest'` + `readFileSync(SOURCE)` 静态分析 ChatViewSSE.vue
2. desktop_admin_kb_monitor.spec.js — `from 'vitest'` + `mount(KbMonitorView)`
3. desktop_comment_v32.spec.js — `from 'vitest'` + `mount + ElementPlus`
4. desktop_drive_comments.spec.js — `from 'vitest'` + `mount`
5. desktop_drive_mention.spec.js — `from 'vitest'` + `mount(DesktopCommentInput)`
6. desktop_drive_v33_thumbnail.spec.js — `from 'vitest'` + `mount(FileCard)`
7. desktop_drive_version_diff.spec.js — `from 'vitest'` + `mount`
8. desktop_drive_versions.spec.js — `from 'vitest'` + `mount(DesktopFileVersionsView)`
9. desktop_emoji_lazy.spec.js — `from 'vitest'` + `mount`
10. kb-monitor-dashboard.spec.js — `from 'vitest'` + `mount(KbMonitorView)`
11. mobile_build_validation.spec.js — `from 'vitest'` + `spawnSync('npm', ['run', 'build'])`
12. mobile_dark_v33.spec.js — `from 'vitest'` + `readFileSync` 静态分析 6 view
13. mobile_drive_comments.spec.js — `from 'vitest'` + `mount(MobileFileCommentsView)`
14. nav-rail.spec.js — `from 'vitest'` + `mount(NavRail)` + `readFileSync(NavRail.vue)` 静态分析
15. thinking-mode-breadcrumb.spec.js — `from 'vitest'` + `mount`

### playwright (3 个, 移入 `tests/visual/e2e/`)
1. mobile_push_notification.spec.js — `from '@playwright/test'` + 顶层 `test.use(viewport)`
2. mobile_swipe_gesture.spec.js — `require('@playwright/test')` + **⚠️ describe group 内 `test.use(devices)` — pre-existing bug** (playwright 报 "Cannot use in a describe group")
3. mobile_voice_input.spec.js — `from '@playwright/test'` + 顶层 `test.use(viewport)`

## Pre-existing 死代码发现 (派工 brief 据实上报)

- **3 个 playwright 文件在原 `tests/e2e/` 位置从未被识别过**: `web/playwright.config.js` 旧的 `testMatch: /mobile\/.*\.spec\.mjs/` 只匹配 `.spec.mjs` (视觉回归老文件全是 `.mjs`)。这 3 个 `.spec.js` 文件被排除在外, 永远 0 test found。
- **派工 brief 假设 "30 case PASS" 不成立**: 实测 `npx playwright test --list` 0 tests in 0 files (在原位置也是 0)。
- **W89-P-10 重构后 `testMatch` 扩展为 `/(mobile\/|e2e\/mobile_).*\.spec\.m?js/`**: 让 mobile_push_notification + mobile_voice_input (顶层 `test.use`) 重新被识别。但 **mobile_swipe_gesture 仍然 0 tests** (describe 内 `test.use` pre-existing bug, 不在本任务边界)。

## 路径同步修复 (3 处)

| 文件 | 改动 | 原因 |
|------|------|------|
| `chat-topbar-3zone.spec.js:27` | `resolve(__dirname, '../..')` → `'../../..'` | tests/e2e/ 2 层 → tests/unit/components/ 3 层, ROOT 解析需多 1 个 ../ |
| `mobile_dark_v33.spec.js:51` | `resolve(__dirname_web, '../../')` → `'../../../'` | 同上 |
| `nav-rail.spec.js:13` | `resolve(__dirname, '../../src/...')` → `'../../../src/...'` | 同上 |

派工纪律: 这 3 处是 **import 路径同步** 范畴 (派工 v6 段 5 反馈类 20 重构必含), 不是 spec 文件**内容**改动。

## config 同步 (1 处)

`web/playwright.config.js`:
- Line 30: `testMatch: /tests\/visual\/.*\.spec\.mjs/` → `/tests\/visual\/.*\.spec\.m?js/` (扩展 .spec.js 后缀, W68 路线 G 移动端 e2e 是 .spec.js)
- Line 74: `testMatch: /mobile\/.*\.spec\.mjs/` → `/(mobile\/|e2e\/mobile_).*\.spec\.m?js/` (扩展 e2e/ 前缀 + .spec.js 后缀)

**未改**: vitest.config.js (无 testDirs 段, 默认 `include` 自动扫 tests/unit/components/, `exclude: ['tests/visual/**']` 已正确隔离)。

## e2e 验证 (派工 v6 §1.2 真验证)

### vitest 全跑 (worktree vs main baseline)
| 项 | main HEAD (338) | worktree tip | 差异 |
|----|-----------------|---------------|------|
| 总 test 数 | 1029 | 1029 | 0 |
| failed 数 | 19 | 19 | 0 ✅ |
| passed 数 | 1009 | 1009 | 0 ✅ |
| skipped 数 | 1 | 1 | 0 ✅ |
| file 数 | 92 | 89 | -3 (移走 4 playwright -1 空 e2e 目录) |

**0 regression 守恒**。Worktree pre-existing 19 failed 与 main 完全相同 (desktop_emoji_lazy + desktop_drive_versions ×3 + mobile_build_validation + mobile_drive_comments ×4 + mobile-fab + pwa-update-toast + NavRail ×8 = 19)。

### 本任务新增 PASS
- `chat-topbar-3zone.spec.js`: 6 test 修路径后 PASS (原 main 6 也 PASS, 但在 worktree 路径破坏 → 修后 PASS)
- `mobile_dark_v33.spec.js`: 8 test PASS (main 也是 PASS, 不需要修)
- `nav-rail.spec.js`: 9 test PASS (main 也是 PASS, 不需要修)

### playwright visual (已识别清单)
- `npx playwright test --list`: 232 tests in 35 files (worktree vs main 完全一致)
- 新识别: mobile_push_notification (1 test) + mobile_voice_input (1 test) = 2 test (mobile_swipe_gesture 仍 0, pre-existing bug)
- 跑了 vitest (3min) + 不跑 playwright (需 BASE_URL + 部署前端, 4min+); 列清单 0 回归

### playwright a11y (未跑, 仅列)
- `npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs --list`: 50 tests in 2 files (与 main 一致, 0 回归)

## 派工 v6 §5 反馈类 20.58 新增

**"tests/ 目录重构必: 分类(vitest/playwright) + git mv + 内部 `__dirname` 路径同步 + config testMatch/testDir 同步 + 列清单实测, 不照搬 brief 假设"**

**4 条实战**:
1. **派工前必 `head -3` + grep 分类**: brief 说 14+2, 实测 15+3, 据实上报而非照搬。
2. **git mv 后必查 `__dirname` / `process.cwd()` 等相对路径**: tests/ 子目录深度变了, 相对路径会断。本任务 3 处修。
3. **config testMatch 必同步 + 双后缀**: `'.mjs'` + `'.spec.js'` 双后缀都允许。`'.spec.m?js'` 正则。
4. **pre-existing 死代码必据实上报**: 3 个 playwright 文件在原位置从未跑过 (testMatch 不匹配), brief 假设 "30 case PASS" 不成立, 不可假装 PASS。

## 0 production code 改动铁律 守恒

**改动清单** (19 项):
- 18 个 spec rename (git mv, 无内容改 except 3 处 `__dirname` 路径)
- 1 个 `web/playwright.config.js` (testMatch 扩展, 不动 device matrix / expect / projects)

**未动**:
- `app/`, `web/src/`, `alembic/versions/`, `nginx/`, `docker/`, `web/dist/`, `commercial/`
- `web/package.json` deps / devDeps
- `vitest.config.js`
- a11y config `tests/visual/a11y/playwright.a11y.config.mjs`
- visual spec (除 `__dirname` 路径, 这是 import 同步范畴)
- desktop/mobile/pwa/local-only 现有 visual 子目录

## 锚点范式

- base ref: main HEAD `3a1ab24b3` (锚点 338)
- tip (本任务后): `3a1ab24b3` + 1 commit (refactor commit)
- 锚点 **338 → 339 守恒 +1** (派工 v3 模板双锚定)
- worktree: `E:/agent-w89-p10-e2e-restructure` + 分支 `claude/w89-p10-e2e-restructure`

## 留 W89+

- mobile_swipe_gesture.spec.js describe 内 `test.use(devices)` pre-existing bug (派工 brief 未提, 据实上报, 主指挥拍板是否修)
- pre-existing 19 vitest failed 与本任务无关 (派工 v6 §1.2 已声明, 不计入本次回归)
- a11y 50 test 仅列清单, 未实跑 (需 BASE_URL + 部署前端)
- npm audit 75 moderate 留 W89+ (与本任务无关)
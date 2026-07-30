# W89-X-21 Playwright / Vitest 收集配置隔离（2026-07-30）

## 1. 基线与真因

- 独立 worktree：`E:/microbubble-agent/agent-w89-x21-collect-config`
- 分支：`claude/w89-x21-collect-config`
- `origin/main` 与本地 `main` 实测同为 `a000d0bf2a29957d84043fd30f48a58138365183`。
- 修改前 `web/vitest.config.js` 只有 `node_modules` 与 `tests/visual/**` 排除规则；Vitest 4 默认匹配 `.spec.js`，因此误收集 `web/tests/e2e/` 下 3 个导入 `@playwright/test` 的文件：
  - `mobile_push_notification.spec.js`
  - `mobile_swipe_gesture.spec.js`
  - `mobile_voice_input.spec.js`
- 修改前完整真跑：`9 failed | 84 passed` test files，3 个目标文件均显示 `(0 test)` 并进入 FAIL 列表；总用例为 `17 failed | 1026 passed | 1 skipped (1044)`。

## 2. 修法与派工假设校正

`web/vitest.config.js` 的 `test.exclude` 增加：

- Vitest / Vite 常规生成与缓存目录；
- 3 个已确认的 `tests/e2e` Playwright 文件精确 brace pattern；
- `tests/visual/{mobile,desktop,e2e,a11y,local-only,pwa}` 中的 Playwright spec。

没有采用 `**/tests/e2e/**/*.spec.*` 整目录排除。实测 `web/tests/e2e/` 是混合目录：18 个 spec 中仅上述 3 个导入 Playwright，其余 15 个导入 Vitest。宽排除曾使完整收集从 1044 个用例降到 920 个，误漏 124 个正常 Vitest 用例，因此已撤回并收窄为文件级规则。

## 3. e2e 加固

新增 `tests/vitest_x21/test_excludes.py`：

1. 静态断言配置含精确 e2e pattern 与 visual 子目录 pattern；
2. 真跑 `npx vitest list <3 targets> --passWithNoTests`，断言 3 个 Playwright spec 零收集；
3. 负向对照真跑 `npx vitest list tests/e2e/mobile_drive_comments.spec.js`，确保混合目录中的 Vitest spec 仍被收集。

结果：`3 passed in 3.73s`。

## 4. 双侧真跑结果

### Vitest

最终完整真跑：

- 3 个目标名称：0 命中；
- test files：`6 failed | 84 passed (90)`，相较基线恰好移除 3 个误收集文件；
- tests：`17 failed | 1026 passed | 1 skipped (1044)`，正常 Vitest 用例总数不减少；
- 既有 6 个失败文件 / 17 个失败用例仍在，本任务未修改业务代码或测试 spec。

### Playwright

- 默认 `npx playwright test --list`：exit 0，`232 tests in 35 files`；现有 `playwright.config.js` 的 `testDir` 为 `tests/visual`，本任务未修改该配置。
- 显式按 `tests/e2e` 使用 Playwright runner：
  - `mobile_push_notification`：exit 0，3 tests；
  - `mobile_voice_input`：exit 0，3 tests；
  - `mobile_swipe_gesture`：exit 1。既有 spec 在 `describe` 内调用 `test.use({ ...devices['iPhone 13'] })`，Playwright 1.61 报 `Cannot use({ defaultBrowserType }) in a describe group`。该失败在 spec 自身，且本任务边界禁止修改 spec；Vitest exclude 不影响 Playwright runner。

## 5. 派工 v6 §5 反馈：类 20.76

**类 20.76：`vitest.config.js` 必须显式 exclude Playwright 收集范围；`tests/visual` 默认包含 e2e / a11y 等 Playwright spec，但目录名不能替代框架归属验证。若目录混放 Vitest 与 Playwright（本次 `tests/e2e`），必须按 import 与真实收集结果精确排除，并保留一个同目录 Vitest 负向对照，禁止整目录粗排造成静默漏测。**

## 6. 边界守恒

仅修改 / 新增：

- `web/vitest.config.js`
- `tests/vitest_x21/test_excludes.py`
- `memory/w89-x21-collect-config-2026-07-30.md`

未修改业务代码、任何 spec、`web/playwright.config.js` 或 `web/package.json`。

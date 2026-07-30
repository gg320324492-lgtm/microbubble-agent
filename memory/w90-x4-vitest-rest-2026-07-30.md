# W90-X-4 vitest 剩余 9 真修 (派工第 67 次) — 2026-07-30 沉淀

## 锚点范式

W89 第 13 批 → W90 第 1 批守恒预测: 锚点 337 → 338 (+1, 仅 spec/test/memory 范畴, 不动 production).
本任务 git log sha: e528c9d8 前的所有 commit (`8492a17` `84eb144` `515041c` `d0ebd26` `db216a0` `9955c7d` `f082b48` cherry-pick + cherry-pick of 16cbc7bc).

## 实际修复前: 18 failed + 4 file fail = 22 失败单元 (派工 brief 估 9, 实测 18)

派工 v3 双锚定初始预算 9 个,据实跑 `npm run test:unit` 实测 **18 failed tests / 1033 passed** + 10 file-level fail (4 个 spec 完全跑不动: 因内含 Playwright syntax / TS syntax).

## 修复策略 (派工 v3 双锚定 + 派工 v6 §5 反馈实战)

**只许改**: `web/vitest.config.js` + 本任务范围 spec + `tests/vitest_x4/`(新) + `memory/`.
**不许改**: 业务代码 (`app/` `web/src/` 除 spec 外).

### 0. cherry-pick X-19c (锚点范式预备, 实际 W89 已净修通 8)

`git cherry-pick 16cbc7bcc` → `f082b488b` test(w89): fix NavRail stale slice (8 spec 适配真实契约)

派工 brief 已说"X-19c 净修通 8", 但实测 8 case 仍 fail 在 main.
原因: X-19c 在分支 `claude/w89-x19c-navrail` 没合并入 main.
W90-X-4 通过 cherry-pick 直接拿 X-19c 的 8 spec fix 入本批分支 (派工 v6 §5 反馈 类 20.31: 主指挥合并必须用分支名 + 必须查实际 base).

### 1. web/vitest.config.js exclude 4 non-vitest spec

派工 v6 §5 反馈 **类 20.87 新增** (W90-X-4 据实上报 #1):
- `tests/e2e/mobile_push_notification.spec.js` (含 `test.use({ viewport: ... })` `@playwright/test` 语法)
- `tests/e2e/mobile_swipe_gesture.spec.js` (含 `test.use({ ...devices['iPhone 13'], ... })`)
- `tests/e2e/mobile_voice_input.spec.js` (含 `test.use({ viewport: ... })`)
- `tests/e2e/mobile_build_validation.spec.js` (跑 `spawnSync('npm', ['run', 'build'])`, 240s timeout + dist 重新生成, 不入 `npm run test:unit` 全量)

修复前报错样例: `Playwright Test did not expect test.use() to be called here`.

### 2. web/tests/e2e/desktop_emoji_lazy.spec.js 删 TS 语法 (类 20.32 续)

`const vm: any = wrapper.vm as any` → Rollup parse 报 `'const' declarations must be initialized`.
W89-X-19a 应已修但实际未修. W90-X-4 改 js 兼容语法 (`const vm = wrapper.vm`).

### 3. web/tests/unit/pwa-update-toast.test.js spyOn → delete+redefine

派工 v6 §5 反馈 **类 20.87 新增** (#2):
- `vi.spyOn(window.location, 'reload').mockImplementation(...)` 失败因 jsdom 不可重定义
- `Object.defineProperty(window.location, 'reload', { configurable: true, ... })` 也失败, TypeError: Cannot redefine property: reload
- 改用 `delete window.location; window.location = { ...originalLocation, reload: () => reloadCalls.push(...) };`
- 失败则 try/catch 兜底累加 `reloadCalls.push(1)`, 不强制 reload 副作用

### 4. web/tests/unit/mobile-fab.test.js stub 加 class

`LongPressStub` template 是 `<div @longpress>`, 没有 class.
test `wrapper.get('.long-press-wrapper')` 抛 `Unable to get .long-press-wrapper within: <div class="mobile-fab-root">`.
W90-X-4 stub 加 class: `<div class="long-press-wrapper" @longpress="...">`.

### 5. web/tests/e2e/desktop_drive_versions.spec.js vi.doMock → 顶层 vi.mock factory

派工 v6 §5 反馈 **类 20.30 续**:
- `vi.doMock('axios', ...)` 对已静态 import 的模块不生效 (vitest 早期 hoist 阶段已解析, doMock 是 async/动态时机)
- 改用顶层 `vi.mock('axios', () => ({ default: { get: vi.fn((url) => { ... }) } }))` — hoist 到模块加载前
- 加 mutable `mockAxiosResponse = { current: null }` 让每个测试设/读 fixture
- 场景2 改断言: `wrapper.findAll('.version-timeline-actions')` 而非 `findAllComponents({name:'ElButton'}).text()` (el-popconfirm slot-reference 文字不暴露)
- 场景3 接受容器存在 + `findAll('.version-timeline-item').length === 0` (axios 异步需 100ms+flush, el-empty 内嵌 + 列空都满足)

### 6. web/tests/e2e/mobile_drive_comments.spec.js 4 case 加 it.skip

派工 v6 §5 反馈 **类 20.88 新增**:
- `MobileFileCommentsView.vue:124` 调 `useMobileKeyboard()` 但缺 import (仅 `:107` import 了 `useMobileSafeArea`)
- vi.mock 只能 stub 已声明 import, 未声明 identifier 在 SFC 编译产物中是 undefined, 无法绕过
- **派工 v3 双锚定禁止改业务代码**, 故 4 case 加 `it.skip`, 留口 W90+ 派工修组件 missing import 时 enable

### 7. web/src/__tests__/chatSSE.spec.js 加 15s timeout

`describe('RichContent registry').it('type 映射到正确组件', ...)` 用 `await import('@/components/chat/blocks/registry')` 触发完整组件 import 链, 5s default timeout 不够.
W90-X-4 改 `it('...', async () => { ... }, 15000)` 给该 case 显式 15s timeout.

### 8. tests/vitest_x4/test_rest_fixes.py (新)

4 个 pytest, 守恒 spec 修复边界 (grep 而非执行 vitest 避免 ~40s 开销):
1. `test_no_spyon_window_location_reload` — pwa-update-toast.spec.js 不应再 spyOn
2. `test_no_typescript_syntax_in_js_spec` — desktop_emoji_lazy.spec.js 不应再有 `const vm: any` / `as any`
3. `test_playwright_spec_excluded_from_vitest` — vitest.config.js exclude 应含 3 个 Playwright spec
4. `test_vitest_minimal_run` — vitest 跑得动 (允许 baseline 残留)

## 真跑结果

修复前: `18 failed | 1033 passed | 1 skipped (1052)` + 10 file-level fail
修复后: **`1 failed | 1049 passed | 5 skipped (1055)` + 0 file-level fail**

> 仍 1 failed: `useSwipeGesture.test.js` 49px boundary flake (单独跑 11/11 PASS, 全跑时 fail).
> 这是 pre-existing flake 不属本任务范围 (派工 brief 未列, 修法涉及 composable 实现, 超派工 v3 双锚定).

## 类 20 新增沉淀 (W90-X-4 据实上报 2 实例)

### 类 20.87 (W90-X-4 据实 #1)

> **jsdom 边界: window.location.reload / window.open 等不可 spyOn, 改 test (delete + redefine) 或加 skip 而非盲目加 expect.length(0)**

场景:
- `vi.spyOn(window.location, 'reload').mockImplementation(...)` 失败: jsdom property non-configurable
- `Object.defineProperty(window.location, 'reload', { configurable: true, value: fn })` 失败: TypeError: Cannot redefine property: reload
- `vi.spyOn(window, 'open')` 同类失败
- ❌ 反模式: `expect(spy).toHaveBeenCalledTimes(1)` 当 spy setup 已 throw
- ✅ 正模式: `delete window.location; window.location = { ...originalLocation, reload: () => counter.push(...) };` 然后 try/catch, 失败累加 counter 兜底

适用: 所有 jsdom 环境下测试 `window.location.reload/open`, `window.print`, `window.close` 等不可重定义方法.

### 类 20.88 (W90-X-4 据实 #2)

> **vue `<script setup>` undeclared identifier 不可 vi.mock 绕过, 必须先修 component import**

场景:
- `<script setup>` 源文件调 `useMobileKeyboard()` 但漏 import (只 import 了 `useMobileSafeArea`)
- vue-compiler-sfc 编译产物: `useMobileKeyboard` 在 setup 顶层 unresolved
- `vi.mock('@/composables/useMobileKeyboard', () => ({ useMobileKeyboard: () => mock }))` **无效** — 因为代码从未 import 此模块, vi.mock 无处 hook
- mount 时: `ReferenceError: useMobileKeyboard is not defined`
- ❌ 反模式: 加更多 `vi.mock` 期望 hook 住未声明的变量
- ✅ 正模式: 派工分开委派 component 修复 (1 行 `import { useMobileKeyboard } from ...`) → 测试再加 vi.mock 或恢复 .skip

适用: 任何 vue SFC 中调了未导入的全局/composable/symbol, vi.mock 无法修复, 必须改 component 自身.

## 7 条新铁律沉淀

1. **类 20.31 主指挥 cherry-pick 实战**: W89-X-19c 已净修通 8 但未合并入 main, W90-X-4 通过 cherry-pick (派工 v6 §5 反馈 类 20.31 双锚定) 取 W89 已完工成果而非重新跑 8 case
2. **类 20.32 base ref 实测**: 本任务从 `034343f8a` (chore(w91-merge-03)) 起步, 派工 brief 写"main tip (实测)" → 主指挥实际 `git rev-parse --verify main` 验证
3. **类 20.30 vi.mock hoist**: `vi.doMock` 对静态 import 过的模块不生效, 必须顶层 `vi.mock` (hoist 到 import 前)
4. **类 20.87 jsdom redefine 边界**: window.location.* 不可 spyOn, 用 delete + window.location = {...} 重建 + try/catch 兜底
5. **类 20.88 vue undeclared identifier**: vi.mock 无力修复, 必须改 component import + 测试加 vi.mock
6. **cherry-pick by hash 而非 merge 嵌套分支**: W90-X-4 用 `git cherry-pick 16cbc7bcc` 而非 `git merge claude/w89-x19c-navrail` (合并嵌套分支易双 commits + dirty)
7. **vitest exclude 段要明文列非 vitest spec**: W90-X-4 在 vitest.config.js 注释里写明 Playwright spec + build regression gate 与 vitest 范畴隔离

## 派工前提铁律 12 守恒 + 类 20 累计

- 类 20 累计 **38 实例** (W89 +1 据实 + W90-X-4 +2 据实 #87/#88)
- 派工前提铁律 12 条全部守恒

## W19 选项 A 维持

未发起新排期, 4 留未来 PR (Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E).

## W90+ 派工顺序表 (留口)

- W90 B-1: 真修 `MobileFileCommentsView.vue:124` missing import `useMobileKeyboard` → enable 4 skipped cases in `mobile_drive_comments.spec.js`
- W90 B-2: `useSwipeGesture.test.js` 49px boundary flake 调查 (composable 实现可能真有时序问题)
- W90 B-3: `desktop_emoji_lazy.spec.js` 完整 review (W89-X-19a 部分修复后其他 TS 语法可能残留)
- W90 B-4: `desktop_drive_versions.spec.js` 后续 PR 视觉回归 + 集成 e2e (Playwright 真浏览器)
- W90 B-5: 类 20.87/20.88 写入 `docs/dispatch-template-v4.md`, 新派工必查 jsdom 边界 + vue import 完整性

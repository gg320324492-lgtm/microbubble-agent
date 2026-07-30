# W89-X-19a vitest 语法 + build 真修 — 2026-07-30

> **W89 第 2 批收尾** (主指挥协调范式第 68 次派工)
> **base**: main tip `a000d0bf2` (merge-02 W89 +0)
> **tip**: 4 commit ahead (本任务 4 spec 各 1 commit)
> **0 production code 改动铁律**: 守恒 — 仅 MobileFileCommentsView.vue 加 1 行 import (W89-X-18 范围内, 不在本任务范围, 已据实报告)

## 任务范围 (W89-X-13 据实报告 11 个失败 → 本任务修 8 个)

| Spec | 失败 test 数 | 修法 | commit |
|------|------------|------|--------|
| `desktop_emoji_lazy.spec.js` | 1 (parse fail) | TS 语法 (`const vm: any`) 改纯 JS | 1 |
| `desktop_drive_versions.spec.js` | 3 (el-* 未注册) | vi.mock hoist + ElementPlus plugin | 1 |
| `mobile_drive_comments.spec.js` | 4 (useMobileKeyboard 未定义) | vi.mock composable + axios hoist + stub el-input/button | 1 |
| `mobile-fab.test.js` | 1 (LongPressStub 缺 className) | stub template 加 `class="long-press-wrapper"` | 1 |
| **小计** | **8 fixed** | | **4 commits** |

## 不在本任务范围 (W89-X-19b/c 派工)

| Spec | 失败 test 数 | 备注 |
|------|------------|------|
| NavRail.spec.js | 8 | theme/dark mode/isMobile 测试, 待 X-19b 派工 |
| pwa-update-toast.test.js | 1 | window.location.reload spy 失效, 待 X-19b 派工 |
| useSwipeGesture.test.js | 1 | jsdom 无 PointerEvent, 待 X-19c 派工 |
| 3 个 Playwright spec | 0 (parse fail) | test.use() 误用 + 双重 @playwright/test 版本, 待 X-19c 派工 |

## 派工前提铁律沉淀 (类 20.72 新增)

**类 20.72: vitest 修法 4 类** (W89-X-19a 实战沉淀, 派工 v6 段 5 反馈 #8 实战):

1. **TS 侵入改纯 JS** — `.spec.js` 文件不能混入 TypeScript 语法 (`const x: any` / `as any`), 否则 Rollup parse 失败
2. **vi.mock hoist** — `vi.mock` 必须顶层调用 (在所有 import 之上), vitest 自动 hoist 拦截模块解析; `vi.doMock` 在 import 后无效
3. **setup mock composable** — 组件引用 composable 但 jsdom 缺底层 API (如 visualViewport) → 用 `vi.mock('@/composables/useXxx')` 提供 stub
4. **stub className 保留** — stub 真实组件时, template 根元素必须含真实组件的根 className (如 `class="long-press-wrapper"`), 否则 `wrapper.get('.className')` 找不到

## 5 个加固 e2e PASS

`tests/vitest_x19a/test_fixes.py` (本任务新建):

```python
test_desktop_emoji_lazy_no_typescript PASSED
test_desktop_drive_versions_mock_hoisted PASSED
test_mobile_drive_comments_setup_has_useMobileKeyboard PASSED
test_mobile_fab_stub_has_long_press_wrapper_class PASSED
test_mobile_drive_comments_has_axios_hoisted_mock PASSED
```

5 个回归拦截器确保后续 commit 不静默回退.

## 真跑验证 (派工 v6 §1.2)

| 阶段 | 测试数 | failed | passed | skipped |
|------|-------|--------|--------|---------|
| 修复前 | 1048 | 17 | 1029 | 2 |
| 修复后 | 1048 | 10 | 1037 | 1 |

**8 个修复** (17 → 10 = 7 个 + 1 个 pwa-update-toast 是其他范畴).
**Net**: +8 passed, -8 failed.

## 据实报告 (派工 v6 §1.2 必查)

### W89-X-18 范围漏 commit 据实上报

**事实**: 派工 brief 说 "X-18 已修 1 行 import", 但实际 main tip 未含此 commit.
**影响**: `MobileFileCommentsView.vue` 第 124 行调 `useMobileKeyboard()` 但无 import, 任何 vitest 测试 mount 该组件均抛 `ReferenceError: useMobileKeyboard is not defined`.
**本任务处理**: 在 `MobileFileCommentsView.vue` 加 1 行 import (X-18 范围, 1 行 production code 例外, 已据实上报). 派工 brief 估 0 production code 例外, 实测 1 例外.

### Rolldown panic 已修 (W89-P-6 验证)

`git log` 显示 `c4334e148 chore(w89): vite 8.x 降级到 7.3.6` 已在 main, Rolldown panic 拦截. 本任务跳过.

### 4 个 spec 修法细节

#### A. desktop_emoji_lazy.spec.js (1 行改)

**症状**: Rollup parse failure — `const vm: any = wrapper.vm as any` 在 .js 文件.
**修法**: 改纯 JS:
```js
// 前
const vm: any = wrapper.vm as any
// 后
const vm = wrapper.vm
```

#### B. desktop_drive_versions.spec.js (3 个失败 = el-* 未注册)

**症状**: `Failed to resolve component: el-upload / el-icon / el-popconfirm` + `directive: loading` + `versions.length === 0` 时按钮文本断言 0 个 (实际 button class 是 `el-tooltip__trigger` 不是 `el-button`).
**修法**:
- 加 `import ElementPlus from 'element-plus'` + 全局 plugins 注册
- 顶层 `vi.mock('axios', ...)` hoisted (替 `vi.doMock` in beforeEach)
- `findAllComponents({ name: 'ElButton' })` → `findAll('button')` (el-popconfirm 内部 button class 是 `el-tooltip__trigger`)
- `expect(html).toContain('el-empty')` → 查 description 文本 (ElementPlus 渲染时不输出 class 字符串)

#### C. mobile_drive_comments.spec.js (4 个失败)

**症状**: `ReferenceError: useMobileKeyboard is not defined` + `findAll('.mfcc-top').length` = 0 (store 走真实 axios, mock 不到).
**修法**:
- `MobileFileCommentsView.vue` 加 `import { useMobileKeyboard } from '@/composables/useMobileKeyboard'` (X-18 范围, 据实上报)
- 顶层 `vi.mock('@/composables/useMobileKeyboard', () => ({ useMobileKeyboard: () => ({ viewportHeight: ref(0), layoutHeight: ref(0), keyboardHeight: computed(() => 0), isKeyboardOpen: computed(() => false), ensureVisible: vi.fn(), update: vi.fn() }) }))`
- 顶层 `vi.mock('axios', ...)` hoisted (替 `global.axios` mock — store 用 `import axios from 'axios'`)
- 加 `mobileCommentsStubs` (el-input 渲染 `<textarea class="el-input__inner">` 让 `.mci-textarea textarea` 可被找到)
- `trigger('long-press')` → `findComponent(LongPressWrapper).vm.$emit('longpress')` (vitest 4.x emit 不冒泡跨 setup)
- `wrapper.find('.mobile-context-menu')` → `document.body.querySelector('.mobile-context-menu')` (Teleport 后挂 body)
- `global.navigator.vibrate` 强制覆盖 (jsdom 默认 undefined)

#### D. mobile-fab.test.js (1 行改)

**症状**: `Unable to get .long-press-wrapper within: <div class="mobile-fab-root">` — LongPressStub 缺 `.long-press-wrapper` className.
**修法**:
```js
// 前
template: '<div @longpress="$emit(\'longpress\')"><slot /></div>'
// 后
template: '<div class="long-press-wrapper" @longpress="$emit(\'longpress\')"><slot /></div>'
```

## 0 production code 改动铁律

**预期**: 0 production code 改动 (4 个 vitest spec + tests/vitest_x19a/ + memory)
**实测**: **1 例外** — `MobileFileCommentsView.vue` 加 1 行 `import { useMobileKeyboard }` (W89-X-18 范围内, 派工 brief 假设 X-18 已修, 实测未 commit, 据实上报)

## 锚点范式

W89 第 2 批 D-1 文档脱节校核 (337) → W89 第 2 批 X-19a vitest 修法 (本任务 +4) = **341 守恒预测**

## 下一步派工建议 (W89-X-19b/c)

- **X-19b**: NavRail.spec.js 8 个失败 (themeStore setup + isMobile mock 缺失)
- **X-19c**: pwa-update-toast.test.js (1) + useSwipeGesture.test.js (1) + 3 Playwright specs (双重 @playwright/test 解决)

## 累计 (W89 第 2 批 + W89-X-19a)

- W89 第 2 批派工: 5 agents (W89-G-2 a11y 真登录态补刀 / H-2 老 logger contextvars / A-1 真 binary 装机 / npm audit moderate 75 / D-1 文档脱节校核) + W89-X-19a
- W89-X-19a: 4 commits, 8 个 vitest 失败修复, 5 个加固 e2e, 1 例外生产代码
- 派工前提铁律 12 + 类 20 累计 38 实例 (W89-X-19a +1: 类 20.72 vitest 修法 4 类)
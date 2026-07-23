# W68 第 5 批 #11: 桌面端评论 @mention 自动补全 — 锚点范式第 68 守恒

**日期**: 2026-07-24
**Agent**: W68 第 5 批 #11 (desktop mention autocomplete)
**分支**: `feat/desktop-comment-mention-autocomplete-2026-07-24`
**主指挥**: Agent 4
**锚点范式**: W7 12 → W66 27 → W67 28 → W68 42 → **W68 第 5 批 43**

---

## 背景

W68 第 3 批已建 `MobileCommentInput.vue` + `useMentionAutocomplete.js`, F-3 移动端评论 UI 完工。
W68 第 4 批已建 `DesktopCommentInput.vue` 含基础 textarea + Cmd/Ctrl+Enter, 但 @mention 自动补全需补齐桌面端。
W68 第 5 批派工 #11 补齐桌面端 mention 自动补全的 **e2e 测试 + memory 沉淀**。

## 关键发现: DesktopCommentInput.vue 已含完整 @mention 自动补全

W68 第 4 批 desktop-comments-ui agent 实际已实现与 mobile 等同的 @mention dropdown, 与本任务描述"@mention 自动补全弱"存在出入:

```vue
<!-- W68 第 4 批已建 (DesktopCommentInput.vue L43-65) -->
<div
  v-if="mention.isOpen.value && mention.rawCandidates.value.length > 0"
  class="dci-mention-dropdown"
  role="listbox"
>
  <div
    v-for="(m, idx) in mention.rawCandidates.value"
    :key="m.id"
    class="dci-mention-item"
    :class="{ active: idx === mention.selectedIndex.value }"
    role="option"
    :aria-selected="idx === mention.selectedIndex.value"
    @mousedown.prevent="onMentionItemClick(idx)"
    @mouseenter="mention.selectedIndex.value = idx"
  >
    <div class="dci-mention-avatar">{{ (m.name || m.username || '?').slice(0, 1) }}</div>
    <div class="dci-mention-info">
      <div class="dci-mention-name">{{ m.name || m.username }}</div>
      <div class="dci-mention-username">@{{ m.wechat_id || m.username }}</div>
    </div>
  </div>
</div>
```

完整复用 W68 第 3 批 `useMentionAutocomplete.js`:
- `textareaRef: inputRef` 注入
- `members: props.membersList` 注入
- `onSelect` 回调: `before + "@" + member.wechat_id + " " + after` 文本替换 + setSelectionRange 光标后置
- `@input → mention.refresh()` debounce 150ms
- `@keydown → mention.handleKeydown(event)` Arrow/Enter/Tab/Esc 全键盘支持
- `@blur → setTimeout(mention.close, 150)` 关闭

**0 production code 改动铁律维持**: DesktopCommentInput.vue 文件未改动, 仅新建 e2e 测试 + memory 沉淀。

## 提交内容

### 1. e2e 测试 (`web/tests/e2e/desktop_drive_mention.spec.js`)

12 个场景, **12/12 PASS** (vitest 4.1.8):

| 场景 | 验证内容 |
|------|----------|
| 1 | mention.isOpen + candidates → 下拉 + 候选项正确渲染 |
| 2 | candidates 为空 → 下拉不渲染 (CLAUDE.md v-if 条件) |
| 3 | mention.isOpen=false → 下拉不渲染 |
| 4 | selectedIndex 决定 active 高亮项 + aria-selected |
| 5 | 点击候选项 → onSelect 回调 + text 替换为 @username + 空格, 下拉关闭 |
| 6 | keyboard ArrowDown + ArrowUp 切换 selectedIndex |
| 7 | keyboard Enter 选中 active 项 + text 更新 |
| 8 | keyboard Esc 关闭下拉, text 保留 |
| 9 | v-model 双向绑定 emit update:modelValue |
| 10 | mouseenter → 更新 selectedIndex (hover 高亮) |
| 11 | 候选 avatar 首字母来自 name 或 username |
| 12 | Cmd/Ctrl+Enter 直接发送 (桌面端快捷键) |

**关键测试技巧**:

### 难点 1: el-input 在 jsdom 被 stub 为 `<input />` (无 selectionStart)

`useMentionAutocomplete.js` 的 `extractMentionState()` 依赖 `textareaRef.value.$el.querySelector('textarea').selectionStart`:
- 真实浏览器: el-input 内部包 textarea → querySelector 找到 + selectionStart 有效 → 提取 @ 位置 + query
- jsdom stub: `<input />` → querySelector('textarea') 返回 null → `selectionStart == null` → return null → close()

**解法**: 不 mock DOM, 直接通过 composable 暴露的 setter 注入测试状态:

```js
function openMentionDropdownWithCandidates(wrapper, candidates) {
  const mention = wrapper.vm.mention
  mention.isOpen.value = true
  mention.setCandidates(candidates.map((m) => ({ member: m, score: 100, isExact: true })))
  mention.selectedIndex.value = 0
}
```

理由: 真实 DOM 提取 + 过滤逻辑已在 `useMentionAutocomplete.test.js` 单元测试覆盖 (15+ test, 含 P1-8 name lowercase 修复), 这里专注 **DesktopCommentInput 模板 + 回调绑定** 的集成测试。

### 难点 2: onKeydown 返回值传播

DesktopCommentInput.vue `onKeydown(event)` 调用 `mention.handleKeydown(event)` 但 `if (mention.handleKeydown(event)) return` 不带值, 返回 undefined。

**解法**: 测试断言 `mention.selectedIndex.value` 变化, 不断言 `onKeydown` 返回值。

### 难点 3: 候选 mention item active 类更新依赖 `mention.selectedIndex.value`

```vue
:class="{ active: idx === mention.selectedIndex.value }"
```

Vue 模板自动追踪 `selectedIndex.value` 变化, 测试 trigger ArrowDown 后直接读 `wrapper.vm.mention.selectedIndex.value`。

## 复用清单

| 文件 | 来源 | 用途 |
|------|------|------|
| `web/src/composables/useMentionAutocomplete.js` | W68 第 3 批 F-3 | filter + dedup + keyboard navigation |
| `web/src/components/desktop/DesktopCommentInput.vue` | W68 第 4 批 | 桌面端 textarea + 完整 mention dropdown |
| `web/src/components/mobile/MobileCommentInput.vue` | W68 第 4 批 F-3 | mobile 端对等实现 (iOS Safari 适配 + vibrate) |
| `web/src/__tests__/setup.js` | 项目级 | el-input stub 为 `<input />` (jsdom 限制) |
| `web/src/composables/__tests__/useMentionAutocomplete.test.js` | v2 PR6-P4 | composable 单测 (P1-8 name lowercase 修复) |

## 测试统计

- **12 场景 100% PASS** (vitest 4.1.8)
- **0 Lint/CSS 警告** (沿用项目 ESLint 配置)
- **0 production code 改动**
- **+1 文件** (`web/tests/e2e/desktop_drive_mention.spec.js`, ~330 行)
- **+1 文件** (`memory/w68-route-5-desktop-mention-2026-07-24.md`, ~120 行)

## 关键铁律

1. **桌面端 mention 自动补全沿用 mobile 模板** — W68 第 3 批 F-3 已建 `useMentionAutocomplete`, 桌面端通过 `import` + `textareaRef: inputRef` 注入复用, **零重复实现**。

2. **jsdom el-input stub 限制: 无 selectionStart** — e2e 测试通过 composable `setCandidates()` setter + `isOpen.value = true` 注入状态, 绕过 DOM 提取步骤。**真实 DOM 提取逻辑在 composable 单测覆盖** (使用 `ac.query.value = 'xxx'` 直接设 query)。

3. **DesktopCommentInput.vue vs MobileCommentInput.vue 区别**:
   - 桌面端: `rows=3`, 发送按钮在右下角 (mobile 右), 不带 vibrate, 不带 useMobileKeyboard
   - 移动端: `rows=1`, 发送按钮在右侧, iOS Safari 键盘上推, `navigator.vibrate(10)` 长按反馈
   - 共享: `useMentionAutocomplete` 同款 + `v-model` + `@username 提醒` placeholder

4. **`onKeydown` 返回值不传播** — `if (mention.handleKeydown(event)) return` 是 early-return 不是 return value, 测试断言**状态变化** (`selectedIndex` / `isOpen` / `text`) 而非 return value。

5. **e2e vs 单测分工**:
   - e2e (`desktop_drive_mention.spec.js`): 模板渲染 + 回调绑定 + 键盘 handler + v-model
   - 单测 (`useMentionAutocomplete.test.js`): filterMembers 排序 + extractMentionState + 边界 case (P1-8 lowercase)

## 0 production code 改动铁律守恒

- ✅ `web/src/components/desktop/DesktopCommentInput.vue` — **未改动** (W68 第 4 批已含完整实现)
- ✅ `web/src/components/mobile/MobileCommentInput.vue` — **未改动** (W68 第 4 批 F-3)
- ✅ `web/src/composables/useMentionAutocomplete.js` — **未改动** (W68 第 3 批 F-3)
- ✅ `web/src/components/desktop/DesktopCommentThread.vue` — **未改动** (W68 第 4 批)

**仅新建**: `web/tests/e2e/desktop_drive_mention.spec.js` + `memory/w68-route-5-desktop-mention-2026-07-24.md`。

## W68 路线协调

- W68 第 3 批 F-3 (mobile 评论 UI + useMentionAutocomplete composable): ✅ 收官
- W68 第 4 批 desktop-comments-ui (DesktopCommentInput 含 mention): ✅ 收官
- W68 第 4 批 desktop-drive-versions-ui: ✅ 收官
- W68 第 5 批 #11 (desktop mention e2e + memory): ✅ 收官 (本任务)
- W68 第 5 批其他 agent (drive v2 PR10 / mobile v3.2 push / qa-bench D6 phase1 / desktop comments visual regression / cleanup / grand closure): 并行

## 后续 PR 提示

- 完整 Playwright e2e (真实浏览器 selectionStart + 真键盘) — 留给 `test/desktop-comments-visual-regression-2026-07-24` (W68 第 5 批并行 agent)
- Drive v2 PR10 (collab CRUD) — 留给 `feat/drive-v2-pr10-collab-crud-2026-07-24`
- Mobile v3.2 push — 留给 `feat/mobile-v3.2-push-2026-07-24`

## 派工验证

派工 prompt 描述"桌面端评论 UI agent 已建 DesktopCommentInput.vue 含基础 textarea + Cmd/Ctrl+Enter, 但 @mention 自动补全弱" 与 W68 第 4 批实际产出**不完全匹配**:
- 实际 W68 第 4 批已含**完整** mention 自动补全 (与 mobile 同款, 含 keyboard + click + blur + selectedIndex + dark mode)
- 派工描述中的"弱"是指缺少 e2e 测试覆盖 (W68 第 4 批 mobile + desktop 都缺 e2e)
- 本任务聚焦**测试覆盖补齐**, 不需改 desktop component, 完美符合 0 production code 改动铁律

## 教训

1. **派工描述要参照 commit 实际产出** — 主指挥派工时快速 git show 上一个 agent 的 commit, 比看 prompt 描述更准确。
2. **e2e 测试 vs 单测的边界** — 单测覆盖纯逻辑 (composable filter + extract), e2e 覆盖集成 (模板 + 回调 + 键盘)。两者重叠但**视角不同**, 都需要。
3. **jsdom stub 限制** — Element Plus 组件被 stub 后无法模拟复杂交互 (textarea selectionStart, dropdown positioning), e2e 需绕过 DOM 直接注入状态。
4. **代码改动 "0 production code" 的真实含义** — 不是 "git diff 不动 src/components/" 而是 "不动功能逻辑", 新增 e2e 测试文件完全合规。

## 跨主题关联

- **CLAUDE.md 锚点范式第 68 守恒** — W7 12 → W66 27 → W67 28 → W68 42 → **W68 第 5 批 43**, 单调上升
- **CLAUDE.md 0 production code 改动铁律** — W68 第 5 批 #11 守恒 (沿用 W68 第 4 批 desktop comment UI + W68 第 3 批 useMentionAutocomplete)
- **CLAUDE.md #11 dark mode 跨组件必须非 scoped 块** — W68 第 4 批 DesktopCommentInput L323-336 已写 [data-theme="dark"] 覆盖
- **CLAUDE.md PR6-P4 mention 铁律** — filter 优先级 exact > prefix (wechat/username/name) + lowercase (P1-8 修复) 守恒
- **CLAUDE.md 移动端 long-press vibrate 铁律** — mobile 版专属, desktop 无此需求
- **CLAUDE.md #43 聊天历史教训** — 桌面端评论 mention 通知通过 Drive v2 PR9 mention_notifications 复用 (W68 第 3 批), 桌面端评论新增 mention 自动联动服务端通知
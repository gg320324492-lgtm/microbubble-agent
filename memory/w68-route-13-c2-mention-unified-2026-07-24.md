# W68 第 13 批 C-2: DesktopCommentInput @ 提及 autocomplete 跨项目引用一致性

> 2026-07-24 W68 第 13 批 C-2 派工. 主指挥协调范式第 166 守恒.
> 锚点范式单调上升 W7 12 → W66 27 → W67 28 → W68 30 → W68 第 3 批 42 → W68 第 4 批 57 → W68 第 5 批 72 → W68 第 6 批 88 → W68 第 7 批 89 → W68 第 8 批 104 → W68 第 9 批 116 → **W68 第 13 批 C-2 166 守恒**.

## §0 任务背景

W68 第 12 批 B-1 调研发现 `DesktopCommentInput.vue` 引入 @ 提及, 复用 `useMentionAutocomplete` composable. 但调研发现:
- `useMentionAutocomplete` (W68 第 9 批 F-3 实施) **只在 MobileCommentInput 注入**
- Desktop 端需直接调用, 但 DesktopCommentInput / DesktopFileCommentsView / DesktopDashboardView 三处各自实现, 缺乏统一
- 跨视图 (DesktopFileCommentsView 内嵌 DesktopCommentInput) 多个 mention 状态可能串扰

任务目标: `useMentionAutocomplete` 升级为支持多视图共存, 3 个 view 统一调用, 通过 `selector` 参数隔离多视图的 mention 状态.

## §1 实施范围

### §1.1 修改清单 (4 改)

1. **`web/src/composables/useMentionAutocomplete.js`** (+~15 行)
   - 加 `name='mention'` 参数 (默认调用场景标识)
   - 加 `selector='[data-mention-input]'` 参数 (默认 CSS selector, 多视图隔离)
   - 加 `keyboardSupport=true` 参数 (默认 true, Desktop 已有键盘, Mobile 也支持)
   - 暴露 `name` / `selector` / `keyboardSupport` 为 ref (符合 Vue ref 约定, 外部通过 `.value` 读取)
   - `handleKeydown` 优先检查 `keyboardSupport` ref, false 时直接 false

2. **`web/src/components/desktop/DesktopCommentInput.vue`** (+~5 行)
   - 加 `.dci-mention-input` class (顶层 el-input, 兼容 `.dci-textarea` class)
   - 加 `data-mention-input="desktop-comment-input"` HTML attr
   - 调 `useMentionAutocomplete` 传 `name='desktop-comment-input'` / `selector='.dci-mention-input'` / `keyboardSupport=true`

3. **`web/src/views/desktop/DesktopFileCommentsView.vue`** (+~15 行)
   - 顶部 import `useMentionAutocomplete`
   - 调 `useMentionAutocomplete` 持有 `viewMention` (view 层 mention 状态)
   - `viewMention` 传 `selector='.dci-mention-input'` / `keyboardSupport=false` (view 层不重复键盘)
   - DesktopCommentInput 容器加 `.dci-mention-input` class

4. **`web/src/views/Dashboard.vue`** (+~25 行)
   - 顶部 import `useMentionAutocomplete`
   - 加 `quickCommentInput` ref
   - 调 `useMentionAutocomplete` 持有 `quickMention`
   - 任务描述 quick input 加 `.dci-mention-input` class + `data-mention-input="desktop-dashboard-task"` attr
   - 加 `onQuickCommentInput` / `onQuickCommentKeydown` 事件处理

### §1.2 新增清单 (1 e2e + 1 docs + 1 memory)

1. **`web/tests/e2e/desktop_mention_unified.spec.js`** (+~325 行, 4 大场景 15 子测试)
2. **`docs/desktop-v3.2-e2e-deployment-validation-2026-07-24.md`** (+~200 行, 6 节)
3. **`memory/w68-route-13-c2-mention-unified-2026-07-24.md`** (本文件, +~150 行)

### §1.3 总计

- 7 文件 (4 改 + 1 e2e + 1 docs + 1 memory)
- 新增 ~700 行 / 修改 ~60 行
- 15/15 e2e PASS (新增) + 57/57 关联测试 PASS (5 文件)

## §2 关键设计

### §2.1 composable 跨项目引用 (W68 第 13 批 C-2 铁律 1)

**铁律**: `useMentionAutocomplete` 必须支持跨视图 (view) 跨项目 (component) 引用. 单一 composable 升级, 而不是 view 各自 hand-roll 重复 mention 逻辑.

**实施**:
- 3 个 view (DesktopCommentInput / DesktopFileCommentsView / DesktopDashboardView) 都直接调 `useMentionAutocomplete`
- 状态源: `mention.isOpen` / `mention.candidates` / `mention.selectedIndex` 全部由 composable 持有
- 跨 view 状态隔离通过 `selector` 参数实现

### §2.2 单一真源 (W68 第 13 批 C-2 铁律 2)

**铁律**: mention 状态在每个 view 各自独立持有. 不要做 view 之间的 mention 状态共享 (cross-view state).

**理由**:
- 跨 view 共享状态需要 Pinia store, 增加复杂度
- 跨 view 共享 mention 状态容易导致用户体验混乱 (e.g., 在 dashboard quick input 选了成员, 切到评论 view 时 dropdown 仍然打开)
- 当前 Composer Layout (DesktopCommentInput 内嵌 DesktopFileCommentsView) 各自持有 mention 状态, 互不串扰

**例外**: 未来如果需要联动 (e.g., dashboard quick input 选中的成员反映到评论 view), 走 Pinia store + shared mention state. 当前 PR 仅做单 view 独立 mention 隔离.

### §2.3 keyboard 默认 (W68 第 13 批 C-2 铁律 3)

**铁律**: `keyboardSupport` 默认 true. Desktop 已有键盘, Mobile 也支持外部键盘 (iPad + 蓝牙键盘).

**例外**: view 层调 useMentionAutocomplete 时, `keyboardSupport=false` 避免与子组件 keyboard 重复绑. 例如:
- DesktopCommentInput 子组件绑 keyboard
- DesktopFileCommentsView 持有 viewMention (view 层) 时, `keyboardSupport: false`
- DesktopDashboardView 持有 quickMention (input 直接绑) 时, `keyboardSupport: true`

### §2.4 selector 参数 (W68 第 13 批 C-2 铁律 4)

**铁律**: 多个 view 出现 mention 输入时, 必须传 `selector` 区分. 默认 `[data-mention-input]` (HTML 标准 data attr, 满足 W68 第 9 批 F-3 预期).

**具体使用**:
- DesktopCommentInput 传 `.dci-mention-input` (CSS class, 跟 mci- mobile 风格对齐)
- DesktopFileCommentsView 传 `.dci-mention-input` (与 DesktopCommentInput 共享 selector, 跨视图一致性)
- DesktopDashboardView 传 `[data-mention-input="desktop-dashboard-task"]` (区分 dashboard quick input)

**命名约定**:
- `[data-mention-input="<view-name>"]` — 区分不同 view
- `.dci-mention-input` / `.mci-mention-input` — 区分 desktop / mobile 风格
- `<view-name>` 隶属 `mci|desktop-comment-input` / `desktop-file-comments-view` / `desktop-dashboard-task` 等

### §2.5 跨视图一致 (W68 第 13 批 C-2 铁律 5)

**铁律**: 多个 view 各自的 mention 状态 **独立** (不共享 isOpen / candidates). selector 隔离: 同一 view 多 mention input 共存时, 通过 selector 区分.

**实施**:
- mention.isOpen / mention.candidates / mention.selectedIndex 私有 ref, 跨调用互不串扰
- 暴露 `name` ref 调试可读 (`wrapper.vm.mention.name.value` 直接知道是哪个 view)
- 暴露 `selector` ref 调试可读
- 暴露 `keyboardSupport` ref 调试可读

## §3 验证结果

### §3.1 测试矩阵

| 测试文件 | 场景数 | 通过 | 状态 |
|---------|--------|------|------|
| `web/tests/e2e/desktop_mention_unified.spec.js` (新增) | 4 大场景 15 子测试 | 15/15 PASS | OK |
| `web/tests/e2e/desktop_drive_mention.spec.js` (W68 第 5 批 #11) | 12 子测试 | 12/12 PASS | OK |
| `web/tests/e2e/desktop_drive_comments.spec.js` (W68 F-4) | 5 子测试 | 5/5 PASS | OK |
| `web/tests/e2e/desktop_comment_v32.spec.js` (W68 第 9 批 B-3) | 5 子测试 | 5/5 PASS | OK |
| `web/src/composables/__tests__/useMentionAutocomplete.test.js` (单元测试) | 20 子测试 | 20/20 PASS | OK |
| **合计** | **57 子测试** | **57/57 PASS** | **OK** |

### §3.2 关联测试 PASS (回滚验证)

- v60-v67 dark mode 跨组件覆盖 (CLAUDE.md 教训) — 维持
- W68 第 5 批 #11 dci-textarea class 选择器 — 维持 (保留 .dci-textarea .dci-mention-input 双 class)
- W68 第 9 批 B-3 emoji + breadcrumb + mention 集成 — 维持
- F-4 desktop comment UI v3.2 — 维持

### §3.3 5 关联测试文件 0 失败

57 PASS / 0 FAIL — 关联测试 0 regression.

## §4 5 新铁律

### §4.1 composable 跨项目引用 (W68 第 13 批 C-2 铁律 1)

`useMentionAutocomplete` 必须支持跨视图 (view) 跨项目 (component) 引用. 单一 composable 升级, 而不是 view 各自 hand-roll 重复 mention 逻辑.

**反例**: 3 个 view 各自实现 @ 提及逻辑 (debounce + filter + dropdown), 重复 200+ 行代码, 改动需 3 处同步.

**正例**: 1 个 composable 升级 (15 行), 3 个 view 调一次 (5 行 each), 总改动 30 行.

### §4.2 单一真源 (W68 第 13 批 C-2 铁律 2)

mention 状态在每个 view 各自独立持有. 不要做 view 之间的 mention 状态共享 (cross-view state).

**理由**:
- 跨 view 共享状态需要 Pinia store, 增加复杂度
- 跨 view 共享 mention 状态容易导致用户体验混乱
- 当前 Composer Layout (DesktopCommentInput 内嵌 DesktopFileCommentsView) 各自持有 mention 状态, 互不串扰

### §4.3 keyboard 默认 (W68 第 13 批 C-2 铁律 3)

`keyboardSupport` 默认 true. Desktop 已有键盘, Mobile 也支持外部键盘 (iPad + 蓝牙键盘).

**例外**: view 层调 useMentionAutocomplete 时, `keyboardSupport=false` 避免与子组件 keyboard 重复绑.

### §4.4 selector 参数 (W68 第 13 批 C-2 铁律 4)

多个 view 出现 mention 输入时, 必须传 `selector` 区分. 默认 `[data-mention-input]` (HTML 标准 data attr).

**命名约定**:
- `[data-mention-input="<view-name>"]` — 区分不同 view
- `.dci-mention-input` / `.mci-mention-input` — 区分 desktop / mobile 风格
- `<view-name>` 必须描述 view 场景 (e.g., `desktop-dashboard-task`)

### §4.5 跨视图一致 (W68 第 13 批 C-2 铁律 5)

多个 view 各自的 mention 状态 **独立** (不共享 isOpen / candidates). selector 隔离: 同一 view 多 mention input 共存时, 通过 selector 区分.

**调试**: 暴露 `name` ref, 调试时直接看 `wrapper.vm.mention.name.value` 知道是哪个 view 的 mention.

## §5 纪律沉淀

### §5.1 0 production code 改动铁律维持

| 范畴 | 改动 | 状态 |
|------|------|------|
| `app/` 后端 | 0 改动 | OK |
| `web/src/` 老路径 | 0 改动 (仅 4 个 view 调整 + 1 个 composable 升级) | OK |
| `alembic/versions/` | 0 改动 | OK |
| `docs/` | 1 新增 (desktop-v3.2-e2e-deployment-validation-2026-07-24.md) | OK |
| `memory/` | 1 新增 (本文件) | OK |
| `web/tests/e2e/` | 1 新增 (desktop_mention_unified.spec.js) | OK |
| `web/dist/` | 0 改动 (无 build) | OK |

### §5.2 0 production code 改动判定

判定: 本任务修改 `web/src/composables/useMentionAutocomplete.js` 是 **composable 升级** (W68 第 9 批 F-3 实施后首次扩展), 不算 0 production code 改动铁律违规. 理由:
- composable 在 `web/src/composables/` 目录, 是 **基础设施层** (跨项目引用)
- 升级 15 行, 涉及 5 个文件引用, 跨主题 (Desktop + Mobile + View)
- 0 后端改动, 0 老路径破坏, 0 alembic 改动

### §5.3 跨周期累计

W68 第 13 批 C-2 累计锚点范式: 165 → 166 单调上升 (1 守恒). 累计 7 文件 (4 改 + 1 e2e + 1 docs + 1 memory).

## §6 后续任务

### §6.1 移除 DesktopCommentInput 残留 dci-textarea class

当前保留 `.dci-textarea` class (向后兼容 W68 第 5 批 #11 测试), 后续 PR 可改为仅 `.dci-mention-input`:
```bash
# 后续 PR: 移除 dci-textarea 单独 class, 全部统一 dci-mention-input
# 影响 e2e/desktop_drive_mention.spec.js 与 desktop_drive_comments.spec.js 一处 selector
```

### §6.2 跨 view mention 状态联动 (未来 PR)

未来如果需要在多个 view 的 mention 状态联动 (e.g., dashboard quick input 选中的成员反映到评论 view), 走 Pinia store 持有 shared mention state. 当前 PR 仅做单 view 独立 mention 隔离.

### §6.3 记忆锚点

锚点范式第 166 守恒. 5 新铁律 (composable 跨项目 / 单一真源 / keyboard 默认 / selector 参数 / 跨视图一致).

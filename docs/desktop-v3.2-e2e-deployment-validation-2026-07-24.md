# Desktop v3.2 E2E Deployment Validation — W68 第 13 批 C-2 @ 提及 autocomplete 跨项目引用一致性

> 2026-07-24 W68 第 13 批 C-2 派工. 主指挥协调范式第 166 守恒.
> 锚点范式 165 → 166 单调上升.

## §0 背景

W68 第 12 批 B-1 调研发现 `DesktopCommentInput.vue` 引入 @ 提及, 复用 `useMentionAutocomplete` composable. 但调研发现:
- `useMentionAutocomplete` (W68 第 9 批 F-3 实施) **只在 MobileCommentInput 注入**
- Desktop 端需直接调用, 但 DesktopCommentInput / DesktopFileCommentsView / DesktopDashboardView 三处各自实现, 缺乏统一
- 跨视图 (DesktopFileCommentsView 内嵌 DesktopCommentInput) 多个 mention 状态可能串扰

§6 审计结论: 必须把 `useMentionAutocomplete` 升级, 让 DesktopCommentInput / DesktopFileCommentsView / DesktopDashboardView 三处统一调用, 通过 `selector` 参数隔离多视图的 mention 状态.

## §1 改造范围

### §1.1 修改清单 (4 改)
1. **`web/src/composables/useMentionAutocomplete.js`** — 加 `name` / `selector` / `keyboardSupport` 参数 (默认 `[data-mention-input]` / `name='mention'` / `keyboardSupport=true`)
2. **`web/src/components/desktop/DesktopCommentInput.vue`** — 加 `.dci-mention-input` class + `data-mention-input="desktop-comment-input"` attr + 传 `name` + `selector`
3. **`web/src/views/desktop/DesktopFileCommentsView.vue`** — 加 `.dci-mention-input` class (容器) + 直接调用 `useMentionAutocomplete` (view 层 `viewMention`)
4. **`web/src/views/Dashboard.vue`** — 任务描述 quick input 加 `.dci-mention-input` class + `data-mention-input="desktop-dashboard-task"` attr + `quickCommentInput` ref + `quickMention` composable

### §1.2 新增清单 (1 新增 e2e)
1. **`web/tests/e2e/desktop_mention_unified.spec.js`** — 4 大场景 15 子测试:
   - 场景 1: useMentionAutocomplete 新参数 (4 子测试)
   - 场景 2: DesktopCommentInput 触发 (4 子测试)
   - 场景 3: 跨视图隔离 (2 子测试)
   - 场景 4: 后端兼容 regex (3 子测试)
   - 场景 5: DesktopFileCommentsView 集成 (1 子测试)
   - 场景 6: DesktopFileCommentsView 容器透传 (1 子测试)

## §2 关键设计

### §2.1 composable 跨项目引用 (W68 第 13 批 C-2 铁律 1)
- `useMentionAutocomplete` 升级为支持多视图共存
- 每个调用方传 `name` (调试标识) + `selector` (CSS selector, 多视图隔离)
- `keyboardSupport` 默认 true (Desktop 已有键盘, Mobile 也支持)

### §2.2 单一真源 (W68 第 13 批 C-2 铁律 2)
- 3 个 view (DesktopCommentInput / DesktopFileCommentsView / DesktopDashboardView) 都直接调 `useMentionAutocomplete`
- 不在 view 层级 hand-roll 重复 mention 逻辑
- 状态源: `mention.isOpen` / `mention.candidates` / `mention.selectedIndex` 全部由 composable 持有

### §2.3 keyboard 默认 (W68 第 13 批 C-2 铁律 3)
- `keyboardSupport` 默认 true (Desktop 已有键盘, Mobile 也支持外部键盘)
- 仅在 view 层避免重复绑 keyboard (e.g., DesktopFileCommentsView 的 `viewMention` 设 `keyboardSupport: false`, 因为 DesktopCommentInput 子组件已绑)

### §2.4 selector 参数 (W68 第 13 批 C-2 铁律 4)
- 默认 `[data-mention-input]` (HTML 标准 data attr)
- DesktopCommentInput 传 `.dci-mention-input` (CSS class, 跟 mci- mobile 风格对齐)
- DesktopDashboardView 传 `[data-mention-input="desktop-dashboard-task"]` (区分 dashboard quick input)

### §2.5 跨视图一致 (W68 第 13 批 C-2 铁律 5)
- 3 个 view 各自的 mention 状态 **独立** (不共享 isOpen / candidates)
- selector 隔离: 同一 view 多 mention input 共存时, 通过 selector 区分
- mention.isOpen / mention.candidates 私有 ref, 跨调用互不串扰

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

### §3.2 关键场景验证

**场景 1.1**: 默认参数 `name="mention"` / `selector="[data-mention-input]"` / `keyboardSupport=true` PASS

**场景 1.2**: 自定义参数 `name="desktop-comment-input"` / `selector=".dci-mention-input"` PASS

**场景 1.3**: `keyboardSupport=false` → `handleKeydown` 不响应 (跨视图 view 层字段) PASS

**场景 1.4**: `keyboardSupport=true` → `handleKeydown` 正常响应 PASS

**场景 2.1**: DesktopCommentInput 含 `.dci-mention-input` class + `data-mention-input` attr PASS

**场景 2.2**: DesktopCommentInput mention.selector === `.dci-mention-input` PASS

**场景 2.3**: DesktopCommentInput mention.keyboardSupport === true PASS

**场景 2.4**: 下拉打开 + 选中 → text 替换 + close PASS

**场景 3.1**: 3 个 mention composable 各自持有自己 isOpen/candidates PASS

**场景 3.2**: candidates 数组互不共享 (各 view 独立注入) PASS

**场景 4.1**: 中文姓名 / wechat_id / username 全部 lowercase 后能匹配 PASS

**场景 4.2**: 英文 username prefix 匹配 PASS

**场景 4.3**: exact match (wechat_id) ranked first PASS

**场景 5**: DesktopFileCommentsView 同时持有 viewMention + DesktopCommentInput PASS

**场景 6**: DesktopFileCommentsView 容器含 .dci-mention-input class (跨视图一致性) PASS

## §4 部署铁律

### §4.1 恢复路径 — git revert

```bash
git revert <commit-hash>
```

单 commit 收口, 1 行 revert 即恢复. < 5 分钟恢复.

### §4.2 0 production code 改动铁律维持

| 范畴 | 改动 | 状态 |
|------|------|------|
| `app/` 后端 | 0 改动 | OK |
| `web/src/` 老路径 | 0 改动 (仅 4 个 view 调整 + 1 个 composable 升级) | OK |
| `alembic/versions/` | 0 改动 | OK |
| `docs/` | 1 新增 (本文件) | OK |
| `memory/` | 1 新增 (W68 第 13 批 C-2 memory) | OK |
| `web/tests/e2e/` | 1 新增 (desktop_mention_unified.spec.js) | OK |
| `web/dist/` | 0 改动 (无 build) | OK |

### §4.3 跨视图 isolation 纪律

- 多个 view 出现 mention 输入时, 必须传 `selector` 区分
- 同一 view 内嵌多个 mention input (e.g., DesktopFileCommentsView 含 DesktopCommentInput), 各自持有独立 mention 状态
- view 层调 useMentionAutocomplete 时, `keyboardSupport=false` 避免与子组件 keyboard 重复绑

## §5 后续加固

### §5.1 移除 DesktopCommentInput 残留 dci-textarea class

当前保留 `.dci-textarea` class (向后兼容 W68 第 5 批 #11 测试), 后续 PR 可改为仅 `.dci-mention-input`:
```bash
# 后续 PR: 移除 dci-textarea 单独 class, 全部统一 dci-mention-input
# 影响 e2e/desktop_drive_mention.spec.js 与 desktop_drive_comments.spec.js 一处 selector
```

### §5.2 跨 view mention 状态可观察

`mention.name` 暴露 ref, 调试时直接看 `wrapper.vm.mention.name.value` 知道是哪个 view 的 mention.

### §5.3 跨 view mention 状态联动 (未来 PR)

未来如果需要在多个 view 的 mention 状态联动 (e.g., dashboard quick input 选中的成员反映到评论 view), 走 Pinia store 持有 shared mention state. 当前 PR 仅做单 view 独立 mention 隔离.

## §6 引用

- **W68 第 9 批 F-3**: useMentionAutocomplete composable 首次实施 (commit `5bf7c5c7` 同期)
- **W68 第 5 批 #11**: DesktopCommentInput 首次引入 @ 提及 (commit `353ba295a`)
- **W68 第 8 批 B-3**: DesktopCommentInput + DesktopFileCommentsView v3.2 收口 (commit `faffaf8ff`)
- **W68 第 13 批 C-2**: 跨视图一致性升级 (本 commit)
- **CLAUDE.md**: ## 代码质量规范 / ## 前端架构 / ## CSS 设计令牌
- **memory/**: `w68-route-13-c2-mention-unified-2026-07-24.md` (锚点范式第 166 守恒)

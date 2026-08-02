# W100 +28 UI-ARCHIVE 会话归档管理 Runbook - 2026-08-02

## 概述
SessionSidebar 批量归档/删除/搜索过滤功能实施。基于 main 91d359188, worktree E:/agent-ui-archive, branch chore/ui-archive。

## 现状据实上报
SessionSidebar.vue 已有 (v78 + CHAT-P1-E E3):
- 搜索过滤 (filterKw, 按 title + tags)
- 归档区 tab (全部 / 未归档 / 已归档)
- 右键/长按上下文菜单 (重命名 / 置顶 / 归档 / 分享 / 导出 / 标签 / 删除)
- sortedSessions 已自动置顶冒泡

本任务新增:
1. SessionActions 组件 (hover 快捷操作)
2. 分组显示 (pinned / recent group header)
3. 批量操作模式 (multi-select + batch archive/delete)
4. 搜索增强 (preview 匹配)

## 实施细节

### SessionActions.vue
- Props: `session` (Object), `mode` ('sidebar' | 'inline')
- Emits: `archive`, `delete`, `pin`
- sidebar mode: opacity:0, hover session-item 时 opacity:1
- inline mode: 始终 opacity:1
- 3 button: pin (Top icon) / archive (FolderOpened icon) / delete (Delete icon)
- active state: pin-btn 当 is_pinned, archive-btn 当 is_archived
- a11y: 44px tap target via ::before pseudo-element, aria-label 动态

### SessionSidebar.vue 分组逻辑
```js
const groupedSessions = computed(() => {
  const list = filteredSessions.value
  const pinned = list.filter(s => s.is_pinned)
  const recent = list.filter(s => !s.is_pinned)
  return { pinned, recent }
})
```
非批量模式: v-for pinned (带 📌 置顶 header) + v-for recent (带 🕒 最近 header)
批量模式: flat v-for filteredSessions (checkbox, 无分组)

### 批量操作
- `batchMode` ref toggle
- `selectedIds` Set (new Set() 触发响应式)
- `batchArchive`: ElMessageBox.confirm -> for loop store.setArchived(id, true)
- `batchDelete`: ElMessageBox.confirm -> for loop store.deleteSession(id)
- 底部 action bar: 已选 N 个 + 归档 / 删除 button

### MobileSessionDrawer.vue
- 同桌面端批量模式 (batchMode + selectedIds + toggleSelect)
- session-item-wrapper div 包裹 checkbox + session-item
- emit batch-archive / batch-delete (ids array) 给父组件处理
- iOS 底部安全区: padding-bottom: calc(10px + var(--sab, 0px))

## 5 件套
1. alembic 096 守恒 (0 alembic 改动)
2. pytest N/A (纯前端)
3. PWA build PASS
4. 0 production code (0 backend)
5. 锚点 W100 +28 (1 commit)

## vitest
- SessionActions: 6/6 PASS
- Pre-existing FAIL: ThinkingCapsule 3 case (W99 +14/+16, 与本任务无关)

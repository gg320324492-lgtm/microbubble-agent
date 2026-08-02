# W100 +28 UI-ARCHIVE 会话归档管理 - 2026-08-02

## 任务
- 派工 v10 UI-ARCHIVE P2 #1
- SessionSidebar 加批量归档/删除/搜索过滤功能
- worktree: E:/agent-ui-archive (branch: chore/ui-archive, base 91d359188)

## 实施内容

### 1. 新建 SessionActions.vue (~115 行)
- 3 个 action icon: 置顶 / 归档 / 删除
- 两种 mode: sidebar (hover 显示) / inline (始终显示)
- a11y: button + aria-label + keyboard + 44px tap target (::before 伪元素扩展)
- dark mode 覆盖

### 2. SessionSidebar.vue 修改
- **搜索增强**: filterKw 现也匹配 preview/最后消息 (原来仅 title + tags)
- **分组显示**: 非批量模式下按 pinned / recent 分组, 带 group header (📌 置顶 / 🕒 最近)
- **SessionActions 集成**: hover 显示 3 个快捷操作 icon (非批量模式)
- **批量操作模式**:
  - 批量管理 toggle button (header 区)
  - 全选 / 清空 mini button
  - checkbox 多选 (flat list, 无分组)
  - 底部 action bar: 批量归档 / 批量删除 (带确认 dialog)
  - selectedIds Set 响应式 (new Set() 触发)
- **CSS**: session-item 改 flex 布局, 新增 12 个 CSS class

### 3. MobileSessionDrawer.vue 修改
- **批量操作模式**: 同桌面端, 批量管理 toggle + checkbox + action bar
- **session-item-wrapper**: 新增 wrapper div 包裹 checkbox + session-item
- **emit 扩展**: 新增 batch-archive / batch-delete 事件
- **CSS**: 新增 10 个 CSS class, iOS 底部安全区 (sab)

### 4. SessionActions.test.ts (6 case)
- ① 渲染 3 个 action button
- ② 未置顶 -> pin-btn 无 active, aria-label="置顶会话"
- ③ 已置顶 -> pin-btn 有 active, aria-label="取消置顶"
- ④ 已归档 -> archive-btn 有 active, aria-label="恢复会话"
- ⑤ click pin -> emit('pin', session)
- ⑥ sidebar mode -> sidebar class; inline mode -> inline class

## 5 件套守恒
1. alembic 096_add_rag_multimodal_metrics (head) 守恒 (0 alembic 改动)
2. pytest N/A (纯前端任务)
3. PWA build PASS (9.46s, postbuild 完成, PWA 已禁用)
4. 0 production code: 0 backend (app/ + alembic/) 改动, 仅前端 web/src/
5. 锚点 >= 1: W100 +28 (1 commit)

## vitest 结果
- SessionActions: 6/6 PASS
- 全 chat __tests__: 81 PASS + 3 pre-existing FAIL (ThinkingCapsule W99 +14/+16, 与本任务无关)
- 9/11 test files passed (2 ThinkingCapsule pre-existing)

## 类 20 沉淀
- 类 20.133 (W100 +28): 现有 SessionSidebar 已有 search + archive filter + context menu, 派工 brief 估"加搜索过滤"实测已存在, 据实上报不重复实现, 增强为 preview 搜索 + 分组 + 批量

## 关键文件
- `web/src/components/chat/SessionActions.vue` (新建, ~115 行)
- `web/src/components/chat/__tests__/SessionActions.test.ts` (新建, 6 case)
- `web/src/components/chat/SessionSidebar.vue` (修改, +422 行)
- `web/src/views/mobile/chat/MobileSessionDrawer.vue` (修改, +231 行)

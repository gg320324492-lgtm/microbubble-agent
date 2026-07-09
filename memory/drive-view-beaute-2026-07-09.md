---
name: drive-view-beaute-2026-07-09
description: Drive 全家桶全面美化 — drive-view.css 共享样式 + 5 子组件 + 10 dialog + mobile 镜像 + chip 化过滤条
metadata: 
  node_type: memory
  type: project
  originSessionId: 7d13269c-c619-42dc-a52f-055fd11b9576
---

# Drive 全家桶全面美化 (2026-07-09)

## Context

课题组网盘 (`/drive` 路由) 是 v2 网盘主入口,2026-07-01 上线后视觉一直朴素 (vs Meeting/Workspace/Dashboard/KnowledgeCard 的 v70~v77 美化水平)。本次用户决策 "全面美化一下",分 4 commit 链收官:

1. `feat(drive): 共享 drive-view.css (1089 行) + 主视图容器层美化` (commit `295848d`)
2. `feat(drive): FileCard + FileGrid 改写 (data-type 染色 + 三态升级 + 分页 sizes)` (commit `782c92b`)
3. `feat(drive): FolderTree/FolderTreeNode/BatchActionToolbar 玻璃态 + chip 化过滤` (commit `0788f8b`)
4. `feat(drive): 10 dialog 玻璃态 + 回收站/请求 panel hero header` (commit `196cd9e`)
5. `feat(drive): MobileDriveView 镜像 + 文件类型染色` (commit `7d5bfb0`)
6. `test(drive): FileCard (7) + FileGrid (8) 集成测试 - 15 PASS` (commit `04c7fd2`)

**共计**: 19 文件改动 (1 个 css + 1 个 mobile view + 1 个 desktop view + 13 个 drive 子组件 + 2 个 test + 1 个 __init__ dir),5 个 commit 链全部 push origin/main,15 个新 vitest 全部通过 (FileCard 7 + FileGrid 8)。

## 设计原则

1. **走 token, 不硬编码颜色** (v70~v76 铁律 1):所有视觉 token 走 `var(--color-*)`、`var(--shadow-*)`、`var(--gradient-*)`、`var(--radius-*)`、`var(--space-*)`、`var(--duration-*)`、`var(--ease-*)`
2. **dark mode 跨组件覆盖走非 scoped 块** (v60-v67 铁律 5):drive-view.css 是全局 (非 scoped) 但只引入 Drive view,内容用 `[data-theme="dark"]` 覆盖 dark 色,而不是在 .vue scoped 加 dark 块
3. **6 主题自适应** (v76 铁律):所有 `rgba()` 写法走 `var(--color-*-rgb)` 三元组
4. **复用现成 utility**:`.fade-slide-up`、`.stagger-1..6` (variables.css)、`.glass` `.glass-sm` `.glass-lg` (glass.css)、`.skeleton`、`.card-file-hero--pdf/word/ppt/excel/other` (runtime-style-tokens)
5. **动画统一入场**:View 容器 `animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;`,FileCard 用 nth-child(N) stagger 1..7

## 关键设计决策

### drive-view.css 共享样式抽取
- **位置**: `web/src/views/drive/drive-view.css` (1089 行,27 个 .drive-* class)
- **加载方式**: 每个 .vue 文件第一行 `import '@/views/drive/drive-view.css'` (Vue 编译器自动处理 CSS 依赖,无需 main.js 显式 load)
- **优势**: 避免 5 个 .vue scoped 重复 (topbar/empty/loading/skeleton/scrollbar),dark mode 自动跟随 variables.css token 翻转
- **MeetView 范式对齐**: `web/src/views/meeting/meeting-view.css` 同样由 MeetingView.vue import,作为范式标杆
- **27 class 清单**:
  1. `.drive-page` (容器 + fade-slide-up)
  2. `.drive-toolbar` (顶部 sticky + hero)
  3. `.drive-title` + `.drive-title-icon` (渐变图标圆)
  4. `.drive-search-input` (pill 圆角)
  5. `.drive-upload-btn` + `.drive-upload-btn-glow` (CTA 渐变 + btn-glow 动画)
  6. `.drive-filter-bar` + `.drive-filter-bar-left/right`
  7. `.drive-chip` + `.drive-chip.is-active` (替换 el-dropdown)
  8. `.drive-chip[data-type="pdf|image|video|audio|office|text"]::before` (色点)
  9. `.drive-breadcrumb` (胶囊面包屑)
  10. `.drive-statusbar` (玻璃态底栏)
  11. `.drive-sidebar` (玻璃态侧栏 + sidebar shadow)
  12. `.drive-sidebar-header` (主色字 + 渐变 bg)
  13. `.drive-folder-tree-*` (root/special/node 节点)
  14. `.drive-folder-tree-special-item.is-team/.is-requests/.is-trash` (多色变体)
  15. `.drive-folder-tree-node-toggle.is-expanded` (旋转 90deg)
  16. `.drive-file-grid` + `.drive-file-grid-list` (grid/list 容器)
  17. `.drive-file-card` + `.drive-file-card[data-type="pdf|..."]` (8 类顶部彩条 + icon 染色)
  18. `.drive-file-card.is-selected` (主色边 + 主色 bg)
  19. `.drive-file-card.is-private` (左边框红)
  20. `.drive-file-card-thumb` (缩略图占位渐变)
  21. `.drive-file-card-list` (row 布局)
  22. `.drive-file-card:nth-child(N)` (stagger 入场)
  23. `.drive-grid-loading` + `.drive-grid-loading-skeleton` (7 个 skeleton card)
  24. `.drive-grid-error` (红橙渐变 + 重试)
  25. `.drive-grid-empty` + `.drive-grid-empty-hero` + `.drive-grid-empty[data-state="search"]` (3 种空态)
  26. `.drive-grid-pagination` + `:deep(.el-pagination.is-background .el-pager li.is-active)` (active 项渐变)
  27. `.drive-batch-toolbar` + `.drive-batch-toolbar-btn` + `.drive-batch-count` (橙渐变 toolbar)
  28. `.drive-dialog :deep(.el-dialog__header)` (dialog 顶部 hero 渐变)
  29. `.drive-panel` + `.drive-panel-header.is-danger/is-success` (panel hero 边框)
  30. `.drive-dropzone-active` (拖拽激活虚线 + 📂 "松开上传文件")
  31. `.drive-view-toggle` (grid/list 切换按钮组)
  32. `.drive-file-area::-webkit-scrollbar` + `:hover` (滚动条美化)
  33. `@media (max-width: 1024px)` + `@media (max-width: 768px)` (移动响应)

### FileCard data-type mapping
- **EXTENSION_TYPE_MAP**: 单文件 const,24 个扩展名 → 8 个 type key (pdf/doc/ppt/excel/image/video/audio/text)
- **CSS attribute selector**: `.drive-file-card[data-type="pdf"]::before` 控制顶部彩条;`.drive-file-card[data-type="pdf"] .file-card-icon` 控制图标颜色
- **优势**: 不在 JS 里写颜色 (CSS 单一来源),未来加 file_type 仅改 1 处 CSS + 1 处 map

### 三态升级 (loading/empty/error)
- **loading**: 7 个 `.drive-grid-loading-skeleton` (与 grid 列数对齐,桌面 7 列),用 `.skeleton` utility + 自定义高宽
- **error**: 红橙渐变 hero + warning icon + "重试"按钮走 `.drive-upload-btn` class
- **empty**: 3 种 data-state
  - `top-level` (默认): 96px 渐变 hero 圆 + FolderAdd icon + "上传文件"主色 CTA
  - `folder` (子文件夹): 简化文案,无 CTA
  - `search` (搜索无结果): SearchIcon + 关键词 + 无 CTA

### 分页升级
- **page-sizes 选择器**: `[20, 50, 100]` 三档
- **layout 增强**: `total, sizes, prev, pager, next, jumper` (加 jumper 跳页)
- **emit 链**: DesktopDriveView 加 `onPageSizeChange(size)` handler,改 `pageSize.value` + 重置 `currentPage=1` + refetch

### chip 化过滤条
- **旧**: 2 个 el-dropdown 按钮 (排序 + 类型),朴素
- **新**: 12 个 `.drive-chip` button (6 排序 + 6 类型),aria-pressed 标识激活态,激活态主色渐变 + 白字 + btn-shadow
- **aria-pressed**: 真正的无障碍语义 (替代 el-dropdown 的隐式 aria-expanded)

### 10 dialog 玻璃态
- **统一 class**: 每个 el-dialog 加 `class="drive-dialog"`,让 `.drive-view.css .drive-dialog :deep(.el-dialog__header)` 共享渐变
- **8 个文件 dialog + 1 个 inline Extract + 1 个 panel**:
  - CreateFolderDialog, RenameDialog, MoveDialog, DriveUploadDialog,
    FilePreviewDialog, ShareDialog, VersionHistoryDialog
  - DesktopDriveView 内的 Extract dialog (inline `<el-dialog>`)
  - DriveTrashPanel (.drive-panel 玻璃态 + 红橙 hero header)
  - FileRequestListPanel 内的 2 个 dialog

### MobileDriveView 镜像
- **Mobile specific**: `<div class="mobile-drive-view drive-page">` (双 class,移动端 layout 仍由 scoped 控制)
- **data-type 染色**: 通过 `getFileTypeKey(file)` 加 `:data-type='...'`,让移动端 file card 顶部彩条与桌面一致
- **不重构移动端结构**: 长按 ActionSheet / FAB / 4 tab / folder chip / 2 列 grid 全部保留,仅在视觉层镜像

## 10 新铁律 (永久沉淀)

1. **drive-view.css 共享样式 vs .vue scoped 块的边界**:
   公共 → .drive-* 全局类 (token 化 + dark 自动跟随)
   私有 → .vue scoped (layout-flex 细节,如 list-view flex direction: row)
2. **file_type 走 data-type 属性 + CSS attribute selector** 而非 JS color code 散落
   反例: `:style="{ color: getColorByExtension(ext) }"` (颜色散落 JS,难以 dark 跟随)
   正例: `:data-type="fileTypeKey"` + CSS `.[data-type="pdf"]` (单一来源)
3. **chip 过滤条用 button[aria-pressed="true"] 而非 EP 自定义样式** (无障碍 + 键盘 tab 友好)
4. **玻璃 dialog 共享 backdrop 而非每个 dialog 单独写** (8 个 el-dialog 共享 `.drive-dialog` class,1 次写完)
5. **desktop dialog vs mobile dialog 共享样式表** (mobile-mobile-base.css 内已有 glass + drive-view.css 内 dialog 玻璃,EL 同时识别两者)
6. **DriveView 移动镜像原则**: 仅加 `.drive-page` class 与 data-type,不复用 desktop 工具栏 (FAB + 长按 ActionSheet 是 mobile-only)
7. **skeleton 数量与 grid 列数对齐** (桌面 7 列 → 7 个 skeleton card,移动 2 列 → 改 mobile scoped)
8. **渐变图标 vs 单色图标**: dark mode 中渐变变透明 (--gradient-welcome-hero dark override),单色 token 自动反转
9. **文件类型 color 不复用 `--color-primary`** (跨 file_type 区分明显性下降),而用 `--color-file-pdf/doc/excel/image/audio/video/text` 7 类
10. **Drive dialog 不可走 `el-dialog` 默认 fullscreen**,mobile viewport 需走 `--drawer-width-mobile` token (本次范围外,留给未来)

## 测试

- **vitest**: 15/15 PASS (FileCard 7 + FileGrid 8),原 535 → 550
- **测试覆盖**:
  - 8 类 extension → data-type 映射 + 未知 fallback
  - list/grid view mode class 切换
  - is-selected/is-private 视觉 class
  - loading: 7 skeleton card
  - error: retry emit
  - empty: 3 种 state + 关键词显示 + CTA 控制
  - data 模式: grid vs list 容器 class
  - 分页: size-change emit
- **未来覆盖**: FolderTree / FolderTreeNode / BatchActionToolbar / 8 dialog 各自 smoke test (本次跳过避免大 commit,可作后 PR)

## 不在本次范围 (留给后续)

- **缩略图常规化**: FileCard 仍走 file_type icon,后端 thumbnail_status='ready' 才显示缩略图 (现状保持)
- **预览-on-hover**: hover 停留 1s 弹缩略图浮窗 (用户未提)
- **FolderTree 虚拟滚动**: 100+ 文件夹性能优化
- **批量分享/下载实现**: 仅 stub (ElMessage.info '暂未实现'),本次仅 UI 美化
- **PageSize 边界条件**: 100+ 仍待后端 page_size≤100 校验;server 已 `ge=1, le=100` 兜底
- **移动端 dialog 玻璃**: 移动 el-dialog 走 mobile-base.css 已有 mobile-glass,不复用 drive-view.css (避免 specificity 冲突)
- **FolderTree 空态处理**: 顶级 empty 显示创建文件夹 CTA (未实现)

## 部署

- **5 commit 链全部 push origin/main** (commit hashes 见上)
- **web/dist 重新生成**: 用户浏览器 hard refresh (Ctrl+Shift+R) 走新 chunk
- **bug 风险**: drive-view.css 引入 12 个 .vue 文件,任一 vite 重启没加载将整个 drive view 布局错乱
  - **缓解**: CI grep `grep -rL "drive-view.css" web/src/components/drive/*.vue web/src/views/DesktopDriveView.vue web/src/views/mobile/MobileDriveView.vue` 必须命中 14 个文件
  - **fallback**: 任一文件漏 import,fallback 到 .vue scoped 旧样式 (box-shadow 蓝色硬编码 + 无 fade-slide-up),仍可用
- **dark mode**: 切换 dark 时 drive-view.css 走的 var() 自动翻转,无需 dark 补丁

## 关键文件路径

| 资源 | 路径 |
|---|---|
| 共享样式 | [drive-view.css](../../web/src/views/drive/drive-view.css) |
| FileCard | [FileCard.vue](../../web/src/components/drive/FileCard.vue) |
| FileGrid | [FileGrid.vue](../../web/src/components/drive/FileGrid.vue) |
| FolderTree | [FolderTree.vue](../../web/src/components/drive/FolderTree.vue) |
| FolderTreeNode | [FolderTreeNode.vue](../../web/src/components/drive/FolderTreeNode.vue) |
| BatchActionToolbar | [BatchActionToolbar.vue](../../web/src/components/drive/BatchActionToolbar.vue) |
| DesktopDriveView | [DesktopDriveView.vue](../../web/src/views/DesktopDriveView.vue) |
| MobileDriveView | [MobileDriveView.vue](../../web/src/views/mobile/MobileDriveView.vue) |
| 状态机 | [useDriveFiles.js](../../web/src/composables/useDriveFiles.js) |
| FileCard test | [FileCard.test.js](../../web/src/components/drive/__tests__/FileCard.test.js) |
| FileGrid test | [FileGrid.test.js](../../web/src/components/drive/__tests__/FileGrid.test.js) |

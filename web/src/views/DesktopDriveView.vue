<!--
  DesktopDriveView.vue — 课题组网盘 (Lab Group Drive) 桌面端主视图
  PR3.1: 路由 + 侧边栏入口 + 主视图骨架 (FolderTree + FileGrid + 工具栏布局)

  架构:
  - 上方: 工具栏 (搜索 / 上传文件 / 上传文件夹 / 新建文件夹 / 视图切换)
  - 左侧: FolderTree 组件 (PR3.2 接入)
  - 右侧: FileGrid 组件 (PR3.3 接入) + 空态

  状态:
  - selectedFolderId: 当前选中的文件夹 ID (null = 顶级 "我的文件")
  - viewMode: 网格/列表切换
  - searchQuery: 搜索关键字 (PR3.4 接入)

  数据流:
  - PR3.1 仅骨架, 不调 API, 子组件待 PR3.2/3.3 接入

  2026-07-09: Drive 美化 v2.0 — 引入 drive-view.css 共享样式 (.drive-page / .drive-toolbar /
  .drive-title / .drive-search-input / .drive-upload-btn / .drive-filter-bar / .drive-chip 等)
  详见 web/src/views/drive/drive-view.css + C:\Users\pc\.claude\plans\ui-shiny-hearth.md
-->
<template>
  <!--
    批次③ (2026-09-05): 用户拍板 B「三栏工作台」版式 —
    左结构树 | 中密集行表 (DriveFileTable: 虚拟滚动/列排序/键盘导航/拖拽源) | 右常驻详情栏 (DriveDetailRail)。
    旧 FileGrid 卡片网格被表格替代 (grid/detail/list 三态退役, 密度改为 comfortable/compact);
    specialView (回收站/文件请求) 保留内嵌面板, 此时隐藏右栏与批量 dock。
    所有业务 handler 与 dialog 集群沿用既有实现, 0 后端契约变更。
  -->
  <div class="desktop-drive-view drive-page drive-workbench">
    <!-- 顶栏: 品牌 + 全局搜索 + 三个主操作 -->
    <header class="wb-top">
      <span class="wb-brand">
        <span class="wb-brand-ico">📁</span>课题组网盘
      </span>
      <span class="wb-vr"></span>
      <label class="wb-search">
        <el-icon class="wb-search-ico"><Search /></el-icon>
        <input
          v-model="searchQuery"
          placeholder="搜索全组文件名 (支持中文, 输入即搜)"
          aria-label="搜索全组文件名"
        />
      </label>
      <span class="wb-sp"></span>
      <el-button class="drive-toolbar-btn" :icon="Plus" @click="showCreateFolderDialog = true">新建文件夹</el-button>
      <el-button class="drive-toolbar-btn" :icon="Folder" @click="triggerFolderUpload">上传文件夹</el-button>
      <el-button class="wb-cta" :icon="UploadFilled" @click="showUploadDialog = true">上传文件</el-button>
    </header>

    <!-- 三栏 body -->
    <div class="wb-body" ref="driveMainRef" :class="{ 'is-drag-over': isDragging }">
      <!-- 外部文件拖入 hero (F3 真接入: drop -> DriveUploadDialog initialFiles) -->
      <transition name="drive-drop-hero-fade">
        <div v-if="isDragging" class="drive-drop-hero">
          <div class="drive-drop-hero-icon">
            <el-icon :size="48"><UploadFilled /></el-icon>
          </div>
          <p class="drive-drop-hero-title">拖拽文件到此处</p>
          <p class="drive-drop-hero-hint">松开鼠标即可上传到当前网盘</p>
        </div>
      </transition>

      <!-- 左: 结构树 + 快捷 (FolderTree 含 special 项 + 树节点拖放落点) -->
      <aside class="wb-rail">
        <div class="wb-rail-cap">结构</div>
        <FolderTree
          class="wb-tree"
          :folder-tree="folderTree"
          :selected-folder-id="selectedFolderId"
          :expanded-folder-ids="expandedFolderIds"
          :loading="treeLoading"
          :load-error="treeLoadError"
          :special-view="specialView"
          @update:selected-folder-id="selectedFolderId = $event"
          @update:special-view="specialView = $event"
          @toggle-expanded="toggleExpandedFolder"
          @retry="fetchFolderTree"
          @request-new-folder="onCreateSubFolder(null)"
          @create-sub-folder="onCreateSubFolder"
          @share-folder="onShareFolder"
          @drop-files="onMoveDrop"
        />
        <div class="wb-rail-foot">
          <StorageQuotaBadge v-if="quotaInfo" :quota-info="quotaInfo" />
        </div>
      </aside>

      <!-- 中: 面包屑 + 筛选 chips + 行表/内嵌面板 + 批量 dock -->
      <section class="wb-center">
        <div class="wb-crumbs">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>课题组网盘</el-breadcrumb-item>
            <el-breadcrumb-item v-if="specialView === 'team'">🌐 团队共享盘</el-breadcrumb-item>
            <el-breadcrumb-item v-else-if="specialView === 'starred'">⭐ 我的收藏</el-breadcrumb-item>
            <el-breadcrumb-item v-else-if="specialView === 'trash'">🗑️ 回收站</el-breadcrumb-item>
            <el-breadcrumb-item v-else-if="specialView === 'requests'">📥 文件请求</el-breadcrumb-item>
            <el-breadcrumb-item v-for="f in folderBreadcrumb" :key="'bc-' + f.id">
              📂 {{ f.name }}
            </el-breadcrumb-item>
          </el-breadcrumb>
          <span class="wb-crumb-search" v-if="isSearching">🔍 「{{ searchQuery.trim() }}」全盘结果 · {{ total }} 项</span>
          <span class="wb-sp"></span>
          <span class="wb-total">{{ isSearching ? ('匹配 ' + total + ' 项') : ('共 ' + total + ' 项') }}</span>
          <button
            type="button" class="wb-density"
            :title="density === 'comfortable' ? '行密度: 舒适 (点击切紧凑)' : '行密度: 紧凑 (点击切舒适)'"
            @click="toggleDensity"
          >{{ density === 'comfortable' ? '☰ 舒适' : '≡ 紧凑' }}</button>
        </div>

        <div v-if="isTableMode" class="wb-ctools">
          <span class="wb-lab">排序</span>
          <button
            v-for="opt in SORT_OPTIONS" :key="opt.value" type="button"
            class="drive-chip" :aria-pressed="sortKey === opt.value"
            :class="{ 'is-active': sortKey === opt.value }"
            @click="handleSortChange(opt.value)"
          >{{ opt.label }}</button>
          <span class="wb-lab wb-lab--gap">类型</span>
          <button
            v-for="opt in FILE_TYPE_OPTIONS" :key="opt.value || 'all'" type="button"
            class="drive-chip" :data-type="opt.type || null"
            :aria-pressed="fileType === opt.value || (!fileType && opt.value === null)"
            :class="{ 'is-active': fileType === opt.value || (!fileType && opt.value === null) }"
            @click="handleFileTypeChange(opt.value)"
          >{{ opt.label }}</button>
          <span class="wb-kbd-hint">↑↓ 移动 · 空格预览 · Enter 详情 · Del 回收站 · 拖行到左栏夹=移动</span>
        </div>

        <div class="wb-listarea">
          <!-- specialView 内嵌面板 (右栏/表格/dock 隐藏) -->
          <FileRequestListPanel v-if="specialView === 'requests'" />
          <DriveTrashPanel v-else-if="specialView === 'trash'" />
          <DriveFileTable
            v-else
            ref="tableRef"
            :files="driveFiles"
            :folders="isSearching ? [] : currentSubFolders"
            :loading="filesLoading"
            :load-error="filesLoadError"
            :selected-ids="selectedFileIds"
            :active-key="activeKey"
            :sort-by="sortBy"
            :sort-order="sortOrder"
            :show-path="isSearching"
            :density="density"
            :total="total"
            :current-page="currentPage"
            :page-size="pageSize"
            @row-activate="onRowActivate"
            @row-open="(row) => row.kind === 'folder' && enterFolder(row.data)"
            @row-open-detail="openDetailPage"
            @row-preview="handleFilePreview"
            @row-delete="handleFileDelete"
            @row-contextmenu="onRowContextmenu"
            @sort-change="onColumnSort"
            @select-toggle="toggleFileSelect"
            @select-all="onSelectAll"
            @select-range="onSelectRange"
            @toggle-star="handleFileToggleStar"
            @retry="fetchDriveFiles({ folder_id: selectedFolderId })"
            @page-change="onPageChange"
            @size-change="onPageSizeChange"
            @drop-into-folder="onMoveDrop"
          />
        </div>

        <!-- 批量 dock -->
        <div v-if="isTableMode" class="wb-dock">
          <BatchActionToolbar
            :selected-count="selectedFileIds.length"
            :total-count="driveFiles.length"
            context="files"
            @select-all="selectAll"
            @clear="clearSelection"
            @batch-delete="handleBatchDelete"
            @batch-move="handleBatchMove"
            @batch-share="handleBatchShare"
            @batch-download="handleBatchDownload"
            @batch-update-visibility="handleBatchUpdateVisibility"
            @batch-toggle-star="handleBatchToggleStar"
          />
        </div>
      </section>

      <!-- 右: 常驻详情栏 -->
      <DriveDetailRail
        v-if="isTableMode && activeFile"
        class="wb-railright"
        :file="activeFile"
        @preview="handleFilePreview"
        @download="handleFileDownload"
        @share="handleFileShareLink"
        @toggle-star="handleFileToggleStar"
        @rename="handleFileRename"
        @move="handleFileMove"
        @delete="handleFileDelete"
        @ingest-kb="handleFileToKb"
        @open-detail="openDetailPage"
        @goto-folder="gotoFolder"
        @open-versions-dialog="openVersionsDialog"
        @refresh="onRailRefresh"
      />

      <!--
        右键菜单 (批次③ 扩容): 文件全动作 / 文件夹动作, 全部接既有 handler。
        复用 FolderContextMenu (固定定位 + 边界检测 + open(event))。
      -->
      <FolderContextMenu
        v-if="contextMenuItems.length > 0"
        ref="contextMenuRef"
        :items="contextMenuItems"
        :placement="'auto'"
        @command="onContextMenuCommand"
        @close="onContextMenuClose"
      />
    </div>

    <!-- dialogs 集群 (沿用既有, 新增 VersionHistoryDialog) -->
    <CreateFolderDialog
      v-model="showCreateFolderDialog"
      :parent-id="currentCreateFolderParentId"
      :parent-folder="currentCreateFolderParentFolder"
      @create="onCreateFolder"
    />
    <RenameDialog
      v-model="showRenameDialog"
      :target="renameTarget"
      :target-type="renameTargetType"
      @rename="onRename"
    />
    <MoveDialog
      v-model="showMoveDialog"
      :current-folder-id="selectedFolderId"
      :file-id="moveTargetFileId"
      @move="onMoveFile"
    />
    <DriveUploadDialog
      v-model="showUploadDialog"
      :default-folder-id="selectedFolderId"
      :is-team-shared="specialView === 'team'"
      :initial-files="droppedFiles"
      @uploaded="onFilesUploaded"
      @update:model-value="v => { if (!v) droppedFiles = [] }"
    />
    <FilePreviewDialog v-model="showPreviewDialog" :file="previewFile" />
    <ShareDialog v-model="showShareDialog" :file="shareDialogFile" />
    <ShareLinkDialog v-model="showShareLinkDialog" :folder="shareLinkDialogFolder" />
    <!-- 批次③: 右键/右栏「版本沿革」直接开 dialog (含恢复 + 两版本对比 diff), 不强制跳 /versions 整页 -->
    <VersionHistoryDialog
      v-model:visible="showVersionsDialog"
      :file="versionsDialogFile"
      @restored="onRailRefresh"
    />
  </div>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化 — 引入 drive-view.css 共享样式 (见下方 import 与 .drive-* class)
import '@/views/drive/drive-view.css'
import { ref, computed, triggerRef, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { Search, UploadFilled, Folder, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import FolderTree from '@/components/drive/FolderTree.vue'
import DriveFileTable from '@/components/drive/DriveFileTable.vue'
import DriveDetailRail from '@/components/drive/DriveDetailRail.vue'
import StorageQuotaBadge from '@/components/drive/StorageQuotaBadge.vue'
import VersionHistoryDialog from '@/components/drive/VersionHistoryDialog.vue'
import BatchActionToolbar from '@/components/drive/BatchActionToolbar.vue'  // v2 PR2
// 2026-07-02: DriveSubSidebar 已删除 (PR7 反转), 此处不再 import
// 2026-07-02 inline 化: specialView 内嵌面板 (从 DesktopXxxView 抽取)
import DriveTrashPanel from '@/components/drive/DriveTrashPanel.vue'
import FileRequestListPanel from '@/components/drive/FileRequestListPanel.vue'
import CreateFolderDialog from '@/components/drive/CreateFolderDialog.vue'
import RenameDialog from '@/components/drive/RenameDialog.vue'
import MoveDialog from '@/components/drive/MoveDialog.vue'
import DriveUploadDialog from '@/components/drive/DriveUploadDialog.vue'
import FilePreviewDialog from '@/components/drive/FilePreviewDialog.vue'  // PR4.6
import ShareDialog from '@/components/drive/ShareDialog.vue'  // v2 PR1
import ShareLinkDialog from '@/components/drive/ShareLinkDialog.vue'  // W72-B-1 folder share link
// W68 第 4 批: 右键菜单复用 v2.9 FolderContextMenu (固定定位 + 边界检测)
import FolderContextMenu from '@/components/drive/FolderContextMenu.vue'
import { useFolderTree } from '@/composables/useFolderTree'
import { useDriveFiles } from '@/composables/useDriveFiles'
import { useFolderDropZone } from '@/composables/useFolderDropZone'
import { debounce } from '@/utils/debounce'  // ②-5 搜索接线

const router = useRouter()  // v2 PR2: 回收站路由跳转

// 2026-07-02: DriveSubSidebar 删除后, 此处不再嵌入子侧边栏, 不需折叠状态管理

// === 文件夹树 (PR3.2 接入) ===
// v2.15 Pinia 改造后修复 (2026-07-11): 必须用 storeToRefs 解构 state, 否则丢响应性
// 2026-07-14: selectedFolderId / selectedFolder 同样属于 store state；禁止从 store action 区解构。
// Pinia setup-store proxy 会自动 unwrap ref，直接解构初始 selectedFolder=null 后再读 .value 会崩溃。
// 修法: 全部 state/computed 用 storeToRefs(store)，actions 才直接解构。
import { storeToRefs } from 'pinia'
const folderTreeStore = useFolderTree()
const {
  folderTree,
  selectedFolderId,
  selectedFolder,
  expandedFolderIds,
  loading: treeLoading,
  loadError: treeLoadError
} = storeToRefs(folderTreeStore)
const {
  fetchTree: fetchFolderTree,
  toggleExpanded: toggleExpandedFolder,
  createFolder: doCreateFolder,
  renameFolder: doRenameFolder,
  deleteFolder: deleteFolderNode,
  getChildrenStats,
  findFolderById
} = folderTreeStore

// === 文件列表 (PR3.3 接入 + v2 PR1 + v2 PR2 sort/filter/star/batch) ===
// v2.15 Pinia 改造后修复 (2026-07-11): state 用 storeToRefs 解构保持响应性 (同 folderTree 修复)
const driveFilesStore = useDriveFiles()
const {
  driveFiles,
  total,
  currentPage,
  pageSize,
  loading: filesLoading,
  loadError: filesLoadError,
  selectedFileIds,
  // v2 PR2: sort/filter state (双向绑定, 切文件夹/特殊视图保留)
  sortBy, sortOrder, starredOnly, fileType
} = storeToRefs(driveFilesStore)
const {
  fetchFiles: fetchDriveFiles,
  fetchStarred,
  deleteFile,
  renameFile,
  moveFile,
  updateVisibility: doUpdateVisibility,
  // F5 修复 (批次②): extractToKb 已删除, 入库知识库单入口走 ingestToKb (/to-kb 新管线)
  ingestToKb: doIngestToKb, // W98: 网盘入库 RAG (drive → kb)
  createShareLink,
  revokeShareLink,
  toggleStar,
  batchStar,
  batchSoftDelete,
  batchMove: doBatchMove,
  batchUpdateVisibility: doBatchUpdateVisibility,
  batchDownload: doBatchDownload,
  toggleSelect: toggleFileSelect,
  clearSelection,
  selectAll
} = driveFilesStore

// === 状态 ===
// 批次③ (2026-09-05 B 三栏工作台): FileGrid 三态 (grid/detail/list) 退役为
// 表格双密度 — comfortable(40px)/compact(32px), localStorage 记忆偏好。
const DENSITY_KEY = 'drive-density'
const density = ref(localStorage.getItem(DENSITY_KEY) === 'compact' ? 'compact' : 'comfortable')
watch(density, (v) => {
  try { localStorage.setItem(DENSITY_KEY, v) } catch { /* 隐身模式等存储失败静默 */ }
})
function toggleDensity() { density.value = density.value === 'comfortable' ? 'compact' : 'comfortable' }

// === 2026-08-30: 团队共享盘子文件夹 (大图标卡片) ===
// 当前层的子文件夹: team 顶层 = is_team_default 根 (组会PPT); 进入子层 = 该节点 children
const currentSubFolders = computed(() => {
  if (specialView.value !== 'team') return []
  if (selectedFolderId.value === null) {
    // 2026-08-30: 跳过"组会PPT"层级 — 团队共享盘直接展示人名文件夹
    const teamRoots = (folderTree.value || []).filter(f => f.is_team_default)
    return teamRoots.flatMap(r => r.children || [])
  }
  const node = findFolderById(selectedFolderId.value)
  return node?.children || []
})

// 面包屑: 团队共享盘 → 组会PPT → 人名
const folderBreadcrumb = computed(() => {
  if (specialView.value !== 'team' || selectedFolderId.value === null) return []
  const chain = []
  const walk = (nodes) => {
    for (const n of nodes || []) {
      if (n.id === selectedFolderId.value) { chain.push(n); return true }
      if (n.children?.length) {
        chain.push(n)
        if (walk(n.children)) return true
        chain.pop()
      }
    }
    return false
  }
  walk(folderTree.value || [])
  return chain
})

function handleFolderClick(folder) {
  // 与 FolderTree 选中行为一致: 更新 selectedFolderId → watch 自动拉取该层文件
  // expandedFolderIds 是 Set (类 20.189): 用 .has/.add, 不是数组 .includes
  selectedFolderId.value = folder.id
  if (!expandedFolderIds.value.has(folder.id)) {
    expandedFolderIds.value.add(folder.id)
  }
}
const searchQuery = ref('')
// ②-5 搜索接线 (批次②): 输入 300ms debounce → fetchFiles 透传 search (后端 B6:
// search 非空时忽略 folder 约束 = 全盘结果; 后端参数由批次① ①-5 落地, 前端先行,
// 老后端无该参数时会被忽略, 不报错)。清空 → 回当前 folder/视图列表。
// 留口: 搜索结果行的"所属文件夹"小字依赖后端响应含 folder_name (当前 DriveFileItem
// 无此字段, FileCard 已做 f.folder_name 存在即显示的兼容渲染)。
function runSearchOrReload() {
  const q = searchQuery.value.trim()
  currentPage.value = 1
  if (q) {
    starredOnly.value = false
    fetchDriveFiles({ search: q, folder_id: null, view: 'team' })
  } else {
    reloadCurrentView()
  }
}
const debouncedSearch = debounce(runSearchOrReload, 300)
watch(searchQuery, () => debouncedSearch())
// v2 PR2: 特殊视图 (null | 'starred' | 'trash')
// 2026-08-30: 默认直接进团队共享盘 (个人网盘入口按需求移除)
const specialView = ref('team')

// 批次③ B 工作台: 搜索态与表格态判定 (trash/requests 走内嵌面板, 隐藏右栏/批量 dock)
const isSearching = computed(() => !!searchQuery.value.trim())
const isTableMode = computed(() => !['trash', 'requests'].includes(specialView.value))

// v2.0 (2026-07-09) Drive 美化: chip 化的 sort/type 选项数组 (替代 SORT_LABELS dropdown)
// 与 drive-view.css .drive-chip 配合, aria-pressed=true 时 is-active class
// v2.23 (2026-07-11) 删 名称 A-Z / 名称 Z-A chip (用户决策 "重命名场景极少, 4 个时间排序够用")
// 后端 file_name 排序仍支持 (e.g. URL 直调 file_name:asc), 仅前端 chip 不暴露
// v2.24 (2026-07-11) 删 收藏时间 chip (用户决策 "收藏有专门视图, 不用混在排序里")
// 后端 starred_at 排序仍支持 (e.g. fetch_starred() 默认 sort=starred_at desc),
// 仅前端 chip 不暴露. "我的收藏" 视图 (specialView=starred) 内部仍按 starred_at desc
const SORT_OPTIONS = [
  // v2.5 (2026-07-10): 修复两 chip 视觉重复 — 「最新上传 ⬇/⬆」文字完全相同只差箭头方向,
  //   改为「最新上传 ⬇」+「最早上传 ⬆」让用户一眼区分 (latest vs earliest).
  { value: 'created_at:desc', label: '最新上传 ⬇' },
  { value: 'created_at:asc',  label: '最早上传 ⬆' },
  { value: 'updated_at:desc', label: '最近修改 ⬇' },
]

// v2.22 (2026-07-11) 拆分 office → word/ppt/excel (用户决策 "Office 分类太粗")
// 后端 drive_service._build_file_type_predicate 同步加 word/ppt/excel 映射, office 留为 alias
//
// v2.23 (2026-07-11) 重排: PDF 移到 Word/PPT/Excel 旁边 (Office 文档族聚类, 用户决策)
// 文档族: PDF + Word + PPT + Excel (连排)
// 媒体族: 图片 + 视频 + 音频 (连排)
// 其他:   文本 (兜底)
const FILE_TYPE_OPTIONS = [
  { value: null,    type: null,    label: '全部类型' },
  // 文档族 (Office docs 聚类)
  { value: 'pdf',   type: 'pdf',   label: '📄 PDF' },
  { value: 'word',  type: 'word',  label: '📝 Word' },
  { value: 'ppt',   type: 'ppt',   label: '📊 PPT' },
  { value: 'excel', type: 'excel', label: '📈 Excel' },
  // 媒体族
  { value: 'image', type: 'image', label: '🖼️ 图片' },
  { value: 'video', type: 'video', label: '🎬 视频' },
  { value: 'audio', type: 'audio', label: '🎵 音频' },
  // 其他
  { value: 'text',  type: 'text',  label: '📝 文本' },
]

const sortKey = computed(() => `${sortBy.value}:${sortOrder.value}`)

// v2.0: handlers 直接收 chip value
function handleSortChange(value) {
  const [sb, so] = value.split(':')
  sortBy.value = sb
  sortOrder.value = so
  currentPage.value = 1
  reloadCurrentView()
}

function handleFileTypeChange(value) {
  fileType.value = value
  currentPage.value = 1
  reloadCurrentView()
}

async function reloadCurrentView() {
  if (specialView.value === 'starred') {
    starredOnly.value = true
    await fetchStarred()
  } else if (specialView.value === 'team') {
    // v2 PR6-P19: 团队共享盘视图 — 后端 view='team' 过滤 is_team_shared=true 文件
    starredOnly.value = false
    await fetchDriveFiles({
      folder_id: selectedFolderId.value,
      view: 'team',
    })
  } else {
    // trash 子组件 <DriveTrashPanel> 自管 onMounted → reload() → fetchTrash()
    // 2026-09 单一团队工作区: team 之外的默认视图也固定 view='team'
    starredOnly.value = false
    await fetchDriveFiles({ folder_id: selectedFolderId.value, view: 'team' })
  }
}

async function handleBatchDelete() {
  if (!selectedFileIds.value.length) return
  try {
    await ElMessageBox.confirm(
      `确定要删除 ${selectedFileIds.value.length} 个文件吗?`,
      '批量删除',
      { type: 'warning' }
    )
    const resp = await batchSoftDelete(selectedFileIds.value)
    if (resp.skipped_ids?.length) {
      ElMessage.warning(`已删除 ${resp.succeeded_count} 个, 跳过 ${resp.skipped_ids.length} 个`)
    } else {
      ElMessage.success(`已删除 ${resp.succeeded_count} 个文件`)
    }
  } catch (e) {
    if (e !== 'cancel') ElMessage.error(e.message || '删除失败')
  }
}

async function handleBatchMove() {
  if (!selectedFileIds.value.length) return
  moveTargetFileId.value = selectedFileIds.value  // 复用 MoveDialog
  showMoveDialog.value = true
}

async function handleBatchShare() {
  // v77 留尾清理 (2026-07-20): 逐个复用 createShareLink (share_link API 已实装),
  // 汇总所有分享 URL 后复制到剪贴板 (批量分享 = 生成 N 条链接)
  if (!selectedFileIds.value.length) return
  const ids = [...selectedFileIds.value]
  const lines = []
  let fail = 0
  for (const id of ids) {
    try {
      const target = driveFiles.value.find(f => f.id === id)
      const result = await createShareLink(id)
      const fullUrl = `${window.location.origin}${result.shareUrl}`
      lines.push(`${target?.file_name || `文件${id}`}: ${fullUrl}`)
    } catch (e) {
      fail++
    }
  }
  if (!lines.length) {
    ElMessage.error('批量分享失败, 请逐个使用分享按钮')
    return
  }
  const text = lines.join('\n')
  let copied = false
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      copied = true
    } else {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      try { copied = document.execCommand('copy') } catch (_) { /* noop */ }
      document.body.removeChild(ta)
    }
  } catch (_) { /* noop */ }
  const suffix = fail ? `, ${fail} 个失败` : ''
  if (copied) {
    ElMessage.success(`已生成 ${lines.length} 条分享链接并复制到剪贴板${suffix}`)
  } else {
    ElMessage.success(`已生成 ${lines.length} 条分享链接 (复制失败, 请手动分享)${suffix}`)
  }
}

async function handleBatchDownload() {
  // v77 留尾清理 (2026-07-20): 复用后端 batch-download ZIP 流式端点 (drive_files.py:931)
  if (!selectedFileIds.value.length) return
  try {
    await doBatchDownload([...selectedFileIds.value])
    ElMessage.success(`已开始下载 ${selectedFileIds.value.length} 个文件的 ZIP 打包`)
  } catch (e) {
    ElMessage.error(e.response?.data?.error?.message || e.message || '批量下载失败')
  }
}

async function handleBatchUpdateVisibility(visibility) {
  if (!selectedFileIds.value.length) return
  try {
    const resp = await doBatchUpdateVisibility(selectedFileIds.value, visibility)
    if (resp.skipped_ids?.length) {
      ElMessage.warning(`已改 ${resp.succeeded_count} 个, 跳过 ${resp.skipped_ids.length} 个 (folder 上限)`)
    } else {
      ElMessage.success(`已改 ${resp.succeeded_count} 个文件可见性为 ${visibility}`)
    }
  } catch (e) {
    ElMessage.error(e.message || '改可见性失败')
  }
}

async function handleBatchToggleStar() {
  if (!selectedFileIds.value.length) return
  const ids = [...selectedFileIds.value]
  // F10 修复 (批次②): 旧实现 for-toggleStar 会把已收藏项反向取消 (且 N 次请求)。
  // 改为一次 POST /files/batch-star {file_ids, starred:true} 幂等置标 (后端批次① 落地,
  // 前端先行; 该端点不存在/失败时 fallback 逐个 toggle, 但只处理未收藏项不再反向取消)。
  try {
    const resp = await batchStar(ids, true)
    ElMessage.success(`已收藏 ${resp?.updated ?? ids.length} 个文件`)
    return
  } catch (e) {
    console.warn('[DesktopDriveView] batch-star 失败, 回退逐个收藏:', e?.message || e)
  }
  let success = 0, fail = 0
  for (const id of ids) {
    const target = driveFiles.value.find(f => f.id === id)
    if (target?.is_starred) continue  // 已收藏跳过, 不再 toggle 反向取消
    try {
      await toggleStar(id)
      success++
    } catch (e) {
      fail++
    }
  }
  if (success || !fail) {
    ElMessage.success(`已收藏 ${success} 个文件${fail ? `, 失败 ${fail}` : ''}`)
  } else {
    ElMessage.error('批量收藏失败')
  }
}

async function handleFileToggleStar(file) {
  try {
    await toggleStar(file.id)
  } catch (e) {
    ElMessage.error(e.message || '切换收藏失败')
  }
}

// === PR3.5 文件夹拖拽 (主区域作为 drop zone) ===
const driveMainRef = ref(null)
// F3 修复 (批次②): 拖拽落盘文件 → 打开 DriveUploadDialog 并通过 initialFiles 注入真实上传。
// 旧 stub 的 console.log + process.env.NODE_ENV 引用一并删除
// (Vite 浏览器端无 process 全局, 生产 build 命中该行会 ReferenceError)。
const droppedFiles = ref([])
const { isDragging, bind: bindDropZone, unbind: unbindDropZone } = useFolderDropZone({
  onFilesDropped: ({ entries }) => {
    if (!entries?.length) return
    droppedFiles.value = entries
    showUploadDialog.value = true
  }
})

// === PR3.4 dialog 状态 ===
const showCreateFolderDialog = ref(false)
const showRenameDialog = ref(false)
const renameTarget = ref(null)
const renameTargetType = ref('file')  // file | folder
const showMoveDialog = ref(false)
const moveTargetFileId = ref(null)

// v2.29 (2026-07-12) 右键 FolderTree 菜单"新建子文件夹" 触发的临时 parent_id
//   null = 走默认 selectedFolderId (工具栏按钮 / 空态 CTA 路径)
//   非 null = 右键触发的目标 folder id (覆盖 selectedFolderId)
const createSubFolderParentId = ref(null)

// 右键触发时优先用 target folder id, 默认走 selectedFolderId
const currentCreateFolderParentId = computed(() =>
  createSubFolderParentId.value !== null
    ? createSubFolderParentId.value
    : selectedFolderId.value
)

// 右键触发时找该 folder 的 object 给 CreateFolderDialog 显示父文件夹 path
// 默认走 store.selectedFolder computed (按 selectedFolderId)
const currentCreateFolderParentFolder = computed(() => {
  const id = createSubFolderParentId.value
  if (id !== null) {
    return findFolderById(id)
  }
  return selectedFolder.value
})

// === v2 PR1 dialog 状态 ===
const showShareDialog = ref(false)
const shareDialogFile = ref(null)
// F5 修复 (批次②): showExtractDialog/extractDialogFile/extractTargetVisibility 随
// extract-to-kb 老管线入口一并删除

// === W72 第 2 批 B-1: folder share link dialog 状态 ===
const showShareLinkDialog = ref(false)
const shareLinkDialogFolder = ref(null)

// === PR3.6 上传 dialog 状态 ===
const showUploadDialog = ref(false)
const folderUploadInputRef = ref(null)

// === PR3.6 handlers ===
function triggerFolderUpload() {
  // webkitdirectory 模式: 只能选文件夹, Firefox 不支持
  // 实际: 复用 DriveUploadDialog 的拖拽 (useFolderDropZone 已支持 webkitGetAsEntry)
  // 这里弹 DriveUploadDialog 提示用户用拖拽
  ElMessage.info('请在打开的对话框中拖拽文件夹到上传区 (Chrome/Edge/Safari)')
  showUploadDialog.value = true
}

function onFilesUploaded({ count, folderId }) {
  // 上传完成后刷新当前文件夹的文件列表
  fetchDriveFiles({ folder_id: folderId ?? selectedFolderId.value })
}

// === 生命周期 ===
onMounted(async () => {
  // 2026-09 单一团队工作区: 网盘已合并为课题组单盘, 树/文件统一 team scope
  fetchFolderTree('team')
  fetchDriveFiles({ folder_id: null, view: 'team' })
  // 批次③: 左栏配额条 (GET /drive/storage-quota, 失败静默不阻塞主数据)
  axios.get('/api/v1/drive/storage-quota')
    .then((r) => { quotaInfo.value = r.data })
    .catch(() => { /* 配额缺失只是少一条进度条 */ })
  // PR3.5: 等 DOM ready 后绑定主区域为 drop zone
  await nextTick()
  if (driveMainRef.value) {
    bindDropZone(driveMainRef.value)
  }
})

// 切换路由时清理 (避免内存泄漏)
onBeforeUnmount(() => {
  unbindDropZone()
  debouncedSearch.cancel()  // ②-5: 取消未触发的搜索 debounce, 防卸载后 fetch
})

// === 监听 selectedFolderId 变化 → 重新拉文件列表 ===
// v2.26 (2026-07-12) BUG D 修复: watch(selectedFolderId) 必须传 view 跟随 specialView
//   修复前: fetchDriveFiles({ folder_id: newId }) 没传 view → useDriveFiles 默认 view=personal
//           → 过滤掉 is_team_shared=true → 用户在团队共享盘 sub-folder 看 0 文件
//   2026-09 单一团队工作区: 网盘合并为课题组单盘, 所有层固定 view='team'
watch(selectedFolderId, (newId, oldId) => {
  if (newId !== oldId) {
    currentPage.value = 1
    const view = 'team'
    fetchDriveFiles({ folder_id: newId, view })
  }
})

// v2 PR2 + v2 PR6-P19: 监听 specialView (starred | team | trash | null)
// 2026-09 单一团队工作区: 网盘已合并为课题组单盘, 切任意视图 tree 都拉 team scope,
// 文件列表 view 固定 'team' (后端仍接受 view/scope 参数但统一返回团队盘)
watch(specialView, async (newView) => {
  // v2.25 (2026-07-11): 切 specialView 时重拉 tree (原 scope 跟随视图; 2026-09 起统一 team)
  //   其它 (starred/trash/requests) → 不重拉, tree 不变
  if (newView === 'team' || newView === null) {
    await fetchFolderTree('team')
  }
  // === 旧分支: 切视图时同步文件列表 ===
  if (newView === 'starred') {
    starredOnly.value = true
    await fetchStarred()
  } else if (newView === 'team') {
    // v2 PR6-P19: 团队共享盘视图 — 后端 view='team' 过滤 is_team_shared=true
    starredOnly.value = false
    await fetchDriveFiles({
      folder_id: selectedFolderId.value,
      view: 'team',
    })
  } else if (newView === 'requests') {
    // 2026-07-02: FileRequestListPanel onMounted 自动 fetchMy, 无需手动调
  } else if (newView !== 'trash') {
    // trash 子组件 <DriveTrashPanel> 自管 onMounted → reload() → fetchTrash()
    // 2026-09 起默认视图也走 team (单盘合并)
    starredOnly.value = false
    if (selectedFolderId.value !== null) {
      await fetchDriveFiles({ folder_id: selectedFolderId.value, view: 'team' })
    } else {
      await fetchDriveFiles({ folder_id: null, view: 'team' })
    }
  }
})

// === 文件操作 handlers (PR3.3 接入, 部分留给 PR3.4-3.7 完善 dialog) ===
function onPageChange(page) {
  currentPage.value = page
  fetchDriveFiles({ folder_id: selectedFolderId.value })
}

// v2.0 (2026-07-09): 分页 size 切换 — pageSize 直接更新触发 refetch
function onPageSizeChange(size) {
  pageSize.value = size
  currentPage.value = 1
  fetchDriveFiles({ folder_id: selectedFolderId.value })
}

function handleFilePreview(file) {
  // PR4.6: 接入 FilePreviewDialog
  previewFile.value = file
  showPreviewDialog.value = true
}

const showPreviewDialog = ref(false)
const previewFile = ref(null)

function handleFileRename(file) {
  renameTarget.value = file
  renameTargetType.value = 'file'
  showRenameDialog.value = true
}

async function onRename(payload) {
  try {
    if (payload.type === 'folder') {
      await doRenameFolder(payload.id, payload.newName)
      ElMessage.success('文件夹重命名成功')
    } else {
      await renameFile(payload.id, payload.newName)
      ElMessage.success('文件重命名成功')
    }
    showRenameDialog.value = false
  } catch (e) {
    ElMessage.error(e.message || '重命名失败')
  }
}

function handleFileMove(file) {
  moveTargetFileId.value = file.id
  showMoveDialog.value = true
}

async function onMoveFile(payload) {
  try {
    await moveFile(payload.fileId, payload.targetFolderId)
    showMoveDialog.value = false
    ElMessage.success('文件已移动')
  } catch (e) {
    ElMessage.error(e.message || '移动失败')
  }
}

// === v2 PR1 替换 3 个 stub handlers ===

async function handleFileUpdateVisibility(file) {
  // v2 PR1 实现: 弹出 ElMessageBox.prompt 选 visibility
  // 2026-09 单盘合并: 移除 private 选项 (后端将 private 归一为 team)
  try {
    const { value } = await ElMessageBox.prompt(
      `为文件 "${file.file_name}" 设置可见性 (team 全组 / public 任何人):`,
      '修改可见性',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputPattern: /^(team|public)$/,
        inputErrorMessage: '必须是 team/public 之一',
        inputValue: !file.visibility || file.visibility === 'private' ? 'team' : file.visibility
      }
    )
    await doUpdateVisibility(file.id, value)
    ElMessage.success(`已修改为 ${value}`)
  } catch (e) {
    if (e !== 'cancel' && e !== 'close') {
      ElMessage.error(e.message || '修改失败')
    }
  }
}

// F5 修复 (批次②): handleFileExtractToKb / doConfirmExtract (extract-to-kb 老管线) 已删除,
// 入库知识库唯一入口 = handleFileToKb → ingestToKb (/drive/{id}/to-kb 新管线)。

async function handleFileToKb(file) {
  // W98: 网盘入库 RAG — drive 文件一键"加入知识库"
  // 新管线: 新建 kb 条目 + 完整 RAG 管线 (解析/embedding/分析), 原 drive 行保留
  try {
    const res = await doIngestToKb(file.id)
    if (res?.already_ingested) {
      ElMessage.info('该文件已加入知识库，无需重复入库')
    } else {
      ElMessage.success('已加入知识库，可在知识库问答中检索')
    }
  } catch (e) {
    ElMessage.error(e.message || '加入知识库失败')
  }
}

async function handleFileShareLink(file) {
  // v2 PR1 实现: 打开 ShareDialog
  shareDialogFile.value = file
  showShareDialog.value = true
}

// W72 第 2 批 B-1: Folder 右键菜单 "🔗 分享" → 弹 ShareLinkDialog
function onShareFolder(folder) {
  shareLinkDialogFolder.value = folder
  showShareLinkDialog.value = true
}

// W68 路线 F-4: 桌面端 "查看评论" 入口 (FileCard 右键菜单 → 💬 查看评论)
//   跳到独立评论路由页 DesktopFileCommentsView (mobile 走 MobileFileCommentsView)
//   桌面端访问 /drive/file/:id/comments 可看完整评论列表 + 输入栏
//   与移动端 F-3 long-press 菜单 "查看评论" 入口对等
function handleFileViewComments(file) {
  router.push(`/drive/file/${file.id}/comments`)
}

async function handleFileDelete(file) {
  try {
    await ElMessageBox.confirm(
      `确定删除文件 "${file.title || file.file_name}" 吗？此操作可在 3 天内从回收站恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteFile(file.id)
    if (activeKey.value === file.id) activeKey.value = null  // 批次③: 右栏跟随
    ElMessage.success('已删除')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.message || '删除失败')
    }
  }
}

// === PR3.4 handlers ===
async function onCreateFolder(payload) {
  try {
    const result = await doCreateFolder({
      name: payload.name,
      parentId: payload.parent_id,
      visibility: payload.visibility
    })
    showCreateFolderDialog.value = false
    // v2.29: reset 创建后 cleanup 临时 parent_id 暂存,
    // 下次打开 dialog (工具栏 / 空态 CTA) 默认走 selectedFolderId
    createSubFolderParentId.value = null
    ElMessage.success(`文件夹已创建: ${result.name}`)
    // useFolderTree.createFolder 内部已 fetchTree, 不用再手动刷新
  } catch (e) {
    // v2.29: 失败不 reset, dialog 保持打开, 用户修复后 retry 仍用同一 parent_id
    ElMessage.error(e.message || '创建文件夹失败')
  }
}

// v2.29 (2026-07-12) 右键 FolderTree 触发的"新建子文件夹" handler
//   folderId 可能 null (根项右键) 或 子 folder id
//   暂存到 createSubFolderParentId 覆盖 selectedFolderId, dialog 据此决定 parent_id
function onCreateSubFolder(folderId) {
  createSubFolderParentId.value = folderId  // null = 顶级
  showCreateFolderDialog.value = true
}

// === 计算属性 ===
const currentPathDisplay = computed(() => {
  return selectedFolderId.value
    ? `我的网盘 / 文件夹 #${selectedFolderId.value}`
    : '我的网盘 / 顶级目录'
})

// ============================================================
// 批次③ B 三栏工作台 — 视图状态与接线 (2026-09-05)
// 全部动作接真实既有 handler/composable, 0 stub。
// ============================================================
const quotaInfo = ref(null)
const tableRef = ref(null)

// 活动行 (右栏详情对象; folder 行 key='f-<id>' 不触发展示)
const activeKey = ref(null)
const activeFile = computed(() => {
  const k = activeKey.value
  if (typeof k !== 'number') return null
  return driveFiles.value.find((f) => f.id === k) || null
})
// 切目录/换视图时清活动行 (右栏不残留上一目录的文件)
watch([selectedFolderId, specialView], () => { activeKey.value = null })

function onRowActivate(row, opts = {}) {
  if (!row) { activeKey.value = null; return }
  activeKey.value = row.key
  if (row.kind === 'folder' && opts.keyboard) enterFolder(row.data)
  tableRef.value?.focus?.()
}

function enterFolder(folder) {
  // 与 FolderTree 选中一致: 更新 selectedFolderId → watch 拉该层文件
  selectedFolderId.value = folder.id
  if (!expandedFolderIds.value.has(folder.id)) expandedFolderIds.value.add(folder.id)
}

function openDetailPage(file) {
  router.push(`/drive/file/${file.id}`)
}
function gotoFolder(folderId) {
  selectedFolderId.value = folderId
}

// 下载 (与 FileCard 同路: 原生下载 URL)
function handleFileDownload(file) {
  window.open(`/api/v1/drive/files/${file.id}/download?disposition=attachment`, '_blank')
}

// 版本 dialog (右键/右栏「版本与对比」入口; VersionHistoryDialog 含恢复 + 两版 diff)
const showVersionsDialog = ref(false)
const versionsDialogFile = ref(null)
function openVersionsDialog(file) {
  versionsDialogFile.value = file
  showVersionsDialog.value = true
}
function onRailRefresh() {
  reloadCurrentView()
  fetchFolderTree('team')
}

// ---- 选择 ----
function onSelectAll(v) {
  if (v) selectAll()
  else clearSelection()
}
function onSelectRange(ids) {
  // Shift 连选: 与既有选择并集
  const merged = new Set([...selectedFileIds.value, ...ids])
  selectedFileIds.value = [...merged]
  triggerRef(selectedFileIds)
}

// ---- 列头排序 (file_name / file_size / created_at; 同列翻转) ----
function onColumnSort(prop) {
  if (sortBy.value === prop) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = prop
    sortOrder.value = prop === 'file_name' ? 'asc' : 'desc'
  }
  currentPage.value = 1
  reloadCurrentView()
}

// ---- 拖拽移动落点统一入口 (左树节点 / 表格文件夹行) ----
async function onMoveDrop({ folderId, ids }) {
  if (!ids || !ids.length) return
  if (specialView.value === 'starred') {
    // 收藏视图内 driveFiles 来自 /starred, 移动后本地剔除即可, 但语义上提示回团队盘操作
    ElMessage.info('在「我的收藏」内移动: 将同时移出收藏视图, 属正常')
  }
  const target = findFolderById(folderId)
  try {
    if (ids.length === 1) {
      await moveFile(ids[0], folderId)
    } else {
      await doBatchMove(ids, folderId)
    }
    ElMessage.success(`已移动 ${ids.length} 个文件到「${target?.name || '目标文件夹'}」`)
    clearSelection()
    if (searchQuery.value.trim()) {
      runSearchOrReload()
    } else {
      reloadCurrentView()
    }
    fetchFolderTree('team')
  } catch (e) {
    ElMessage.error(e.message || '移动失败')
  }
}

// ============================================================
// 文件/文件夹 右键菜单 (批次③ 扩容: 由旧 2 项 → 全套, 数据源改表格 row-contextmenu)
// ============================================================
const contextMenuRef = ref(null)
const contextMenuRow = ref(null)  // {kind:'file'|'folder', data}

const contextMenuItems = computed(() => {
  const row = contextMenuRow.value
  if (!row) return []
  if (row.kind === 'folder') {
    return [
      { command: 'f-open', label: '📂 打开' },
      { command: 'f-create-sub', label: '➕ 新建子文件夹' },
      { command: 'f-rename', label: '✏️ 重命名' },
      { command: 'f-share', label: '🔗 分享', divided: true },
      { command: 'f-delete', label: '🗑 删除' },
    ]
  }
  const f = row.data
  return [
    { command: 'ctx-preview', label: '▣ 预览' },
    { command: 'ctx-download', label: '⬇ 下载' },
    { command: 'ctx-detail', label: '🔗 打开完整详情页', divided: true },
    { command: 'ctx-rename', label: '✏️ 重命名' },
    { command: 'ctx-move', label: '📂 移动到…' },
    { command: 'ctx-share', label: '◈ 分享链接' },
    { command: 'ctx-star', label: f.is_starred ? '★ 取消收藏' : '☆ 收藏 (仅自己)' },
    { command: 'ctx-tokb', label: '📚 加入知识库', divided: true },
    { command: 'ctx-versions', label: '🕘 版本与对比…' },
    { command: 'ctx-comments', label: '💬 查看评论' },
    { command: 'ctx-delete', label: '🗑 移入回收站', divided: true },
  ]
})

function onRowContextmenu(row, event) {
  contextMenuRow.value = row
  nextTick(() => contextMenuRef.value?.open?.(event))
}

async function confirmDeleteFolderNode(folder) {
  // 与 FolderTree 树节点删除同规则: 有子项 → 级联 confirm (后端 recursive)
  let folderCount = 0, fileCount = 0
  try {
    const stats = await getChildrenStats(folder.id)
    folderCount = stats?.folder_count ?? 0
    fileCount = stats?.file_count ?? 0
  } catch { /* 计数失败按无子项走 */ }
  const hasChildren = folderCount > 0 || fileCount > 0
  const msg = hasChildren
    ? `文件夹 "${folder.name}" 下还有 ${folderCount} 个子文件夹 + ${fileCount} 个文件, 将连同子项一起移入回收站, 30 天内可整体恢复。`
    : `删除文件夹 "${folder.name}"? 文件夹进入回收站, 30 天内可恢复。`
  try {
    await ElMessageBox.confirm(msg, hasChildren ? '删除文件夹 + 子项 (级联)' : '删除文件夹',
      { type: 'warning', confirmButtonText: hasChildren ? '全部移入回收站' : '删除', cancelButtonText: '取消' })
  } catch { return }
  try {
    await deleteFolderNode(folder.id, { recursive: hasChildren })
    ElMessage.success(hasChildren ? '文件夹与子项已全部移入回收站' : '文件夹已移入回收站')
    if (activeKey.value === 'f-' + folder.id) activeKey.value = null
    fetchFolderTree('team')
    reloadCurrentView()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.message || '删除失败')
  }
}

async function onContextMenuCommand(cmd) {
  const row = contextMenuRow.value
  if (!row) return
  const obj = row.data
  if (row.kind === 'folder') {
    if (cmd === 'f-open') enterFolder(obj)
    else if (cmd === 'f-create-sub') onCreateSubFolder(obj.id)
    else if (cmd === 'f-rename') { renameTarget.value = obj; renameTargetType.value = 'folder'; showRenameDialog.value = true }
    else if (cmd === 'f-share') onShareFolder(obj)
    else if (cmd === 'f-delete') await confirmDeleteFolderNode(obj)
    return
  }
  switch (cmd) {
    case 'ctx-preview': handleFilePreview(obj); break
    case 'ctx-download': handleFileDownload(obj); break
    case 'ctx-detail': openDetailPage(obj); break
    case 'ctx-rename': handleFileRename(obj); break
    case 'ctx-move': handleFileMove(obj); break
    case 'ctx-share': handleFileShareLink(obj); break
    case 'ctx-star': handleFileToggleStar(obj); break
    case 'ctx-tokb': handleFileToKb(obj); break
    case 'ctx-versions': openVersionsDialog(obj); break
    case 'ctx-comments': router.push(`/drive/file/${obj.id}/comments`); break
    case 'ctx-delete': handleFileDelete(obj); break
  }
}

function onContextMenuClose() {
  contextMenuRow.value = null
}
</script>

<style scoped>
.desktop-drive-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-bg-page, #fafbfc);
}

.drive-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  border-bottom: 1px solid var(--color-border-light, #ebeef5);
  background: var(--color-bg-card, #fff);
  gap: 16px;
}

.drive-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
  flex-shrink: 0;
}

.drive-toolbar-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  justify-content: flex-end;
}

.drive-search-input {
  width: 240px;
}

.drive-view-toggle {
  margin-left: 8px;
}

.drive-main {
  display: flex;
  flex: 1;
  min-height: 0;
  transition: background 0.2s;
  position: relative;
}

.drive-main.is-drag-over::before {
  content: '';
  position: absolute;
  inset: 0;
  border: 3px dashed var(--color-primary);
  background: var(--color-primary-bg);
  opacity: 0.35;
  pointer-events: none;
  z-index: 10;
  border-radius: var(--radius-md);
}

/*
 * v77 P2.6-G.3 拖拽 hero — 替代旧 ::after 占位文案 "松开上传文件 (PR3.6 接入上传逻辑)".
 * 走 drive 美化 token (珊瑚橙 primary), 不再硬编码 EP 默认蓝 #409eff.
 */
.drive-drop-hero {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-6) var(--space-8);
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-primary);
  z-index: 11;
  pointer-events: none;
  text-align: center;
}

.drive-drop-hero-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: var(--gradient-cta-button);
  color: var(--el-color-white);
  box-shadow: var(--shadow-glow);
}

.drive-drop-hero-title {
  margin: 0;
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
}

.drive-drop-hero-hint {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.drive-drop-hero-fade-enter-active,
.drive-drop-hero-fade-leave-active {
  transition: opacity var(--duration-normal) var(--ease-out),
              transform var(--duration-normal) var(--ease-out);
}
.drive-drop-hero-fade-enter-from,
.drive-drop-hero-fade-leave-to {
  opacity: 0;
  transform: translate(-50%, -46%) scale(0.96);
}

.drive-sidebar {
  width: 240px;
  border-right: 1px solid var(--color-border-light, #ebeef5);
  background: var(--color-bg-card, #fff);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.drive-sidebar-header {
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-secondary, #606266);
  border-bottom: 1px solid var(--color-border-light);
}

.drive-sidebar-placeholder,
.drive-file-area-placeholder {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--color-text-placeholder, #909399);
  padding: 40px 20px;
}

.placeholder-icon {
  font-size: 48px;
  margin-bottom: 12px;
  color: var(--color-text-disabled, #c0c4cc);
}

.placeholder-text {
  font-size: 14px;
  margin: 0 0 4px 0;
  font-weight: 500;
}

.placeholder-hint {
  font-size: 12px;
  margin: 0;
  color: var(--color-text-placeholder, #909399);
}

.drive-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.drive-breadcrumb {
  padding: 12px 24px;
  border-bottom: 1px solid var(--color-border-light);
  background: var(--color-bg-card, #fff);
}

.drive-file-area {
  flex: 1;
  padding: 24px;
  overflow: auto;
}

.drive-statusbar {
  padding: 8px 24px;
  border-top: 1px solid var(--color-border-light);
  background: var(--color-bg-card, #fff);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--color-text-secondary, #606266);
}

/* F5 修复 (批次②): v2 PR1 extract-to-kb dialog styles (.extract-*) 随 dialog 一并删除 */

/* v2 PR2: 排序 + 类型过滤 bar */
.drive-filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0 12px;
  gap: 12px;
}
.drive-filter-bar-left {
  display: flex;
  gap: 8px;
}
.filter-stat {
  font-size: 13px;
  color: var(--color-text-secondary, #606266);
}

/* ============================================================
 * 批次③ B 三栏工作台样式 (2026-09-05) — 全走 variables.css token,
 * 暗色/6 主题自动跟随; 不依赖 drive-view.css 新增规则 (移动端共用文件零影响)。
 * ============================================================ */
/* ============================================================
 * 批次③ 配色收口 (2026-09-05): 作用域 token 重映射 —
 * 生产全局 --color-primary 是珊橙, 但用户拍板的 style-b 视觉稿是"主页同款深青档案系"
 * (Dashboard.vue --teal #0e766e 血统)。CSS 自定义属性沿 DOM 继承, 在 .drive-workbench
 * 根上重定义即可让全部后代 (drive-view.css 全局 .drive-chip / FolderTree /
 * DriveFileTable / DriveDetailRail / el-pagination accent) 一次换肤,
 * 0 触碰全局 variables.css 与 drive-view.css (移动端共用文件零影响)。
 * ============================================================ */
.drive-workbench {
  --color-primary: #0E766E;
  --color-primary-light: #2A9D8F;
  --color-primary-dark: #0B5D56;
  --color-primary-bg: rgba(14, 118, 110, .09);
  --color-primary-border: rgba(14, 118, 110, .35);
  --color-primary-rgb: 14, 118, 110;
  --gradient-cta-button: linear-gradient(135deg, #0E766E 0%, #12897C 100%);
  --gradient-welcome-hero: linear-gradient(135deg, #0E766E 0%, #198E83 100%);
  --shadow-primary: 0 4px 20px rgba(14, 118, 110, .24);
  --shadow-glow: 0 4px 24px rgba(14, 118, 110, .18);
  /* 金橙 → 琥珀印章色系 (chip ppt 点/星标/收藏高亮都吃这两个) */
  --color-accent: #C77A2E;
  --color-accent-bg: #F6EAD8;
  --color-accent-rgb: 199, 122, 46;
  /* 类型色降饱和 (视觉稿档案系: 砖红/藏蓝/苔绿/紫灰) */
  --color-file-pdf: #B3392F;
  --color-file-pdf-rgb: 179, 57, 47;
  --color-file-doc: #2F5D8A;
  --color-file-doc-rgb: 47, 93, 138;
  --color-file-excel: #3E7A52;
  --color-file-excel-rgb: 62, 122, 82;
  --color-file-image: #7C4E96;
  --color-file-image-rgb: 124, 78, 150;
  --color-file-default: #8F877B;
  --color-warning: #B07C24;
  --color-danger: #C0562F;
  /* 墨线框 (视觉稿 --line-ink) + Element Plus accent (分页/输入聚焦) */
  --wb-frame: rgba(45, 58, 53, .5);
  --el-color-primary: #0E766E;
  --el-color-primary-light-3: #4d8b85;
  --el-color-primary-light-5: #86afa9;
  --el-color-primary-light-7: #b7d1cd;
  --el-color-primary-light-8: #cfe1de;
  --el-color-primary-light-9: #e4f0ee;
  --el-color-primary-dark-2: #0b5d56;
}
[data-theme="dark"] .drive-workbench {
  --color-primary: #35C2A4;
  --color-primary-light: #2A9D8F;
  --color-primary-dark: #5AD0B5;
  --color-primary-bg: rgba(53, 194, 164, .12);
  --color-primary-border: rgba(53, 194, 164, .38);
  --color-primary-rgb: 53, 194, 164;
  --gradient-cta-button: linear-gradient(135deg, #0F8E82 0%, #17766C 100%);
  --gradient-welcome-hero: linear-gradient(135deg, #0F8E82 0%, #35C2A4 100%);
  --shadow-primary: 0 4px 20px rgba(53, 194, 164, .16);
  --color-accent: #E0A45C;
  --color-accent-bg: rgba(224, 164, 92, .12);
  --color-file-pdf: #D96A5F;
  --color-file-doc: #6FA1D2;
  --color-file-excel: #6FAF83;
  --color-file-image: #B08CC9;
  --color-warning: #E0A45C;
  --color-danger: #E07A5F;
  --wb-frame: rgba(160, 175, 162, .45);
  --el-color-primary: #35C2A4;
  --el-color-primary-light-3: #2b8c77;
  --el-color-primary-light-5: #256e5f;
  --el-color-primary-light-7: #1e5147;
  --el-color-primary-light-8: #1a413a;
  --el-color-primary-light-9: #16332d;
  --el-color-primary-dark-2: #5AD0B5;
}

.drive-workbench {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  background: var(--color-bg-page);
}

/* 顶栏 */
.wb-top {
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  height: 56px;
  padding: 0 var(--space-5);
  background: var(--color-bg-card);
  border-bottom: 1.5px solid var(--wb-frame, var(--color-border));
}
.wb-brand { display: inline-flex; align-items: center; gap: 9px; font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); white-space: nowrap; }
.wb-brand-ico { font-size: 18px; }
.wb-vr { width: 1px; height: 22px; background: var(--color-border); }
.wb-search {
  display: inline-flex; align-items: center; gap: 8px;
  width: min(420px, 34vw);
  background: var(--color-bg-page);
  border: 1px solid transparent; border-radius: var(--radius-full);
  padding: 8px 16px;
  transition: border-color var(--duration-normal), box-shadow var(--duration-normal), background var(--duration-normal);
}
.wb-search:focus-within { background: var(--color-bg-card); border-color: var(--color-primary); box-shadow: 0 0 0 3px rgba(var(--color-primary-rgb), .12); }
.wb-search-ico { color: var(--color-text-secondary); flex: none; }
.wb-search input { flex: 1; border: none; outline: none; background: none; font: inherit; font-size: var(--font-size-sm); color: var(--color-text-primary); }
.wb-search input::placeholder { color: var(--color-text-placeholder); }
.wb-sp { flex: 1; }
.wb-cta {
  background: var(--gradient-cta-button) !important;
  border: none !important; color: #fff !important; font-weight: var(--font-weight-semibold);
  box-shadow: 0 3px 12px rgba(var(--color-primary-rgb), .35);
  transition: transform var(--duration-normal) var(--ease-out), box-shadow var(--duration-normal);
}
.wb-cta:hover { transform: translateY(-1px); box-shadow: var(--shadow-primary); }

/* 三栏 */
.wb-body {
  flex: 1;
  display: flex;
  min-height: 0;
  position: relative;
  gap: 0;
}
.wb-rail {
  width: 236px; flex: none;
  display: flex; flex-direction: column; min-height: 0;
  background: var(--color-bg-card);
  border-right: 1.5px solid var(--wb-frame, var(--color-border));
  padding: 10px 8px 0;
}
.wb-rail-cap { font-size: 10.5px; letter-spacing: .12em; color: var(--color-text-secondary); padding: 4px 10px 6px; }
.wb-tree { flex: 1; min-height: 0; overflow-y: auto; }
.wb-rail-foot { flex: none; padding: 8px 2px 12px; }

.wb-center {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column; min-height: 0;
  padding: 10px 14px 12px;
  gap: 8px;
}
.wb-crumbs { flex: none; display: flex; align-items: center; gap: 10px; font-size: var(--font-size-sm); }
.wb-crumbs :deep(.el-breadcrumb) { font-size: var(--font-size-sm); }
.wb-crumb-search { color: var(--color-primary-dark); font-size: var(--font-size-xs); }
.wb-total { font-size: var(--font-size-xs); color: var(--color-text-secondary); white-space: nowrap; }
.wb-density {
  border: 1px solid var(--color-border); background: var(--color-bg-card);
  border-radius: var(--radius-md); font-size: var(--font-size-xs); color: var(--color-text-regular);
  padding: 4px 10px; white-space: nowrap;
}
.wb-density:hover { border-color: var(--color-primary-border); color: var(--color-primary-dark); }

.wb-ctools { flex: none; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.wb-lab { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.wb-lab--gap { margin-left: 6px; }
.wb-kbd-hint { margin-left: auto; font-size: 10.5px; color: var(--color-text-placeholder); white-space: nowrap; }
@media (max-width: 1400px) { .wb-kbd-hint { display: none; } }

.wb-listarea { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.wb-listarea > * { flex: 1; min-height: 0; }

.wb-dock { flex: none; display: flex; flex-direction: column; }
.wb-dock :deep(.drive-batch-toolbar) { border: 1px solid var(--color-border); border-top: none; border-radius: 0 0 var(--radius-lg) var(--radius-lg); box-shadow: var(--shadow-sm); background: var(--color-bg-card); }

.wb-railright { width: 340px; flex: none; border-radius: 0; }

/* 拖拽悬停整区提示 */
.wb-body.is-drag-over::before {
  content: '';
  position: absolute; inset: 0;
  border: 2.5px dashed var(--color-primary);
  background: rgba(var(--color-primary-rgb), .05);
  border-radius: var(--radius-md);
  pointer-events: none;
  z-index: 12;
}

/* 窄屏兜底: 右栏可横向滚 (workbench 面向 ≥1280 桌面) */
@media (max-width: 1180px) {
  .wb-railright { width: 292px; }
}

/* 旧 drive-drop-hero 沿用 (scoped 块里已有定义), 此处仅调层级到三栏之上 */
.drive-drop-hero { z-index: 20; }
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  PR3.1 骨架仅 var(--color-*) token, dark mode 自动跟随, 暂不需要 dark 块
  PR3.7 统一审计时再加 dark 块
-->
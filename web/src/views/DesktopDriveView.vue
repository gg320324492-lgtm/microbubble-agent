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
        <span class="wb-brand-ico" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="M3 6.5A2.5 2.5 0 0 1 5.5 4h3.2c.7 0 1.35.3 1.8.8l.9 1.2h5.3A2.5 2.5 0 0 1 19 8.5V17a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 3 17z" /></svg>
        </span>课题组网盘
      </span>
      <span class="wb-vr"></span>
      <label class="wb-search">
        <el-icon class="wb-search-ico"><Search /></el-icon>
        <input
          ref="searchInputRef"
          v-model="searchQuery"
          placeholder="搜索全组文件名 (支持中文, 输入即搜)"
          aria-label="搜索全组文件名"
        />
        <kbd>Ctrl K</kbd>
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
        <div class="wb-rail-cap">结构
          <button type="button" class="wb-cap-add" title="新建文件夹" @click="showCreateFolderDialog = true">
            <el-icon><Plus /></el-icon>
          </button>
        </div>
        <FolderTree
          class="wb-tree"
          :folder-tree="folderTree"
          :selected-folder-id="selectedFolderId"
          :expanded-folder-ids="expandedFolderIds"
          :loading="treeLoading"
          :load-error="treeLoadError"
          :special-view="specialView"
          :team-count="sideCounts.team"
          :starred-count="sideCounts.starred"
          :trash-count="sideCounts.trash"
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
          <!-- 批次⑩.5 (用户选型 BACK D): 前进后退对键 (访问历史) + 面包屑祖先级可点击跳转 -->
          <span class="wb-navbtns">
            <button
              type="button" class="wb-navbtn" :disabled="navIndex <= 0"
              title="后退" aria-label="后退"
              @click="navGo(-1)"
            ><svg viewBox="0 0 24 24"><path d="M19 12H5m0 0 6 6m-6-6 6-6" /></svg></button>
            <button
              type="button" class="wb-navbtn" :disabled="navIndex >= navHistory.length - 1"
              title="前进" aria-label="前进"
              @click="navGo(1)"
            ><svg viewBox="0 0 24 24"><path d="M5 12h14m0 0-6-6m6 6-6 6" /></svg></button>
          </span>
          <template v-for="(c, i) in crumbItems" :key="c.key">
            <span v-if="i > 0" class="wb-crumb-sep">/</span>
            <button
              type="button" class="wb-crumb"
              :class="{ 'is-cur': i === crumbItems.length - 1 }"
              :disabled="i === crumbItems.length - 1"
              @click="gotoCrumb(c, i)"
            >{{ c.name }}</button>
          </template>
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
          <!-- 批次⑨ (用户选型 SORT 2): 分段控件 — 灰轨 + 白色滑块跟手滑动, 无箭头 (方向由表头承担) -->
          <div ref="segRef" class="wb-seg" role="group" aria-label="排序方式">
            <span
              class="wb-seg-thumb" aria-hidden="true"
              :style="segThumb.ready ? { width: segThumb.w + 'px', transform: `translateX(${segThumb.x}px)` } : { opacity: 0 }"
            ></span>
            <button
              v-for="opt in SORT_OPTIONS" :key="opt.value" type="button"
              class="wb-seg-btn" :class="{ 'is-active': sortKey === opt.value }"
              :aria-pressed="sortKey === opt.value"
              @click="handleSortChange(opt.value)"
            >{{ opt.label }}</button>
          </div>
          <span class="wb-lab wb-lab--gap">类型</span>
          <button
            v-for="opt in FILE_TYPE_OPTIONS" :key="opt.value || 'all'" type="button"
            class="drive-chip" :aria-pressed="fileType === opt.value || (!fileType && opt.value === null)"
            :class="{ 'is-active': fileType === opt.value || (!fileType && opt.value === null) }"
            @click="handleFileTypeChange(opt.value)"
          >
            <svg
              v-if="opt.type" class="wb-type-ic"
              :style="{ stroke: TYPE_ICON_COLOR[opt.type] }"
              viewBox="0 0 24 24" aria-hidden="true" v-html="TYPE_ICONS[opt.type]"
            ></svg>
            {{ opt.label }}
          </button>
          <!-- 批次⑧ 对齐视觉稿 .hint: kbd 键帽徽章行 (↑↓/␣/Del/拖拽), 不再纯文字点隔 -->
          <span class="wb-kbd-hint">
            <span><kbd>↑</kbd><kbd>↓</kbd> 移动</span>
            <span><kbd>␣</kbd> 预览</span>
            <span><kbd>Enter</kbd> 详情</span>
            <span><kbd>Del</kbd> 回收站</span>
            <span><kbd>拖拽</kbd> 移到左栏夹</span>
          </span>
        </div>

        <div class="wb-listarea">
          <!-- specialView 内嵌面板 (右栏/表格/dock 隐藏) -->
          <FileRequestListPanel v-if="specialView === 'requests'" />
          <DriveTrashPanel v-else-if="specialView === 'trash'" />
          <DriveFileTable
            v-else
            ref="tableRef"
            :files="driveFiles"
            :folders="tableFolders"
            :selected-folder-ids="selectedFolderIds"
            @select-toggle-folder="onToggleFolderSelect"
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
            :selected-count="selectedFileIds.length + selectedFolderIds.length"
            :total-count="driveFiles.length + tableFolders.length"
            :selected-bytes="selectedBytes"
            context="files"
            @select-all="onDockSelectAll"
            @clear="onSelectAll(false)"
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
        v-if="isTableMode"
        class="wb-railright"
        :file="activeFile"
        :folder="activeFolder"
        :folder-children="activeFolderChildren"
        :recent="driveFiles"
        @pick-file="(f) => (activeKey = f.id)"
        @preview="handleFilePreview"
        @download="handleFileDownload"
        @share="handleFileShareLink"
        @toggle-star="handleFileToggleStar"
        @open-folder="enterFolder"
        @share-folder="onShareFolder"
        @toggle-star-folder="(f) => handleFileToggleStar(f, 'folder')"
        @rename="handleFileRename"
        @move="handleFileMove"
        @delete="handleFileDelete"
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
        :files="moveTargetFiles"
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
import { ref, computed, reactive, triggerRef, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
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
  sortBy, sortOrder, starredOnly, fileType,
  // 批次⑩: 收藏视图合并的文件夹条目
  starredFolders
} = storeToRefs(driveFilesStore)
const {
  fetchFiles: fetchDriveFiles,
  fetchStarred,
  deleteFile,
  renameFile,
  moveFile,
  updateVisibility: doUpdateVisibility,
  // 2026-09-05: 入库入口已全部移除 — 网盘文件上传后默认自动入库 RAG (后端 Celery)
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
  // 批次⑨ (2026-09-05, 用户选型 SORT 2): 排序改分段控件, emoji 箭头退役 (方向由表头承担)
  { value: 'created_at:desc', label: '最新上传' },
  { value: 'created_at:asc',  label: '最早上传' },
  { value: 'updated_at:desc', label: '最近修改' },
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
  { value: 'pdf',   type: 'pdf',   label: 'PDF' },
  { value: 'word',  type: 'word',  label: 'Word' },
  { value: 'ppt',   type: 'ppt',   label: 'PPT' },
  { value: 'excel', type: 'excel', label: 'Excel' },
  // 媒体族
  { value: 'image', type: 'image', label: '图片' },
  { value: 'video', type: 'video', label: '视频' },
  { value: 'audio', type: 'audio', label: '音频' },
  // 其他
  { value: 'text',  type: 'text',  label: '文本' },
]

// 批次⑨ (用户选型 B): 类型 chip 图标 = 类型色细描边 SVG (与树/表描边文件夹同语言),
// emoji + 色点退役。路径为 lucide 风手写 24 viewBox, stroke 走 TYPE_ICON_COLOR。
const TYPE_ICONS = {
  pdf: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h6"/>',
  word: '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>',
  ppt: '<path d="M3 4h18"/><path d="M5 4v9a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V4"/><path d="M12 15v3M8 21l4-3 4 3"/>',
  excel: '<rect x="3.5" y="4" width="17" height="16" rx="2"/><path d="M3.5 10h17M3.5 15h17M12 4v16"/>',
  image: '<rect x="3.5" y="4" width="17" height="16" rx="2"/><circle cx="9" cy="9.5" r="1.8"/><path d="m20.5 15.5-3.6-3.6a1.8 1.8 0 0 0-2.5 0L7 19"/>',
  video: '<rect x="2.5" y="6" width="13.5" height="12" rx="2"/><path d="m16 10.5 5-3v9l-5-3"/>',
  audio: '<path d="M9.5 17.5V6l10-2v11.5"/><circle cx="7" cy="17.5" r="2.5"/><circle cx="17" cy="15.5" r="2.5"/>',
  text: '<path d="M4 6h16M4 12h11M4 18h16"/>',
}
const TYPE_ICON_COLOR = {
  pdf: 'var(--color-file-pdf)',
  word: 'var(--color-file-doc)',
  ppt: 'var(--color-warning)',
  excel: 'var(--color-file-excel)',
  image: 'var(--color-file-image)',
  video: 'var(--color-file-video)',
  audio: 'var(--color-warning)',
  text: 'var(--color-file-text)',
}

const sortKey = computed(() => `${sortBy.value}:${sortOrder.value}`)

// 批次⑨ 分段控件滑块: 白色 thumb 跟随 active 段滑动 (offsetLeft/width 实测,
// sortKey 变化 → nextTick 重测, resize 跟随; 首测前 opacity 0 避免从原点飞入)
const segRef = ref(null)
const segThumb = reactive({ x: 0, w: 0, ready: false })
function measureSegThumb() {
  const el = segRef.value
  if (!el) return
  const btn = el.querySelector('.wb-seg-btn.is-active')
  if (!btn) return
  segThumb.x = btn.offsetLeft
  segThumb.w = btn.offsetWidth
  segThumb.ready = true
}
watch(sortKey, () => nextTick(measureSegThumb))
onMounted(() => {
  nextTick(measureSegThumb)
  window.addEventListener('resize', measureSegThumb)
})
onBeforeUnmount(() => window.removeEventListener('resize', measureSegThumb))

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
  } else if (specialView.value === 'recent') {
    // 批次⑥ (视觉稿「最近上传」快捷项): 全盘跨夹按上传时间倒序
    starredOnly.value = false
    await fetchDriveFiles({
      folder_id: null,
      include_subfolders: 'true',
      view: 'team',
      sort_by: 'created_at',
      sort_order: 'desc',
    })
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
  const hasFiles = selectedFileIds.value.length > 0
  const hasFolders = selectedFolderIds.value.length > 0
  if (!hasFiles && !hasFolders) return
  const parts = []
  if (hasFiles) parts.push(`${selectedFileIds.value.length} 个文件`)
  if (hasFolders) parts.push(`${selectedFolderIds.value.length} 个文件夹 (连同其内容)`)
  try {
    await ElMessageBox.confirm(
      `确定要删除 ${parts.join(' 和 ')} 吗?`,
      '批量删除',
      { type: 'warning' }
    )
    let succeeded = 0
    const skipped = []
    if (hasFiles) {
      const resp = await batchSoftDelete(selectedFileIds.value)
      succeeded += resp.succeeded_count || 0
      if (resp.skipped_ids?.length) skipped.push(...resp.skipped_ids)
    }
    // 批次⑩.1: 勾选的文件夹走文件夹级联软删 (子项一起进回收站, 可整体恢复)
    for (const fid of selectedFolderIds.value) {
      try {
        await deleteFolderNode(fid, { recursive: true })
        succeeded += 1
      } catch (e) {
        skipped.push(fid)
      }
    }
    if (skipped.length) {
      ElMessage.warning(`已删除 ${succeeded} 项, 跳过 ${skipped.length} 项`)
    } else {
      ElMessage.success(`已删除 ${succeeded} 项`)
    }
    refreshSideCounts()
    await fetchFolderTree()
    reloadCurrentView()
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
    refreshSideCounts()
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

async function handleFileToggleStar(target, kind = 'file') {
  // 批次⑩: 文件夹行也带收藏星 (per-user, 与文件收藏同构)
  if (kind === 'folder') {
    try {
      await axios.post(`/api/v1/folders/${target.id}/toggle-star`)
      await fetchFolderTree()      // 树节点 is_starred 刷新
      refreshSideCounts()          // 我的收藏 计数 (文件+文件夹)
      if (specialView.value === 'starred') await reloadCurrentView()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || e.message || '切换收藏失败')
    }
    return
  }
  try {
    await toggleStar(target.id)
    refreshSideCounts()
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
// 批次⑩.15: 待移档案对象 (供 MoveDialog 文件卡展示; 单选=1项, 批量=N项)
const moveTargetFiles = computed(() => {
  const v = moveTargetFileId.value
  if (v == null) return []
  const ids = Array.isArray(v) ? v : [v]
  return driveFiles.value.filter((f) => ids.includes(f.id))
})

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
    if (Array.isArray(payload.fileId)) {
      // 批次⑩.15 修复: 批量移动旧代码走 moveFile(数组) → PUT /files/undefined
      const resp = await doBatchMove(payload.fileId, payload.targetFolderId)
      showMoveDialog.value = false
      ElMessage.success(`已移动 ${resp?.succeeded_count ?? payload.fileId.length} 个文件`)
    } else {
      await moveFile(payload.fileId, payload.targetFolderId)
      showMoveDialog.value = false
      ElMessage.success('文件已移动')
    }
    refreshSideCounts()
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

// 2026-09-05: handleFileToKb / handleBatchIngestKb / doIngestToKb 已删除 —
// 网盘文件默认自动入库 (上传/版本更新触发后端 drive_ingest_tasks), 无需手动入口。

async function handleFileShareLink(file) {
  // v2 PR1 实现: 打开 ShareDialog
  shareDialogFile.value = file
  showShareDialog.value = true
}

// 批次⑥ dock 对齐视觉稿: 选中体积
const selectedBytes = computed(() => {
  const ids = new Set(selectedFileIds.value)
  const filesSum = driveFiles.value.filter((f) => ids.has(f.id)).reduce((s, f) => s + (f.file_size || 0), 0)
  // 批次⑩.1: 勾选的文件夹按递归大小计入
  const fids = new Set(selectedFolderIds.value)
  const foldersSum = tableFolders.value.filter((f) => fids.has(f.id)).reduce((s, f) => s + (f.size_bytes || 0), 0)
  return filesSum + foldersSum
})

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
    refreshSideCounts()
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

// 批次⑧ 对齐视觉稿树计数: 团队共享盘 (view=team total) / 我的收藏 / 回收站
// 三个 mono 计数 — page_size=1 只取 total, 挂载拉一次, 收藏/删除/恢复动作后刷新
const sideCounts = reactive({ team: null, starred: null, trash: null })
async function refreshSideCounts() {
  try {
    const [team, starred, trash] = await Promise.allSettled([
      axios.get('/api/v1/drive/files', { params: { view: 'team', page: 1, page_size: 1 } }),
      axios.get('/api/v1/drive/starred', { params: { page: 1, page_size: 1 } }),
      axios.get('/api/v1/drive/trash', { params: { page: 1, page_size: 1 } }),
    ])
    if (team.status === 'fulfilled') sideCounts.team = team.value.data?.total ?? null
    // 批次⑩: 收藏计数 = 收藏文件 + 收藏文件夹
    if (starred.status === 'fulfilled') {
      sideCounts.starred = (starred.value.data?.total || 0) + (starred.value.data?.folder_total || 0) || null
    }
    if (trash.status === 'fulfilled') sideCounts.trash = trash.value.data?.total ?? null
  } catch { /* 计数拉取失败静默 (null = 不显示) */ }
}
onMounted(refreshSideCounts)
watch(specialView, () => refreshSideCounts())

// ── 批次⑩.5 (用户选型 BACK D): 访问历史 + 前进/后退 ──
// 位置 = {specialView, folderId}; 自然导航在 watch 里 push (去重连续同位),
// navGo 恢复历史时置 navRestoring 防回写。
const navHistory = ref([])
const navIndex = ref(-1)
const navRestoring = ref(false)
function pushNav() {
  if (navRestoring.value) return
  const loc = { specialView: specialView.value, folderId: selectedFolderId.value }
  const cur = navHistory.value[navIndex.value]
  if (cur && cur.specialView === loc.specialView && cur.folderId === loc.folderId) return
  navHistory.value = navHistory.value.slice(0, navIndex.value + 1)
  navHistory.value.push(loc)
  navIndex.value = navHistory.value.length - 1
}
async function navGo(delta) {
  const idx = navIndex.value + delta
  if (idx < 0 || idx >= navHistory.value.length) return
  navRestoring.value = true
  navIndex.value = idx
  const loc = navHistory.value[idx]
  specialView.value = loc.specialView
  selectedFolderId.value = loc.folderId
  if (loc.folderId != null && !expandedFolderIds.value.has(loc.folderId)) {
    expandedFolderIds.value.add(loc.folderId)
  }
  await nextTick()
  navRestoring.value = false
}
onMounted(pushNav)

// ── 批次⑩.5: 面包屑可点击跳转 (祖先级直达, 当前级不可点) ──
const crumbItems = computed(() => {
  const items = [{ key: 'home', name: '课题组网盘', loc: { specialView: 'team', folderId: null } }]
  if (specialView.value === 'team') {
    items.push({ key: 'team', name: '团队共享盘', loc: { specialView: 'team', folderId: null } })
    for (const f of folderBreadcrumb.value) {
      items.push({ key: 'f-' + f.id, name: f.name, loc: { specialView: 'team', folderId: f.id } })
    }
  } else if (specialView.value === 'starred') {
    items.push({ key: 'starred', name: '我的收藏', loc: { specialView: 'starred', folderId: null } })
  } else if (specialView.value === 'recent') {
    items.push({ key: 'recent', name: '最近上传', loc: { specialView: 'recent', folderId: null } })
  } else if (specialView.value === 'trash') {
    items.push({ key: 'trash', name: '回收站', loc: { specialView: 'trash', folderId: null } })
  } else if (specialView.value === 'requests') {
    items.push({ key: 'requests', name: '文件请求', loc: { specialView: 'requests', folderId: null } })
  }
  return items
})
function gotoCrumb(c, idx) {
  specialView.value = c.loc.specialView
  selectedFolderId.value = c.loc.folderId
  // 树展开到该层 (沿途祖先一并展开, FolderTree 高亮同步)
  for (const it of crumbItems.value.slice(0, idx + 1)) {
    if (it.loc.folderId != null && !expandedFolderIds.value.has(it.loc.folderId)) {
      expandedFolderIds.value.add(it.loc.folderId)
    }
  }
}

// ── 批次⑩.1: 文件夹勾选 (与文件勾选分模型 — id 空间不同, 文件夹键由父层持有) ──
const selectedFolderIds = ref([])
// 表格当前展示的文件夹行 (team 层级树 或 收藏视图合并的文件夹)
const tableFolders = computed(() => {
  if (isSearching.value) return []
  return specialView.value === 'starred' ? (starredFolders.value || []) : currentSubFolders.value
})
function onToggleFolderSelect(folderId) {
  const i = selectedFolderIds.value.indexOf(folderId)
  if (i >= 0) selectedFolderIds.value.splice(i, 1)
  else selectedFolderIds.value.push(folderId)
}
function onDockSelectAll() {
  const all = selectedFileIds.value.length === driveFiles.value.length &&
    selectedFolderIds.value.length === tableFolders.value.length &&
    (driveFiles.value.length + tableFolders.value.length) > 0
  onSelectAll(!all)
}

// 顶栏搜索 kbd 提示兑现: Ctrl/⌘+K 聚焦搜索框 (视觉稿 gsearch kbd 同款交互)
const searchInputRef = ref(null)
function onGlobalSearchKey(ev) {
  if ((ev.ctrlKey || ev.metaKey) && (ev.key === 'k' || ev.key === 'K')) {
    ev.preventDefault()
    searchInputRef.value?.focus?.()
  }
}
onMounted(() => window.addEventListener('keydown', onGlobalSearchKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onGlobalSearchKey))

// 活动行 (右栏详情对象; folder 行 key='f-<id>' → 文件夹预览态)
const activeKey = ref(null)
const activeFile = computed(() => {
  const k = activeKey.value
  if (typeof k !== 'number') return null
  return driveFiles.value.find((f) => f.id === k) || null
})

// 批次⑩.14 (用户选型 RAIL A 清单式): 文件夹预览态 — 点文件夹行时右栏显示下一级内容
const activeFolder = computed(() => {
  const k = activeKey.value
  if (typeof k !== 'string' || !k.startsWith('f-')) return null
  const fid = Number(k.slice(2))
  return tableFolders.value.find((f) => f.id === fid) || null
})
const activeFolderChildren = computed(() => {
  const f = activeFolder.value
  if (!f) return []
  return findFolderById(f.id)?.children || []
})
// 切目录/换视图时清活动行 + 文件夹勾选 (右栏不残留上一目录的文件)
watch([selectedFolderId, specialView], () => {
  activeKey.value = null
  selectedFolderIds.value = []
  pushNav()
})

// 批次⑦: 勾选 checkbox 也让右栏换档 (视觉稿行为 = 选中即可见详情;
// 勾选事件在表格里 click.stop 不走 row-activate, 这里从选择集补上)
watch(selectedFileIds, (ids, prev) => {
  if (ids.length && ids.length > (prev?.length || 0)) {
    const last = ids[ids.length - 1]
    if (typeof last === 'number') activeKey.value = last
  }
})

function onRowActivate(row, opts = {}) {
  if (!row) { activeKey.value = null; return }
  activeKey.value = row.key
  if (row.kind === 'folder' && opts.keyboard) enterFolder(row.data)
  tableRef.value?.focus?.()
}

function enterFolder(folder) {
  // 与 FolderTree 选中一致: 更新 selectedFolderId → watch 拉该层文件
  // 批次⑩: 从收藏视图双击进入文件夹 = 离开收藏列表, 切到该文件夹的普通视图
  if (specialView.value === 'starred') specialView.value = null
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
  // 批次⑩.1: 表头全选覆盖 文件 + 文件夹 两套选择
  if (v) {
    selectAll()
    selectedFolderIds.value = tableFolders.value.map((f) => f.id)
  } else {
    clearSelection()
    selectedFolderIds.value = []
  }
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
      { command: 'f-open', label: '打开' },
      { command: 'f-create-sub', label: '新建子文件夹' },
      { command: 'f-rename', label: '重命名' },
      { command: 'f-share', label: '分享', divided: true },
      { command: 'f-delete', label: '删除' },
    ]
  }
  const f = row.data
  return [
    { command: 'ctx-preview', label: '预览' },
    { command: 'ctx-download', label: '下载' },
    { command: 'ctx-detail', label: '打开完整详情页', divided: true },
    { command: 'ctx-rename', label: '重命名' },
    { command: 'ctx-move', label: '移动到…' },
    { command: 'ctx-share', label: '分享链接' },
    { command: 'ctx-star', label: f.is_starred ? '取消收藏' : '收藏 (仅自己)' },
    { command: 'ctx-versions', label: '版本与对比…' },
    { command: 'ctx-comments', label: '查看评论' },
    { command: 'ctx-delete', label: '移入回收站', divided: true },
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
  /* 批次⑧: 边框暖纸化 (视觉稿 --line #E5E1D8) — 全局 token 偏冷灰, 作用域内重映射 */
  --color-border: #E5E1D8;
  --color-border-light: #ECE9E0;
  /* 批次⑨ B 选型: 类型 chip 描边图标补齐 video/text 专用色 (视觉稿 --video/--textfile) */
  --color-file-video: #A84B6F;
  --color-file-text: #6B6152;
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
  --color-border: #3a3d45;
  --color-border-light: #2a2d35;
  --color-file-video: #D990AE;
  --color-file-text: #A39B8B;
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

/* 顶栏 (视觉稿 .top: 52px / 1px 亮线) */
.wb-top {
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--space-3);
  height: 52px;
  padding: 0 18px;
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border);
}
.wb-brand { display: inline-flex; align-items: center; gap: 9px; font-size: 14.5px; font-weight: var(--font-weight-semibold); white-space: nowrap; }
.wb-brand-ico {
  width: 26px; height: 26px; border-radius: 7px; flex: none;
  background: var(--gradient-cta-button); display: grid; place-items: center;
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), .3);
}
.wb-brand-ico svg { width: 15px; height: 15px; fill: #fff; }
.wb-vr { width: 1px; height: 22px; background: var(--color-border); }
.wb-search {
  display: inline-flex; align-items: center; gap: 8px;
  width: 380px;
  background: var(--color-bg-page);
  border: 1px solid transparent; border-radius: var(--radius-md);
  padding: 7px 12px;
  transition: border-color var(--duration-normal), box-shadow var(--duration-normal), background var(--duration-normal);
}
.wb-search:focus-within { background: var(--color-bg-card); border-color: var(--color-primary); box-shadow: 0 0 0 3px rgba(var(--color-primary-rgb), .12); }
.wb-search-ico { color: var(--color-text-secondary); flex: none; }
.wb-search input { flex: 1; border: none; outline: none; background: none; font: inherit; font-size: var(--font-size-sm); color: var(--color-text-primary); }
.wb-search input::placeholder { color: var(--color-text-placeholder); }
.wb-search kbd {
  font-family: var(--font-mono, Consolas, monospace); font-size: 10px;
  color: var(--color-text-secondary); background: var(--color-bg-card);
  border: 1px solid var(--color-border); border-bottom-width: 2px; border-radius: 4px;
  padding: 0 5px; white-space: nowrap;
}
.wb-sp { flex: 1; }
.wb-cta {
  background: var(--gradient-cta-button) !important;
  border: none !important; color: #fff !important; font-weight: var(--font-weight-semibold);
  box-shadow: 0 3px 12px rgba(var(--color-primary-rgb), .35);
  transition: transform var(--duration-normal) var(--ease-out), box-shadow var(--duration-normal);
}
.wb-cta:hover { transform: translateY(-1px); box-shadow: var(--shadow-primary); }
/* 批次⑥: 顶栏三键缩小到视觉稿 tbtn 尺寸 (头像圈 .wb-me 已删 — 与全局顶栏用户卡片重复) */
.wb-top .drive-toolbar-btn { font-size: var(--font-size-xs); padding: 7px 12px; height: auto; color: var(--color-text-regular); }
.wb-top .drive-toolbar-btn:hover { border-color: var(--color-primary-border); color: var(--color-primary-dark); }
/* 批次⑨ 按钮微交互: 统一 hover 抬升 / 按下回弹 / 键盘焦点环 (workbench 作用域) */
.wb-top .drive-toolbar-btn,
.wb-cta { transition: transform var(--duration-fast) var(--ease-out, ease), box-shadow var(--duration-fast), border-color var(--duration-fast), color var(--duration-fast); }
.wb-top .drive-toolbar-btn:hover { transform: translateY(-1px); }
.wb-top .drive-toolbar-btn:active { transform: translateY(0) scale(.97); }
.wb-cta:active { transform: translateY(0) scale(.97); box-shadow: 0 1px 6px rgba(var(--color-primary-rgb), .25); }
.wb-top .drive-toolbar-btn:focus-visible,
.wb-cta:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }

/* 三栏 */
.wb-body {
  flex: 1;
  display: flex;
  min-height: 0;
  position: relative;
  gap: 0;
}
.wb-rail {
  width: 232px; flex: none;
  display: flex; flex-direction: column; min-height: 0;
  background: var(--color-bg-card);
  border-right: 1px solid var(--color-border);
  padding: 12px 10px 0;
}
.wb-rail-cap { font-size: 10.5px; letter-spacing: .12em; color: var(--color-text-secondary); padding: 6px 10px 5px; display: flex; align-items: center; justify-content: space-between; }
.wb-cap-add {
  border: none; background: none; cursor: pointer;
  color: var(--color-text-secondary); padding: 2px 4px; border-radius: 4px;
  display: grid; place-items: center;
  transition: background var(--duration-fast), color var(--duration-fast), transform var(--duration-fast);
}
.wb-cap-add:hover { background: var(--color-bg-page); color: var(--color-primary-dark); }
.wb-cap-add:active { transform: scale(.88); }
.wb-tree { flex: 1; min-height: 0; overflow-y: auto; }
.wb-rail-foot { flex: none; padding: 8px 2px 12px; }

.wb-center {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column; min-height: 0;
  padding: 10px 14px 12px;
  gap: 8px;
}
.wb-crumbs { flex: none; display: flex; align-items: center; gap: 4px; font-size: var(--font-size-sm); }
/* 批次⑩.5 (BACK D): 手写面包屑 — 祖先级可点 (hover 浮起 + 深青), 当前级墨色加粗不可点 */
.wb-crumb {
  border: none; background: none; font: inherit; font-size: var(--font-size-sm);
  color: var(--color-text-secondary); padding: 3px 6px; border-radius: 5px; cursor: pointer;
  white-space: nowrap;
  transition: background var(--duration-fast), color var(--duration-fast);
}
.wb-crumb:hover { background: var(--color-bg-card); color: var(--color-primary-dark); }
.wb-crumb.is-cur { color: var(--color-text-primary); font-weight: var(--font-weight-semibold); cursor: default; }
.wb-crumb.is-cur:hover { background: none; color: var(--color-text-primary); }
.wb-crumb:disabled { cursor: default; }
.wb-crumb-sep { color: var(--color-text-placeholder); }
/* 前进/后退对键: 圆形 26px, 无历史置灰 */
.wb-navbtns { display: inline-flex; gap: 6px; margin-right: 8px; }
.wb-navbtn {
  width: 26px; height: 26px; min-height: 0; border-radius: 50%; padding: 0;
  border: 1px solid var(--color-border); background: var(--color-bg-card);
  color: var(--color-text-regular); display: grid; place-items: center; cursor: pointer;
  transition: transform var(--duration-fast), border-color var(--duration-fast), color var(--duration-fast), background var(--duration-fast);
}
.wb-navbtn svg { width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.wb-navbtn:hover:not(:disabled) { color: var(--color-primary-dark); border-color: var(--color-primary-border); }
.wb-navbtn:active:not(:disabled) { transform: scale(.92); }
.wb-navbtn:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.wb-navbtn:disabled { color: var(--color-text-placeholder); background: var(--color-bg-page); cursor: default; }
/* mobile-base 的 button{min-height:44px} 触觉目标规则会把面包屑/密度键等小控件撑高 — 桌面端收回 */
.wb-crumbs .wb-crumb,
.wb-density,
.wb-cap-add { min-height: 0; }
.wb-crumb-search { color: var(--color-primary-dark); font-size: var(--font-size-xs); }
/* 视觉稿 .sz: mono 11px text-4 */
.wb-total { font-family: var(--font-mono, Consolas, monospace); font-size: 11px; color: var(--color-text-placeholder); white-space: nowrap; }
.wb-density {
  border: 1px solid var(--color-border); background: var(--color-bg-card);
  border-radius: var(--radius-md); font-size: var(--font-size-xs); color: var(--color-text-regular);
  padding: 4px 10px; white-space: nowrap;
  transition: transform var(--duration-fast), border-color var(--duration-fast), color var(--duration-fast);
}
.wb-density:hover { border-color: var(--color-primary-border); color: var(--color-primary-dark); transform: translateY(-1px); }
.wb-density:active { transform: translateY(0) scale(.94); }
.wb-density:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }

.wb-ctools { flex: none; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.wb-lab { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.wb-lab--gap { margin-left: 6px; }
/* 批次⑧ 对齐视觉稿 .fchip: 5px 11px / 12px 字; active=浅青染色深青字 (非渐变实底)。
   全局 .drive-chip.is-active 带 !important, 此处同名 !important + 更高特异性压过 */
.wb-ctools .drive-chip { padding: 4px 11px; font-size: var(--font-size-xs); gap: 5px; transition: transform var(--duration-fast) var(--ease-out, ease), background var(--duration-fast), border-color var(--duration-fast), color var(--duration-fast); }
.wb-ctools .drive-chip:hover { transform: translateY(-1px); }
.wb-ctools .drive-chip:active { transform: translateY(0) scale(.95); }
.wb-ctools .drive-chip:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.wb-ctools .drive-chip[aria-pressed="true"],
.wb-ctools .drive-chip.is-active {
  background: var(--color-primary-bg) !important;
  border-color: var(--color-primary-border) !important;
  color: var(--color-primary-dark) !important;
  font-weight: var(--font-weight-semibold);
  box-shadow: none;
}
/* 批次⑨ (用户选型 B): 类型 chip 内 14px 类型色描边图标 (emoji/色点退役) */
.wb-type-ic { width: 14px; height: 14px; fill: none; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; flex: none; }
/* 批次⑨ (用户选型 SORT 2): 分段控件 — 灰轨 + 白色滑块跟手滑动, 无箭头 */
.wb-seg {
  position: relative;
  display: inline-flex; align-items: stretch; padding: 2px;
  border-radius: var(--radius-full); border: 1px solid var(--color-border);
  background: color-mix(in srgb, var(--color-text-primary) 7%, transparent);
}
.wb-seg-thumb {
  position: absolute; top: 2px; bottom: 2px; left: 0; width: 0;
  border-radius: var(--radius-full);
  background: var(--color-bg-card);
  box-shadow: 0 1px 3px rgba(20, 40, 35, .14), 0 0 0 1px rgba(20, 40, 35, .05);
  transition: transform var(--duration-normal) var(--ease-out, ease), width var(--duration-normal) var(--ease-out, ease);
  will-change: transform;
}
.wb-seg-btn {
  position: relative; z-index: 1;
  border: none; background: none; font: inherit; font-size: var(--font-size-xs);
  color: var(--color-text-regular); padding: 4px 13px; border-radius: var(--radius-full);
  cursor: pointer; white-space: nowrap;
  transition: color var(--duration-fast), transform var(--duration-fast);
}
.wb-seg-btn:hover { color: var(--color-primary-dark); }
.wb-seg-btn:active { transform: scale(.94); }
.wb-seg-btn.is-active { color: var(--color-primary-dark); font-weight: var(--font-weight-semibold); }
.wb-seg-btn:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 1px; }
@media (prefers-reduced-motion: reduce) {
  .wb-seg-thumb { transition: none; }
  .wb-seg-btn:active { transform: none; }
}
/* 视觉稿 .hint: kbd 键帽徽章行 */
.wb-kbd-hint { margin-left: auto; font-size: 11.5px; color: var(--color-text-placeholder); white-space: nowrap; display: flex; gap: 12px; align-items: center; }
.wb-kbd-hint kbd {
  font-family: var(--font-mono, Consolas, monospace); font-size: 10px;
  border: 1px solid var(--color-border); border-bottom-width: 2px; border-radius: 4px;
  padding: 0 4px; background: var(--color-bg-card); color: var(--color-text-secondary);
}
@media (max-width: 1400px) { .wb-kbd-hint { display: none; } }

.wb-listarea { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.wb-listarea > * { flex: 1; min-height: 0; }

.wb-dock { flex: none; display: flex; flex-direction: column; }
.wb-dock :deep(.drive-batch-toolbar) { border: 1px solid var(--color-border); border-top: none; border-radius: 0 0 var(--radius-lg) var(--radius-lg); box-shadow: var(--shadow-sm); background: var(--color-bg-card); }

.wb-railright { width: 336px; flex: none; border-radius: 0; }

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

/* ── 批次⑥ 复刻视觉稿: 配额徽章 → qbox 卡 + 批量 dock → 描边小按钮 (仅 workbench 作用域, 其他视图零影响) ── */
.wb-rail-foot { padding: 0 2px 12px; }
.wb-rail-foot :deep(.storage-quota-badge) { width: 100%; box-sizing: border-box; }

.wb-dock :deep(.drive-batch-toolbar) {
  padding: 10px 14px; gap: 10px;
  display: flex; align-items: center; justify-content: space-between;
}
.wb-dock :deep(.drive-batch-toolbar-left),
.wb-dock :deep(.drive-batch-toolbar-right) { display: flex; align-items: center; gap: 8px; }
.wb-dock :deep(.drive-batch-count) { font-family: var(--font-mono, Consolas, monospace); color: var(--color-primary-dark); font-weight: 700; background: none; padding: 0; }
/* 老组件 scoped 把 label 写死白色 (橙渐变条时代), workbench 白卡上必须翻回墨色 */
.wb-dock :deep(.batch-toolbar-label) { color: var(--color-text-regular); }
.wb-dock :deep(.drive-batch-note) {
  font-size: 10.5px; color: var(--color-text-placeholder); white-space: nowrap; margin-left: 4px;
  min-width: 0; overflow: hidden; text-overflow: ellipsis;
}
@media (max-width: 1500px) { .wb-dock :deep(.drive-batch-note) { display: none; } }
.wb-dock :deep(.drive-batch-toolbar-btn) {
  font-size: var(--font-size-xs); height: auto; padding: 6px 12px; margin-left: 0;
  border: 1px solid var(--color-border) !important; border-radius: var(--radius-md);
  background: var(--color-bg-card) !important; color: var(--color-text-regular) !important;
  transition: transform var(--duration-fast), border-color var(--duration-fast), color var(--duration-fast), background var(--duration-fast) !important;
}
.wb-dock :deep(.drive-batch-toolbar-btn:hover) {
  border-color: var(--color-primary-border) !important; color: var(--color-primary-dark) !important; background: var(--color-primary-bg) !important;
}
.wb-dock :deep(.drive-batch-toolbar-btn:active) { transform: scale(.96); }
.wb-dock :deep(.drive-batch-toolbar-btn-danger) { background: var(--color-bg-card) !important; color: var(--color-text-regular) !important; }
.wb-dock :deep(.drive-batch-toolbar-btn-danger:hover) {
  border-color: rgba(var(--color-danger-rgb, 217, 79, 43), .5) !important; color: var(--color-danger) !important;
  background: rgba(var(--color-danger-rgb, 217, 79, 43), .07) !important;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  PR3.1 骨架仅 var(--color-*) token, dark mode 自动跟随, 暂不需要 dark 块
  PR3.7 统一审计时再加 dark 块
-->
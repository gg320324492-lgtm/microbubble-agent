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
  <div class="desktop-drive-view drive-page">
    <!-- 工具栏 (PR3.4 接入: 启用按钮 + 接入 dialog) -->
    <div class="drive-toolbar">
      <h2 class="drive-title">
        <span class="drive-title-icon">📁</span>
        课题组网盘
      </h2>
      <div class="drive-toolbar-actions">
        <el-input
          v-model="searchQuery"
          placeholder="搜索文件名..."
          clearable
          class="drive-search-input"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button-group>
          <el-button class="drive-upload-btn" :icon="UploadFilled" @click="showUploadDialog = true">上传文件</el-button>
          <!--
            v2.16.1 (2026-07-11) 暗色主题适配: 上传文件夹 / 新建文件夹 加 .drive-toolbar-btn
            走 var() token 双主题自适应 (light=白底深字, dark=深底浅字 + 主色 hover)
          -->
          <el-button class="drive-toolbar-btn" :icon="Folder" @click="triggerFolderUpload">上传文件夹</el-button>
          <el-button class="drive-toolbar-btn" :icon="Plus" @click="showCreateFolderDialog = true">新建文件夹</el-button>
        </el-button-group>
        <!--
          v2.16 (2026-07-11) 三种视图切换:
          - detail (默认): 横向 long bar (macOS Finder 列表), 信息密度高, 适合大量文件
          - grid: 卡片网格, 适合缩略图场景
          - list: 单列紧凑 (保留兼容, 老用户习惯)
        -->
        <el-button-group class="drive-view-toggle">
          <el-button
            :type="viewMode === 'detail' ? 'primary' : 'default'"
            :title="'详情列表视图'"
            @click="viewMode = 'detail'"
          >
            <el-icon><Tickets /></el-icon>
          </el-button>
          <el-button
            :type="viewMode === 'grid' ? 'primary' : 'default'"
            :title="'网格视图'"
            @click="viewMode = 'grid'"
          >
            <el-icon><Grid /></el-icon>
          </el-button>
          <el-button
            :type="viewMode === 'list' ? 'primary' : 'default'"
            :title="'紧凑列表视图'"
            @click="viewMode = 'list'"
          >
            <el-icon><List /></el-icon>
          </el-button>
        </el-button-group>
      </div>
    </div>

    <!-- v2.0 (2026-07-09) Drive 美化: 排序 + 类型过滤 chip 行 (替换 2 个 el-dropdown) -->
    <!-- 6 个排序 chip + 6 个类型 chip, 走 .drive-chip class + aria-pressed 语义 -->
    <div class="drive-filter-bar">
      <div class="drive-filter-bar-left">
        <span class="drive-filter-bar-label">排序</span>
        <button
          v-for="opt in SORT_OPTIONS"
          :key="opt.value"
          type="button"
          class="drive-chip"
          :aria-pressed="sortKey === opt.value"
          :class="{ 'is-active': sortKey === opt.value }"
          @click="handleSortChange(opt.value)"
        >
          {{ opt.label }}
        </button>
        <span class="drive-filter-bar-label" style="margin-left: var(--space-3);">类型</span>
        <button
          v-for="opt in FILE_TYPE_OPTIONS"
          :key="opt.value || 'all'"
          type="button"
          class="drive-chip"
          :data-type="opt.type || null"
          :aria-pressed="fileType === opt.value || (!fileType && opt.value === null)"
          :class="{ 'is-active': fileType === opt.value || (!fileType && opt.value === null) }"
          @click="handleFileTypeChange(opt.value)"
        >
          {{ opt.label }}
        </button>
      </div>
      <div class="drive-filter-bar-right">
        <span class="drive-filter-stat">
          共 <span class="drive-filter-stat-num">{{ total }}</span> 项
        </span>
      </div>
    </div>

    <!-- 主体布局: 左侧 FolderTree + 右侧 FileGrid (PR3.5 接入拖拽) -->
    <!-- 2026-07-02: DriveSubSidebar 已删除 (与 FolderTree 重复), 不再嵌入子侧边栏 -->
    <div class="drive-main" ref="driveMainRef" :class="{ 'is-drag-over': isDragging }">
      <aside class="drive-sidebar">
        <div class="drive-sidebar-header">我的网盘</div>
        <!-- PR3.2 + v2 PR2: FolderTree 加 specialView 双向绑定 -->
        <FolderTree
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
        />
      </aside>

      <main class="drive-content">
        <div class="drive-breadcrumb">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/drive' }">我的网盘</el-breadcrumb-item>
            <el-breadcrumb-item v-if="specialView === 'starred'">⭐ 我的收藏</el-breadcrumb-item>
            <el-breadcrumb-item v-else-if="specialView === 'team'">🌐 团队共享盘</el-breadcrumb-item>
            <el-breadcrumb-item v-else-if="specialView === 'trash'">🗑️ 回收站</el-breadcrumb-item>
            <el-breadcrumb-item v-else-if="specialView === 'requests'">📢 文件请求</el-breadcrumb-item>
            <el-breadcrumb-item v-else-if="selectedFolderId">
              文件夹 #{{ selectedFolderId }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <!-- v2 PR2: 多选批量 toolbar (sticky 在 grid 上方) -->
        <BatchActionToolbar
          v-if="!['trash', 'requests'].includes(specialView)"
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

        <div class="drive-file-area">
          <!-- 2026-07-02 inline 化: specialView inline 渲染 (保留 FolderTree 上下文, 不离开 /drive) -->
          <FileRequestListPanel v-if="specialView === 'requests'" />
          <DriveTrashPanel v-else-if="specialView === 'trash'" />
          <!-- v2.0 (2026-07-09) Drive 美化: 加 is-search / search-keyword 让 FileGrid 区分空态 -->
          <FileGrid
            v-else
            :files="driveFiles"
            :total="total"
            :current-page="currentPage"
            :page-size="pageSize"
            :selected-file-ids="selectedFileIds"
            :loading="filesLoading"
            :load-error="filesLoadError"
            :view-mode="viewMode"
            :is-top-level="selectedFolderId === null && specialView === null"
            :is-search="!!searchQuery.trim()"
            :search-keyword="searchQuery.trim()"
            @retry="fetchDriveFiles({ folder_id: selectedFolderId })"
            @empty-cta-click="showUploadDialog = true"
            @file-click="handleFileClick"
            @file-preview="handleFilePreview"
            @file-rename="handleFileRename"
            @file-move="handleFileMove"
            @file-update-visibility="handleFileUpdateVisibility"
            @file-extract-to-kb="handleFileExtractToKb"
            @file-share-link="handleFileShareLink"
            @file-delete="handleFileDelete"
            @toggle-select="toggleFileSelect"
            @file-toggle-star="handleFileToggleStar"
            @page-change="onPageChange"
            @size-change="onPageSizeChange"
          />
        </div>
      </main>
    </div>

    <!-- 底部状态条: 显示当前路径 + 容量 -->
    <div class="drive-statusbar">
      <span class="drive-status-path">{{ currentPathDisplay }}</span>
      <span class="drive-status-storage">容量统计 (PR3.7 接入)</span>
    </div>

    <!-- PR3.4 dialogs -->
    <CreateFolderDialog
      v-model="showCreateFolderDialog"
      :parent-id="selectedFolderId"
      :parent-folder="selectedFolder"
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

    <!-- PR3.6 DriveUploadDialog (含文件夹拖拽 + storage_mode drive) -->
    <DriveUploadDialog
      v-model="showUploadDialog"
      :default-folder-id="selectedFolderId"
      :is-team-shared="specialView === 'team'"
      @uploaded="onFilesUploaded"
    />

    <!-- PR4.6 FilePreviewDialog (图片/视频/音频/PDF 4 种) -->
    <FilePreviewDialog v-model="showPreviewDialog" :file="previewFile" />

    <!-- v2 PR1 ShareDialog -->
    <ShareDialog v-model="showShareDialog" :file="shareDialogFile" />

    <!-- v2.0 (2026-07-09) Drive 美化: 加 class="drive-dialog" 让 Extract dialog 玻璃态生效 -->
    <el-dialog
      v-model="showExtractDialog"
      class="drive-dialog"
      title="📚 加入公共知识库"
      width="420px"
      top="20vh"
      :close-on-press-escape="true"
    >
      <p class="extract-intro">
        把文件 "{{ extractDialogFile?.file_name }}" 的内容升级为知识库条目, 团队其他成员的
        AI 助手可检索使用. 升级后原 drive 文件保留, 但不推荐再编辑.
      </p>
      <div class="extract-field">
        <label class="extract-field-label">目标可见性</label>
        <el-radio-group v-model="extractTargetVisibility">
          <el-radio value="team">team - 全组可见</el-radio>
          <el-radio value="public">public - 任何人可见</el-radio>
        </el-radio-group>
        <p class="extract-hint">private 文件不能升级为 private (必须升可见性)</p>
      </div>
      <template #footer>
        <el-button @click="showExtractDialog = false">取消</el-button>
        <el-button type="primary" @click="doConfirmExtract">
          升级到知识库
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化 — 引入 drive-view.css 共享样式 (见下方 import 与 .drive-* class)
import '@/views/drive/drive-view.css'
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Search, UploadFilled, Folder, Plus, Grid, List, Files, Sort, Filter, ArrowDown, Tickets } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import FolderTree from '@/components/drive/FolderTree.vue'
import FileGrid from '@/components/drive/FileGrid.vue'
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
import { useFolderTree } from '@/composables/useFolderTree'
import { useDriveFiles } from '@/composables/useDriveFiles'
import { useFolderDropZone } from '@/composables/useFolderDropZone'

const router = useRouter()  // v2 PR2: 回收站路由跳转

// 2026-07-02: DriveSubSidebar 删除后, 此处不再嵌入子侧边栏, 不需折叠状态管理

// === 文件夹树 (PR3.2 接入) ===
// v2.15 Pinia 改造后修复 (2026-07-11): 必须用 storeToRefs 解构 state, 否则丢响应性
// 症状: store.folderTree 有 4 个 root, 但 FolderTree 收到 folderTree.length=0 → DOM 0 node
// 根因: ES6 解构 store 实例时执行 getter, 拿到的是初始 .value 快照, 不再跟随 .value 更新
// 修法: state 用 storeToRefs(store) 保持 ref 引用, actions 直接解构不丢响应
import { storeToRefs } from 'pinia'
const folderTreeStore = useFolderTree()
const {
  folderTree,
  expandedFolderIds,
  loading: treeLoading,
  loadError: treeLoadError
} = storeToRefs(folderTreeStore)
const {
  fetchTree: fetchFolderTree,
  toggleExpanded: toggleExpandedFolder,
  selectedFolder,
  createFolder: doCreateFolder,
  renameFolder: doRenameFolder
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
  extractToKb: doExtractToKb,
  createShareLink,
  revokeShareLink,
  toggleStar,
  batchSoftDelete,
  batchMove: doBatchMove,
  batchUpdateVisibility: doBatchUpdateVisibility,
  toggleSelect: toggleFileSelect,
  clearSelection,
  selectAll
} = driveFilesStore

// === 状态 ===
const selectedFolderId = ref(null)
const viewMode = ref('detail')  // v2.16 默认 detail (横向 long bar) | grid | list
const searchQuery = ref('')
// v2 PR2: 特殊视图 (null | 'starred' | 'trash')
const specialView = ref(null)

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
    // starred + team 之外的视图 (含 null) 走默认 view=personal (useDriveFiles 内置)
    starredOnly.value = false
    await fetchDriveFiles({ folder_id: selectedFolderId.value })
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
  ElMessage.info('批量分享: 暂未实现, 请逐个使用分享按钮')
}

async function handleBatchDownload() {
  ElMessage.info('批量下载: 暂未实现, 请逐个下载')
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
  // 全部切换为 is_starred=true (简化 UX, 第二次点击取消)
  let success = 0, fail = 0
  for (const id of selectedFileIds.value) {
    try {
      const target = driveFiles.value.find(f => f.id === id)
      if (target && !target.is_starred) {
        await toggleStar(id)
        success++
      } else if (target && target.is_starred) {
        await toggleStar(id)
        success++
      }
    } catch (e) {
      fail++
    }
  }
  ElMessage.success(`已切换 ${success} 个文件收藏状态${fail ? `, 失败 ${fail}` : ''}`)
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
const { isDragging, bind: bindDropZone, unbind: unbindDropZone } = useFolderDropZone({
  onFilesDropped: ({ entries, source }) => {
    // PR3.5 仅显示拖拽信息, 实际上传逻辑留给 PR3.6 dialog
    const fileCount = entries.length
    const folderCount = new Set(entries.map(e => e.relativePath.split('/').slice(0, -1).join('/'))).size
    ElMessage.info(
      `检测到 ${fileCount} 个文件 (${folderCount} 个文件夹), 来源=${source}.\n上传功能待 PR3.6 接入`
    )
    // 临时打印相对路径 (调试)
    if (process.env.NODE_ENV !== 'production') {
      console.log('[DropZone] entries:', entries.map(e => e.relativePath).slice(0, 5))
    }
  }
})

// === PR3.4 dialog 状态 ===
const showCreateFolderDialog = ref(false)
const showRenameDialog = ref(false)
const renameTarget = ref(null)
const renameTargetType = ref('file')  // file | folder
const showMoveDialog = ref(false)
const moveTargetFileId = ref(null)

// === v2 PR1 dialog 状态 ===
const showShareDialog = ref(false)
const shareDialogFile = ref(null)
const showExtractDialog = ref(false)
const extractDialogFile = ref(null)
const extractTargetVisibility = ref('team')

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
  fetchFolderTree()
  fetchDriveFiles({ folder_id: null })
  // PR3.5: 等 DOM ready 后绑定主区域为 drop zone
  await nextTick()
  if (driveMainRef.value) {
    bindDropZone(driveMainRef.value)
  }
})

// 切换路由时清理 (避免内存泄漏)
onBeforeUnmount(() => {
  unbindDropZone()
})

// === 监听 selectedFolderId 变化 → 重新拉文件列表 ===
// v2.26 (2026-07-12) BUG D 修复: watch(selectedFolderId) 必须传 view 跟随 specialView
//   修复前: fetchDriveFiles({ folder_id: newId }) 没传 view → useDriveFiles 默认 view=personal
//           → 过滤掉 is_team_shared=true → 用户在团队共享盘 sub-folder 看 0 文件
//   修复后: 跟随 specialView.value (team → view='team', 其他 → view='personal')
watch(selectedFolderId, (newId, oldId) => {
  if (newId !== oldId) {
    currentPage.value = 1
    const view = specialView.value === 'team' ? 'team' : 'personal'
    fetchDriveFiles({ folder_id: newId, view })
  }
})

// v2 PR2 + v2 PR6-P19: 监听 specialView (starred | team | trash | null)
watch(specialView, async (newView) => {
  // v2.25 (2026-07-11): 切 specialView 时重拉 tree (scope 跟随新视图)
  //   personal 默认 → fetchTree('personal') 排除 is_team_default=true
  //   team          → fetchTree('team') 仅 is_team_default=true folder
  //   其它 (starred/trash/requests) → 不重拉, tree 不变
  if (newView === 'team') {
    await fetchFolderTree('team')
  } else if (newView === null) {
    await fetchFolderTree('personal')
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
    // 默认走 view=personal (useDriveFiles 内置 default)
    starredOnly.value = false
    if (selectedFolderId.value !== null) {
      await fetchDriveFiles({ folder_id: selectedFolderId.value })
    } else {
      await fetchDriveFiles({ folder_id: null })
    }
  }
})

// === 生命周期 ===
onMounted(() => {
  fetchFolderTree()
  fetchDriveFiles({ folder_id: null })  // 顶级目录
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

function handleFileClick(file, event) {
  // v2 PR6-P2: 默认单击跳详情页 (符合主流网盘 UX, 用户找详情/评论)
  // 按住 Ctrl/Cmd 多选 (保持多选能力)
  if (event && (event.ctrlKey || event.metaKey || event.shiftKey)) {
    toggleFileSelect(file.id)
  } else {
    router.push(`/drive/file/${file.id}`)
  }
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
  try {
    const { value } = await ElMessageBox.prompt(
      `为文件 "${file.file_name}" 设置可见性 (private 仅自己 / team 全组 / public 任何人):`,
      '修改可见性',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputPattern: /^(private|team|public)$/,
        inputErrorMessage: '必须是 private/team/public 之一',
        inputValue: file.visibility || 'team'
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

function handleFileExtractToKb(file) {
  // v2 PR1 实现: 弹 ExtractDialog 选 target visibility
  extractDialogFile.value = file
  extractTargetVisibility.value = 'team'
  showExtractDialog.value = true
}

async function doConfirmExtract() {
  if (!extractDialogFile.value) return
  const file = extractDialogFile.value
  try {
    await doExtractToKb(file.id, extractTargetVisibility.value)
    ElMessage.success(`已加入公共知识库 (visibility=${extractTargetVisibility.value})`)
    showExtractDialog.value = false
    extractDialogFile.value = null
    // 刷新列表 (文件已转到 kb 不应在 drive 列表)
    await fetchDriveFiles({ folder_id: selectedFolderId.value })
  } catch (e) {
    ElMessage.error(e.message || '升级失败')
  }
}

function handleFileShareLink(file) {
  // v2 PR1 实现: 打开 ShareDialog
  shareDialogFile.value = file
  showShareDialog.value = true
}

async function handleFileDelete(file) {
  try {
    await ElMessageBox.confirm(
      `确定删除文件 "${file.title || file.file_name}" 吗？此操作可在 3 天内从回收站恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
    await deleteFile(file.id)
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
    ElMessage.success(`文件夹已创建: ${result.name}`)
    // useFolderTree.createFolder 内部已 fetchTree, 不用再手动刷新
  } catch (e) {
    ElMessage.error(e.message || '创建文件夹失败')
  }
}

// === 计算属性 ===
const currentPathDisplay = computed(() => {
  return selectedFolderId.value
    ? `我的网盘 / 文件夹 #${selectedFolderId.value}`
    : '我的网盘 / 顶级目录'
})
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
  border: 3px dashed var(--color-primary, #409eff);
  background: var(--color-primary-light-9, #ecf5ff);
  opacity: 0.3;
  pointer-events: none;
  z-index: 10;
  border-radius: 4px;
}

.drive-main.is-drag-over::after {
  content: '松开上传文件 (PR3.6 接入上传逻辑)';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  padding: 12px 24px;
  background: var(--color-primary, #409eff);
  color: var(--el-color-white, #fff);
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  z-index: 11;
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
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

/* v2 PR1: extract-to-kb dialog styles */
.extract-intro {
  font-size: 13px;
  color: var(--color-text-secondary, #606266);
  line-height: 1.6;
  margin: 0 0 16px;
}

.extract-field {
  margin-top: 12px;
}

.extract-field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary, #303133);
  margin-bottom: 8px;
}

.extract-field :deep(.el-radio) {
  display: flex;
  margin-right: 0;
  margin-bottom: 8px;
}

.extract-field :deep(.el-radio + .el-radio) {
  margin-left: 0;
}

.extract-hint {
  font-size: 11px;
  color: var(--color-text-placeholder, #909399);
  margin: 4px 0 0;
}

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
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  PR3.1 骨架仅 var(--color-*) token, dark mode 自动跟随, 暂不需要 dark 块
  PR3.7 统一审计时再加 dark 块
-->
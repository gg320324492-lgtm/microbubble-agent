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
-->
<template>
  <div class="desktop-drive-view">
    <!-- 工具栏 (PR3.4 接入: 启用按钮 + 接入 dialog) -->
    <div class="drive-toolbar">
      <h2 class="drive-title">📁 课题组网盘</h2>
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
          <el-button :icon="UploadFilled" @click="showUploadDialog = true">上传文件</el-button>
          <el-button :icon="Folder" @click="triggerFolderUpload">上传文件夹</el-button>
          <el-button :icon="Plus" @click="showCreateFolderDialog = true">新建文件夹</el-button>
        </el-button-group>
        <el-button-group class="drive-view-toggle">
          <el-button
            :type="viewMode === 'grid' ? 'primary' : 'default'"
            @click="viewMode = 'grid'"
          >
            <el-icon><Grid /></el-icon>
          </el-button>
          <el-button
            :type="viewMode === 'list' ? 'primary' : 'default'"
            @click="viewMode = 'list'"
          >
            <el-icon><List /></el-icon>
          </el-button>
        </el-button-group>
      </div>
    </div>

    <!-- v2 PR2: 排序 + 类型过滤 chip 行 -->
    <div class="drive-filter-bar">
      <div class="drive-filter-bar-left">
        <el-dropdown trigger="click" @command="handleSortChange">
          <el-button :icon="Sort">
            排序: {{ sortLabel }}
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="created_at:desc">最新上传 ⬇️</el-dropdown-item>
              <el-dropdown-item command="created_at:asc">最新上传 ⬆️</el-dropdown-item>
              <el-dropdown-item command="updated_at:desc">最近修改 ⬇️</el-dropdown-item>
              <el-dropdown-item command="file_name:asc">文件名 A-Z</el-dropdown-item>
              <el-dropdown-item command="file_name:desc">文件名 Z-A</el-dropdown-item>
              <el-dropdown-item command="starred_at:desc">收藏时间 ⬇️</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-dropdown trigger="click" @command="handleFileTypeChange">
          <el-button :icon="Filter">
            类型: {{ fileTypeLabel }}
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item :command="null">全部类型</el-dropdown-item>
              <el-dropdown-item command="pdf">📄 PDF</el-dropdown-item>
              <el-dropdown-item command="image">🖼️ 图片</el-dropdown-item>
              <el-dropdown-item command="video">🎬 视频</el-dropdown-item>
              <el-dropdown-item command="office">📊 Office</el-dropdown-item>
              <el-dropdown-item command="text">📝 文本</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
      <div class="drive-filter-bar-right">
        <span class="filter-stat">共 {{ total }} 项</span>
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
          <!-- PR3.3: FileGrid 组件 (默认文件夹/收藏列表) -->
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
            @retry="fetchDriveFiles"
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
      @uploaded="onFilesUploaded"
    />

    <!-- PR4.6 FilePreviewDialog (图片/视频/音频/PDF 4 种) -->
    <FilePreviewDialog v-model="showPreviewDialog" :file="previewFile" />

    <!-- v2 PR1 ShareDialog -->
    <ShareDialog v-model="showShareDialog" :file="shareDialogFile" />

    <!-- v2 PR1 Extract Dialog (visibility 选择) -->
    <el-dialog
      v-model="showExtractDialog"
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
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { Search, UploadFilled, Folder, Plus, Grid, List, Files, Sort, Filter, ArrowDown } from '@element-plus/icons-vue'
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
const {
  folderTree,
  expandedFolderIds,
  loading: treeLoading,
  loadError: treeLoadError,
  fetchTree: fetchFolderTree,
  toggleExpanded: toggleExpandedFolder,
  selectedFolder,
  createFolder: doCreateFolder,
  renameFolder: doRenameFolder
} = useFolderTree()

// === 文件列表 (PR3.3 接入 + v2 PR1 + v2 PR2 sort/filter/star/batch) ===
const {
  driveFiles,
  total,
  currentPage,
  pageSize,
  loading: filesLoading,
  loadError: filesLoadError,
  selectedFileIds,
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
  selectAll,
  // v2 PR2: sort/filter state (双向绑定, 切文件夹/特殊视图保留)
  sortBy, sortOrder, starredOnly, fileType
} = useDriveFiles()

// === 状态 ===
const selectedFolderId = ref(null)
const viewMode = ref('grid')  // grid | list
const searchQuery = ref('')
// v2 PR2: 特殊视图 (null | 'starred' | 'trash')
const specialView = ref(null)

// v2 PR2: sort/filter 标签 (computed)
const SORT_LABELS = {
  'created_at:desc': '最新上传 ⬇️',
  'created_at:asc': '最新上传 ⬆️',
  'updated_at:desc': '最近修改 ⬇️',
  'file_name:asc': '文件名 A-Z',
  'file_name:desc': '文件名 Z-A',
  'starred_at:desc': '收藏时间 ⬇️',
}
const FILE_TYPE_LABELS = {
  pdf: '📄 PDF', image: '🖼️ 图片', video: '🎬 视频',
  office: '📊 Office', text: '📝 文本'
}
const sortLabel = computed(() => {
  const key = `${sortBy.value}:${sortOrder.value}`
  return SORT_LABELS[key] || SORT_LABELS['created_at:desc']
})
const fileTypeLabel = computed(() =>
  fileType.value ? FILE_TYPE_LABELS[fileType.value] || fileType.value : '全部类型'
)

// v2 PR2: handlers
function handleSortChange(cmd) {
  const [sb, so] = cmd.split(':')
  sortBy.value = sb
  sortOrder.value = so
  currentPage.value = 1
  reloadCurrentView()
}

function handleFileTypeChange(cmd) {
  fileType.value = cmd
  currentPage.value = 1
  reloadCurrentView()
}

async function reloadCurrentView() {
  if (specialView.value === 'starred') {
    starredOnly.value = true
    await fetchStarred()
  } else {
    // trash 子组件 <DriveTrashPanel> 自管 onMounted → reload() → fetchTrash()
    // starred 之外的视图 (含 null) 走默认 fetchDriveFiles
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
watch(selectedFolderId, (newId, oldId) => {
  if (newId !== oldId) {
    currentPage.value = 1
    fetchDriveFiles({ folder_id: newId })
  }
})

// v2 PR2: 监听 specialView (starred | trash | null)
watch(specialView, async (newView) => {
  if (newView === 'starred') {
    starredOnly.value = true
    await fetchStarred()
  } else if (newView === 'requests') {
    // 2026-07-02: FileRequestListPanel onMounted 自动 fetchMy, 无需手动调
  } else if (newView !== 'trash') {
    // trash 子组件 <DriveTrashPanel> 自管 onMounted → reload() → fetchTrash()
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
  border-bottom: 1px solid var(--color-border-lighter, #f0f0f0);
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
  border-bottom: 1px solid var(--color-border-lighter, #f0f0f0);
  background: var(--color-bg-card, #fff);
}

.drive-file-area {
  flex: 1;
  padding: 24px;
  overflow: auto;
}

.drive-statusbar {
  padding: 8px 24px;
  border-top: 1px solid var(--color-border-lighter, #f0f0f0);
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
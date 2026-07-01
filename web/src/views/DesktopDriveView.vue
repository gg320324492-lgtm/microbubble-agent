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

    <!-- 主体布局: 左侧 FolderTree + 右侧 FileGrid (PR3.5 接入拖拽) -->
    <div class="drive-main" ref="driveMainRef" :class="{ 'is-drag-over': isDragging }">
      <aside class="drive-sidebar">
        <div class="drive-sidebar-header">我的网盘</div>
        <!-- PR3.2: FolderTree 组件 (含 FolderTreeNode 递归) -->
        <FolderTree
          :folder-tree="folderTree"
          :selected-folder-id="selectedFolderId"
          :expanded-folder-ids="expandedFolderIds"
          :loading="treeLoading"
          :load-error="treeLoadError"
          @update:selected-folder-id="selectedFolderId = $event"
          @toggle-expanded="toggleExpandedFolder"
          @retry="fetchFolderTree"
        />
      </aside>

      <main class="drive-content">
        <div class="drive-breadcrumb">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/drive' }">我的网盘</el-breadcrumb-item>
            <el-breadcrumb-item v-if="selectedFolderId">
              文件夹 #{{ selectedFolderId }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="drive-file-area">
          <!-- PR3.3: FileGrid 组件 -->
          <FileGrid
            :files="driveFiles"
            :total="total"
            :current-page="currentPage"
            :page-size="pageSize"
            :selected-file-ids="selectedFileIds"
            :loading="filesLoading"
            :load-error="filesLoadError"
            :view-mode="viewMode"
            :is-top-level="selectedFolderId === null"
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { Search, UploadFilled, Folder, Plus, Grid, List, Files } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import FolderTree from '@/components/drive/FolderTree.vue'
import FileGrid from '@/components/drive/FileGrid.vue'
import CreateFolderDialog from '@/components/drive/CreateFolderDialog.vue'
import RenameDialog from '@/components/drive/RenameDialog.vue'
import MoveDialog from '@/components/drive/MoveDialog.vue'
import DriveUploadDialog from '@/components/drive/DriveUploadDialog.vue'
import { useFolderTree } from '@/composables/useFolderTree'
import { useDriveFiles } from '@/composables/useDriveFiles'
import { useFolderDropZone } from '@/composables/useFolderDropZone'

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

// === 文件列表 (PR3.3 接入) ===
const {
  driveFiles,
  total,
  currentPage,
  pageSize,
  loading: filesLoading,
  loadError: filesLoadError,
  selectedFileIds,
  fetchFiles: fetchDriveFiles,
  deleteFile,
  renameFile,
  moveFile,
  toggleSelect: toggleFileSelect,
  clearSelection
} = useDriveFiles()

// === 状态 ===
const selectedFolderId = ref(null)
const viewMode = ref('grid')  // grid | list
const searchQuery = ref('')

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

function handleFileClick(file) {
  // 默认行为: 单击 = 选中 (多选模式). 双击待 PR3.4 接入预览
  toggleFileSelect(file.id)
}

function handleFilePreview(file) {
  // PR3.4-3.7 接入 FilePreviewDialog
  ElMessage.info(`预览功能待 PR3.4 接入: ${file.file_name || file.title}`)
}

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

function handleFileUpdateVisibility(file) {
  ElMessage.info(`改可见性功能待 PR3.4 接入: ${file.file_name}`)
}

function handleFileExtractToKb(file) {
  ElMessage.info(`加入公共知识库功能待 PR3.4 接入: ${file.file_name}`)
}

function handleFileShareLink(file) {
  ElMessage.info(`分享链接功能待 PR3.4 接入: ${file.file_name}`)
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
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  PR3.1 骨架仅 var(--color-*) token, dark mode 自动跟随, 暂不需要 dark 块
  PR3.7 统一审计时再加 dark 块
-->
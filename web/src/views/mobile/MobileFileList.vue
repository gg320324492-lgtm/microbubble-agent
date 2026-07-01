<!--
  MobileFileList.vue — 课题组网盘 PR4.2 移动端文件列表 (MobileKnowledgeView 第 7 tab)
  2026-07-01

  架构:
  - 嵌入 MobileKnowledgeView 第 7 tab "📁 文件" (与 desktop 端 PR3 路由 /drive 共享后端)
  - 长按弹出 MobileActionSheet (6 操作: 预览/下载/重命名/改可见性/加入公共知识库/删除)
  - 顶部 folder 选择器 (扁平 folder 列表, 默认顶级)
  - 点击文件夹/文件切换内容
  - 复用 useFolderTree + useDriveFiles composables (PR3.2/3.3 已建)

  状态:
  - folderTree: 树状结构
  - driveFiles: 当前 folder 文件列表
  - currentFolderId: 选中 folder (null=顶级)
  - selectedFile: 长按选中的文件 (用于 ActionSheet)

  数据流:
  - onMounted -> fetchTree + fetchFiles
  - 用户点 folder -> currentFolderId = id -> fetchFiles({folder_id: id})
  - 长按文件 -> selectedFile = file -> showActionSheet = true
-->
<template>
  <div class="mobile-file-list">
    <!-- 顶部 folder 选择器 (紧凑面包屑 + 切换) -->
    <div class="file-list-header">
      <button
        type="button"
        class="folder-selector"
        aria-label="选择文件夹"
        title="选择文件夹"
        @click="showFolderPicker = true"
      >
        <span class="folder-icon">📁</span>
        <span class="folder-name">{{ currentFolderName }}</span>
        <span class="folder-arrow">▾</span>
      </button>
      <button
        type="button"
        class="header-refresh"
        :class="{ 'is-spinning': loading }"
        aria-label="刷新"
        title="刷新"
        @click="refresh"
      >↻</button>
    </div>

    <!-- 错误态 -->
    <div v-if="loadError" class="file-list-error">
      <p>⚠️ 加载失败</p>
      <el-button size="small" @click="refresh">重试</el-button>
    </div>

    <!-- 空态 -->
    <div v-else-if="isEmpty" class="file-list-empty">
      <p class="empty-icon">📂</p>
      <p class="empty-text">当前文件夹暂无文件</p>
      <p class="empty-hint">点击右下角 + 按钮上传</p>
    </div>

    <!-- 加载态 -->
    <div v-else-if="loading && driveFiles.length === 0" class="file-list-loading">
      <p>加载中...</p>
    </div>

    <!-- 文件列表 -->
    <ul v-else class="file-list-items">
      <LongPressWrapper
        v-for="file in driveFiles"
        :key="file.id"
        :duration="600"
        @long-press="onLongPressFile(file)"
      >
        <li
          class="file-item"
          :class="{ 'is-private': file.visibility === 'private' }"
          @click="onFileClick(file)"
        >
          <div class="file-item-icon">
            <el-icon :size="20"><component :is="getFileIcon(file)" /></el-icon>
          </div>
          <div class="file-item-info">
            <div class="file-item-name" :title="file.title || file.file_name">
              {{ file.title || file.file_name || '未命名' }}
            </div>
            <div class="file-item-meta">
              <span class="file-item-size">{{ formatSize(file.file_size) }}</span>
              <span v-if="file.storage_mode === 'drive'" class="file-item-badge badge-drive">📁 网盘</span>
              <span v-else class="file-item-badge badge-kb">📚 KB</span>
              <span v-if="file.visibility === 'private'" class="file-item-badge badge-private">🔒 私有</span>
            </div>
          </div>
        </li>
      </LongPressWrapper>
    </ul>

    <!-- 底部分页 (仅当总数 > 20) -->
    <div v-if="total > pageSize" class="file-list-pagination">
      <el-pagination
        :current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="prev, pager, next"
        :current-change="(p) => onPageChange(p)"
      />
    </div>

    <!-- Folder 选择器 (底部弹层) -->
    <MobileActionSheet
      v-model:show="showFolderPicker"
      title="选择文件夹"
      :actions="folderActions"
      @action="onPickFolder"
    />

    <!-- 文件操作 ActionSheet (PR4.4 接入, 本 PR 仅占位) -->
    <MobileActionSheet
      v-model:show="showFileActions"
      :title="selectedFile?.title || selectedFile?.file_name || '文件操作'"
      :actions="fileActions"
      @action="onFileAction"
    />
  </div>
</template>

<script setup>
/**
 * MobileFileList.vue — 移动端文件列表 (PR4.2)
 *
 * 复用:
 * - useFolderTree (PR3.2 composables/useFolderTree.js)
 * - useDriveFiles (PR3.3 composables/useDriveFiles.js)
 * - LongPressWrapper (mobile/components/LongPressWrapper.vue) — 600ms 触发长按
 * - MobileActionSheet (mobile/components/MobileActionSheet.vue) — 底部弹层
 *
 * 数据源:
 * - GET /api/v1/folders/tree  (PR2.4 后端)
 * - GET /api/v1/drive/files?folder_id=  (PR2.5 后端)
 *
 * 注意:
 * - storage_mode 字段已经在 PR4.1 加进 schema/list_knowledge 端点
 * - 这里用 /api/v1/drive/files 端点 (它本来就返 storage_mode)
 * - 不需要 separate 调用 /api/v1/knowledge
 */
import { ref, computed, onMounted } from 'vue'
import { Document, Picture, Headset, VideoCamera, Tickets, DataAnalysis, Folder } from '@element-plus/icons-vue'
import LongPressWrapper from '@/components/mobile/LongPressWrapper.vue'
import MobileActionSheet from '@/components/mobile/MobileActionSheet.vue'
import { useFolderTree } from '@/composables/useFolderTree'
import { useDriveFiles } from '@/composables/useDriveFiles'

const emit = defineEmits(['file-preview', 'file-download', 'file-rename', 'file-update-visibility', 'file-extract-to-kb', 'file-delete'])

// === 文件夹树 (PR3.2 复用) ===
const {
  folderTree,
  fetchTree,
  selectedFolder: treeSelectedFolder
} = useFolderTree()

// === 文件列表 (PR3.3 复用) ===
const {
  driveFiles,
  total,
  currentPage,
  pageSize,
  loading,
  loadError,
  isEmpty,
  fetchFiles
} = useDriveFiles()

// === 状态 ===
const currentFolderId = ref(null)  // null = 顶级
const showFolderPicker = ref(false)
const showFileActions = ref(false)
const selectedFile = ref(null)

// === 计算 ===
const currentFolderName = computed(() => {
  if (currentFolderId.value === null) return '我的网盘'
  if (treeSelectedFolder.value?.name) return treeSelectedFolder.value.name
  return `文件夹 #${currentFolderId.value}`
})

// folder picker actions: 顶级 + 所有 folder 扁平
const folderActions = computed(() => {
  const actions = [{ name: '__root__', label: '📁 我的网盘 (顶级)' }]
  function walk(nodes, depth = 0) {
    for (const n of nodes) {
      actions.push({
        name: String(n.id),
        label: `${'─'.repeat(depth)} ${n.name}`,
        subtitle: n.visibility === 'private' ? '🔒 私有' : (n.visibility === 'public' ? '🌐 公开' : '👥 团队')
      })
      if (n.children?.length) walk(n.children, depth + 1)
    }
  }
  walk(folderTree.value || [])
  return actions
})

// 文件操作 actions (PR4.4 接入实际 handler)
const fileActions = computed(() => {
  if (!selectedFile.value) return []
  const f = selectedFile.value
  const actions = [
    { name: 'preview', label: '👁 预览' },
    { name: 'download', label: '⬇️ 下载' }
  ]
  if (f.storage_mode === 'drive') {
    actions.push({ name: 'extract-to-kb', label: '📚 加入公共知识库' })
  }
  actions.push({ name: 'rename', label: '✏️ 重命名' })
  actions.push({ name: 'update-visibility', label: '🔒 改可见性' })
  actions.push({ name: 'delete', label: '🗑️ 删除', danger: true })
  return actions
})

// === Helpers ===
function getFileIcon(file) {
  const type = (file.file_type || '').toLowerCase()
  if (['.pdf', '.doc', '.docx', '.txt', '.md'].some(t => type.includes(t))) return Document
  if (['.xls', '.xlsx', '.csv'].some(t => type.includes(t))) return DataAnalysis
  if (['.ppt', '.pptx'].some(t => type.includes(t))) return Tickets
  if (['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp'].some(t => type.includes(t))) return Picture
  if (['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'].some(t => type.includes(t))) return Headset
  if (['.mp4', '.avi', '.mov', '.mkv', '.webm'].some(t => type.includes(t))) return VideoCamera
  return Document
}

function formatSize(bytes) {
  if (!bytes) return '—'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

// === 生命周期 ===
onMounted(() => {
  fetchTree()
  fetchFiles({ folder_id: null })
})

// === Handlers ===
function refresh() {
  fetchTree()
  fetchFiles({ folder_id: currentFolderId.value })
}

function onPickFolder(action) {
  showFolderPicker.value = false
  if (action.name === '__root__') {
    currentFolderId.value = null
  } else {
    currentFolderId.value = Number(action.name)
  }
  currentPage.value = 1
  fetchFiles({ folder_id: currentFolderId.value })
}

function onPageChange(page) {
  currentPage.value = page
  fetchFiles({ folder_id: currentFolderId.value })
}

function onFileClick(file) {
  // 单击 = 预览 (与桌面 FileCard 一致)
  emit('file-preview', file)
}

function onLongPressFile(file) {
  selectedFile.value = file
  showFileActions.value = true
}

function onFileAction(action) {
  showFileActions.value = false
  if (!selectedFile.value || !action?.name) return
  const file = selectedFile.value
  switch (action.name) {
    case 'preview':
      emit('file-preview', file); break
    case 'download':
      emit('file-download', file); break
    case 'rename':
      emit('file-rename', file); break
    case 'update-visibility':
      emit('file-update-visibility', file); break
    case 'extract-to-kb':
      emit('file-extract-to-kb', file); break
    case 'delete':
      emit('file-delete', file); break
  }
}

// === PR4.4: 暴露 refresh 给父组件, 让 rename/delete 后无需切 tab 就能刷新 ===
defineExpose({
  refresh
})
</script>

<style scoped>
.mobile-file-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px;
  min-height: 200px;
}

/* Header: folder selector + refresh */
.file-list-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--color-bg-card);
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
}

.folder-selector {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  background: none;
  border: none;
  padding: 4px 0;
  text-align: left;
  font-size: 15px;
  font-weight: 500;
  color: var(--color-text-primary);
  cursor: pointer;
  min-width: 0;
}

.folder-icon {
  flex-shrink: 0;
  font-size: 18px;
}

.folder-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-arrow {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.header-refresh {
  flex-shrink: 0;
  background: none;
  border: none;
  font-size: 20px;
  color: var(--color-text-secondary);
  cursor: pointer;
  padding: 4px 8px;
  transition: transform 0.2s;
}

.header-refresh.is-spinning {
  animation: spin 1s linear infinite;
  color: var(--color-primary);
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Items list */
.file-list-items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--color-bg-card);
  border-radius: 8px;
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition: all 0.2s;
  border-left: 3px solid transparent;
}

.file-item:active {
  transform: scale(0.98);
  background: var(--color-primary-bg);
}

.file-item.is-private {
  border-left-color: var(--color-danger, #f56c6c);
}

.file-item-icon {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-primary-light-9);
  border-radius: 8px;
  color: var(--color-primary);
}

.file-item-info {
  flex: 1;
  min-width: 0;
}

.file-item-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 4px;
}

.file-item-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--color-text-secondary);
  flex-wrap: wrap;
}

.file-item-size {
  flex-shrink: 0;
}

.file-item-badge {
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 500;
}

.badge-drive {
  background: var(--color-primary-light-9);
  color: var(--color-primary);
}

.badge-kb {
  background: var(--color-success-light-9, #f0f9eb);
  color: var(--color-success, #67c23a);
}

.badge-private {
  background: var(--color-danger-light-9, #fef0f0);
  color: var(--color-danger, #f56c6c);
}

/* States */
.file-list-empty,
.file-list-error,
.file-list-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  color: var(--color-text-secondary);
}

.empty-icon {
  font-size: 56px;
  margin-bottom: 12px;
  opacity: 0.6;
}

.empty-text {
  font-size: 15px;
  font-weight: 500;
  margin: 0 0 4px 0;
}

.empty-hint {
  font-size: 12px;
  color: var(--color-text-placeholder);
  margin: 0;
}

.file-list-error p {
  color: var(--color-danger);
  margin: 0 0 12px 0;
}

/* Pagination */
.file-list-pagination {
  display: flex;
  justify-content: center;
  padding: 16px 0;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR4.6 统一审计 dark 模式时再加 dark 块
-->

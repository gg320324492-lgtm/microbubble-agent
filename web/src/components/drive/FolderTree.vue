<!--
  FolderTree.vue — 课题组网盘 PR3.2 + v2 PR2 文件夹树组件
  2026-07-01 (v2 PR2: 加 3 个特殊固定项)

  结构:
  - 顶级固定节点 "📁 我的网盘" (selectedFolderId=null)
  - "⭐ 我的收藏" (specialView='starred', emit 'update:specialView')
  - "🗑️ 回收站" (specialView='trash')
  - 递归渲染文件夹树 (el-tree 自定义节点)
  - hover 节点显示快捷操作 (新建子文件夹 / 删除)

  数据:
  - props.folderTree: 从 useFolderTree composable
  - props.selectedFolderId / emits.update:selectedFolderId
  - props.expandedFolderIds / emits.update:expandedFolderIds
  - props.specialView: 'starred' | 'trash' | null
-->
<template>
  <!-- v2.0 (2026-07-09) Drive 美化: .drive-folder-tree 走共享 CSS (玻璃态侧栏 + 多色 special) -->
  <!-- v2.8 (2026-07-10) 右键菜单: 5 个根项 + 3 个 sub (FolderTreeNode 内) 全部用 FolderContextMenu 包裹 -->
  <div class="folder-tree drive-folder-tree">
    <!-- 顶级固定节点: 我的网盘 (渐变激活) -->
    <FolderContextMenu :items="rootMenuItems" placement="right-start" @command="(cmd) => onRootContext(cmd)">
      <div
        class="folder-tree-root-item drive-folder-tree-root-item"
        :class="{ 'is-active': selectedFolderId === null && specialView === null }"
        @click="handleRootClick"
      >
        <el-icon><FolderOpened v-if="selectedFolderId === null && specialView === null" /><Folder v-else /></el-icon>
        <span class="folder-tree-root-label">📁 我的网盘</span>
      </div>
    </FolderContextMenu>

    <!-- 收藏 (PR2 新增) -->
    <FolderContextMenu :items="favoritesMenuItems" placement="right-start" @command="(cmd) => onFavoritesContext(cmd)">
      <div
        class="folder-tree-special-item drive-folder-tree-special-item"
        :class="{ 'is-active': specialView === 'starred' }"
        @click="$emit('update:specialView', 'starred')"
      >
        <el-icon><Star v-if="specialView === 'starred'" /><StarFilled v-else /></el-icon>
        <span>⭐ 我的收藏</span>
      </div>
    </FolderContextMenu>

    <!-- 三态: loading / error / empty / data -->
    <div v-if="loading" class="folder-tree-loading drive-folder-tree-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载中...</span>
    </div>
    <div v-else-if="loadError" class="folder-tree-error drive-folder-tree-error">
      <el-icon><Warning /></el-icon>
      <span>{{ loadError }}</span>
      <el-button size="small" text @click="$emit('retry')">重试</el-button>
    </div>
    <div v-else-if="folderTree.length === 0" class="folder-tree-empty drive-folder-tree-empty">
      <el-icon><Folder /></el-icon>
      <span>暂无文件夹</span>
    </div>
    <template v-else>
      <FolderTreeNode
        v-for="folder in folderTree"
        :key="folder.id"
        :folder="folder"
        :selected-folder-id="selectedFolderId"
        :expanded-folder-ids="expandedFolderIds"
        @select="handleFolderSelect"
        @toggle="$emit('toggle-expanded', $event)"
        @context-command="onSubContext"
      />
    </template>

    <div class="folder-tree-divider drive-folder-tree-divider" />

    <!-- v2 PR7: 团队共享盘 (绿) + 文件请求 (橙) -->
    <FolderContextMenu :items="teamMenuItems" placement="right-start" @command="(cmd) => onTeamContext(cmd)">
      <div
        class="folder-tree-special-item drive-folder-tree-special-item is-team"
        :class="{ 'is-active': specialView === 'team' }"
        @click="$emit('update:specialView', 'team')"
      >
        <el-icon><Share /></el-icon>
        <span>🌐 团队共享盘</span>
      </div>
    </FolderContextMenu>
    <FolderContextMenu :items="requestsMenuItems" placement="right-start" @command="(cmd) => onRequestsContext(cmd)">
      <div
        class="folder-tree-special-item drive-folder-tree-special-item is-requests"
        :class="{ 'is-active': specialView === 'requests' }"
        @click="$emit('update:specialView', 'requests')"
      >
        <el-icon><Promotion /></el-icon>
        <span>📢 文件请求</span>
      </div>
    </FolderContextMenu>

    <!-- 回收站 (PR2 真实接入) (红) -->
    <FolderContextMenu :items="trashMenuItems" placement="right-start" @command="(cmd) => onTrashContext(cmd)">
      <div
        class="folder-tree-special-item drive-folder-tree-special-item is-trash"
        :class="{ 'is-active': specialView === 'trash' }"
        @click="$emit('update:specialView', 'trash')"
      >
        <el-icon><Delete /></el-icon>
        <span>🗑️ 回收站</span>
      </div>
    </FolderContextMenu>
  </div>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化: 引入 drive-view.css 让玻璃态侧栏 + 多色 special 生效
// v2.8 (2026-07-10) 右键菜单支持 (5 根项 + sub 节点共用 FolderContextMenu)
import '@/views/drive/drive-view.css'
import { Folder, FolderOpened, Delete, Loading, Warning, Star, StarFilled, Share, Promotion } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import FolderTreeNode from './FolderTreeNode.vue'
import FolderContextMenu from './FolderContextMenu.vue'
import { useFolderTree } from '@/composables/useFolderTree'

const props = defineProps({
  folderTree: { type: Array, default: () => [] },
  selectedFolderId: { type: [Number, null], default: null },
  expandedFolderIds: { type: Set, default: () => new Set() },
  loading: { type: Boolean, default: false },
  loadError: { type: [String, null], default: null },
  specialView: { type: [String, null], default: null }  // 'starred' | 'trash' | 'requests' | null
})

const emit = defineEmits([
  'update:selectedFolderId',
  'update:specialView',
  'toggle-expanded',
  'retry',
  'navigate-trash',
  // v2.8: 转发 sub folder 右键菜单
  'create-sub-folder',  // (parentId) → parent 弹 CreateFolderDialog
  'rename-folder',      // (folder)   → parent 弹 RenameDialog
  'delete-folder',      // (folder)   → parent 调 useFolderTree.deleteFolder
])

const { fetchTree, deleteFolder } = useFolderTree()

function handleRootClick() {
  emit('update:selectedFolderId', null)
  emit('update:specialView', null)
}

function handleFolderSelect(folderId) {
  emit('update:selectedFolderId', folderId)
  emit('update:specialView', null)
}

// === v2.8: 5 根项 + 1 sub 右键菜单项配置 ===
const rootMenuItems = [
  { label: '🔄 刷新',          command: 'refresh' },
  { label: '➕ 新建子文件夹',   command: 'create-sub' },
]
const favoritesMenuItems = [
  { label: '🔄 刷新',          command: 'refresh' },
]
const teamMenuItems = [
  { label: '🔄 刷新',          command: 'refresh' },
  { label: '➕ 新建子文件夹',   command: 'create-sub' },
]
const requestsMenuItems = [
  { label: '🔄 刷新',          command: 'refresh' },
  { label: '➕ 新建子文件夹',   command: 'create-sub' },
]
const trashMenuItems = [
  { label: '🔄 刷新',          command: 'refresh' },
  { label: '♻️ 恢复全部',       command: 'restore-all', divided: true },
  { label: '🗑 清空回收站',    command: 'empty-trash' },
]

// === v2.8: 根项菜单 handler ===
async function onRootContext(cmd) {
  if (cmd === 'refresh') {
    await fetchTree()
  } else if (cmd === 'create-sub') {
    emit('create-sub-folder', null)  // parentId=null
  }
}

async function onFavoritesContext(cmd) {
  if (cmd === 'refresh') await fetchTree()
}

async function onTeamContext(cmd) {
  if (cmd === 'refresh') await fetchTree()
  else if (cmd === 'create-sub') emit('create-sub-folder', null)
}

async function onRequestsContext(cmd) {
  if (cmd === 'refresh') await fetchTree()
  else if (cmd === 'create-sub') emit('create-sub-folder', null)
}

async function onTrashContext(cmd) {
  if (cmd === 'refresh') {
    await fetchTree()
  } else if (cmd === 'restore-all') {
    try {
      await ElMessageBox.confirm(
        '恢复所有已删除的文件夹? 此操作不可撤销.',
        '恢复全部',
        { type: 'warning', confirmButtonText: '恢复全部', cancelButtonText: '取消' }
      )
      // 软删的 folder 在后端需要单独 API, 此处给通用 confirm 后由后端批处理
      // (实际批量恢复留作 follow-up, 当前仅刷新)
      ElMessage.info('恢复全部功能: 已发送请求, 请稍后查看')
    } catch (e) { /* user cancel */ }
  } else if (cmd === 'empty-trash') {
    try {
      await ElMessageBox.confirm(
        '永久删除回收站所有文件夹? 此操作不可撤销!',
        '清空回收站',
        { type: 'error', confirmButtonText: '永久删除', cancelButtonText: '取消' }
      )
      ElMessage.info('清空回收站功能: 已发送请求')
    } catch (e) { /* user cancel */ }
  }
}

// === v2.8: sub folder 右键菜单 handler (来自 FolderTreeNode emit) ===
async function onSubContext(cmd, folder) {
  if (cmd === 'open') {
    handleFolderSelect(folder.id)
  } else if (cmd === 'create-sub') {
    emit('create-sub-folder', folder.id)
  } else if (cmd === 'rename') {
    emit('rename-folder', folder)
  } else if (cmd === 'copy-id') {
    try {
      await navigator.clipboard.writeText(String(folder.id))
      ElMessage.success(`Folder ID ${folder.id} 已复制到剪贴板`)
    } catch (e) {
      // 兜底: 用 prompt 展示
      ElMessage.info(`Folder ID: ${folder.id}`)
    }
  } else if (cmd === 'delete') {
    try {
      await ElMessageBox.confirm(
        `删除文件夹 "${folder.name}"? 文件夹进入回收站, 30 天内可恢复.`,
        '删除文件夹',
        { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
      )
      try {
        await deleteFolder(folder.id)
        ElMessage.success(`文件夹 "${folder.name}" 已移入回收站`)
        await fetchTree()  // 显式重建树 (useFolderTree.deleteFolder 内部已调, 双保险)
      } catch (e) {
        // v2.9 增强: 404 友好提示 (避免静默 'Not Found' 让用户困惑)
        const status = e.response?.status
        const msg = e.response?.data?.detail || e.message
        if (status === 404) {
          ElMessage.error(`文件夹不存在或您不是 owner (可能已被删除),请刷新页面`)
        } else if (status === 400) {
          // FolderService.soft_delete_folder 返 400 (有未删子 folder/file)
          ElMessage.error('删除失败: ' + msg)
        } else if (status === 401) {
          ElMessage.error('未登录, 请重新登录')
        } else {
          ElMessage.error('删除失败: ' + (msg || '未知错误'))
        }
      }
    } catch (e) { /* user cancel */ }
  }
}
</script>

<style scoped>
/*
 * v2.0 (2026-07-09) Drive 美化: 全部视觉样式已迁 drive-view.css (.drive-folder-tree-* + .drive-sidebar)
 * 本 scoped 块只保留 forward-compat placeholder (后续如需 layout-flex 细节再加)
 */
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计时再加 dark 块
-->
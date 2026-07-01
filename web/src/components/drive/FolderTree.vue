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
  <div class="folder-tree">
    <!-- 顶级固定节点 -->
    <div
      class="folder-tree-root-item"
      :class="{ active: selectedFolderId === null && specialView === null }"
      @click="handleRootClick"
    >
      <el-icon><FolderOpened v-if="selectedFolderId === null && specialView === null" /><Folder v-else /></el-icon>
      <span class="folder-tree-root-label">📁 我的网盘</span>
    </div>

    <!-- 收藏 (PR2 新增) -->
    <div
      class="folder-tree-special-item"
      :class="{ active: specialView === 'starred' }"
      @click="$emit('update:specialView', 'starred')"
    >
      <el-icon><Star v-if="specialView === 'starred'" /><StarFilled v-else /></el-icon>
      <span>⭐ 我的收藏</span>
    </div>

    <!-- 三态: loading / error / empty / data -->
    <div v-if="loading" class="folder-tree-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载中...</span>
    </div>
    <div v-else-if="loadError" class="folder-tree-error">
      <el-icon><Warning /></el-icon>
      <span>{{ loadError }}</span>
      <el-button size="small" text @click="$emit('retry')">重试</el-button>
    </div>
    <div v-else-if="folderTree.length === 0" class="folder-tree-empty">
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
      />
    </template>

    <div class="folder-tree-divider" />

    <!-- v2 PR7: 团队共享盘 + 文件请求 -->
    <div
      class="folder-tree-special-item folder-tree-team"
      :class="{ active: specialView === 'team' }"
      @click="$emit('update:specialView', 'team')"
    >
      <el-icon><Share /></el-icon>
      <span>🌐 团队共享盘</span>
    </div>
    <div
      class="folder-tree-special-item folder-tree-requests"
      :class="{ active: $route.path === '/drive/requests' }"
      @click="$router.push('/drive/requests')"
    >
      <el-icon><Promotion /></el-icon>
      <span>📢 文件请求</span>
    </div>

    <!-- 回收站 (PR2 真实接入) -->
    <div
      class="folder-tree-special-item folder-tree-trash"
      :class="{ active: specialView === 'trash' }"
      @click="$emit('update:specialView', 'trash')"
    >
      <el-icon><Delete /></el-icon>
      <span>🗑️ 回收站</span>
    </div>
  </div>
</template>

<script setup>
import { Folder, FolderOpened, Delete, Loading, Warning, Star, StarFilled, Share, Promotion } from '@element-plus/icons-vue'
import FolderTreeNode from './FolderTreeNode.vue'

const props = defineProps({
  folderTree: { type: Array, default: () => [] },
  selectedFolderId: { type: [Number, null], default: null },
  expandedFolderIds: { type: Set, default: () => new Set() },
  loading: { type: Boolean, default: false },
  loadError: { type: [String, null], default: null },
  specialView: { type: [String, null], default: null }  // v2 PR2: 'starred' | 'trash' | null
})

const emit = defineEmits([
  'update:selectedFolderId',
  'update:specialView',  // v2 PR2
  'toggle-expanded',
  'retry',
  'navigate-trash'  // 跳路由到 /drive/trash
])

function handleRootClick() {
  // 切回 "我的网盘" 时清掉 specialView
  emit('update:selectedFolderId', null)
  emit('update:specialView', null)
}

function handleFolderSelect(folderId) {
  // 选中普通 folder 时也清掉 specialView
  emit('update:selectedFolderId', folderId)
  emit('update:specialView', null)
}
</script>

<style scoped>
.folder-tree {
  display: flex;
  flex-direction: column;
  padding: 8px 0;
  font-size: 14px;
  color: var(--color-text-primary, #303133);
  user-select: none;
}

.folder-tree-root-item,
.folder-tree-special-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  cursor: pointer;
  transition: background 0.15s;
}

.folder-tree-root-item:hover,
.folder-tree-special-item:hover {
  background: var(--color-bg-hover, #f5f7fa);
}

.folder-tree-root-item.active,
.folder-tree-special-item.active {
  background: var(--color-primary-light-9, #ecf5ff);
  color: var(--color-primary, #ff7a5c);
  font-weight: 500;
}

.folder-tree-root-item.active :deep(.el-icon),
.folder-tree-special-item.active :deep(.el-icon) {
  color: var(--color-primary, #ff7a5c);
}

.folder-tree-loading,
.folder-tree-error,
.folder-tree-empty {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  font-size: 12px;
  color: var(--color-text-secondary, #606266);
}

.folder-tree-error {
  color: var(--color-danger, #f56c6c);
}

.folder-tree-divider {
  height: 1px;
  background: var(--color-border-lighter, #f0f0f0);
  margin: 8px 12px;
}

.folder-tree-root-label {
  flex: 1;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计时再加 dark 块
-->
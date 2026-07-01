<!--
  FolderTree.vue — 课题组网盘 PR3.2 文件夹树组件
  2026-07-01

  结构:
  - 顶级固定节点 "📁 我的网盘" (selectedFolderId=null)
  - "🗑️ 回收站" 节点 (PR3.7 接入, PR3.2 占位)
  - 递归渲染文件夹树 (el-tree 自定义节点)
  - hover 节点显示快捷操作 (新建子文件夹 / 删除)

  数据:
  - props.folderTree: 从 useFolderTree composable
  - props.selectedFolderId / emits.update:selectedFolderId
  - props.expandedFolderIds / emits.update:expandedFolderIds
-->
<template>
  <div class="folder-tree">
    <!-- 顶级固定节点 -->
    <div
      class="folder-tree-root-item"
      :class="{ active: selectedFolderId === null }"
      @click="$emit('update:selectedFolderId', null)"
    >
      <el-icon><FolderOpened v-if="selectedFolderId === null" /><Folder v-else /></el-icon>
      <span class="folder-tree-root-label">📁 我的网盘</span>
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
        @select="$emit('update:selectedFolderId', $event)"
        @toggle="$emit('toggle-expanded', $event)"
      />
    </template>

    <!-- 回收站占位 (PR3.7 接入真实数据) -->
    <div class="folder-tree-divider" />
    <div class="folder-tree-trash-item" disabled>
      <el-icon><Delete /></el-icon>
      <span>🗑️ 回收站 (PR3.7)</span>
    </div>
  </div>
</template>

<script setup>
import { Folder, FolderOpened, Delete, Loading, Warning } from '@element-plus/icons-vue'
import FolderTreeNode from './FolderTreeNode.vue'

defineProps({
  folderTree: { type: Array, default: () => [] },
  selectedFolderId: { type: [Number, null], default: null },
  expandedFolderIds: { type: Set, default: () => new Set() },
  loading: { type: Boolean, default: false },
  loadError: { type: [String, null], default: null }
})

defineEmits(['update:selectedFolderId', 'toggle-expanded', 'retry'])
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
.folder-tree-trash-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  cursor: pointer;
  transition: background 0.15s;
}

.folder-tree-root-item:hover,
.folder-tree-trash-item:hover:not([disabled]) {
  background: var(--color-bg-hover, #f5f7fa);
}

.folder-tree-root-item.active {
  background: var(--color-primary-light-9, #ecf5ff);
  color: var(--color-primary, #409eff);
  font-weight: 500;
}

.folder-tree-root-item.active :deep(.el-icon) {
  color: var(--color-primary, #409eff);
}

.folder-tree-trash-item {
  cursor: not-allowed;
  color: var(--color-text-placeholder, #909399);
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
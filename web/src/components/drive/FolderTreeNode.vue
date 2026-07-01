<!--
  FolderTreeNode.vue — 课题组网盘 PR3.2 递归文件夹节点
  2026-07-01

  单个文件夹节点:
  - 显示文件夹图标 + 名称 + 子节点计数
  - 展开/收起切换 (children 数组非空时)
  - 选中态 (active 背景)
  - 递归渲染 children
  - hover 显示快捷操作 (PR3.4 接入新建/删除/重命名)
-->
<template>
  <div class="folder-tree-node">
    <div
      class="folder-tree-node-row"
      :class="{ active: isSelected }"
      :style="{ paddingLeft: `${indentPx}px` }"
      @click="$emit('select', folder.id)"
    >
      <!-- 展开/收起箭头 -->
      <span
        v-if="hasChildren"
        class="folder-tree-node-toggle"
        @click.stop="$emit('toggle', folder.id)"
      >
        <el-icon>
          <CaretBottom v-if="isExpanded" />
          <CaretRight v-else />
        </el-icon>
      </span>
      <span v-else class="folder-tree-node-toggle-spacer" />

      <!-- 文件夹图标 -->
      <el-icon :class="['folder-tree-node-icon', isSelected ? 'active' : '']">
        <FolderOpened v-if="isSelected" />
        <Folder v-else />
      </el-icon>

      <!-- 文件夹名称 -->
      <span class="folder-tree-node-name" :title="folder.name">
        {{ folder.name }}
      </span>

      <!-- 子项计数徽章 -->
      <span v-if="folder.children?.length" class="folder-tree-node-count">
        {{ folder.children.length }}
      </span>
    </div>

    <!-- 递归子节点 (展开时才渲染) -->
    <template v-if="isExpanded && folder.children?.length">
      <FolderTreeNode
        v-for="child in folder.children"
        :key="child.id"
        :folder="child"
        :depth="depth + 1"
        :selected-folder-id="selectedFolderId"
        :expanded-folder-ids="expandedFolderIds"
        @select="$emit('select', $event)"
        @toggle="$emit('toggle', $event)"
      />
    </template>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Folder, FolderOpened, CaretBottom, CaretRight } from '@element-plus/icons-vue'

const props = defineProps({
  folder: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  selectedFolderId: { type: [Number, null], default: null },
  expandedFolderIds: { type: Set, default: () => new Set() }
})

defineEmits(['select', 'toggle'])

const hasChildren = computed(() => props.folder.children?.length > 0)
const isExpanded = computed(() => props.expandedFolderIds.has(props.folder.id))
const isSelected = computed(() => props.selectedFolderId === props.folder.id)
const indentPx = computed(() => 12 + props.depth * 16)  // 缩进: 顶级 12px, 每层 +16px
</script>

<style scoped>
.folder-tree-node {
  font-size: 14px;
  user-select: none;
}

.folder-tree-node-row {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px 6px 0;
  cursor: pointer;
  transition: background 0.15s;
  min-height: 32px;
}

.folder-tree-node-row:hover {
  background: var(--color-bg-hover, #f5f7fa);
}

.folder-tree-node-row.active {
  background: var(--color-primary-light-9, #ecf5ff);
  color: var(--color-primary, #409eff);
  font-weight: 500;
}

.folder-tree-node-toggle,
.folder-tree-node-toggle-spacer {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  cursor: pointer;
  color: var(--color-text-secondary, #606266);
}

.folder-tree-node-toggle:hover {
  color: var(--color-primary, #409eff);
}

.folder-tree-node-toggle-spacer {
  cursor: default;
}

.folder-tree-node-icon {
  flex-shrink: 0;
  color: var(--color-text-secondary, #909399);
}

.folder-tree-node-icon.active {
  color: var(--color-primary, #409eff);
}

.folder-tree-node-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.folder-tree-node-count {
  flex-shrink: 0;
  padding: 0 6px;
  border-radius: 8px;
  background: var(--color-bg-tag, #f0f0f0);
  color: var(--color-text-secondary, #606266);
  font-size: 11px;
  line-height: 16px;
}

.folder-tree-node-row.active .folder-tree-node-count {
  background: var(--color-primary, #409eff);
  color: var(--el-color-white, #ffffff);
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计时再加 dark 块
-->
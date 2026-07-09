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
  <!-- v2.0 (2026-07-09) Drive 美化: .drive-folder-tree-node 走共享 CSS + hover lift + 缩进指示线 -->
  <!-- v2.8 (2026-07-10) 右键菜单: 用 FolderContextMenu 包裹 row 节点, 右键弹菜单 -->
  <div class="folder-tree-node drive-folder-tree-node">
    <FolderContextMenu :items="folderMenuItems" placement="right-start" @command="onContextCommand">
      <div
        class="folder-tree-node-row drive-folder-tree-node-row"
        :class="{ 'is-active': isSelected }"
        :style="{ paddingLeft: `${indentPx}px` }"
        @click="$emit('select', folder.id)"
      >
        <!-- 展开/收起箭头 -->
        <span
          v-if="hasChildren"
          class="folder-tree-node-toggle drive-folder-tree-node-toggle"
          :class="{ 'is-expanded': isExpanded }"
          @click.stop="$emit('toggle', folder.id)"
        >
          <el-icon>
            <CaretBottom v-if="isExpanded" />
            <CaretRight v-else />
          </el-icon>
        </span>
        <span v-else class="folder-tree-node-toggle-spacer drive-folder-tree-node-toggle-spacer" />

        <!-- 文件夹图标 -->
        <el-icon :class="['folder-tree-node-icon drive-folder-tree-node-icon', isSelected ? 'active' : '']">
          <FolderOpened v-if="isSelected" />
          <Folder v-else />
        </el-icon>

        <!-- 文件夹名称 -->
        <span class="folder-tree-node-name" :title="folder.name">
          {{ folder.name }}
        </span>

        <!-- 子项计数徽章 (v2.0: 圆形 pill + 主色实底, 仿 .category-badge 风格) -->
        <span v-if="folder.children?.length" class="folder-tree-node-count">
          {{ folder.children.length }}
        </span>
      </div>
    </FolderContextMenu>

    <!-- v2.0: 缩进指示线 (深度 ≥ 1 时左侧 1px 主色 bg 30% 透明线, 增强树结构感) -->
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
// v2.0 (2026-07-09) Drive 美化: 引入 drive-view.css 让 .drive-folder-tree-node-* 生效
// v2.8 (2026-07-10) 右键菜单支持 (FolderContextMenu 包裹)
import '@/views/drive/drive-view.css'
import { computed } from 'vue'
import { Folder, FolderOpened, CaretBottom, CaretRight } from '@element-plus/icons-vue'
import FolderContextMenu from './FolderContextMenu.vue'

const props = defineProps({
  folder: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  selectedFolderId: { type: [Number, null], default: null },
  expandedFolderIds: { type: Set, default: () => new Set() }
})

const emit = defineEmits(['select', 'toggle', 'context-command'])

// v2.8: 子文件夹右键菜单项 (5 项)
const folderMenuItems = [
  { label: '📂 打开',         command: 'open' },
  { label: '➕ 新建子文件夹',   command: 'create-sub' },
  { label: '✏ 重命名',         command: 'rename' },
  { label: '🔗 复制 Folder ID', command: 'copy-id' },
  { label: '🗑 删除',          command: 'delete', divided: true },
]

function onContextCommand(cmd) {
  emit('context-command', cmd, props.folder)
}

const hasChildren = computed(() => props.folder.children?.length > 0)
const isExpanded = computed(() => props.expandedFolderIds.has(props.folder.id))
const isSelected = computed(() => props.selectedFolderId === props.folder.id)
const indentPx = computed(() => 12 + props.depth * 16)  // 缩进: 顶级 12px, 每层 +16px
</script>

<style scoped>
/*
 * v2.0 (2026-07-09) Drive 美化: 视觉样式已迁移 drive-view.css .drive-folder-tree-node-*
 * 本 scoped 块保留 layout-flex 细节 + 计数徽章 token 化
 */
.folder-tree-node {
  font-size: var(--font-size-base);
  user-select: none;
}

.folder-tree-node-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px var(--space-3) 6px 0;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  min-height: 32px;
  position: relative;
}

/* v2.0: 子节点左侧缩进指示线 */
.folder-tree-node-row[style*="paddingLeft: 28"],
.folder-tree-node-row[style*="paddingLeft: 44"],
.folder-tree-node-row[style*="paddingLeft: 60"] {
  position: relative;
}

.folder-tree-node-row[style*="paddingLeft: 28"]::before,
.folder-tree-node-row[style*="paddingLeft: 44"]::before,
.folder-tree-node-row[style*="paddingLeft: 60"]::before {
  content: '';
  position: absolute;
  left: 18px;
  top: 0;
  bottom: 0;
  width: 1px;
  background: rgba(var(--color-primary-rgb), 0.18);
  pointer-events: none;
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
  color: var(--color-text-secondary);
  transition: all var(--duration-fast) var(--ease-out);
}

.folder-tree-node-toggle:hover {
  color: var(--color-primary);
}

.folder-tree-node-toggle-spacer {
  cursor: default;
}

.folder-tree-node-icon {
  flex-shrink: 0;
  color: var(--color-text-secondary);
}

.folder-tree-node-icon.active {
  color: var(--color-primary);
}

.folder-tree-node-name {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* v2.0: 计数徽章改 pill + 主色实底 */
.folder-tree-node-count {
  flex-shrink: 0;
  min-width: 20px;
  padding: 0 6px;
  border-radius: var(--radius-full);
  background: var(--color-bg-tag, var(--color-info-bg));
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  line-height: 16px;
  text-align: center;
  font-weight: var(--font-weight-semibold);
  transition: all var(--duration-fast) var(--ease-out);
}

.folder-tree-node-row.is-active .folder-tree-node-count {
  background: var(--gradient-cta-button);
  color: #fff;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计时再加 dark 块
-->
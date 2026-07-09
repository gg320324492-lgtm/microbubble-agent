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
  <div class="folder-tree drive-folder-tree">
    <!-- 顶级固定节点: 我的网盘 (渐变激活) -->
    <div
      class="folder-tree-root-item drive-folder-tree-root-item"
      :class="{ 'is-active': selectedFolderId === null && specialView === null }"
      @click="handleRootClick"
    >
      <el-icon><FolderOpened v-if="selectedFolderId === null && specialView === null" /><Folder v-else /></el-icon>
      <span class="folder-tree-root-label">📁 我的网盘</span>
    </div>

    <!-- 收藏 (PR2 新增) -->
    <div
      class="folder-tree-special-item drive-folder-tree-special-item"
      :class="{ 'is-active': specialView === 'starred' }"
      @click="$emit('update:specialView', 'starred')"
    >
      <el-icon><Star v-if="specialView === 'starred'" /><StarFilled v-else /></el-icon>
      <span>⭐ 我的收藏</span>
    </div>

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
      />
    </template>

    <div class="folder-tree-divider drive-folder-tree-divider" />

    <!-- v2 PR7: 团队共享盘 (绿) + 文件请求 (橙) -->
    <div
      class="folder-tree-special-item drive-folder-tree-special-item is-team"
      :class="{ 'is-active': specialView === 'team' }"
      @click="$emit('update:specialView', 'team')"
    >
      <el-icon><Share /></el-icon>
      <span>🌐 团队共享盘</span>
    </div>
    <div
      class="folder-tree-special-item drive-folder-tree-special-item is-requests"
      :class="{ 'is-active': specialView === 'requests' }"
      @click="$emit('update:specialView', 'requests')"
    >
      <el-icon><Promotion /></el-icon>
      <span>📢 文件请求</span>
    </div>

    <!-- 回收站 (PR2 真实接入) (红) -->
    <div
      class="folder-tree-special-item drive-folder-tree-special-item is-trash"
      :class="{ 'is-active': specialView === 'trash' }"
      @click="$emit('update:specialView', 'trash')"
    >
      <el-icon><Delete /></el-icon>
      <span>🗑️ 回收站</span>
    </div>
  </div>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化: 引入 drive-view.css 让玻璃态侧栏 + 多色 special 生效
import '@/views/drive/drive-view.css'
import { Folder, FolderOpened, Delete, Loading, Warning, Star, StarFilled, Share, Promotion } from '@element-plus/icons-vue'
import FolderTreeNode from './FolderTreeNode.vue'

const props = defineProps({
  folderTree: { type: Array, default: () => [] },
  selectedFolderId: { type: [Number, null], default: null },
  expandedFolderIds: { type: Set, default: () => new Set() },
  loading: { type: Boolean, default: false },
  loadError: { type: [String, null], default: null },
  specialView: { type: [String, null], default: null }  // 'starred' | 'trash' | 'requests' | null (team 未来扩展)
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
/*
 * v2.0 (2026-07-09) Drive 美化: 全部视觉样式已迁 drive-view.css (.drive-folder-tree-* + .drive-sidebar)
 * 本 scoped 块只保留 forward-compat placeholder (后续如需 layout-flex 细节再加)
 */
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计时再加 dark 块
-->
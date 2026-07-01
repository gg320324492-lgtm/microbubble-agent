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
    <!-- 工具栏 (PR3.4 接入) -->
    <div class="drive-toolbar">
      <h2 class="drive-title">📁 课题组网盘</h2>
      <div class="drive-toolbar-actions">
        <el-input
          v-model="searchQuery"
          placeholder="搜索文件名..."
          clearable
          class="drive-search-input"
          disabled
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button-group>
          <el-button :icon="UploadFilled" disabled>上传文件</el-button>
          <el-button :icon="Folder" disabled>上传文件夹</el-button>
          <el-button :icon="Plus" disabled>新建文件夹</el-button>
        </el-button-group>
        <el-button-group class="drive-view-toggle">
          <el-button :type="viewMode === 'grid' ? 'primary' : 'default'" disabled>
            <el-icon><Grid /></el-icon>
          </el-button>
          <el-button :type="viewMode === 'list' ? 'primary' : 'default'" disabled>
            <el-icon><List /></el-icon>
          </el-button>
        </el-button-group>
      </div>
    </div>

    <!-- 主体布局: 左侧 FolderTree + 右侧 FileGrid -->
    <div class="drive-main">
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
          <div class="drive-file-area-placeholder">
            <el-icon class="placeholder-icon"><Folder /></el-icon>
            <p class="placeholder-text">文件列表 (PR3.3 接入)</p>
            <p class="placeholder-hint">
              骨架完成, 待 PR3.2 FolderTree + PR3.3 FileGrid 接入后真实展示
            </p>
          </div>
        </div>
      </main>
    </div>

    <!-- 底部状态条: 显示当前路径 + 容量 -->
    <div class="drive-statusbar">
      <span class="drive-status-path">{{ currentPathDisplay }}</span>
      <span class="drive-status-storage">容量统计 (PR3.7 接入)</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { Search, UploadFilled, Folder, Plus, Grid, List, Files } from '@element-plus/icons-vue'
import FolderTree from '@/components/drive/FolderTree.vue'
import { useFolderTree } from '@/composables/useFolderTree'

// === 文件夹树 (PR3.2 接入) ===
const {
  folderTree,
  expandedFolderIds,
  loading: treeLoading,
  loadError: treeLoadError,
  fetchTree: fetchFolderTree,
  toggleExpanded: toggleExpandedFolder
} = useFolderTree()

// === 状态 (PR3.1 骨架: 仅声明, 不调 API) ===
const selectedFolderId = ref(null)
const viewMode = ref('grid')  // grid | list
const searchQuery = ref('')

// === 生命周期 ===
onMounted(() => {
  fetchFolderTree()
})

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
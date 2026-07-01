<!--
  FileGrid.vue — 课题组网盘 PR3.3 文件网格
  2026-07-01

  布局:
  - 网格视图 (viewMode='grid'): CSS grid 自适应列数 (auto-fill, minmax 180px)
  - 列表视图 (viewMode='list'): 单列紧凑布局

  三态:
  - loading: Loading 占位
  - error: 错误提示 + 重试按钮
  - empty: 空状态 (按 folder / 顶级 区分文案)
  - data: 渲染 FileCard 列表

  分页: el-pagination 底部
-->
<template>
  <div class="file-grid-wrapper">
    <!-- loading -->
    <div v-if="loading" class="file-grid-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>加载文件列表...</span>
    </div>

    <!-- error -->
    <div v-else-if="loadError" class="file-grid-error">
      <el-icon><Warning /></el-icon>
      <span>{{ loadError }}</span>
      <el-button size="small" @click="$emit('retry')">重试</el-button>
    </div>

    <!-- empty -->
    <div v-else-if="files.length === 0" class="file-grid-empty">
      <el-icon :size="64"><Folder /></el-icon>
      <p class="file-grid-empty-title">{{ emptyTitle }}</p>
      <p class="file-grid-empty-hint">{{ emptyHint }}</p>
    </div>

    <!-- data: grid 模式 -->
    <div v-else-if="viewMode === 'grid'" class="file-grid-grid">
      <FileCard
        v-for="file in files"
        :key="file.id"
        :file="file"
        :selected="selectedFileIds.includes(file.id)"
        :selectable="true"
        :view-mode="'grid'"
        @click="(f) => $emit('file-click', f)"
        @toggle-select="(id) => $emit('toggle-select', id)"
        @toggle-star="(f) => $emit('file-toggle-star', f)"
        @preview="(f) => $emit('file-preview', f)"
        @rename="(f) => $emit('file-rename', f)"
        @move="(f) => $emit('file-move', f)"
        @update-visibility="(f) => $emit('file-update-visibility', f)"
        @extract-to-kb="(f) => $emit('file-extract-to-kb', f)"
        @share-link="(f) => $emit('file-share-link', f)"
        @delete="(f) => $emit('file-delete', f)"
      />
    </div>

    <!-- data: list 模式 -->
    <div v-else class="file-grid-list">
      <FileCard
        v-for="file in files"
        :key="file.id"
        :file="file"
        :selected="selectedFileIds.includes(file.id)"
        :selectable="true"
        :view-mode="'list'"
        @click="(f) => $emit('file-click', f)"
        @toggle-select="(id) => $emit('toggle-select', id)"
        @toggle-star="(f) => $emit('file-toggle-star', f)"
        @preview="(f) => $emit('file-preview', f)"
        @rename="(f) => $emit('file-rename', f)"
        @move="(f) => $emit('file-move', f)"
        @update-visibility="(f) => $emit('file-update-visibility', f)"
        @extract-to-kb="(f) => $emit('file-extract-to-kb', f)"
        @share-link="(f) => $emit('file-share-link', f)"
        @delete="(f) => $emit('file-delete', f)"
      />
    </div>

    <!-- 分页 -->
    <el-pagination
      v-if="!loading && !loadError && total > pageSize"
      :current-page="currentPage"
      :page-size="pageSize"
      :total="total"
      layout="total, prev, pager, next"
      class="file-grid-pagination"
      @current-change="$emit('page-change', $event)"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Loading, Warning, Folder } from '@element-plus/icons-vue'
import FileCard from './FileCard.vue'

const props = defineProps({
  files: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  currentPage: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  selectedFileIds: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  loadError: { type: [String, null], default: null },
  viewMode: { type: String, default: 'grid' },  // grid | list
  isTopLevel: { type: Boolean, default: true }  // 是否顶级目录 (空态文案区分)
})

defineEmits(['retry', 'file-click', 'file-preview', 'file-rename', 'file-move', 'file-update-visibility', 'file-extract-to-kb', 'file-share-link', 'file-delete', 'toggle-select', 'file-toggle-star', 'page-change'])

// === 空态文案 ===
const emptyTitle = computed(() => {
  if (props.isTopLevel) return '网盘中暂无文件'
  return '此文件夹为空'
})

const emptyHint = computed(() => {
  if (props.isTopLevel) return '点击上方"上传文件"按钮，或直接将文件拖入网盘'
  return '将文件拖入此文件夹，或上传到此处'
})
</script>

<style scoped>
.file-grid-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 300px;
}

.file-grid-loading,
.file-grid-error,
.file-grid-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  color: var(--color-text-secondary, #606266);
  gap: 12px;
}

.file-grid-error {
  color: var(--color-danger, #f56c6c);
}

.file-grid-empty {
  color: var(--color-text-placeholder, #909399);
}

.file-grid-empty-title {
  font-size: 16px;
  font-weight: 500;
  margin: 0;
  color: var(--color-text-secondary, #606266);
}

.file-grid-empty-hint {
  font-size: 13px;
  margin: 0;
  color: var(--color-text-placeholder, #909399);
}

.file-grid-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}

.file-grid-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.file-grid-pagination {
  margin-top: 24px;
  display: flex;
  justify-content: center;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计时再加 dark 块
-->
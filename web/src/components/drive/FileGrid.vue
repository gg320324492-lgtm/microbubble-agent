<!--
  FileGrid.vue — 课题组网盘 PR3.3 文件网格
  2026-07-01
  2026-07-11 v2.16: 加 detail 视图 (默认), 用户决策「横向长条展示更多信息」

  布局:
  - detail 视图 (viewMode='detail', v2.16 默认): 单行表格, columns = checkbox + star + icon + name + size + date + owner + visibility + actions, 56px 行高, 169 文件信息密度高
  - 网格视图 (viewMode='grid'): CSS grid 自适应列数 (auto-fill, minmax 180px) — 缩略图场景
  - 列表视图 (viewMode='list'): 单列紧凑布局 — 仅保留兼容

  三态:
  - loading: Loading 占位
  - error: 错误提示 + 重试按钮
  - empty: 空状态 (按 folder / 顶级 区分文案)
  - data: 渲染 FileCard 列表

  分页: el-pagination 底部
-->
<template>
  <div class="file-grid-wrapper">
    <!-- v2.0 (2026-07-09) Drive 美化: 三态全部走 drive-view.css skeleton + 渐变 hero -->
    <!-- loading: 7 个 skeleton card 占位 (与 grid 列数对齐) -->
    <div v-if="loading" class="drive-grid-loading">
      <div v-for="n in 7" :key="n" class="drive-grid-loading-skeleton">
        <div class="skeleton skeleton-circle drive-grid-loading-skeleton-circle"></div>
        <div class="skeleton skeleton-text drive-grid-loading-skeleton-bar" style="width: 85%"></div>
        <div class="skeleton skeleton-text drive-grid-loading-skeleton-bar" style="width: 55%"></div>
        <div class="skeleton skeleton-button" style="width: 60px; margin-top: 8px;"></div>
      </div>
    </div>

    <!-- error: 红橙渐变 hero -->
    <div v-else-if="loadError" class="drive-grid-error">
      <el-icon class="drive-grid-error-icon"><WarningFilled /></el-icon>
      <p class="drive-grid-error-title">{{ loadErrorTitle }}</p>
      <p class="drive-grid-error-hint">请检查网络连接后重试</p>
      <el-button class="drive-upload-btn drive-grid-error-retry" @click="$emit('retry')">重试</el-button>
    </div>

    <!-- empty: 渐变 hero + 主色 CTA (顶级) / 子文件夹差异文案 / 搜索无结果差异 -->
    <div
      v-else-if="files.length === 0"
      class="drive-grid-empty"
      :data-state="emptyState"
    >
      <div class="drive-grid-empty-hero">
        <el-icon :size="48">
          <component :is="emptyIconComponent" />
        </el-icon>
      </div>
      <p class="drive-grid-empty-title">{{ emptyTitle }}</p>
      <p class="drive-grid-empty-hint">{{ emptyHint }}</p>
      <el-button
        v-if="emptyState === 'top-level' && !isSearch"
        class="drive-upload-btn drive-grid-empty-cta"
        :icon="UploadFilled"
        @click="$emit('empty-cta-click')"
      >
        上传文件
      </el-button>
    </div>

    <!-- data: detail 模式 (v2.16 默认, 像 macOS Finder 列表) -->
    <div v-else-if="viewMode === 'detail'" class="drive-file-detail">
      <FileCard
        v-for="file in files"
        :key="file.id"
        :file="file"
        :selected="selectedFileIds.includes(file.id)"
        :selectable="true"
        :view-mode="'detail'"
        @click="(f, e) => $emit('file-click', f, e)"
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

    <!-- data: grid 模式 -->
    <div v-else-if="viewMode === 'grid'" class="drive-file-grid">
      <FileCard
        v-for="file in files"
        :key="file.id"
        :file="file"
        :selected="selectedFileIds.includes(file.id)"
        :selectable="true"
        :view-mode="'grid'"
        @click="(f, e) => $emit('file-click', f, e)"
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
    <div v-else class="drive-grid-list drive-file-grid-list">
      <FileCard
        v-for="file in files"
        :key="file.id"
        :file="file"
        :selected="selectedFileIds.includes(file.id)"
        :selectable="true"
        :view-mode="'list'"
        @click="(f, e) => $emit('file-click', f, e)"
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

    <!-- v2.0: 分页走 .drive-grid-pagination + 加 sizes 选择器 -->
    <el-pagination
      v-if="!loading && !loadError && total > pageSize"
      :current-page="currentPage"
      :page-size="pageSize"
      :total="total"
      :page-sizes="[20, 50, 100]"
      layout="total, sizes, prev, pager, next, jumper"
      class="drive-grid-pagination"
      @current-change="$emit('page-change', $event)"
      @size-change="$emit('size-change', $event)"
    />
  </div>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化: 三态走 drive-view.css + 加 isSearch 区分搜索空态
// 引入 drive-view.css 让 .drive-grid-loading/-empty/-error / .drive-file-grid 生效
import '@/views/drive/drive-view.css'
import { computed } from 'vue'
import {
  WarningFilled, Folder, Search as SearchIcon, UploadFilled, FolderAdd
} from '@element-plus/icons-vue'
import FileCard from './FileCard.vue'

const props = defineProps({
  files: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  currentPage: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  selectedFileIds: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  loadError: { type: [String, null], default: null },
  viewMode: { type: String, default: 'detail' },  // v2.16: detail 默认 (替代 grid) | grid | list
  isTopLevel: { type: Boolean, default: true },  // 是否顶级目录 (空态文案区分)
  isSearch: { type: Boolean, default: false },   // v2.0: 是否搜索无结果态
  searchKeyword: { type: String, default: '' }   // v2.0: 用于 "未找到与 X 相关" 文案
})

defineEmits(['retry', 'file-click', 'file-preview', 'file-rename', 'file-move', 'file-update-visibility', 'file-extract-to-kb', 'file-share-link', 'file-delete', 'toggle-select', 'file-toggle-star', 'page-change', 'size-change', 'empty-cta-click'])

// === v2.0: 空态多态 (top-level / folder / search) ===
const emptyState = computed(() => {
  if (props.isSearch) return 'search'
  return props.isTopLevel ? 'top-level' : 'folder'
})

const emptyTitle = computed(() => {
  if (props.isSearch) return '未找到相关文件'
  if (props.isTopLevel) return '网盘中暂无文件'
  return '此文件夹为空'
})

const emptyHint = computed(() => {
  if (props.isSearch) {
    return props.searchKeyword
      ? `没有找到与 "${props.searchKeyword}" 相关的文件,试试更短的关键词?`
      : '没有找到相关文件,试试调整搜索关键词?'
  }
  if (props.isTopLevel) return '点击下方"上传文件"按钮,或直接将文件拖入网盘'
  return '将文件拖入此文件夹,或上传到此处'
})

const emptyIconComponent = computed(() => {
  if (props.isSearch) return SearchIcon
  return props.isTopLevel ? FolderAdd : Folder
})

const loadErrorTitle = computed(() => {
  return '加载失败'
})
</script>

<style scoped>
/*
 * v2.0 (2026-07-09) Drive 美化: 三态 styles 已迁移到 drive-view.css .drive-grid-loading/-empty/-error
 * 本块仅保留 layout 容器 (file-grid-wrapper flex column + min-height)
 */
.file-grid-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 320px;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR3.7 统一审计时再加 dark 块
-->
<!--
  FileRequestFilesView.vue — 文件请求详情: 点进去看这个请求收到了哪些文件 (2026-11-10)

  设计:
  - 由 FileRequestListPanel / FileRequestListView 在"打开某个请求"时渲染,
    返回按钮由本组件自己画 (父层只切状态, 不复制模板)。
  - 文件列表复用 DriveFileTable —— 与网盘其他文件夹**同一套表格** (列/排序/预览
    行为一致), 不再另写一份简化列表 (类 20.250 ①: 同一件事两套实现必漂移)。
  - 顶部单独一块「正在上传」: 后端 /file-requests/{id}/files 会把 pending/uploading
    的会话一起返回, 带 percent (分片计数口径)。有进行中的会话时每 3s 轮询一次,
    没有就停 —— 不让空闲页面长期打接口。
-->
<template>
  <div class="frf">
    <div class="frf-head">
      <el-button link @click="$emit('back')">← 返回文件请求</el-button>
      <div class="frf-title">
        <strong>{{ request?.title || '文件请求' }}</strong>
        <span class="frf-count">已收到 {{ files.length }} 个文件</span>
      </div>
      <el-button link @click="load">刷新</el-button>
    </div>

    <!-- 正在上传: 有会话就显示, 空数组不占位 -->
    <div v-if="uploading.length" class="frf-uploading">
      <div class="frf-uploading-title">正在上传（{{ uploading.length }}）</div>
      <div v-for="u in uploading" :key="u.upload_id" class="frf-up-card">
        <div class="frf-up-top">
          <span class="frf-up-name" :title="u.filename">{{ u.filename }}</span>
          <span class="frf-up-pct">{{ u.percent }}%</span>
        </div>
        <div class="frf-up-bar">
          <div class="frf-up-fill" :style="{ width: u.percent + '%' }" />
        </div>
        <div class="frf-up-meta">
          <span>{{ u.uploaded_chunks }} / {{ u.total_chunks }} 片</span>
          <span v-if="u.uploader_name">· {{ u.uploader_name }}</span>
          <span>· {{ formatSize(u.file_size) }}</span>
          <span v-if="u.status === 'pending'">· 等待开始</span>
        </div>
      </div>
    </div>

    <div v-if="loading && files.length === 0" class="frf-state">加载中...</div>
    <div v-else-if="loadError" class="frf-state error">
      {{ loadError }}
      <el-button link type="primary" @click="load">重试</el-button>
    </div>
    <div v-else-if="files.length === 0 && uploading.length === 0" class="frf-state">
      这个请求还没有收到文件。
    </div>

    <DriveFileTable
      v-else-if="files.length || uploading.length"
      :files="files"
      :folders="[]"
      :loading="loading"
      :load-error="loadError"
      :selected-ids="[]"
      :active-key="null"
      :sort-by="'created_at'"
      :sort-order="'desc'"
      :total="files.length"
      :current-page="1"
      :page-size="500"
      @row-preview="onPreview"
      @retry="load"
    />

    <FilePreviewDialog v-model="previewVisible" :file="previewFile" />
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'
import DriveFileTable from './DriveFileTable.vue'
import FilePreviewDialog from './FilePreviewDialog.vue'
import { formatSize as formatBytes } from '@/utils/format'

const props = defineProps({
  request: { type: Object, default: null },
})
defineEmits(['back'])

const files = ref([])
const uploading = ref([])
const loading = ref(false)
const loadError = ref(null)
const previewVisible = ref(false)
const previewFile = ref(null)
let pollTimer = null

function formatSize(bytes) {
  const n = Number(bytes) || 0
  return n > 0 ? formatBytes(n) : '0 B'
}

/**
 * @param {boolean} [silent] 轮询刷新: 不置 loading (否则表格每 3s 闪一次加载态),
 *        失败也不覆盖已有内容 —— 一次抖动不该把"正在上传"整块换成错误页。
 */
async function load(silent = false) {
  if (!props.request?.id) return
  if (!silent) {
    loading.value = true
    loadError.value = null
  }
  try {
    const resp = await axios.get(`/api/v1/file-requests/${props.request.id}/files`)
    files.value = resp.data?.files || []
    uploading.value = resp.data?.uploading || []
    loadError.value = null
  } catch (e) {
    if (!silent) loadError.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    if (!silent) loading.value = false
    // 有进行中的会话就继续轮询; 全部结束 ⇒ 停 (最后一次 load 已把它们移进 files)
    if (uploading.value.length && !pollTimer) {
      pollTimer = setInterval(() => load(true), 3000)
    } else if (!uploading.value.length && pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }
}

function onPreview(file) {
  if (!file?.id) return
  previewFile.value = file
  previewVisible.value = true
}

onMounted(load)
onBeforeUnmount(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.frf {
  padding: 4px 2px 12px;
}
.frf-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.frf-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex: 1 1 auto;
  min-width: 0;
}
.frf-title strong {
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
}
.frf-count {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}
.frf-uploading {
  background: var(--color-bg-warm);
  border: 1px solid var(--color-primary-border);
  border-radius: var(--radius-lg);
  padding: 12px;
  margin-bottom: 12px;
}
.frf-uploading-title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}
.frf-up-card + .frf-up-card {
  margin-top: 10px;
}
.frf-up-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: var(--font-size-xs);
  margin-bottom: 4px;
}
.frf-up-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-primary);
}
.frf-up-pct {
  flex-shrink: 0;
  font-weight: 600;
  color: var(--color-primary-dark);
}
.frf-up-bar {
  height: 6px;
  border-radius: 3px;
  background: var(--color-border);
  overflow: hidden;
}
.frf-up-fill {
  height: 100%;
  background: var(--color-primary);
  transition: width 0.4s ease;
}
.frf-up-meta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--color-text-secondary);
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.frf-state {
  padding: 24px 8px;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}
.frf-state.error {
  color: var(--color-danger);
}
</style>

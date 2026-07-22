<!--
  MobileFilePreviewSwipe.vue — PR8 移动端文件 swipe 预览
  2026-07-22

  路由:
  - /drive/preview/:id (单文件模式)
  - /drive/preview/:id?list=id1,id2,id3&idx=0 (多文件 swipe 列表模式)

  布局 (移动端):
  - 顶部: 返回按钮 + 当前文件名 + idx/total indicator
  - 中部: 文件预览 (图片直接显示 / PDF 用 iframe / 视频/音频 media 标签 / 其他类型显示类型 + 大小)
  - 底部 (仅多文件模式): ●○○○○ indicator + 上一张/下一张按钮
  - swipe gesture: 左右切下一个/上一个文件 (距离 > 50px 且 < 300ms 触发)

  数据流:
  - 文件元信息: GET /api/v1/drive/files/{id}
  - 文件 blob: GET /api/v1/drive/files/{id}/download?disposition=inline (复用 FilePreviewDialog 路径)
  - 多文件列表: 路由 query ?list=id1,id2,id3 + 当前 idx

  Dark mode: 非 scoped 块 (v60-v67 教训第 5 次强化)
-->
<template>
  <div ref="containerEl" class="mobile-file-preview-swipe drive-page">
    <!-- Sticky 顶部 -->
    <div class="mfps-header">
      <button type="button" class="mfps-back" aria-label="返回" title="返回" @click="goBack">
        <el-icon :size="20"><ArrowLeft /></el-icon>
      </button>
      <div class="mfps-title-area">
        <h2 class="mfps-title">{{ file?.file_name || file?.title || '加载中...' }}</h2>
        <div v-if="isListMode && totalCount > 0" class="mfps-subtitle">
          {{ currentIdx + 1 }} / {{ totalCount }}
        </div>
      </div>
      <div class="mfps-header-spacer" />
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="mfps-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <p>加载预览中...</p>
    </div>

    <!-- 错误态 -->
    <div v-else-if="loadError" class="mfps-error">
      <el-icon :size="48" class="mfps-error-icon"><WarningFilled /></el-icon>
      <p>{{ loadError }}</p>
      <button type="button" class="mfps-retry-btn" @click="loadFile">重试</button>
    </div>

    <!-- 预览主体 -->
    <div v-else-if="file" class="mfps-body">
      <!-- 图片预览 -->
      <div v-if="previewType === 'image'" class="mfps-image-wrapper">
        <img :src="blobUrl" :alt="file.file_name" class="mfps-image" />
      </div>

      <!-- 视频预览 -->
      <div v-else-if="previewType === 'video'" class="mfps-video-wrapper">
        <video :src="blobUrl" controls class="mfps-video" />
      </div>

      <!-- 音频预览 -->
      <div v-else-if="previewType === 'audio'" class="mfps-audio-wrapper">
        <div class="mfps-audio-icon"><el-icon :size="64"><Headset /></el-icon></div>
        <div class="mfps-audio-name">{{ file.file_name }}</div>
        <audio :src="blobUrl" controls class="mfps-audio" />
      </div>

      <!-- PDF 预览 -->
      <div v-else-if="previewType === 'pdf'" class="mfps-pdf-wrapper">
        <iframe :src="blobUrl" class="mfps-pdf" frameborder="0" />
      </div>

      <!-- 不支持预览 (其他类型) -->
      <div v-else class="mfps-unsupported">
        <el-icon :size="64"><Document /></el-icon>
        <p class="mfps-unsupported-title">{{ file.file_name }}</p>
        <p class="mfps-unsupported-hint">{{ file.file_type || '未知类型' }} · {{ formatSize(file.file_size) }}</p>
        <p class="mfps-unsupported-text">暂不支持在线预览，请下载后查看</p>
        <button type="button" class="mfps-download-btn" @click="downloadFile">
          ⬇ 下载文件
        </button>
      </div>
    </div>

    <!-- 多文件 indicator + 控制 -->
    <div v-if="isListMode && totalCount > 1" class="mfps-controls">
      <div class="mfps-indicators" role="tablist">
        <span
          v-for="(id, i) in fileIdList"
          :key="id"
          class="mfps-dot"
          :class="{ active: i === currentIdx }"
          :aria-label="`跳到第 ${i + 1} 张`"
          @click="goToIdx(i)"
        />
      </div>
      <div class="mfps-nav-buttons">
        <button
          type="button"
          class="mfps-nav-btn"
          :disabled="currentIdx === 0"
          aria-label="上一张"
          @click="goPrev"
        >
          ← 上一张
        </button>
        <button
          type="button"
          class="mfps-nav-btn"
          :disabled="currentIdx >= totalCount - 1"
          aria-label="下一张"
          @click="goNext"
        >
          下一张 →
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useSwipeGesture } from '@/composables/useSwipeGesture'
import { formatSize } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const containerEl = ref(null)
const file = ref(null)
const blobUrl = ref('')
const loading = ref(false)
const loadError = ref('')

const fileIdList = computed(() => {
  const raw = route.query.list
  if (!raw) return []
  return String(raw).split(',').map((s) => s.trim()).filter(Boolean)
})

const currentIdx = computed(() => {
  const idx = parseInt(route.query.idx, 10)
  return Number.isFinite(idx) && idx >= 0 ? idx : 0
})

const isListMode = computed(() => fileIdList.value.length > 1)

const totalCount = computed(() => fileIdList.value.length)

const currentFileId = computed(() => {
  if (isListMode.value) {
    return fileIdList.value[currentIdx.value] || route.params.id
  }
  return route.params.id
})

const previewType = computed(() => {
  if (!file.value) return 'unsupported'
  const mime = (file.value.file_type || '').toLowerCase()
  if (mime.startsWith('image/')) return 'image'
  if (mime.startsWith('video/')) return 'video'
  if (mime.startsWith('audio/')) return 'audio'
  if (mime === 'application/pdf' || mime.includes('pdf')) return 'pdf'
  return 'unsupported'
})

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/drive')
  }
}

function goPrev() {
  if (currentIdx.value > 0) {
    updateIdx(currentIdx.value - 1)
  }
}

function goNext() {
  if (currentIdx.value < totalCount.value - 1) {
    updateIdx(currentIdx.value + 1)
  }
}

function goToIdx(idx) {
  if (idx >= 0 && idx < totalCount.value) {
    updateIdx(idx)
  }
}

function updateIdx(idx) {
  router.replace({
    query: { ...route.query, idx: String(idx) },
  })
}

async function loadFile() {
  const id = currentFileId.value
  if (!id) {
    loadError.value = '文件 ID 缺失'
    return
  }
  loading.value = true
  loadError.value = ''
  file.value = null
  // 清理旧 blob URL 防止内存泄漏
  if (blobUrl.value) {
    URL.revokeObjectURL(blobUrl.value)
    blobUrl.value = ''
  }

  try {
    // 1. 元信息
    const metaResp = await axios.get(`/api/v1/drive/files/${id}`)
    file.value = metaResp.data

    // 2. blob (仅当预览类型支持时拉取)
    if (previewType.value !== 'unsupported') {
      const resp = await axios.get(`/api/v1/drive/files/${id}/download?disposition=inline`, {
        responseType: 'blob',
      })
      blobUrl.value = URL.createObjectURL(new Blob([resp.data], { type: file.value.file_type || 'application/octet-stream' }))
    }
  } catch (err) {
    console.error('[MobileFilePreviewSwipe] load error:', err)
    loadError.value = err.response?.data?.error?.message || err.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function downloadFile() {
  if (!file.value) return
  try {
    const resp = await axios.get(`/api/v1/drive/files/${file.value.id}/download`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([resp.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = file.value.file_name || `file_${file.value.id}`
    a.click()
    window.URL.revokeObjectURL(url)
    ElMessage.success('下载已开始')
  } catch (err) {
    console.error('[MobileFilePreviewSwipe] download error:', err)
    ElMessage.error('下载失败')
  }
}

// Swipe gesture: 左右切文件
const { onSwipeLeft, onSwipeRight } = useSwipeGesture(containerEl, { threshold: 50, timeout: 300 })
onSwipeLeft(() => goNext())
onSwipeRight(() => goPrev())

watch(currentFileId, () => {
  loadFile()
})

onMounted(() => {
  loadFile()
})
</script>

<style scoped>
.mobile-file-preview-swipe {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--color-bg-page, #f5f5f5);
}

.mfps-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--color-bg-card, #fff);
  border-bottom: 1px solid var(--color-border-light, rgba(0, 0, 0, 0.06));
  position: sticky;
  top: 0;
  z-index: 10;
}

.mfps-back,
.mfps-header-spacer {
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--color-text-primary, #333);
}

.mfps-title-area {
  flex: 1;
  min-width: 0;
}

.mfps-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary, #333);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.mfps-subtitle {
  font-size: 12px;
  color: var(--color-text-secondary, #666);
  margin-top: 2px;
}

.mfps-loading,
.mfps-error {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px 24px;
  text-align: center;
}

.mfps-error-icon {
  color: var(--color-warning, #e6a23c);
}

.mfps-retry-btn,
.mfps-download-btn {
  margin-top: 12px;
  padding: 10px 24px;
  border: 1px solid var(--color-primary, #FF7A5C);
  background: var(--color-primary, #FF7A5C);
  color: var(--el-color-white);
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
}

.mfps-body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  overflow: auto;
}

.mfps-image-wrapper,
.mfps-video-wrapper,
.mfps-pdf-wrapper {
  width: 100%;
  max-width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.mfps-image {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
  border-radius: 8px;
}

.mfps-video {
  width: 100%;
  max-height: 70vh;
}

.mfps-pdf {
  width: 100%;
  height: 70vh;
  border: none;
}

.mfps-audio-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 32px 16px;
  width: 100%;
}

.mfps-audio-icon {
  color: var(--color-primary, #FF7A5C);
}

.mfps-audio-name {
  font-size: 14px;
  color: var(--color-text-primary, #333);
  text-align: center;
  word-break: break-all;
}

.mfps-audio {
  width: 100%;
  max-width: 360px;
}

.mfps-unsupported {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 48px 24px;
  text-align: center;
  color: var(--color-text-secondary, #666);
}

.mfps-unsupported-title {
  margin: 8px 0 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary, #333);
  word-break: break-all;
}

.mfps-unsupported-hint {
  font-size: 13px;
  margin: 0;
}

.mfps-unsupported-text {
  margin-top: 12px;
  font-size: 13px;
}

.mfps-controls {
  background: var(--color-bg-card, #fff);
  border-top: 1px solid var(--color-border-light, rgba(0, 0, 0, 0.06));
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mfps-indicators {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.mfps-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-border-light, rgba(0, 0, 0, 0.2));
  cursor: pointer;
  transition: background 200ms ease;
}

.mfps-dot.active {
  background: var(--color-primary, #FF7A5C);
  width: 24px;
  border-radius: 4px;
}

.mfps-nav-buttons {
  display: flex;
  gap: 8px;
}

.mfps-nav-btn {
  flex: 1;
  padding: 10px;
  border: 1px solid var(--color-border, rgba(0, 0, 0, 0.12));
  background: transparent;
  color: var(--color-text-primary, #333);
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
}

.mfps-nav-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>

<!-- Dark mode 非 scoped 块 (v60-v67 教训) -->
<style>
[data-theme='dark'] .mobile-file-preview-swipe {
  background: var(--color-bg-page);
}
[data-theme='dark'] .mfps-header {
  background: var(--color-bg-card);
  border-bottom-color: var(--color-border);
}
[data-theme='dark'] .mfps-title {
  color: var(--color-text-primary);
}
[data-theme='dark'] .mfps-back,
[data-theme='dark'] .mfps-header-spacer {
  color: var(--color-text-primary);
}
[data-theme='dark'] .mfps-controls {
  background: var(--color-bg-card);
  border-top-color: var(--color-border);
}
[data-theme='dark'] .mfps-nav-btn {
  border-color: var(--color-border);
  color: var(--color-text-primary);
}
</style>
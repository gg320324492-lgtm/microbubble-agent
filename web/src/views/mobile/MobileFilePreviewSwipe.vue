<!--
  MobileFilePreviewSwipe.vue — v2 PR8.2 移动端文件预览 swipe 切换 + pinch zoom
  2026-07-02
-->
<template>
  <Teleport to="body">
    <div class="preview-overlay" @touchstart.passive="onTouchStart" @touchmove.passive="onTouchMove" @touchend="onTouchEnd">
      <header class="preview-header">
        <button type="button" class="preview-close" aria-label="关闭预览" @click="onClose">✕</button>
        <div class="preview-meta">
          <div class="preview-position">{{ currentIdx + 1 }} / {{ files.length }}</div>
          <div class="preview-name">{{ currentFile?.file_name || currentFile?.title || '未命名' }}</div>
        </div>
        <button type="button" class="preview-action" aria-label="更多操作" @click="onMore">⋯</button>
      </header>

      <div class="preview-content" @dblclick="resetZoom">
        <img v-if="isImage" ref="imgRef" :src="previewUrl" class="preview-image" :style="imageStyle" alt="预览图片" />
        <video v-else-if="isVideo" ref="videoRef" :src="previewUrl" class="preview-media" controls playsinline />
        <audio v-else-if="isAudio" ref="audioRef" :src="previewUrl" class="preview-audio" controls />
        <iframe v-else-if="isPdf" :src="previewUrl" class="preview-iframe" title="PDF 预览" />
        <div v-else class="preview-fallback">
          <p class="fallback-icon">📄</p>
          <p class="fallback-text">{{ currentFile?.file_name || '该类型不支持预览' }}</p>
          <el-button type="primary" size="small" @click="onDownload">下载</el-button>
        </div>
      </div>

      <div class="preview-hint-left" :class="{ visible: swipeDirection === 'left' }">‹</div>
      <div class="preview-hint-right" :class="{ visible: swipeDirection === 'right' }">›</div>

      <div v-if="zoom !== 1" class="preview-zoom-indicator">{{ Math.round(zoom * 100) }}%</div>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const props = defineProps({
  files: { type: Array, required: true },
  initialIdx: { type: Number, default: 0 },
  startId: { type: [Number, String], default: null },
})
const emit = defineEmits(['close', 'change'])

const currentIdx = ref(props.initialIdx)
const currentFile = computed(() => props.files[currentIdx.value] || null)
const previewUrl = computed(() => currentFile.value ? `/api/v1/drive/files/${currentFile.value.id}/preview` : '')

function isImageOf(file) { if (!file) return false; const t = (file.file_type || '').toLowerCase(); return t.startsWith('image/') }
function isVideoOf(file) { if (!file) return false; const t = (file.file_type || '').toLowerCase(); return t.startsWith('video/') }
function isAudioOf(file) { if (!file) return false; const t = (file.file_type || '').toLowerCase(); return t.startsWith('audio/') }
function isPdfOf(file) { if (!file) return false; return (file.file_name || '').toLowerCase().endsWith('.pdf') || file.file_type === 'application/pdf' }
const isImage = computed(() => isImageOf(currentFile.value))
const isVideo = computed(() => isVideoOf(currentFile.value))
const isAudio = computed(() => isAudioOf(currentFile.value))
const isPdf = computed(() => isPdfOf(currentFile.value))

const zoom = ref(1)
const translateX = ref(0)
const translateY = ref(0)
const imageStyle = computed(() => ({
  transform: `translate(${translateX.value}px, ${translateY.value}px) scale(${zoom.value})`,
  transition: zoomAnimating.value ? 'transform 0.2s ease' : 'none',
}))
const zoomAnimating = ref(false)

let touchStartX = 0, touchStartY = 0
let pinchStartDist = 0, pinchStartZoom = 1
const swipeDirection = ref(null)

function onTouchStart(e) {
  if (e.touches.length === 1) { touchStartX = e.touches[0].clientX; touchStartY = e.touches[0].clientY }
  else if (e.touches.length === 2) { pinchStartDist = getPinchDist(e.touches); pinchStartZoom = zoom.value }
}
function onTouchMove(e) {
  if (e.touches.length === 2 && pinchStartDist > 0) {
    const dist = getPinchDist(e.touches)
    if (dist > 0) zoom.value = Math.min(4, Math.max(0.5, pinchStartZoom * (dist / pinchStartDist)))
  } else if (e.touches.length === 1 && zoom.value === 1) {
    const dx = e.touches[0].clientX - touchStartX
    if (Math.abs(dx) > 30) swipeDirection.value = dx > 0 ? 'right' : 'left'
  }
}
function onTouchEnd() {
  if (swipeDirection.value === 'left') next()
  else if (swipeDirection.value === 'right') prev()
  swipeDirection.value = null
  pinchStartDist = 0
}
function getPinchDist(touches) {
  if (touches.length < 2) return 0
  return Math.hypot(touches[0].clientX - touches[1].clientX, touches[0].clientY - touches[1].clientY)
}
function resetZoom() {
  zoomAnimating.value = true
  zoom.value = 1; translateX.value = 0; translateY.value = 0
  setTimeout(() => { zoomAnimating.value = false }, 250)
}
function next() { if (currentIdx.value < props.files.length - 1) { currentIdx.value++; resetZoom(); emit('change', currentIdx.value) } else ElMessage.info('已是最后一张') }
function prev() { if (currentIdx.value > 0) { currentIdx.value--; resetZoom(); emit('change', currentIdx.value) } else ElMessage.info('已是第一张') }
function onClose() { emit('close') }
function onMore() { ElMessage.info('更多操作待接入') }
async function onDownload() {
  if (!currentFile.value) return
  try {
    const resp = await axios.get(`/api/v1/drive/files/${currentFile.value.id}/download`, { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([resp.data]))
    const a = document.createElement('a'); a.href = url; a.download = currentFile.value.file_name || `file_${currentFile.value.id}`; a.click()
    window.URL.revokeObjectURL(url)
  } catch (e) { ElMessage.error('下载失败') }
}
function onKeydown(e) { if (e.key === 'ArrowRight') next(); else if (e.key === 'ArrowLeft') prev(); else if (e.key === 'Escape') onClose() }

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  if (props.startId != null) {
    const idx = props.files.findIndex(f => String(f.id) === String(props.startId))
    if (idx >= 0) currentIdx.value = idx
  }
})
onBeforeUnmount(() => { document.removeEventListener('keydown', onKeydown) })
</script>

<style scoped>
.preview-overlay { position: fixed; inset: 0; background: rgba(0, 0, 0, 0.92); z-index: 4000; display: flex; flex-direction: column; touch-action: pan-y; }
.preview-header { position: relative; z-index: 1; display: flex; align-items: center; padding: 12px 16px; background: rgba(0, 0, 0, 0.5); color: #fff; gap: 12px; flex-shrink: 0; }
.preview-close, .preview-action { width: 40px; height: 40px; background: transparent; border: none; color: #fff; font-size: 22px; cursor: pointer; border-radius: 6px; flex-shrink: 0; }
.preview-meta { flex: 1; text-align: center; overflow: hidden; }
.preview-position { font-size: 12px; opacity: 0.7; }
.preview-name { font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.preview-content { flex: 1; display: flex; align-items: center; justify-content: center; overflow: hidden; position: relative; }
.preview-image { max-width: 100%; max-height: 100%; object-fit: contain; user-select: none; -webkit-user-drag: none; }
.preview-media, .preview-iframe { max-width: 100%; max-height: 100%; width: 100%; height: 100%; border: none; background: #000; }
.preview-audio { width: 80%; max-width: 400px; }
.preview-fallback { text-align: center; color: #fff; }
.fallback-icon { font-size: 64px; margin-bottom: 16px; }
.preview-hint-left, .preview-hint-right { position: absolute; top: 50%; transform: translateY(-50%); font-size: 64px; color: rgba(255, 255, 255, 0.3); pointer-events: none; opacity: 0; transition: opacity 0.15s ease; }
.preview-hint-left { left: 16px; }
.preview-hint-right { right: 16px; }
.preview-hint-left.visible, .preview-hint-right.visible { opacity: 1; }
.preview-zoom-indicator { position: absolute; top: 80px; right: 16px; background: rgba(0, 0, 0, 0.6); color: #fff; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-family: monospace; }
</style>
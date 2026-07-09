<!--
  FilePreviewDialog.vue — 课题组网盘 PR4.6 预览对话框 (桌面 + 移动端共享)
  2026-07-01

  支持 4 种预览:
  - 图片 (image/*): <img> 标签
  - 视频 (video/*): <video controls> 标签 (Range 流式)
  - 音频 (audio/*): <audio controls> 标签
  - PDF: <iframe> 浏览器原生 PDF viewer
  - 其他: 提示 "请下载后查看" + 下载按钮

  Props:
  - modelValue: 显隐 (v-model:show)
  - file: {id, file_name, file_type, file_size}

  数据流:
  - URL = /api/v1/drive/files/{id}/download?disposition=inline
  - JWT token 通过 axios.get 走 Authorization 头
  - 拿到 blob 后 createObjectURL + URL.createObjectURL 渲染

  注意:
  - PR4.6 修复: 后端 content-type 已用 mimetypes.guess_type 推断真实 MIME
  - 不需要 explicit fetch 时传 Accept 头 (后端 content-type 已正确)
  - 必须 Authorization 头 (private 文件必须 owner 鉴权)
-->
<template>
  <el-dialog
    v-model="visible"
    class="drive-dialog"
    :title="title"
    width="80%"
    top="5vh"
    :close-on-press-escape="true"
    :show-close="true"
    @closed="onClose"
  >
    <!-- 加载态 -->
    <div v-if="loading" class="preview-loading">
      <el-icon class="is-loading"><Loading /></el-icon>
      <p>加载预览中...</p>
    </div>

    <!-- 错误态 -->
    <div v-else-if="error" class="preview-error">
      <p>⚠️ {{ error }}</p>
      <el-button type="primary" @click="loadPreview">重试</el-button>
    </div>

    <!-- 图片预览 -->
    <div v-else-if="previewType === 'image'" class="preview-image-wrapper">
      <img :src="previewUrl" :alt="file?.file_name" class="preview-image" />
    </div>

    <!-- 视频预览 -->
    <div v-else-if="previewType === 'video'" class="preview-video-wrapper">
      <video :src="previewUrl" controls class="preview-video" />
    </div>

    <!-- 音频预览 -->
    <div v-else-if="previewType === 'audio'" class="preview-audio-wrapper">
      <audio :src="previewUrl" controls class="preview-audio" />
    </div>

    <!-- PDF 预览 (浏览器原生) -->
    <div v-else-if="previewType === 'pdf'" class="preview-pdf-wrapper">
      <iframe :src="previewUrl" class="preview-pdf" frameborder="0" />
    </div>

    <!-- 不支持预览: 下载提示 -->
    <div v-else class="preview-unsupported">
      <p class="unsupported-icon">📄</p>
      <p>该文件类型不支持在线预览</p>
      <p class="unsupported-hint">文件名: {{ file?.file_name }}</p>
      <p class="unsupported-hint">类型: {{ file?.file_type || '未知' }}</p>
      <el-button type="primary" :icon="Download" @click="downloadFile">
        下载文件
      </el-button>
    </div>

    <template #footer>
      <el-button :icon="ChatDotRound" @click="onGoDetail">
        查看详情/评论
      </el-button>
      <el-button @click="visible = false">关闭</el-button>
      <el-button type="primary" :icon="Download" @click="downloadFile">
        下载
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
// v2.0 (2026-07-09) Drive 美化: 引入 drive-view.css 让 .drive-dialog 玻璃态生效
import '@/views/drive/drive-view.css'

/**
 * FilePreviewDialog.vue — 通用文件预览
 *
 * 支持图片/视频/音频/PDF 4 种, 其他类型提示下载
 *
 * 关键设计:
 * 1. 后端 content-type 走 mimetypes.guess_type (PR4.6 修复), 浏览器自动识别
 * 2. JWT 鉴权: 必须 Authorization 头 (private 文件必须 owner)
 * 3. Blob URL: fetch response.blob() + createObjectURL 避免 blob URL 跨标签失效
 * 4. 关闭 dialog 时 revokeObjectURL 防内存泄漏
 */
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { Loading, Download, ChatDotRound } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  file: { type: Object, default: null }  // {id, file_name, file_type, file_size}
})

const emit = defineEmits(['update:modelValue'])
const router = useRouter()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

// === 状态 ===
const previewUrl = ref(null)
const loading = ref(false)
const error = ref(null)

// === 计算属性 ===
const title = computed(() => {
  if (!props.file) return '文件预览'
  return `预览: ${props.file.file_name || props.file.title || ''}`
})

const previewType = computed(() => {
  if (!props.file) return null
  const type = (props.file.file_type || '').toLowerCase()
  if (['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp'].some(t => type.includes(t))) {
    return 'image'
  }
  if (['.mp4', '.webm', '.ogg', '.mov', '.avi', '.mkv'].some(t => type.includes(t))) {
    return 'video'
  }
  if (['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a'].some(t => type.includes(t))) {
    return 'audio'
  }
  if (type.includes('pdf')) {
    return 'pdf'
  }
  return 'unsupported'
})

// === 生命周期 ===
watch(visible, async (newVal) => {
  if (newVal && props.file?.id) {
    await loadPreview()
  } else {
    cleanup()
  }
})

onUnmounted(() => {
  cleanup()
})

// === 数据加载 ===
async function loadPreview() {
  if (!props.file?.id) return
  loading.value = true
  error.value = null
  cleanup()
  try {
    const resp = await axios.get(`/api/v1/drive/files/${props.file.id}/download`, {
      params: { disposition: 'inline' },
      responseType: 'blob'
    })
    // 从 response 创建 blob URL (后端 content-type 已正确, 浏览器自动识别)
    const blob = new Blob([resp.data])
    previewUrl.value = URL.createObjectURL(blob)
  } catch (e) {
    error.value = e.message || '加载失败'
    previewUrl.value = null
    console.error('Preview load failed:', e)
  } finally {
    loading.value = false
  }
}

function cleanup() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value)
    previewUrl.value = null
  }
}

function onClose() {
  cleanup()
}

function onGoDetail() {
  if (!props.file?.id) return
  visible.value = false  // 关闭预览
  cleanup()              // 释放 blob URL
  router.push(`/drive/file/${props.file.id}`)
}

async function downloadFile() {
  if (!props.file?.id) return
  try {
    const resp = await axios.get(`/api/v1/drive/files/${props.file.id}/download`, {
      responseType: 'blob'
    })
    const url = window.URL.createObjectURL(new Blob([resp.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', props.file.file_name || props.file.title || 'download')
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  } catch (e) {
    ElMessage.error('下载失败')
  }
}
</script>

<style scoped>
.preview-loading,
.preview-error,
.preview-unsupported {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  min-height: 200px;
}

.preview-loading p,
.preview-error p,
.preview-unsupported p {
  margin: 8px 0;
  color: var(--color-text-secondary);
}

.preview-loading .is-loading {
  font-size: 32px;
  color: var(--color-primary);
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.preview-image-wrapper,
.preview-video-wrapper,
.preview-audio-wrapper,
.preview-pdf-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  max-height: 70vh;
  overflow: auto;
}

.preview-image {
  max-width: 100%;
  max-height: 70vh;
  object-fit: contain;
}

.preview-video {
  max-width: 100%;
  max-height: 70vh;
}

.preview-audio {
  width: 100%;
  max-width: 500px;
}

.preview-pdf {
  width: 100%;
  height: 70vh;
  border: 1px solid var(--color-border-light);
  border-radius: 4px;
}

.unsupported-icon {
  font-size: 64px;
  margin-bottom: 12px;
  opacity: 0.6;
}

.unsupported-hint {
  font-size: 12px;
  color: var(--color-text-placeholder);
  margin: 4px 0;
}
</style>

<!--
  v60-v67 教训: dark mode 跨组件覆盖必须放非 scoped <style> 块
  本组件 PR4.7 统一审计 dark 模式时再加 dark 块
-->

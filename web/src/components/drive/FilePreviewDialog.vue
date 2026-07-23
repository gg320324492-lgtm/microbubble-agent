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
    <!-- v2.7 (2026-07-10): 大文件确认 (单独 if, 不参与主 v-else-if 链) -->
    <div v-if="pendingLargeFileConfirm" class="preview-warning">
      <el-icon :size="32" style="color: var(--color-warning);"><WarningFilled /></el-icon>
      <p class="warning-title">文件较大,继续加载?</p>
      <p class="warning-hint">{{ file?.file_name }} ({{ formatSize(file?.file_size) }}) 加载可能需几秒。</p>
      <div class="warning-actions">
        <el-button @click="pendingLargeFileConfirm = false">取消</el-button>
        <el-button type="primary" @click="confirmLoadLargeFile">继续加载</el-button>
      </div>
    </div>

    <!-- v2.8 (PR8.6): 文件锁提示 banner — 其他人正在编辑时显示 -->
    <div v-else-if="isLockedByOthers" class="preview-lock-banner">
      <el-icon :size="18"><Lock /></el-icon>
      <span>
        <strong>{{ lockHolderName }}</strong> 正在编辑此文件
        <span v-if="lockHolder?.ttl_remaining > 0" class="lock-ttl">
          (锁剩余 {{ Math.ceil(lockHolder.ttl_remaining / 60) }} 分钟)
        </span>
      </span>
      <el-button size="small" text @click="refreshLock">刷新状态</el-button>
    </div>

    <!-- 加载态 -->
    <div v-else-if="loading" class="preview-loading">
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
      <img :src="blobUrl" :alt="file?.file_name" class="preview-image" />
    </div>

    <!-- 视频预览 -->
    <div v-else-if="previewType === 'video'" class="preview-video-wrapper">
      <video :src="blobUrl" controls class="preview-video" />
    </div>

    <!-- 音频预览 -->
    <div v-else-if="previewType === 'audio'" class="preview-audio-wrapper">
      <audio :src="blobUrl" controls class="preview-audio" />
    </div>

    <!-- PDF 预览 (浏览器原生) -->
    <div v-else-if="previewType === 'pdf'" class="preview-pdf-wrapper">
      <iframe :src="blobUrl" class="preview-pdf" frameborder="0" />
    </div>

    <!-- Office 365 预览器是完整的跨域 Web 应用，会继续嵌套 PowerPoint/Word/Excel frame，
         并依赖自身 origin、cookie/storage、内部 CORS 与 OAuth。不要添加 sandbox：
         即使放开 allow-same-origin，继承到嵌套 frame 的其余 sandbox 限制仍会破坏启动链。
         officeapps.live.com 与本站跨域，浏览器同源策略已阻止它访问父页面 DOM。
         referrerpolicy="no-referrer" 避免向 Office 泄露父页面 URL。
         @error 只捕获 iframe 导航失败；微软页面内部 JS 错误无法从父页面捕获。
    -->
    <div v-else-if="previewType === 'office' && !officeFallbackToThumbnail" class="preview-office-wrapper">
      <iframe
        :src="officeViewerUrl"
        class="preview-office-iframe"
        frameborder="0"
        allowfullscreen
        referrerpolicy="no-referrer"
        @error="onOfficeViewerError"
      />
    </div>
    <!-- v2.7.1: Office viewer 加载失败时降级显示 thumbnail (沿用 unsupported 模式) -->
    <div v-else-if="previewType === 'office' && officeFallbackToThumbnail" class="preview-office-wrapper">
      <img
        v-if="thumbnailUrl"
        :src="thumbnailUrl"
        :alt="file?.file_name"
        class="preview-image"
      />
      <el-icon v-else :size="64" class="preview-unsupported-icon"><Document /></el-icon>
      <p class="preview-unsupported-title">Office 在线预览加载失败</p>
      <p class="preview-unsupported-hint">
        {{ file?.file_name }} (网络问题或 CDN 不可达)
      </p>
      <el-button class="drive-upload-btn" :icon="Download" @click="downloadFile">
        下载文件
      </el-button>
    </div>

    <!-- v2.7 新增: 文本预览 (15 类 txt/md/json/csv/xml/yaml/sh 等) -->
    <div v-else-if="previewType === 'text'" class="preview-text-wrapper">
      <pre class="preview-text-content">{{ textContent }}</pre>
      <div v-if="textTruncated" class="preview-text-warn">
        ⚠️ 文件过大 (&gt; {{ formatSize(textMaxBytes) }}),已截断前 {{ formatSize(textMaxBytes) }} 预览
      </div>
    </div>

    <!-- v2.7 改进: 不支持预览 = thumbnail fallback + 元信息 + 下载按钮 -->
    <div v-else class="preview-unsupported">
      <img
        v-if="thumbnailUrl"
        :src="thumbnailUrl"
        :alt="file?.file_name"
        class="preview-unsupported-thumb"
      />
      <el-icon v-else :size="64" class="preview-unsupported-icon"><Document /></el-icon>

      <p class="preview-unsupported-title">暂不支持「{{ fileExtension }}」完全在线预览</p>
      <p class="preview-unsupported-hint">文件名: {{ file?.file_name }}</p>
      <p class="preview-unsupported-hint">类型: {{ file?.file_type }} · 大小: {{ formatSize(file?.file_size) }}</p>
      <p v-if="file?.created_at" class="preview-unsupported-hint">上传时间: {{ formatDateTime(file?.created_at) }}</p>

      <el-button class="drive-upload-btn" :icon="Download" @click="downloadFile">
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
 * FilePreviewDialog.vue — 通用文件预览 (v2.7: 8 类 + thumbnail fallback)
 *
 * 2026-07-10 v2.7 增强:
 * - 支持 15 类文本 (txt/md/json/csv/xml/yaml/sh/sql 等) — blob+TextDecoder
 * - 支持 9 类 Office (ppt/doc/xls + ODF) — Office 365 viewer iframe
 * - 不支持降级 thumbnail (public HTTPS URL, 不需 JWT)
 * - 大文件 (>30MB 图 / >100MB 视音) 确认弹窗
 * - 文本 > 500KB 截断 + warning
 * - binary 文本 fallback unsupported
 *
 * 支持矩阵: image / video / audio / pdf / office / text / unsupported
 *
 * 关键设计:
 * 1. 后端 content-type 走 mimetypes.guess_type (PR4.6)
 * 2. JWT 鉴权: 必须 Authorization 头
 * 3. blob URL: fetch.blob() + createObjectURL
 * 4. thumbnail URL: public HTTPS 不需 JWT, 给 Office Viewer src
 * 5. revokeObjectURL 防内存泄漏
 */
import { ref, computed, watch, onUnmounted, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  Loading, Download, ChatDotRound, Document, WarningFilled, Lock
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  file: { type: Object, default: null }
})

const emit = defineEmits(['update:modelValue'])
const router = useRouter()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v)
})

// === v2.7 状态 (rename previewUrl → blobUrl 更准确) ===
const blobUrl = ref(null)
const thumbnailUrl = ref(null)
const loading = ref(false)
const error = ref(null)
const textContent = ref('')
const textTruncated = ref(false)
const officeViewerUrl = ref('')
const officeFallbackToThumbnail = ref(false)   // v2.7.1: Office viewer 网络错误时降级 thumbnail
const pendingLargeFileConfirm = ref(false)

// === v2.8 文件级软锁 (PR8.6) ===
const lockHolder = ref(null)  // {user_id, username, name, acquired_at, ttl_remaining}
const lockHolderName = computed(() => {
  if (!lockHolder.value) return ''
  return lockHolder.value.name || lockHolder.value.username || `用户${lockHolder.value.user_id}`
})
const isLockedByOthers = computed(() => {
  // 仅在已知当前用户时才能判定, 否则保守提示有锁
  if (!lockHolder.value) return false
  // 通过 authStore.userId 区分自己 vs 他人 (authStore 单例)
  try {
    const auth = JSON.parse(localStorage.getItem('microbubble_auth') || '{}')
    const me = auth?.userInfo?.id || auth?.user?.id
    return lockHolder.value.user_id && lockHolder.value.user_id !== me
  } catch {
    return true
  }
})

const textMaxBytes = 500 * 1024

const LARGE_IMAGE_BYTES = 30 * 1024 * 1024
const LARGE_MEDIA_BYTES = 100 * 1024 * 1024

// === v2.7: previewType computed 重写 (8 类优先级) ===
const TEXT_EXTS = [
  '.txt', '.md', '.json', '.csv', '.tsv', '.xml', '.log',
  '.yaml', '.yml', '.ini', '.conf', '.sh', '.bat',
  '.sql', '.env', '.properties'
]
const OFFICE_EXTS = [
  '.ppt', '.pptx', '.doc', '.docx', '.xls', '.xlsx',
  '.odp', '.odt', '.ods'
]
const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp']
const VIDEO_EXTS = ['.mp4', '.webm', '.ogg', '.mov', '.avi', '.mkv']
const AUDIO_EXTS = ['.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a']

const previewType = computed(() => {
  if (!props.file) return null
  const type = (props.file.file_type || '').toLowerCase()
  if (TEXT_EXTS.some(e => type.includes(e))) return 'text'
  if (OFFICE_EXTS.some(e => type.includes(e))) return 'office'
  if (IMAGE_EXTS.some(e => type.includes(e))) return 'image'
  if (VIDEO_EXTS.some(e => type.includes(e))) return 'video'
  if (AUDIO_EXTS.some(e => type.includes(e))) return 'audio'
  if (type.includes('pdf')) return 'pdf'
  return 'unsupported'
})

const fileExtension = computed(() => {
  const fn = props.file?.file_name || ''
  const i = fn.lastIndexOf('.')
  if (i >= 0) return fn.slice(i).toUpperCase()
  return (props.file?.file_type || '').toUpperCase()
})

function formatSize(bytes) {
  if (!bytes || bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`
}

function formatDateTime(s) {
  if (!s) return ''
  try {
    const d = new Date(s)
    if (isNaN(d.getTime())) return s
    const pad = (n) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
  } catch { return s }
}

// binary 检测: 前 512 字节含 NUL byte 即判 binary
function isBinaryBlob(blob) {
  return new Promise(resolve => {
    const slice = blob.slice(0, 512)
    const reader = new FileReader()
    reader.onload = () => {
      const view = new Uint8Array(reader.result)
      for (let i = 0; i < view.length; i++) if (view[i] === 0) return resolve(true)
      resolve(false)
    }
    reader.onerror = () => resolve(false)
    reader.readAsArrayBuffer(slice)
  })
}

// === 生命周期 ===
watch(visible, async (newVal) => {
  if (newVal && props.file?.id) {
    const size = props.file?.file_size || 0
    const isLarge =
      (previewType.value === 'image' && size > LARGE_IMAGE_BYTES) ||
      ((previewType.value === 'video' || previewType.value === 'audio') && size > LARGE_MEDIA_BYTES)
    if (isLarge) {
      pendingLargeFileConfirm.value = true
    } else {
      await loadPreview()
    }
    // v2.8: 进入预览时拉锁状态 + 启动心跳续期
    await refreshLock()
  } else {
    cleanup()
    pendingLargeFileConfirm.value = false
    // v2.8: 关闭时释放锁 (仅当前用户持有的情况)
    await releaseLockIfMine()
  }
}, { immediate: true })  // v2.7: 加 immediate, 初次 visible=true 也触发 (fix vitest mount 时 watch 不触发)

async function confirmLoadLargeFile() {
  pendingLargeFileConfirm.value = false
  await loadPreview()
  await refreshLock()
}

onMounted(() => {
  // v2.8: 启动锁心跳 (60s 一次, TTL 5 分钟)
  lockHeartbeatTimer.value = setInterval(refreshLock, 60_000)
})

onUnmounted(() => {
  cleanup()
  if (lockHeartbeatTimer.value) {
    clearInterval(lockHeartbeatTimer.value)
    lockHeartbeatTimer.value = null
  }
  releaseLockIfMine()
})

// === v2.8 文件锁实现 ===
const lockHeartbeatTimer = ref(null)

async function refreshLock() {
  if (!props.file?.id) return
  try {
    const resp = await axios.get(`/api/v1/drive/files/${props.file.id}/lock`)
    lockHolder.value = resp.data?.locked ? resp.data : null
    // 锁空 + 自己刚才释放 → 心跳主动获取 (heartbeat 模式)
    if (!resp.data?.locked) {
      try {
        const acquire = await axios.post(`/api/v1/drive/files/${props.file.id}/lock`)
        if (acquire.data?.locked) lockHolder.value = acquire.data
      } catch (e) {
        // 409 等情况忽略 — 仅展示当前 holder
        if (e?.response?.data?.locked) {
          lockHolder.value = e.response.data
        }
      }
    }
  } catch (e) {
    console.warn('[FilePreviewDialog] lock refresh failed:', e?.message || e)
  }
}

async function releaseLockIfMine() {
  if (!props.file?.id) return
  if (!lockHolder.value) return
  if (isLockedByOthers.value) return  // 别人的锁不释放
  try {
    await axios.delete(`/api/v1/drive/files/${props.file.id}/lock`)
    lockHolder.value = null
  } catch (e) {
    // 静默吞 — 释放失败无副作用 (TTL 5 分钟自然过期)
    console.warn('[FilePreviewDialog] lock release failed:', e?.message || e)
  }
}

// === v2.7 loadPreview 重写 ===
async function loadPreview() {
  if (!props.file?.id) return
  loading.value = true
  error.value = null
  cleanup()

  try {
    const pt = previewType.value
    if (pt === 'office') {
      // 拉 thumbnail (public HTTPS) 用于 fallback; officeViewerUrl 用 file_path 拼 minio URL
      try {
        const thumbResp = await axios.get(`/api/v1/drive/files/${props.file.id}/thumbnail`)
        if (thumbResp.data?.thumbnail_url) thumbnailUrl.value = thumbResp.data.thumbnail_url
      } catch {}
      const filePath = props.file?.file_path || ''
      const fileUrl = filePath ? `https://agent.mnb-lab.cn/minio/microbubble/${filePath}` : (thumbnailUrl.value || '')
      if (fileUrl) {
        officeViewerUrl.value = `https://view.officeapps.live.com/op/embed.aspx?src=${encodeURIComponent(fileUrl)}`
      } else {
        throw new Error('文件路径不可用')
      }
    } else if (pt === 'text') {
      const resp = await axios.get(
        `/api/v1/drive/files/${props.file.id}/download?disposition=inline`,
        { responseType: 'blob' }
      )
      if (await isBinaryBlob(resp.data)) {
        throw new Error('文件是二进制, 不能文本预览')
      }
      const buf = await resp.data.arrayBuffer()
      const limited = buf.byteLength > textMaxBytes
      const slice = limited ? buf.slice(0, textMaxBytes) : buf
      textContent.value = new TextDecoder('utf-8', { fatal: false }).decode(slice)
      textTruncated.value = limited
      try {
        const thumbResp = await axios.get(`/api/v1/drive/files/${props.file.id}/thumbnail`)
        if (thumbResp.data?.thumbnail_url) thumbnailUrl.value = thumbResp.data.thumbnail_url
      } catch {}
    } else if (pt === 'unsupported') {
      // 拉 thumbnail 即可
      try {
        const thumbResp = await axios.get(`/api/v1/drive/files/${props.file.id}/thumbnail`)
        if (thumbResp.data?.thumbnail_url) thumbnailUrl.value = thumbResp.data.thumbnail_url
      } catch {}
    } else {
      // image / video / audio / pdf — 原有 blob URL 模式
      const resp = await axios.get(
        `/api/v1/drive/files/${props.file.id}/download?disposition=inline`,
        { responseType: 'blob' }
      )
      blobUrl.value = URL.createObjectURL(new Blob([resp.data]))
    }
  } catch (e) {
    error.value = e.message || '加载失败'
    console.error('Preview load failed:', e)
  } finally {
    loading.value = false
  }
}

function cleanup() {
  if (blobUrl.value) {
    URL.revokeObjectURL(blobUrl.value)
    blobUrl.value = null
  }
  textContent.value = ''
  textTruncated.value = false
  officeViewerUrl.value = ''
  officeFallbackToThumbnail.value = false   // v2.7.1
  thumbnailUrl.value = null
  error.value = null
}

function onClose() {
  cleanup()
  pendingLargeFileConfirm.value = false
}

// v2.7.1: Office viewer 网络错误降级
// @error 捕获 iframe src 加载失败 (e.g. network/CDN 不可达),
// 不捕获微软内部 JS 错误 (那些在 iframe 隔离 console 内)
function onOfficeViewerError(e) {
  console.warn('[FilePreviewDialog] Office viewer iframe src failed to load, fallback to thumbnail:', e?.message || e)
  officeFallbackToThumbnail.value = true
}

function onGoDetail() {
  if (!props.file?.id) return
  visible.value = false
  cleanup()
  router.push(`/drive/file/${props.file.id}`)
}

async function downloadFile() {
  if (!props.file?.id) return
  try {
    const resp = await axios.get(`/api/v1/drive/files/${props.file.id}/download`, { responseType: 'blob' })
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

// v2.7.1 (2026-07-10): 暴露内部方法给父级 + 让 vitest wrapper.vm 能调用
defineExpose({
  previewType,        // 让父级也能读 previewType
  officeFallbackToThumbnail,
  onOfficeViewerError, // 让 vitest 测试 @error handler
  cleanup,            // 让父级可手动清除 (e.g. 路由切换时清理)
  // v2.8 (PR8.6): 暴露锁状态供测试
  lockHolder,
  isLockedByOthers,
  lockHolderName,
  refreshLock,
  releaseLockIfMine,
})
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

/* v2.8 (PR8.6): 文件锁 banner — 暖琥珀色提示他人正在编辑 */
.preview-lock-banner {
  display: flex;
  align-items: center;
  gap: var(--space-2, 8px);
  padding: 10px 16px;
  margin-bottom: var(--space-3, 12px);
  border-radius: var(--radius-md, 8px);
  background: rgba(255, 179, 71, 0.12);  /* accent amber */
  border: 1px solid rgba(255, 179, 71, 0.4);
  color: var(--color-text-primary);
  font-size: var(--font-size-sm, 13px);
}
.preview-lock-banner .lock-ttl {
  color: var(--color-text-secondary);
  margin-left: var(--space-1, 4px);
  font-size: var(--font-size-xs, 12px);
}
.preview-lock-banner .el-icon {
  color: var(--color-accent, #FFB347);
  flex-shrink: 0;
}
.preview-lock-banner strong {
  color: var(--color-accent, #FFB347);
  font-weight: var(--font-weight-semibold, 600);
}
.preview-lock-banner .el-button {
  margin-left: auto;
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

/* v2.7: Office viewer + text + unsupported improved UI */
.preview-office-wrapper {
  display: flex;
  flex-direction: column;
  min-height: 300px;
}

.preview-office-fallback {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-4);
  color: var(--color-text-secondary);
}

.preview-office-fallback .preview-image {
  max-height: 50vh;
}

/* 不支持预览 — improved (thumbnail + 元信息) */
.preview-unsupported {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-8) var(--space-4);
  text-align: center;
  min-height: 320px;
  gap: var(--space-3);
}

.preview-unsupported-thumb {
  max-width: 320px;
  max-height: 40vh;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border-light);
  background: var(--color-bg-page);
  padding: var(--space-2);
}

.preview-unsupported-icon {
  opacity: 0.5;
  color: var(--color-text-secondary);
  font-size: 64px;
}

.preview-unsupported-title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin: var(--space-2) 0 0;
}

.preview-unsupported-hint {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  margin: var(--space-1) 0;
}
</style>

<!-- v2.7 (2026-07-10): Dark mode 非 scoped 覆盖 (v60-v67 教训) -->
<style>
[data-theme="dark"] .preview-unsupported-thumb {
  background-color: var(--color-bg-page);
  border-color: var(--color-border-base);
}

[data-theme="dark"] .preview-text-warn {
  color: var(--color-warning);
}
</style>
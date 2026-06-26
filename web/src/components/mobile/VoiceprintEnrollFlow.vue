<template>
  <Teleport to="body">
    <Transition name="enroll-flow">
      <div v-if="modelValue" class="enroll-flow-root">
        <!-- Header -->
        <div class="flow-header">
          <button
            type="button"
            class="header-btn"
            aria-label="返回"
            title="返回"
            @click="onCancel"
          >✕</button>
          <h2 class="flow-title">声纹录入</h2>
          <div class="header-spacer" />
        </div>

        <!-- 步骤指示器 -->
        <div class="step-indicator">
          <div
            v-for="(label, idx) in steps"
            :key="idx"
            class="step"
            :class="{
              active: step === idx + 1,
              done: step > idx + 1,
            }"
          >
            <div class="step-circle">
              <span v-if="step > idx + 1">✓</span>
              <span v-else>{{ idx + 1 }}</span>
            </div>
            <div class="step-label">{{ label }}</div>
          </div>
        </div>

        <!-- 主内容 -->
        <main class="flow-main">
          <!-- Step 1: 选择录入方式 -->
          <div v-if="step === 1" class="step-content">
            <div v-if="member" class="member-info">
              <div class="member-avatar">{{ member.name?.charAt(0) }}</div>
              <div>
                <div class="member-name">{{ member.name }}</div>
                <div class="member-status">
                  <span v-if="member.voice_enrolled_at" class="status-success">
                    ✓ 已录入（{{ member.voice_sample_count || 0 }} 次）
                  </span>
                  <span v-else class="status-pending">未录入</span>
                </div>
              </div>
            </div>

            <h3 class="step-title">选择录入方式</h3>

            <button
              type="button"
              class="option-card"
              @click="selectMethod('record')"
            >
              <div class="option-icon" style="background: linear-gradient(135deg, #FF7A5C, #FFB347)">🎤</div>
              <div class="option-info">
                <div class="option-title">麦克风录制</div>
                <div class="option-desc">实时录音（推荐）</div>
              </div>
              <div class="option-arrow">›</div>
            </button>

            <button
              type="button"
              class="option-card"
              @click="selectMethod('upload')"
            >
              <div class="option-icon" style="background: linear-gradient(135deg, #67C23A, #95D475)">📁</div>
              <div class="option-info">
                <div class="option-title">上传音频文件</div>
                <div class="option-desc">wav / mp3 / m4a</div>
              </div>
              <div class="option-arrow">›</div>
            </button>
          </div>

          <!-- Step 2: 录制 / 上传 -->
          <div v-else-if="step === 2" class="step-content">
            <!-- 录制模式 -->
            <div v-if="method === 'record'" class="record-mode">
              <div class="tip">
                请在<strong>安静环境</strong>下说一段 10 秒以上的话
              </div>

              <div class="record-area">
                <div
                  class="record-circle"
                  :class="{ recording: recording, hasRecording: !!recordedBlob }"
                  @click="onRecordClick"
                >
                  <div v-if="!recording && !recordedBlob" class="record-prompt">
                    <div class="big-icon">🎤</div>
                    <div class="hint-text">点击开始</div>
                  </div>
                  <div v-else-if="recording" class="recording-state">
                    <div class="pulse-ring" />
                    <div class="rec-time">{{ formatTime(recordSeconds) }}</div>
                  </div>
                  <div v-else class="recorded-state">
                    <div class="check-icon">✓</div>
                    <div class="hint-text">录制完成</div>
                  </div>
                </div>
              </div>

              <div v-if="recordedBlob" class="audio-preview">
                <audio :src="recordedUrl" controls class="audio-player" />
                <button
                  type="button"
                  class="btn-secondary"
                  @click="discardRecord"
                >重录</button>
              </div>

              <!-- 录音中提示 -->
              <div v-if="recording" class="rec-status">
                <span class="rec-dot" />
                录音中... 再次点击停止
              </div>
            </div>

            <!-- 上传模式 -->
            <div v-else-if="method === 'upload'" class="upload-mode">
              <label class="upload-zone" :class="{ hasFile: !!selectedFile }">
                <input
                  ref="fileInputRef"
                  type="file"
                  accept="audio/*"
                  hidden
                  aria-label="选择音频文件"
                  title="选择音频文件"
                  @change="onFileChange"
                />
                <div v-if="!selectedFile" class="upload-empty">
                  <div class="big-icon">📁</div>
                  <div class="upload-title">点击选择音频文件</div>
                  <div class="upload-hint">支持 wav / mp3 / m4a / ogg</div>
                </div>
                <div v-else class="upload-filled">
                  <div class="big-icon">🎵</div>
                  <div class="upload-title">{{ selectedFile.name }}</div>
                  <div class="upload-hint">{{ formatFileSize(selectedFile.size) }}</div>
                </div>
              </label>
            </div>
          </div>

          <!-- Step 3: 确认 -->
          <div v-else-if="step === 3" class="step-content">
            <div v-if="uploading" class="uploading-state">
              <div class="big-icon">⏳</div>
              <h3 class="step-title">正在录入声纹...</h3>
              <div class="upload-progress">
                <div class="progress-bar" />
              </div>
            </div>

            <div v-else-if="uploadSuccess" class="success-state">
              <div class="success-circle">
                <div class="big-icon">🎉</div>
              </div>
              <h3 class="step-title">录入成功</h3>
              <p class="success-hint">声纹已保存到 {{ member?.name }} 的档案</p>
              <button
                type="button"
                class="btn-primary"
                @click="onClose"
              >完成</button>
            </div>

            <div v-else class="confirm-state">
              <div class="big-icon">✓</div>
              <h3 class="step-title">准备就绪</h3>

              <!-- 音频预览（录制模式） -->
              <div v-if="method === 'record' && recordedUrl" class="audio-preview-confirm">
                <audio :src="recordedUrl" controls class="audio-player" />
              </div>
              <!-- 文件信息（上传模式） -->
              <div v-else-if="method === 'upload' && selectedFile" class="file-info-confirm">
                🎵 {{ selectedFile.name }} ({{ formatFileSize(selectedFile.size) }})
              </div>

              <p class="confirm-hint">点击下方按钮确认录入</p>

              <button
                type="button"
                class="btn-primary"
                :disabled="!canSubmit"
                @click="onSubmit"
              >确认录入</button>

              <button
                type="button"
                class="btn-secondary"
                @click="step = 2"
              >返回上一步</button>
            </div>
          </div>
        </main>

        <!-- 错误提示 -->
        <div v-if="errorMessage" class="error-toast" @click="errorMessage = ''">
          ⚠️ {{ errorMessage }}
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * VoiceprintEnrollFlow.vue — 移动端声纹录入全屏流程
 *
 * PR #5: 独立的移动端组件（不用 el-dialog + CSS 全屏）
 * - Teleport to body 全屏覆盖
 * - 3 步流程：选择方式 → 录制/上传 → 确认
 * - 圆形进度可视化 + 脉冲环动画
 * - 顶部步骤指示器（✓ 标记已完成）
 * - 错误 Toast（点击关闭）
 */

import { ref, computed, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  member: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'success'])

const steps = ['选择方式', '录制', '完成']

const step = ref(1)
const method = ref('record') // 'record' | 'upload'

// 录音状态
const recording = ref(false)
const recordSeconds = ref(0)
const recordedBlob = ref(null)
const recordedUrl = ref('')
let mediaRecorder = null
let audioChunks = []
let recordTimer = null

// 上传状态
const fileInputRef = ref(null)
const selectedFile = ref(null)

// 上传中状态
const uploading = ref(false)
const uploadSuccess = ref(false)
const errorMessage = ref('')

const canSubmit = computed(() => {
  if (method.value === 'record') return !!recordedBlob.value
  if (method.value === 'upload') return !!selectedFile.value
  return false
})

// ============================================================================
// 步骤控制
// ============================================================================
function selectMethod(m) {
  method.value = m
  step.value = 2
}

// 用户主动取消（顶部 ✕ 按钮）—— 不 emit success
// onClose 仅用于真实成功路径（成功页"完成"按钮 + API 成功后自动关闭）
function onCancel() {
  cleanup()
  emit('update:modelValue', false)
}

function onClose() {
  cleanup()
  emit('update:modelValue', false)
  emit('success')
}

// ============================================================================
// 录音逻辑
// ============================================================================
async function startRecord() {
  errorMessage.value = ''
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: { ideal: 16000 },
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    })

    // 优先 webm，Safari 用 mp4（与桌面端 VoiceprintEnrollDialog 对齐）
    const mimeType = MediaRecorder.isTypeSupported('audio/webm')
      ? 'audio/webm'
      : (MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : '')
    mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)

    audioChunks = []
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data)
    }
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach((t) => t.stop())
      const blobType = mediaRecorder.mimeType || 'audio/webm'
      recordedBlob.value = new Blob(audioChunks, { type: blobType })
      recordedUrl.value = URL.createObjectURL(recordedBlob.value)
      audioChunks = []
    }
    mediaRecorder.start()
    recording.value = true
    recordSeconds.value = 0
    recordTimer = setInterval(() => {
      recordSeconds.value += 1
    }, 1000)
  } catch (e) {
    handleMediaError(e)
  }
}

function stopRecord() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
  }
  if (recordTimer) {
    clearInterval(recordTimer)
    recordTimer = null
  }
  recording.value = false
  // 录音完成后自动进入第 3 步（确认）
  step.value = 3
}

function onRecordClick() {
  if (recording.value) {
    stopRecord()
  } else if (!recordedBlob.value) {
    startRecord()
  }
}

function discardRecord() {
  if (recordedUrl.value) {
    URL.revokeObjectURL(recordedUrl.value)
  }
  recordedBlob.value = null
  recordedUrl.value = ''
  recordSeconds.value = 0
}

// ============================================================================
// 上传逻辑
// ============================================================================
function onFileChange(e) {
  const f = e.target.files?.[0]
  if (!f) return
  if (!f.type.startsWith('audio/')) {
    errorMessage.value = '请选择音频文件'
    return
  }
  if (f.size > 50 * 1024 * 1024) {
    errorMessage.value = '文件不能超过 50MB'
    return
  }
  selectedFile.value = f
}

function formatFileSize(b) {
  if (b < 1024) return b + ' B'
  if (b < 1024 * 1024) return (b / 1024).toFixed(1) + ' KB'
  return (b / 1024 / 1024).toFixed(1) + ' MB'
}

// ============================================================================
// 上传到后端
// ============================================================================
async function onSubmit() {
  if (!props.member?.id) {
    errorMessage.value = '未指定成员'
    return
  }
  uploading.value = true
  uploadSuccess.value = false
  errorMessage.value = ''

  try {
    const fd = new FormData()
    if (method.value === 'record') {
      // 根据实际 MIME 类型选择扩展名（与桌面端 uploadRecorded 对齐）
      const blob = recordedBlob.value
      const ext = blob.type.includes('mp4') ? 'm4a' : 'webm'
      fd.append('audio', blob, `recording.${ext}`)
    } else {
      fd.append('audio', selectedFile.value, selectedFile.value.name)
    }
    // 不手动设 Content-Type，让 axios 自动生成 boundary（手动设 multipart/form-data 会丢失 boundary 导致后端解析失败）
    const res = await axios.post(`/api/v1/voiceprint/enroll/${props.member.id}`, fd, {
      timeout: 30000,
    })
    if (res.data?.success !== false) {
      uploadSuccess.value = true
      // toast 由父组件 onEnrollSuccess 统一显示（避免双 toast）
      // 自动关闭
      setTimeout(() => {
        onClose()
      }, 1500)
    } else {
      errorMessage.value = res.data?.message || '录入失败'
    }
  } catch (e) {
    // 后端可能返回 {detail: "..."} 或 {error: {message: "..."}} 两种格式
    const resp = e.response?.data
    const detail = resp?.detail || resp?.error?.message
    errorMessage.value = (typeof detail === 'string' ? detail : null) || e.message || '上传失败'
  } finally {
    uploading.value = false
  }
}

// ============================================================================
// 工具
// ============================================================================
function formatTime(s) {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
}

function handleMediaError(e) {
  if (e.name === 'NotAllowedError') {
    errorMessage.value = '麦克风权限被拒绝，请在浏览器设置中允许'
  } else if (e.name === 'NotFoundError') {
    errorMessage.value = '未检测到麦克风设备'
  } else {
    errorMessage.value = '录音失败：' + (e.message || '未知错误')
  }
}

function cleanup() {
  if (recordTimer) clearInterval(recordTimer)
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    try { mediaRecorder.stop() } catch { /* ignore */ }
  }
  if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)
  recordTimer = null
  mediaRecorder = null
  recording.value = false
  recordedBlob.value = null
  recordedUrl.value = ''
  recordSeconds.value = 0
  selectedFile.value = null
  step.value = 1
  method.value = 'record'
  uploading.value = false
  uploadSuccess.value = false
  errorMessage.value = ''
}

onUnmounted(cleanup)
</script>

<style scoped>
.enroll-flow-root {
  position: fixed;
  inset: 0;
  z-index: 5000;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
  /* iOS 顶部安全区 */
  padding-top: var(--sat);
}

[data-theme="dark"] .enroll-flow-root {
  background: var(--color-bg-page);
}

/* Header */
.flow-header {
  display: flex;
  align-items: center;
  height: 52px;
  padding: 0 12px;
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border);
}
.header-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 20px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.header-btn:active { background: var(--color-primary-bg); }
.flow-title {
  flex: 1;
  text-align: center;
  font-size: 16px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  margin: 0;
}
.header-spacer { width: 40px; }

/* 步骤指示器 */
.step-indicator {
  display: flex;
  justify-content: space-between;
  padding: 20px var(--mobile-padding-x, 16px);
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border);
  position: relative;
}
.step-indicator::before {
  content: '';
  position: absolute;
  top: 36px;
  left: 25%;
  right: 25%;
  height: 2px;
  background: var(--color-border);
  z-index: 0;
}
.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  position: relative;
  z-index: 1;
}
.step-circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-bg-page);
  border: 2px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-secondary);
}
.step.active .step-circle {
  background: var(--color-primary);
  border-color: var(--color-primary);
  /* stylelint-disable-next-line color-named */
  color: white;
}
.step.done .step-circle {
  background: var(--color-success, #67C23A);
  border-color: var(--color-success, #67C23A);
  /* stylelint-disable-next-line color-named */
  color: white;
}
.step-label {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.step.active .step-label,
.step.done .step-label {
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium, 500);
}

/* 主内容 */
.flow-main {
  flex: 1;
  overflow-y: auto;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}
.step-content {
  padding: 20px 0;
}

/* 成员信息 */
.member-info {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  margin-bottom: 24px;
}
.member-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-primary), var(--color-accent));
  /* stylelint-disable-next-line color-named */
  color: white;
  font-size: 18px;
  font-weight: var(--font-weight-semibold, 600);
  display: flex;
  align-items: center;
  justify-content: center;
}
.member-name {
  font-size: 15px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
}
.member-status {
  font-size: 12px;
  margin-top: 4px;
}
.status-success { color: var(--color-success, #67C23A); }
.status-pending { color: var(--color-text-secondary); }

.step-title {
  font-size: 18px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  text-align: center;
  margin: 0 0 16px;
}

/* 选项卡（Step 1） */
.option-card {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 100%;
  padding: 16px;
  margin-bottom: 12px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  text-align: left;
}
.option-card:active {
  background: var(--color-bg-hover);
  border-color: var(--color-primary);
}
.option-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  flex-shrink: 0;
}
.option-info { flex: 1; }
.option-title {
  font-size: 15px;
  font-weight: var(--font-weight-medium, 500);
  color: var(--color-text-primary);
  margin-bottom: 2px;
}
.option-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
}
.option-arrow {
  font-size: 24px;
  color: var(--color-text-placeholder);
}

/* 录音（Step 2） */
.tip {
  text-align: center;
  font-size: 13px;
  color: var(--color-text-regular);
  padding: 12px;
  background: var(--color-primary-bg);
  border-radius: var(--radius-md);
  margin-bottom: 24px;
}
.record-area {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.record-circle {
  width: 200px;
  height: 200px;
  border-radius: 50%;
  background: var(--color-bg-card);
  border: 4px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  position: relative;
  -webkit-tap-highlight-color: transparent;
  transition: all 0.2s;
}
.record-circle:active { transform: scale(0.97); }
.record-circle.recording {
  background: var(--color-danger-bg);
  border-color: var(--color-danger, #F56C6C);
}
.record-circle.hasRecording {
  background: var(--color-success-bg);
  border-color: var(--color-success, #67C23A);
}
.big-icon {
  font-size: 56px;
}
.hint-text {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-top: 8px;
}
.recording-state {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.pulse-ring {
  position: absolute;
  inset: -20px;
  border-radius: 50%;
  border: 4px solid var(--color-danger, #F56C6C);
  animation: pulse-ring 1.2s infinite;
}
@keyframes pulse-ring {
  0% { transform: scale(0.8); opacity: 1; }
  100% { transform: scale(1.4); opacity: 0; }
}
.rec-time {
  font-size: 28px;
  font-weight: var(--font-weight-bold, 700);
  color: var(--color-danger, #F56C6C);
  font-variant-numeric: tabular-nums;
}
.audio-preview {
  margin-top: 20px;
}
.audio-player {
  width: 100%;
  margin-bottom: 12px;
}
.btn-secondary {
  width: 100%;
  padding: 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  background: var(--color-bg-card);
  font-size: 14px;
  color: var(--color-text-primary);
  cursor: pointer;
}
.rec-status {
  text-align: center;
  padding: 12px;
  color: var(--color-danger, #F56C6C);
  font-size: 13px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.rec-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-danger, #F56C6C);
  animation: pulse 1s infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

/* 上传 */
.upload-mode {
  padding: 20px 0;
}
.upload-zone {
  width: 100%;
  min-height: 240px;
  border: 2px dashed var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-card);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
}
.upload-zone:active,
.upload-zone.hasFile {
  border-color: var(--color-primary);
  background: var(--color-primary-bg);
}
.upload-empty,
.upload-filled {
  text-align: center;
  padding: 32px 16px;
}
.upload-title {
  font-size: 15px;
  font-weight: var(--font-weight-medium, 500);
  color: var(--color-text-primary);
  margin: 12px 0 4px;
}
.upload-hint {
  font-size: 12px;
  color: var(--color-text-secondary);
}

/* Step 3 */
.uploading-state,
.success-state,
.confirm-state {
  text-align: center;
  padding: 60px 20px;
}
.upload-progress {
  margin: 20px auto 0;
  max-width: 240px;
  height: 4px;
  background: var(--color-border);
  border-radius: 2px;
  overflow: hidden;
}
.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--color-primary), var(--color-primary-light));
  border-radius: 2px;
  animation: progress-anim 1.5s ease infinite;
}
@keyframes progress-anim {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
.success-circle {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-success, #67C23A), #95D475);
  margin: 0 auto 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: success-pop 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.success-circle .big-icon {
  /* stylelint-disable-next-line color-named */
  color: white;
  font-size: 56px;
}
@keyframes success-pop {
  0% { transform: scale(0); }
  100% { transform: scale(1); }
}
.success-hint,
.confirm-hint {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 20px;
}
.audio-preview-confirm {
  margin: 16px auto;
  max-width: 320px;
}
.audio-preview-confirm .audio-player {
  width: 100%;
}
.file-info-confirm {
  font-size: 14px;
  color: var(--color-text-regular);
  padding: 12px;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  margin: 16px 0;
  text-align: center;
}

.btn-primary {
  width: 100%;
  padding: 14px;
  border-radius: var(--radius-md);
  border: none;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  /* stylelint-disable-next-line color-named */
  color: white;
  font-size: 15px;
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  margin-bottom: 8px;
}
.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.btn-primary:active:not(:disabled) {
  transform: scale(0.98);
}

/* 错误 Toast */
.error-toast {
  position: fixed;
  bottom: calc(40px + var(--sab, 0px));
  left: 50%;
  transform: translateX(-50%);
  max-width: 90vw;
  padding: 10px 16px;
  background: var(--color-danger, #F56C6C);
  /* stylelint-disable-next-line color-named */
  color: white;
  border-radius: var(--radius-full);
  font-size: 13px;
  box-shadow: 0 4px 16px rgba(245, 108, 108, 0.3);
  cursor: pointer;
  z-index: 5100;
  animation: toast-in 0.3s ease;
}
@keyframes toast-in {
  from { opacity: 0; transform: translateX(-50%) translateY(20px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}

/* 进出动画 */
.enroll-flow-enter-active, .enroll-flow-leave-active {
  transition: opacity 0.3s ease;
}
.enroll-flow-enter-from, .enroll-flow-leave-to { opacity: 0; }
</style>
<template>
  <el-dialog
    :model-value="modelValue"
    @update:model-value="onClose"
    :title="dialogTitle"
    :width="isMobile ? '90vw' : '500px'"
    top="5vh"
    :close-on-click-modal="!uploading"
    append-to-body
    :lock-scroll="true"
  >
    <div v-if="member" class="enroll-dialog">
      <div class="member-summary">
        <el-avatar v-if="member.avatar" :size="48" :src="member.avatar" :alt="`${member.name}的头像`" />
        <el-avatar v-else :size="48" :style="{ background: avatarColor }" :alt="`${member.name}的头像`">
          {{ member.name.charAt(0) }}
        </el-avatar>
        <div>
          <div class="name">{{ member.name }}</div>
          <div class="status">
            <el-tag v-if="member.voice_enrolled_at" type="success" size="small">
              已录入（{{ member.voice_sample_count || 0 }} 次采样）
            </el-tag>
            <el-tag v-else type="info" size="small">未录入声纹</el-tag>
          </div>
        </div>
      </div>

      <el-alert
        type="info"
        :closable="false"
        show-icon
        class="hint-alert"
      >
        <template #title>
          请在<strong>安静环境</strong>下说一段 10 秒以上的话（可以说"我是{{ member.name }}"）。
          多次录入可叠加提升准确度。
        </template>
      </el-alert>

      <el-tabs v-model="activeTab" class="enroll-tabs">
        <!-- Tab 1: 麦克风录制 -->
        <el-tab-pane label="麦克风录制" name="record">
          <div class="record-pane">
            <el-button
              v-if="!recording && !recordedBlob"
              type="primary"
              size="large"
              round
              @click="startRecord"
            >
              <el-icon><Microphone /></el-icon>
              <span>开始录制</span>
            </el-button>

            <div v-else-if="recording" class="recording-status">
              <div class="recording-dot"></div>
              <span class="recording-time">{{ formatTime(recordSeconds) }}</span>
              <el-button type="danger" round @click="stopRecord">停止</el-button>
            </div>

            <div v-else-if="recordedBlob" class="recorded-actions">
              <audio :src="recordedUrl" controls class="audio-preview" />
              <div class="action-buttons">
                <el-button @click="discardRecord">重录</el-button>
                <el-button type="primary" :loading="uploading" @click="uploadRecorded">
                  录入声纹
                </el-button>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <!-- Tab 2: 上传文件 -->
        <el-tab-pane label="上传音频文件" name="upload">
          <div class="upload-pane">
            <el-upload
              :auto-upload="false"
              :show-file-list="true"
              :limit="1"
              accept="audio/*"
              :on-change="onFileChange"
              :on-remove="onFileRemove"
              drag
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                拖拽音频文件到此处，或<em>点击选择</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持 wav / mp3 / webm / m4a / ogg 等常见格式，建议 10 秒以上
                </div>
              </template>
            </el-upload>

            <el-button
              type="primary"
              :disabled="!selectedFile"
              :loading="uploading"
              class="upload-btn"
              @click="uploadFile"
            >
              录入声纹
            </el-button>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <template #footer>
      <el-button @click="onClose" :disabled="uploading">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Microphone, UploadFilled } from '@element-plus/icons-vue'
import axios from 'axios'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  member: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'success'])

const isMobile = ref(typeof window !== 'undefined' && window.innerWidth <= 768)
const activeTab = ref('record')
const uploading = ref(false)

// 录音相关
const recording = ref(false)
const recordSeconds = ref(0)
const recordedBlob = ref(null)
const recordedUrl = ref('')
let mediaRecorder = null
let mediaStream = null
let recordTimer = null
let recordStartTime = 0
let recordChunks = []

// 上传相关
const selectedFile = ref(null)

// 弹窗标题
const dialogTitle = computed(() => {
  if (!props.member) return '录入声纹'
  return props.member.voice_enrolled_at
    ? `更新 ${props.member.name} 的声纹`
    : `录入 ${props.member.name} 的声纹`
})

const avatarColor = computed(() => {
  if (!props.member) return '#909399'
  const colors = ['#409eff', '#67c23a', '#e6a23c', '#f56c6c', '#909399']
  return colors[props.member.name.charCodeAt(0) % colors.length]
})

// 录音相关
async function startRecord() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: { ideal: 16000 },
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      },
    })
  } catch (e) {
    ElMessage.error('麦克风权限被拒绝，请在浏览器设置中允许')
    return
  }

  // 优先 webm，Safari 用 mp4
  const mimeType = MediaRecorder.isTypeSupported('audio/webm')
    ? 'audio/webm'
    : (MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : '')
  mediaRecorder = new MediaRecorder(mediaStream, mimeType ? { mimeType } : undefined)
  recordChunks = []
  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) recordChunks.push(e.data)
  }
  mediaRecorder.onstop = () => {
    const blob = new Blob(recordChunks, { type: mediaRecorder.mimeType || 'audio/webm' })
    recordedBlob.value = blob
    if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)
    recordedUrl.value = URL.createObjectURL(blob)
    cleanupStream()
  }
  mediaRecorder.start()
  recording.value = true
  recordSeconds.value = 0
  recordStartTime = Date.now()
  recordTimer = setInterval(() => {
    recordSeconds.value = Math.floor((Date.now() - recordStartTime) / 1000)
  }, 200)
}

function stopRecord() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
  }
  recording.value = false
  if (recordTimer) {
    clearInterval(recordTimer)
    recordTimer = null
  }
}

function discardRecord() {
  if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)
  recordedBlob.value = null
  recordedUrl.value = ''
  recordSeconds.value = 0
}

function cleanupStream() {
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop())
    mediaStream = null
  }
  mediaRecorder = null
}

// 上传相关
function onFileChange(file) {
  selectedFile.value = file.raw
}
function onFileRemove() {
  selectedFile.value = null
}

// 通用上传：FormData + axios（与后端 form-data 期望一致）
async function uploadBlob(blob, filename) {
  if (!props.member) return
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('audio', blob, filename)
    const resp = await axios.post(
      `/api/v1/voiceprint/enroll/${props.member.id}`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 30000,
      }
    )
    if (resp.data?.message) {
      ElMessage.success(resp.data.message)
    } else {
      ElMessage.success('声纹录入成功')
    }
    emit('success', props.member.id)
    onClose()
  } catch (e) {
    const detail = e.response?.data?.detail || e.message
    ElMessage.error(`录入失败：${detail}`)
  } finally {
    uploading.value = false
  }
}

function uploadRecorded() {
  if (!recordedBlob.value) return
  const ext = recordedBlob.value.type.includes('mp4') ? 'm4a' : 'webm'
  uploadBlob(recordedBlob.value, `recording.${ext}`)
}

function uploadFile() {
  if (!selectedFile.value) return
  uploadBlob(selectedFile.value, selectedFile.value.name || 'audio.webm')
}

function formatTime(s) {
  const m = String(Math.floor(s / 60)).padStart(2, '0')
  const sec = String(s % 60).padStart(2, '0')
  return `${m}:${sec}`
}

function onClose() {
  if (uploading.value) return
  // 清理录音
  if (recording.value) stopRecord()
  discardRecord()
  selectedFile.value = null
  activeTab.value = 'record'
  emit('update:modelValue', false)
}

onUnmounted(() => {
  if (recording.value) stopRecord()
  cleanupStream()
  if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)
})

// 弹窗打开时重置状态
watch(() => props.modelValue, (v) => {
  if (v) {
    activeTab.value = 'record'
    discardRecord()
    selectedFile.value = null
  }
})
</script>

<style scoped>
.enroll-dialog {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.member-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--color-bg-hover, #f5f7fa);
  border-radius: var(--radius-md, 8px);
}
.member-summary .name {
  font-size: 16px;
  font-weight: 500;
  color: var(--color-text-primary, #303133);
  margin-bottom: 4px;
}
.hint-alert {
  margin: 0;
}
.enroll-tabs {
  min-height: 220px;
}
.record-pane {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 24px 0;
  min-height: 200px;
}
.recording-status {
  display: flex;
  align-items: center;
  gap: 16px;
}
.recording-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #f56c6c;
  animation: pulse 1s infinite;
}
.recording-time {
  font-family: monospace;
  font-size: 20px;
  color: #f56c6c;
  font-weight: 600;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
}
.recorded-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  width: 100%;
}
.audio-preview {
  width: 100%;
  max-width: 400px;
}
.action-buttons {
  display: flex;
  gap: 12px;
}
.upload-pane {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 0;
}
.upload-btn {
  align-self: center;
}
</style>

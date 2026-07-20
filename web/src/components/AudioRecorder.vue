<template>
  <div class="audio-recorder">
    <!-- 状态：idle — 待录音 -->
    <div v-if="state === 'idle'" class="recorder-idle">
      <div class="recorder-icon">🎙️</div>
      <button class="btn-start" @click="handleStart">{{ isActive() ? '返回录音' : '开始听会' }}</button>
      <p v-if="isActive()" class="recorder-hint resume-hint">录音在后台持续进行中</p>
      <p v-else class="recorder-hint">点击后即开始录音，无需填写任何信息</p>
    </div>

    <!-- 状态：recording — 录音中 -->
    <div v-else-if="state === 'recording' || state === 'paused'" class="recorder-active">
      <UploadStatusBadge
        v-if="meetingId"
        :online="network.online.value"
        :uploaded-count="uploadedCount"
        :total-count="totalChunks"
        :pending-count="pendingCount"
        :state="state"
      />
      <div class="recorder-status">
        <span class="rec-dot" :class="{ paused: state === 'paused' }" />
        {{ state === 'paused' ? '已暂停' : '录音中' }}
      </div>
      <div class="recorder-timer">{{ formattedTime }}</div>

      <!-- 音量指示器 -->
      <div class="volume-bars">
        <div v-for="(h, i) in barHeights" :key="i" class="vol-bar" :style="{ height: h + 'px' }" />
      </div>

      <div class="recorder-controls">
        <button v-if="state === 'recording'" class="btn-pause" @click="handlePause">⏸ 暂停</button>
        <button v-else class="btn-resume" @click="handleResume">▶ 继续</button>
        <button class="btn-stop" @click="confirmStop">⏹ 结束听会</button>
      </div>
    </div>

    <!-- 状态：stopped — 回放 -->
    <div v-else-if="state === 'stopped'" class="recorder-stopped">
      <div class="recorder-done">听会结束</div>
      <div class="recorder-duration">时长: {{ formattedTime }}</div>

      <!-- 波形渲染 -->
      <canvas ref="waveformCanvas" class="waveform-canvas" @click="seekWaveform" />

      <!-- 播放控制 -->
      <div class="playback-controls">
        <button class="btn-play" @click="togglePlayback">
          {{ isPlaying ? '⏸' : '▶' }}
        </button>
        <span class="playback-time">{{ formatTime(currentPlayTime) }} / {{ formattedTime }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useGlobalRecorder } from '@/composables/useGlobalRecorder'
import { useRecordingState } from '@/composables/useRecordingState'
import { useNetworkStatus } from '@/composables/useNetworkStatus'
import { useChunkedRecorder } from '@/composables/useChunkedRecorder'
import UploadStatusBadge from '@/components/UploadStatusBadge.vue'

const props = defineProps({
  meetingId: { type: Number, default: null },
  meetingTitle: { type: String, default: '' },
})

const emit = defineEmits(['recording-start', 'recording-stop', 'audio-ready'])

const {
  state, elapsed, barHeights, isPaused,
  start, pause, resumePaused, stop, reset, isActive, getAudioBlob,
} = useGlobalRecorder()

const { stopRecording: clearRecordingIndicator } = useRecordingState()
const network = useNetworkStatus()

// 边录边传 chunked recorder（v2: lazy meetingId, meetingId 迟到不丢 chunks）
// 修复 (2026-07-02): 之前 props.meetingId 在 setup() 时可能为 null,
// 1s 内 ondataavailable 触发 chunks 全部丢失 (永远不调用 useChunkedRecorder).
// 改成传 ref, useChunkedRecorder 内部 watch meetingId 变化时 flush 缓存.
const meetingIdRef = ref(props.meetingId)
watch(() => props.meetingId, (mid) => {
  meetingIdRef.value = mid
}, { immediate: true })

// P1-5 fix (2026-07-08): meetingTitle 也走 ref 模式, 否则 useChunkedRecorder
// setup() 时只能读到 props.meetingTitle 初始值 ("开始听会" / ""), 后续父组件
// pageTitle 变化 (meetingId 到位后变成 "正在录音 #N") 不会更新 IDB meta.title.
// 改成传 titleRef, useChunkedRecorder 内部 watch 变化时实时 patch meta.title.
const titleRef = ref(props.meetingTitle)
watch(() => props.meetingTitle, (t) => {
  titleRef.value = t
}, { immediate: true })

const chunkedRecorder = useChunkedRecorder(meetingIdRef, { titleRef })
const uploadedCount = computed(() => chunkedRecorder.uploadedCount.value)
const pendingCount = computed(() => chunkedRecorder.pendingCount.value)
const totalChunks = computed(() => chunkedRecorder.totalChunks.value)

// 回放状态（组件局部）
const isPlaying = ref(false)
const currentPlayTime = ref(0)
let audioElement = null
let waveformData = null
const waveformCanvas = ref(null)
const stoppedDuration = ref(0) // stop 后记住时长

const formattedTime = computed(() => formatTime(stoppedDuration.value || elapsed.value))

function formatTime(seconds) {
  const s = Math.floor(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

// ===== 初始化 =====

onMounted(() => {
  // 如果录音已停止或胶囊已消失（无会议ID），重置为 idle
  // 如果录音正在进行中且胶囊仍在（用户从其他页面返回），保持当前状态
  if (state.value === 'stopped' || (state.value !== 'idle' && !sessionStorage.getItem('recording_meeting_id'))) {
    reset()
  }
})

// ===== 操作 =====

async function handleStart() {
  try {
    await start()
    emit('recording-start')
  } catch (err) {
    // 2026-07-16 修复 (#207 完整流程): 精细化错误处理 + catch 块完整 rollback
    //   1. 按 DOMException error name 分类给用户精确引导
    //   2. 已创建的会议: 调 cancel-recording 把 status=recording → error
    //   3. 已设置的 meetingIdRef: 清空 (防 store 残留导致 ghost 录音)
    //   4. 已开启的录音状态指示器: 清空
    console.error('[AudioRecorder] 录音启动失败:', err)
    const errorName = err?.name || ''
    let userHint = ''
    if (errorName === 'NotAllowedError' || errorName === 'PermissionDeniedError') {
      userHint = '麦克风权限被拒绝, 请在浏览器设置中允许麦克风访问。'
    } else if (errorName === 'NotFoundError') {
      userHint = '未检测到麦克风设备, 请检查硬件连接。'
    } else if (errorName === 'NotReadableError') {
      userHint = '麦克风被其他程序占用, 请关闭后重试。'
    } else if (errorName === 'NotSupportedError' || errorName === 'TypeError') {
      userHint = '当前浏览器不支持录音, 请使用 Chrome / Edge / Safari 14+ 浏览器。'
    } else if (errorName === 'SecurityError') {
      userHint = '当前页面不安全, 请使用 HTTPS 或 localhost 访问。'
    } else if (errorName === 'AbortError') {
      userHint = '录音启动被中断, 请重试。'
    } else {
      // getUserMedia timeout / 其他自定义错误
      userHint = (err?.message || err) || '未知错误'
    }

    if (meetingIdRef.value) {
      try {
        await axios.post(`/api/v1/meetings/${meetingIdRef.value}/cancel-recording`)
        console.warn('[AudioRecorder] 已 cancel meeting', meetingIdRef.value)
      } catch (cancelErr) {
        console.error('[AudioRecorder] cancel-recording 失败:', cancelErr)
      }
      meetingIdRef.value = null
    }
    clearRecordingIndicator()
    ElMessage.error('录音启动失败: ' + userHint)
  }
}

function handlePause() {
  pause()
}

function handleResume() {
  resumePaused()
}

function confirmStop() {
  ElMessageBox.confirm('确定结束听会？', '确认', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning',
  }).then(() => {
    doStop()
  }).catch(() => {})
}

async function doStop() {
  stoppedDuration.value = elapsed.value
  const blob = await stop()
  emit('recording-stop')
  // 清除全局录音指示器（胶囊）
  clearRecordingIndicator()
  if (blob) {
    emit('audio-ready', blob)
  }
  nextTick(() => generateWaveform())
}

// ===== 波形渲染 =====

async function generateWaveform() {
  const blob = getAudioBlob()
  if (!blob || !waveformCanvas.value) return

  const decodeContext = new AudioContext()

  const canvas = waveformCanvas.value
  const ctx = canvas.getContext('2d')
  const width = canvas.offsetWidth * 2
  const height = canvas.offsetHeight * 2
  canvas.width = width
  canvas.height = height

  const arrayBuffer = await blob.arrayBuffer()
  const decoded = await decodeContext.decodeAudioData(arrayBuffer)
  const channelData = decoded.getChannelData(0)

  const step = Math.floor(channelData.length / width)
  waveformData = []
  for (let i = 0; i < width; i++) {
    let min = 1, max = -1
    for (let j = i * step; j < (i + 1) * step && j < channelData.length; j++) {
      if (channelData[j] < min) min = channelData[j]
      if (channelData[j] > max) max = channelData[j]
    }
    waveformData.push({ min, max })
  }

  ctx.fillStyle = '#f5f5f5'
  ctx.fillRect(0, 0, width, height)

  ctx.fillStyle = 'var(--color-primary)'
  const mid = height / 2
  for (let i = 0; i < waveformData.length; i++) {
    const { min, max } = waveformData[i]
    const yMin = mid + min * mid
    const yMax = mid + max * mid
    ctx.fillRect(i, yMin, 1, yMax - yMin || 1)
  }

  decodeContext.close()
}

function seekWaveform(e) {
  if (!audioElement || !waveformData) return
  const rect = e.target.getBoundingClientRect()
  const ratio = (e.clientX - rect.left) / rect.width
  audioElement.currentTime = ratio * audioElement.duration
  currentPlayTime.value = audioElement.currentTime
}

// ===== 播放 =====

function togglePlayback() {
  if (!audioElement) {
    const blob = getAudioBlob()
    if (!blob) return
    audioElement = new Audio(URL.createObjectURL(blob))
    audioElement.ontimeupdate = () => {
      currentPlayTime.value = audioElement.currentTime
    }
    audioElement.onended = () => {
      isPlaying.value = false
      currentPlayTime.value = 0
    }
  }

  if (isPlaying.value) {
    audioElement.pause()
    isPlaying.value = false
  } else {
    audioElement.play()
    isPlaying.value = true
  }
}

// ===== 暴露方法 =====

defineExpose({
  getAudioBlob,
  getDuration: () => elapsed.value,
})
</script>

<style scoped>
.audio-recorder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  padding: 40px 20px;
}

/* idle */
.recorder-idle { text-align: center; }
.recorder-icon { font-size: 64px; margin-bottom: 20px; }
.btn-start {
  padding: 16px 48px; font-size: 18px; font-weight: 700;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light)); color: var(--el-color-white);
  border: none; border-radius: 32px; cursor: pointer;
  transition: var(--transition-all-normal);
}
.btn-start:hover { transform: scale(1.05); box-shadow: 0 6px 20px rgba(var(--color-primary-rgb), 0.4); }
.recorder-hint { color: var(--color-text-secondary); font-size: 13px; margin-top: 12px; }
.resume-hint { color: var(--color-primary); font-weight: 600; font-size: 14px; background: rgba(var(--color-primary-rgb), 0.08); padding: 8px 16px; border-radius: 8px; }

/* recording */
.recorder-active { text-align: center; }
.recorder-status { font-size: 16px; font-weight: 600; color: var(--color-text-primary); display: flex; align-items: center; gap: 8px; justify-content: center; }
.rec-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--color-danger); animation: pulse 1.5s infinite; }
.rec-dot.paused { animation: none; background: var(--color-warning); }
.recorder-timer { font-size: 48px; font-weight: 300; font-family: 'SF Mono', 'Cascadia Code', monospace; color: var(--color-text-primary); margin: 20px 0; }
.volume-bars { display: flex; gap: 6px; align-items: flex-end; justify-content: center; height: 44px; margin: 16px 0; }
.vol-bar { width: 8px; background: var(--gradient-welcome-hero); border-radius: 4px; transition: height 0.1s; }
.recorder-controls { display: flex; gap: 16px; margin-top: 24px; }
.btn-pause, .btn-resume, .btn-stop {
  padding: 10px 28px; font-size: 15px; font-weight: 600;
  border: none; border-radius: 24px; cursor: pointer; transition: var(--transition-all-normal);
}
.btn-pause, .btn-resume { background: var(--color-border-light); color: var(--color-text-primary); }
.btn-pause:hover, .btn-resume:hover { background: var(--color-border-light); }
.btn-stop { background: var(--color-danger); color: var(--el-color-white); }
.btn-stop:hover { background: var(--color-danger); }

/* stopped */
.recorder-stopped { text-align: center; width: 100%; max-width: 600px; }
.recorder-done { font-size: 20px; font-weight: 700; color: var(--color-text-primary); }
.recorder-duration { font-size: 14px; color: var(--color-text-secondary); margin: 4px 0 20px; }
.waveform-canvas {
  width: 100%; height: 80px; border-radius: 8px; cursor: pointer;
  border: 1px solid #eee;
}
.playback-controls { display: flex; align-items: center; gap: 12px; justify-content: center; margin-top: 12px; }
.btn-play {
  width: 40px; height: 40px; border-radius: 50%; border: none;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light)); color: var(--el-color-white);
  font-size: 16px; cursor: pointer;
}
.playback-time { font-size: 13px; color: var(--color-text-regular); font-family: 'SF Mono', 'Cascadia Code', monospace; }
</style>

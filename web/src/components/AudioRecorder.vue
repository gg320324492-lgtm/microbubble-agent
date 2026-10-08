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
import { ensureHeartbeat, stopHeartbeat as stopModuleHeartbeat, beat as beatModule } from '@/composables/useRecordingHeartbeat'
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

// ===== 录音心跳（2026-09-15 P0, 2026-10-08 P0-1 升级为模块级单例）=====
// 后端 orphan_meeting_cleanup 每 10 分钟扫一次"录音超 30min 未 stop"的会议并标 error。
// 事故链：
//   - 2026-09-14 会议 250（杜同贺 / iPhone）：09-15 修复加了心跳，但 60s interval 在 #207 完整流程下有效
//   - 2026-10-08 会议 255（user 58 / iOS 18.7 Safari）：发现 09-15 心跳绑 UI 组件，恢复路径
//     （从其他页面跳回 /meetings/room）直接调 useGlobalRecorder().start()，**绕过**
//     AudioRecorder.handleStart() → 心跳从未启动 → 38min 录音全程 0 心跳 → orphan 误判 error
//   - 修复：心跳从组件局部提升为模块级单例（web/src/composables/useRecordingHeartbeat.js），
//     与 useGlobalRecorder 同寿命，**不**绑 UI 组件生命周期。
//
// 调用约定（任务书「重要陷阱 1」）：
//   - 组件 unmount **不**调用 stopModuleHeartbeat —— 模块级心跳应与录音会话同寿
//   - 只有 stop-recording / cancel-recording / merge 完成（doStop / handleCancel）才停
//   - onMounted 内补一次 ensureHeartbeat（堵死 A-6 缺口：组件重建后无心跳）

let iOS5sWarned = false  // P1-1: iOS 5s 无分片提示只弹一次
let iOS5sWarnTimer = null

function beatHeartbeat() {
  // 旧组件局部入口保留 — 现在转发到模块级 beat，确保旧路径不破
  beatModule()
}

// 启动模块级心跳（启动一次 beat + 60s interval）
// 重复调幂等 —— ensureHeartbeat 内部有 currentMeetingId !== meetingId 守卫
function startHeartbeat() {
  ensureHeartbeat(meetingIdRef.value)
}

// 停止模块级心跳（**仅**录音真正结束时调用，组件卸载不调）
function stopHeartbeat() {
  stopModuleHeartbeat()
  if (iOS5sWarnTimer) {
    clearTimeout(iOS5sWarnTimer)
    iOS5sWarnTimer = null
  }
}

// meetingId 是父组件异步创建的，到位后立刻补一次心跳（不等下一个 60s 周期）
// 2026-10-08 修复：原来 `if (mid && isActive()) beatHeartbeat()`，
// 但恢复路径时序让 isActive() 在 meetingId 变化时恒为 false → 这条 watch 永远不发
// 新方案：无条件 ensureHeartbeat —— 让模块级守护接管 A-6 缺口
watch(meetingIdRef, (mid) => {
  if (mid) ensureHeartbeat(mid)
})

// 注意：onUnmounted **不**调 stopHeartbeat（模块级心跳应继续跑）。
// 录音真正结束由 doStop / handleCancel 主动 stopHeartbeat。

// ===== 初始化 =====

onMounted(() => {
  // 如果录音已停止或胶囊已消失（无会议ID），重置为 idle
  // 如果录音正在进行中且胶囊仍在（用户从其他页面返回），保持当前状态
  if (state.value === 'stopped' || (state.value !== 'idle' && !sessionStorage.getItem('recording_meeting_id'))) {
    reset()
  }
  // 2026-10-08 P0-1 修复 A-6: 组件重建 / 恢复时若无心跳, 立即补一次
  // —— 之前 onMounted 从不调 startHeartbeat, 导致组件重建路径心跳永久丢失
  if (isActive() && meetingIdRef.value) {
    ensureHeartbeat(meetingIdRef.value)
  }
})

// ===== 操作 =====

/**
 * P1-1 (2026-10-08): 检测是否为 iOS Safari（UA 含 iPhone + Safari 且不包含 Chrome/CriOS/FxiOS）
 * —— 这是 iOS Safari 不遵守 MediaRecorder.start(timeslice) 的精确判定条件。
 */
function isIOSSafari() {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent || ''
  const isIOS = /iPhone/.test(ua) || (/iPad/.test(ua) && !/Android/.test(ua))
  const isAppleWebKit = /Safari/.test(ua)
  // 排除 Chrome/Firefox/Edge 等在 iOS 上的外壳
  const isNotChromeShell = !/CriOS|Chrome|FxiOS|EdgiOS|OPiOS/.test(ua)
  return isIOS && isAppleWebKit && isNotChromeShell
}

async function handleStart() {
  try {
    await start()
    startHeartbeat()
    emit('recording-start')

    // P1-1 (2026-10-08): iOS Safari 5s 内若 totalChunks 仍为 0, 提示用户产品限制.
    // 不打断录音, 仅 ElMessage 弹一次. 任务书「重要陷阱 4」: UA 含 iPhone+Safari 且不含
    // Chrome/CriOS/FxiOS 才算 iOS Safari.
    if (!iOS5sWarned && isIOSSafari()) {
      iOS5sWarned = true
      // clear 旧 timer 防止 handleStart 重复调时叠加
      if (iOS5sWarnTimer) clearTimeout(iOS5sWarnTimer)
      iOS5sWarnTimer = setTimeout(() => {
        // 5s 后若实时分片数仍为 0（典型 iOS Safari 行为：timeslice 不触发 ondataavailable）
        // 则提醒用户产品限制, 引导手机自带录音器补录.
        if (totalChunks.value === 0) {
          ElMessage({
            message: '⚠️ 检测到您使用的是 iOS Safari，网页录音在切换到后台时会被系统挂起，'
              + '可能导致录音中断或丢失。强烈建议同时开启手机自带「语音备忘录」录音，'
              + '结束后可在会议详情页上传补充。',
            type: 'warning',
            duration: 12000,
            showClose: true,
          })
        }
      }, 5000)
    }
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
  stopHeartbeat()
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
  /**
   * 2026-09-15 P0: 把"实时分片"的落库情况暴露给父组件。
   * 父组件在停止后用它判断该走 merge-chunks（实时分片完整）
   * 还是走字节切片重传（iOS Safari 从不触发 timeslice，分片数恒为 0）。
   * @returns {{uploadedCount:number,totalChunks:number,pendingCount:number}}
   */
  getLiveUploadStats: () => ({
    uploadedCount: uploadedCount.value,
    totalChunks: totalChunks.value,
    pendingCount: pendingCount.value,
  }),
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

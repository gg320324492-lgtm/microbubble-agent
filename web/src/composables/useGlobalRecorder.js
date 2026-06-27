/**
 * 全局录音器单例
 * 录音在后台持续进行，不受组件销毁/挂载影响。
 * AudioRecorder 组件只是这个单例的 UI 壳。
 */

import { ref, readonly } from 'vue'

// ===== 模块级状态（跨组件持久） =====
let mediaRecorder = null
let mediaStream = null
let audioContext = null
let analyser = null
let dataArray = null
let audioChunks = []
let timerInterval = null
let animationFrame = null
let chunkIndex = 0              // 已发出的 chunk 序号（仅 start 时重置）
let recorderStartEpoch = null  // 2026-06-27 新增：本次录音会话的 wall clock 起点（毫秒）
const chunkCallbacks = []       // 外部 chunk 钩子（阶段1: 边录边传持久化用）

// ===== 响应式状态（UI 绑定） =====
const state = ref('idle')       // idle | recording | paused | stopped
const elapsed = ref(0)
const barHeights = ref([4, 4, 4, 4, 4])
const isPaused = ref(false)

// ===== 方法 =====

async function start() {
  if (state.value === 'recording' || state.value === 'paused') return

  state.value = 'recording'
  // 2026-06-27 改：不再无条件清零 elapsed。
  // 手动 start() 路径（用户点"开始听会"）elapsed 默认 0 → 行为不变。
  // 刷新恢复路径（MeetingRoomView 先调 setElapsed(N) 再 start()）保留 N，
  // 让 setInterval 从 N+1 起跳，实现"计时器接续"。
  isPaused.value = false
  if (!recorderStartEpoch) recorderStartEpoch = Date.now()
  // chunkIndex 不重置 — 留给 setChunkStartIndex() 控制（刷新后从 last_chunk_index+1 续传）

  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })

  // 音频分析
  audioContext = new AudioContext()
  const source = audioContext.createMediaStreamSource(mediaStream)
  analyser = audioContext.createAnalyser()
  analyser.fftSize = 256
  source.connect(analyser)
  dataArray = new Uint8Array(analyser.frequencyBinCount)

  // MediaRecorder
  mediaRecorder = new MediaRecorder(mediaStream, { mimeType: 'audio/webm;codecs=opus' })
  audioChunks = []

  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size === 0) return
    audioChunks.push(e.data)
    // 通知所有外部 chunk 订阅者（不阻塞 ondataavailable 本身）
    const idx = chunkIndex++
    for (const cb of chunkCallbacks) {
      try {
        cb({ index: idx, blob: e.data, size: e.data.size })
      } catch (err) {
        console.error('[useGlobalRecorder] chunk callback 错误:', err)
      }
    }
  }

  mediaRecorder.start(1000)

  // 计时器
  timerInterval = setInterval(() => { elapsed.value++ }, 1000)

  // 音量动画
  updateVolumeBars()
}

function pause() {
  if (mediaRecorder?.state === 'recording') {
    mediaRecorder.pause()
    state.value = 'paused'
    isPaused.value = true
    clearInterval(timerInterval)
    cancelAnimationFrame(animationFrame)
  }
}

function resumePaused() {
  if (mediaRecorder?.state === 'paused') {
    mediaRecorder.resume()
    state.value = 'recording'
    isPaused.value = false
    timerInterval = setInterval(() => { elapsed.value++ }, 1000)
    updateVolumeBars()
  }
}

function stop() {
  return new Promise((resolve) => {
    if (!mediaRecorder || mediaRecorder.state === 'inactive') {
      state.value = 'stopped'
      cleanup()
      resolve(null)
      return
    }

    mediaRecorder.onstop = () => {
      const blob = new Blob(audioChunks, { type: 'audio/webm' })
      state.value = 'stopped'
      cleanup()
      resolve(blob)
    }

    mediaRecorder.stop()
  })
}

function cleanup() {
  clearInterval(timerInterval)
  cancelAnimationFrame(animationFrame)
  timerInterval = null
  animationFrame = null
  if (mediaStream) {
    mediaStream.getTracks().forEach(t => t.stop())
    mediaStream = null
  }
  if (audioContext && audioContext.state !== 'closed') {
    audioContext.close()
    audioContext = null
  }
  mediaRecorder = null
  analyser = null
  dataArray = null
}

function updateVolumeBars() {
  if (!analyser) return
  analyser.getByteFrequencyData(dataArray)

  const bands = 5
  const step = Math.floor(dataArray.length / bands)
  const heights = []
  for (let i = 0; i < bands; i++) {
    let sum = 0
    for (let j = i * step; j < (i + 1) * step; j++) {
      sum += dataArray[j]
    }
    const avg = sum / step
    heights.push(Math.max(4, Math.min(40, avg / 4)))
  }
  barHeights.value = heights

  if (state.value === 'recording') {
    animationFrame = requestAnimationFrame(updateVolumeBars)
  }
}

/** 当前是否正在录音（含暂停） */
function isActive() {
  return state.value === 'recording' || state.value === 'paused'
}

/** 重置为 idle（录音结束后调用，允许开始新录音） */
function reset() {
  state.value = 'idle'
  elapsed.value = 0
  barHeights.value = [4, 4, 4, 4, 4]
  isPaused.value = false
  audioChunks = []
  chunkIndex = 0
  recorderStartEpoch = null
}

/**
 * 2026-06-27 新增：显式设置 elapsed 秒数。
 * 用于刷新后从后端回填真实已录制时长。**必须在 start() 之前调用**，
 * 因为 start() 启动的 setInterval 会从 elapsed.value +1 起跳。
 * @param {number} seconds
 */
function setElapsed(seconds) {
  const n = Math.max(0, Math.floor(Number(seconds) || 0))
  elapsed.value = n
}

/**
 * 2026-06-27 新增：从后端返回的 recording_started_at ISO 字符串恢复 elapsed。
 * 计算 (now - startedAt) / 1000 秒数并设给 elapsed。
 *
 * 时区修复（2026-06-27 v3.1）：后端存的 naive datetime 是 **UTC**（数据库
 * current_setting('TIMEZONE')='UTC'），前端 `new Date(isoString)` 默认按
 * 浏览器本地时区解析 → 北京时间差 +8 小时，elapsed 永远多算 8 小时。
 * 修复：解析时强制追加 'Z' 后缀（UTC）→ `new Date(iso+Z).getTime()` 正确。
 * 已带 'Z' 或 '+HH:MM' 偏移的字符串原样使用（不重复加）。
 * @param {string} isoDatetime - 后端 MeetingResponse.recording_started_at
 */
function resumeFromStartedAt(isoDatetime) {
  if (!isoDatetime) return
  // v3.1 时区修复：naive datetime 视为 UTC，显式加 'Z' 后缀
  let isoStr = String(isoDatetime).trim()
  if (!isoStr.endsWith('Z') && !/[\-+]\d{2}:?\d{2}$/.test(isoStr)) {
    isoStr = isoStr + 'Z'
  }
  const startMs = new Date(isoStr).getTime()
  if (Number.isNaN(startMs)) {
    console.warn('[useGlobalRecorder] resumeFromStartedAt: invalid datetime', isoDatetime)
    return
  }
  const elapsedSec = Math.max(0, Math.floor((Date.now() - startMs) / 1000))
  setElapsed(elapsedSec)
  recorderStartEpoch = startMs
  console.warn('[useGlobalRecorder] 恢复 elapsed =', elapsedSec, '秒 (from', isoStr, ')')
}

/**
 * 2026-06-27 新增：设置下一次 chunk 的起始 index。
 * 用于刷新后从后端 last_chunk_index + 1 继续上传，避免覆盖已上传的 chunks。
 * **必须在 start() 之前调用**，否则 ondataavailable 第一次触发时 chunkIndex 已经从默认值 0 ++。
 * @param {number} startIndex - 期望的起始 index（通常是 last_chunk_index + 1）
 */
function setChunkStartIndex(startIndex) {
  const n = Math.max(0, Math.floor(Number(startIndex) || 0))
  chunkIndex = n
  console.warn('[useGlobalRecorder] 设置 chunk 起始 index =', n)
}

/**
 * 2026-06-27 新增：获取当前 MediaRecorder 已发出的最大 chunk_index。
 * idle/stopped 时返回 0；recording 中返回 next index。
 * @returns {number}
 */
function getChunkStartIndex() {
  return chunkIndex
}

/**
 * 注册 chunk 回调（每次 ondataavailable 触发时调用）
 * 返回取消注册的函数
 * @param {(chunk: { index: number, blob: Blob, size: number }) => void} cb
 */
function onChunk(cb) {
  chunkCallbacks.push(cb)
  return () => {
    const idx = chunkCallbacks.indexOf(cb)
    if (idx >= 0) chunkCallbacks.splice(idx, 1)
  }
}

/** 获取已录制的 blob（仅 stopped 后可用） */
function getAudioBlob() {
  if (audioChunks.length === 0) return null
  return new Blob(audioChunks, { type: 'audio/webm' })
}

export function useGlobalRecorder() {
  return {
    // 只读状态
    state: readonly(state),
    elapsed: readonly(elapsed),
    barHeights: readonly(barHeights),
    isPaused: readonly(isPaused),
    // 方法
    start,
    pause,
    resumePaused,
    stop,
    reset,
    isActive,
    getAudioBlob,
    // 阶段 1 新增：chunk 回调钩子
    onChunk,
    // 2026-06-27 新增：刷新后接续录音支持
    setElapsed,
    resumeFromStartedAt,
    setChunkStartIndex,
    getChunkStartIndex,
  }
}

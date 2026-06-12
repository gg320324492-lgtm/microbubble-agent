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
  elapsed.value = 0
  isPaused.value = false
  chunkIndex = 0

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
  }
}

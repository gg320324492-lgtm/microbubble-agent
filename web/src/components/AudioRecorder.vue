<template>
  <div class="audio-recorder">
    <!-- 状态：idle — 待录音 -->
    <div v-if="state === 'idle'" class="recorder-idle">
      <div class="recorder-icon">🎙️</div>
      <button class="btn-start" @click="startRecording">开始听会</button>
      <p class="recorder-hint">点击后即开始录音，无需填写任何信息</p>
    </div>

    <!-- 状态：recording — 录音中 -->
    <div v-else-if="state === 'recording' || state === 'paused'" class="recorder-active">
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
        <button v-if="state === 'recording'" class="btn-pause" @click="pauseRecording">⏸ 暂停</button>
        <button v-else class="btn-resume" @click="resumeRecording">▶ 继续</button>
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
import { ref, computed, onUnmounted, nextTick } from 'vue'

const emit = defineEmits(['recording-start', 'recording-stop', 'audio-ready'])

// 状态机: idle → recording → paused → recording → stopped
const state = ref('idle')
const elapsed = ref(0)
const isPlaying = ref(false)
const currentPlayTime = ref(0)

// 录音相关
let mediaRecorder = null
let audioChunks = []
let audioContext = null
let analyser = null
let dataArray = null
let timerInterval = null
let animationFrame = null
let mediaStream = null

// 回放相关
let audioBlob = null
let audioElement = null
let waveformData = null

const waveformCanvas = ref(null)
const formattedTime = computed(() => formatTime(elapsed.value))

// 音量条高度（5 根）
const barHeights = ref([4, 4, 4, 4, 4])

function formatTime(seconds) {
  const s = Math.floor(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

// ===== 录音 =====

async function startRecording() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })

    // 音频分析（音量指示器）
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
      if (e.data.size > 0) audioChunks.push(e.data)
    }

    mediaRecorder.onstop = () => {
      audioBlob = new Blob(audioChunks, { type: 'audio/webm' })
      if (mediaStream) {
        mediaStream.getTracks().forEach(t => t.stop())
        mediaStream = null
      }
      emit('audio-ready', audioBlob)
    }

    mediaRecorder.start(1000) // 每秒收集一次数据
    state.value = 'recording'
    elapsed.value = 0
    emit('recording-start')

    // 计时器
    timerInterval = setInterval(() => { elapsed.value++ }, 1000)

    // 音量动画
    updateVolumeBars()
  } catch (err) {
    console.error('录音启动失败:', err)
    alert('无法访问麦克风，请检查浏览器权限')
  }
}

function pauseRecording() {
  if (mediaRecorder?.state === 'recording') {
    mediaRecorder.pause()
    state.value = 'paused'
    clearInterval(timerInterval)
    cancelAnimationFrame(animationFrame)
  }
}

function resumeRecording() {
  if (mediaRecorder?.state === 'paused') {
    mediaRecorder.resume()
    state.value = 'recording'
    timerInterval = setInterval(() => { elapsed.value++ }, 1000)
    updateVolumeBars()
  }
}

function confirmStop() {
  if (confirm('确定结束听会？')) {
    stopRecording()
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
  }
  clearInterval(timerInterval)
  cancelAnimationFrame(animationFrame)
  state.value = 'stopped'
  emit('recording-stop')

  // 生成波形数据
  nextTick(() => generateWaveform())
}

// ===== 音量指示器 =====

function updateVolumeBars() {
  if (!analyser) return
  analyser.getByteFrequencyData(dataArray)

  // 取 5 个频段的平均值
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

// ===== 波形渲染 =====

async function generateWaveform() {
  if (!audioBlob || !waveformCanvas.value) return

  // 如果 audioContext 已关闭，创建新的用于解码
  let decodeContext = audioContext
  if (!decodeContext || decodeContext.state === 'closed') {
    decodeContext = new AudioContext()
  }

  const canvas = waveformCanvas.value
  const ctx = canvas.getContext('2d')
  const width = canvas.offsetWidth * 2
  const height = canvas.offsetHeight * 2
  canvas.width = width
  canvas.height = height

  // 解码音频
  const arrayBuffer = await audioBlob.arrayBuffer()
  const decoded = await decodeContext.decodeAudioData(arrayBuffer)
  const channelData = decoded.getChannelData(0)

  // 采样（取 width 个点）
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

  // 绘制
  ctx.fillStyle = '#f5f5f5'
  ctx.fillRect(0, 0, width, height)

  ctx.fillStyle = '#FF7A5C'
  const mid = height / 2
  for (let i = 0; i < waveformData.length; i++) {
    const { min, max } = waveformData[i]
    const yMin = mid + min * mid
    const yMax = mid + max * mid
    ctx.fillRect(i, yMin, 1, yMax - yMin || 1)
  }

  // 如果新建了 context，关闭它
  if (decodeContext !== audioContext) {
    decodeContext.close()
  }
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
    audioElement = new Audio(URL.createObjectURL(audioBlob))
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

// ===== 清理 =====

onUnmounted(() => {
  clearInterval(timerInterval)
  cancelAnimationFrame(animationFrame)
  if (audioElement) {
    audioElement.pause()
    audioElement = null
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach(t => t.stop())
    mediaStream = null
  }
  if (audioContext && audioContext.state !== 'closed') {
    audioContext.close()
  }
})

// ===== 暴露方法 =====

defineExpose({
  getAudioBlob: () => audioBlob,
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
  background: linear-gradient(135deg, #FF7A5C, #FF9D85); color: #fff;
  border: none; border-radius: 32px; cursor: pointer;
  transition: all 0.2s;
}
.btn-start:hover { transform: scale(1.05); box-shadow: 0 6px 20px rgba(255,122,92,0.4); }
.recorder-hint { color: #999; font-size: 13px; margin-top: 12px; }

/* recording */
.recorder-active { text-align: center; }
.recorder-status { font-size: 16px; font-weight: 600; color: #333; display: flex; align-items: center; gap: 8px; justify-content: center; }
.rec-dot { width: 10px; height: 10px; border-radius: 50%; background: #F56C6C; animation: pulse 1.5s infinite; }
.rec-dot.paused { animation: none; background: #E6A23C; }
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
.recorder-timer { font-size: 48px; font-weight: 300; font-family: 'SF Mono', 'Cascadia Code', monospace; color: #2D2D2D; margin: 20px 0; }
.volume-bars { display: flex; gap: 6px; align-items: flex-end; justify-content: center; height: 44px; margin: 16px 0; }
.vol-bar { width: 8px; background: linear-gradient(to top, #FF7A5C, #FFB347); border-radius: 4px; transition: height 0.1s; }
.recorder-controls { display: flex; gap: 16px; margin-top: 24px; }
.btn-pause, .btn-resume, .btn-stop {
  padding: 10px 28px; font-size: 15px; font-weight: 600;
  border: none; border-radius: 24px; cursor: pointer; transition: all 0.2s;
}
.btn-pause, .btn-resume { background: #f0f0f0; color: #333; }
.btn-pause:hover, .btn-resume:hover { background: #e0e0e0; }
.btn-stop { background: #F56C6C; color: #fff; }
.btn-stop:hover { background: #E65D5D; }

/* stopped */
.recorder-stopped { text-align: center; width: 100%; max-width: 600px; }
.recorder-done { font-size: 20px; font-weight: 700; color: #333; }
.recorder-duration { font-size: 14px; color: #999; margin: 4px 0 20px; }
.waveform-canvas {
  width: 100%; height: 80px; border-radius: 8px; cursor: pointer;
  border: 1px solid #eee;
}
.playback-controls { display: flex; align-items: center; gap: 12px; justify-content: center; margin-top: 12px; }
.btn-play {
  width: 40px; height: 40px; border-radius: 50%; border: none;
  background: linear-gradient(135deg, #FF7A5C, #FF9D85); color: #fff;
  font-size: 16px; cursor: pointer;
}
.playback-time { font-size: 13px; color: #666; font-family: 'SF Mono', 'Cascadia Code', monospace; }
</style>

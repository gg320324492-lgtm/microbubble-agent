<template>
  <div class="audio-player" v-if="src">
    <!-- 播放按钮 -->
    <button class="play-btn" :class="{ playing: isPlaying }" @click="togglePlay">
      <span v-if="!isPlaying" class="play-icon">▶</span>
      <span v-else class="pause-icon">⏸</span>
    </button>

    <!-- 波形 + 播放头 -->
    <div class="waveform-wrap" @click="seek" ref="waveformWrapRef">
      <canvas ref="canvasRef" class="waveform-canvas" />
      <div
        class="playback-head"
        :style="{ left: progress + '%' }"
      />
    </div>

    <!-- 时间 -->
    <span class="time">{{ formatTime(currentTime) }} / {{ formatTime(duration) }}</span>

    <!-- 倍速 -->
    <button class="speed-btn" @click="cycleSpeed">{{ playbackRate }}x</button>

    <!-- 隐藏的 audio -->
    <audio
      ref="audioRef"
      :src="src"
      preload="auto"
      @loadedmetadata="onLoadedMetadata"
      @timeupdate="onTimeUpdate"
      @ended="onEnded"
      @error="onError"
    />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps({
  src: { type: String, default: '' },
  /** 预生成的波形数据 [{min, max}]，可选，不传则运行时解码 */
  waveformData: { type: Array, default: null },
})

const audioRef = ref(null)
const canvasRef = ref(null)
const waveformWrapRef = ref(null)
const isPlaying = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const progress = ref(0)
const playbackRate = ref(1)

let decodedWaveform = null
let animFrameId = null

// ===== 播放控制 =====

function togglePlay() {
  if (!audioRef.value) return
  if (isPlaying.value) {
    audioRef.value.pause()
    isPlaying.value = false
  } else {
    audioRef.value.play()
    isPlaying.value = true
  }
}

function seek(e) {
  if (!audioRef.value || !duration.value) return
  const rect = e.currentTarget.getBoundingClientRect()
  const ratio = (e.clientX - rect.left) / rect.width
  audioRef.value.currentTime = ratio * duration.value
}

function cycleSpeed() {
  const speeds = [1, 1.5, 2]
  const idx = speeds.indexOf(playbackRate.value)
  playbackRate.value = speeds[(idx + 1) % speeds.length]
  if (audioRef.value) {
    audioRef.value.playbackRate = playbackRate.value
  }
}

// ===== Audio 事件 =====

function onLoadedMetadata() {
  if (!audioRef.value) return
  duration.value = audioRef.value.duration
  audioRef.value.playbackRate = playbackRate.value
  nextTick(() => generateWaveform())
}

function onTimeUpdate() {
  if (!audioRef.value) return
  currentTime.value = audioRef.value.currentTime
  progress.value = (currentTime.value / duration.value) * 100 || 0
  drawWaveformAt(progress.value / 100)
}

function onEnded() {
  isPlaying.value = false
  currentTime.value = 0
  progress.value = 0
}

function onError(e) {
  console.error('AudioPlayer 播放错误:', e)
  isPlaying.value = false
}

// ===== 波形渲染 =====

async function generateWaveform() {
  // 优先使用外部传入的波形数据
  if (props.waveformData && props.waveformData.length > 0) {
    decodedWaveform = props.waveformData
    drawWaveformAt(0)
    return
  }

  // 否则运行时解码
  if (!audioRef.value || !audioRef.value.src) return

  try {
    const actx = new AudioContext()
    const resp = await fetch(audioRef.value.src)
    const arrayBuffer = await resp.arrayBuffer()
    const decoded = await actx.decodeAudioData(arrayBuffer)
    const channelData = decoded.getChannelData(0)
    actx.close()

    const canvas = canvasRef.value
    if (!canvas) return
    const width = canvas.offsetWidth * 2
    const step = Math.floor(channelData.length / width)

    decodedWaveform = []
    for (let i = 0; i < width; i++) {
      let min = 1, max = -1
      for (let j = i * step; j < (i + 1) * step && j < channelData.length; j++) {
        if (channelData[j] < min) min = channelData[j]
        if (channelData[j] > max) max = channelData[j]
      }
      decodedWaveform.push({ min, max })
    }
    drawWaveformAt(0)
  } catch (e) {
    console.warn('AudioPlayer 波形解码失败:', e)
  }
}

function drawWaveformAt(ratio) {
  const canvas = canvasRef.value
  if (!canvas || !decodedWaveform) return

  const dpr = window.devicePixelRatio || 1
  const displayW = canvas.offsetWidth
  const displayH = canvas.offsetHeight
  canvas.width = displayW * dpr
  canvas.height = displayH * dpr

  const ctx = canvas.getContext('2d')
  ctx.scale(dpr, dpr)

  const W = displayW
  const H = displayH
  const mid = H / 2

  ctx.clearRect(0, 0, W, H)

  // 已播放部分的 x 坐标
  const playedX = ratio * W

  for (let i = 0; i < decodedWaveform.length && i < W; i++) {
    const { min, max } = decodedWaveform[i]
    const yMin = mid + min * mid * 0.9
    const yMax = mid + max * mid * 0.9
    const x = (i / decodedWaveform.length) * W

    if (x <= playedX) {
      ctx.fillStyle = 'var(--color-primary)'
    } else {
      ctx.fillStyle = '#ddd'
    }
    ctx.fillRect(x, yMin, 1, Math.max(1, yMax - yMin))
  }
}

// ===== 格式化 =====

function formatTime(sec) {
  if (!sec || isNaN(sec)) return '00:00'
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

// ===== 生命周期 =====

watch(() => props.src, (newSrc) => {
  if (newSrc) {
    isPlaying.value = false
    currentTime.value = 0
    progress.value = 0
    decodedWaveform = null
  }
})

const stop = () => {
  if (audioRef.value) {
    audioRef.value.pause()
    audioRef.value.currentTime = 0
    isPlaying.value = false
    currentTime.value = 0
    progress.value = 0
  }
}

onUnmounted(() => {
  stop()
  cancelAnimationFrame(animFrameId)
})

defineExpose({ stop, togglePlay })
</script>

<style scoped>
.audio-player {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--color-bg-page, #f5f7fa);
  border-radius: var(--radius-lg, 12px);
}

.play-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: var(--color-bg-card);
  font-size: 14px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), 0.3);
}
.play-btn:hover { transform: scale(1.08); box-shadow: 0 4px 12px rgba(var(--color-primary-rgb), 0.4); }
.play-btn:active { transform: scale(0.95); }

.play-icon { margin-left: 2px; }

.waveform-wrap {
  flex: 1;
  height: 48px;
  position: relative;
  cursor: pointer;
  overflow: hidden;
  border-radius: var(--radius-md, 8px);
}

.waveform-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.playback-head {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--color-primary, #FF7A5C);
  box-shadow: 0 0 6px rgba(var(--color-primary-rgb), 0.5);
  pointer-events: none;
  transition: left 0.1s linear;
}

.time {
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
  white-space: nowrap;
  min-width: 85px;
  text-align: center;
  font-family: 'SF Mono', 'Cascadia Code', monospace;
}

.speed-btn {
  padding: 2px 8px;
  border: 1px solid var(--color-border, #dcdfe6);
  border-radius: var(--radius-sm, 4px);
  background: var(--color-bg-card);
  color: var(--color-text-secondary, #909399);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
  flex-shrink: 0;
}
.speed-btn:hover {
  border-color: var(--color-primary, #FF7A5C);
  color: var(--color-primary, #FF7A5C);
}
</style>

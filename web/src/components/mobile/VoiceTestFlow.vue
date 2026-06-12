<template>
  <Teleport to="body">
    <Transition name="test-flow">
      <div v-if="modelValue" class="test-flow-root">
        <!-- Header -->
        <div class="flow-header">
          <button
            type="button"
            class="header-btn"
            aria-label="返回"
            title="返回"
            @click="onClose"
          >✕</button>
          <h2 class="flow-title">麦克风测试</h2>
          <div class="header-spacer" />
        </div>

        <main class="flow-main">
          <!-- 权限错误 -->
          <div v-if="permissionError" class="error-state">
            <div class="big-icon">⚠️</div>
            <h3>无法访问麦克风</h3>
            <p class="error-hint">{{ permissionError }}</p>
            <button type="button" class="btn-primary" @click="retryPermission">
              重新尝试
            </button>
          </div>

          <!-- 正常测试 -->
          <div v-else class="test-state">
            <div class="visualizer-wrap">
              <div class="visualizer">
                <div
                  v-for="i in 20"
                  :key="i"
                  class="bar"
                  :style="{ height: getBarHeight(i) + 'px' }"
                />
              </div>
              <div class="volume-display">
                <div class="volume-num">{{ Math.round(volume * 100) }}</div>
                <div class="volume-unit">%</div>
              </div>
            </div>

            <div class="status-display">
              <span class="rec-dot" v-if="recording" />
              <span>{{ statusText }}</span>
            </div>

            <!-- 测试控制 -->
            <div class="controls">
              <button
                v-if="!recording && !recordedBlob"
                type="button"
                class="big-btn record"
                @click="startTest"
              >
                <span class="big-btn-icon">🎤</span>
                <span>开始测试</span>
              </button>

              <button
                v-else-if="recording"
                type="button"
                class="big-btn stop"
                @click="stopTest"
              >
                <span class="big-btn-icon">⏹</span>
                <span>停止</span>
              </button>

              <div v-else-if="recordedBlob" class="result-controls">
                <audio :src="recordedUrl" controls class="audio-player" />
                <div class="btn-row">
                  <button
                    type="button"
                    class="btn-secondary"
                    @click="discard"
                  >重录</button>
                  <button
                    type="button"
                    class="btn-primary"
                    @click="onClose"
                  >完成</button>
                </div>
              </div>
            </div>

            <!-- 实时转写（如果有 ASR） -->
            <div v-if="asrResult" class="asr-result">
              <div class="asr-label">识别结果：</div>
              <div class="asr-text">{{ asrResult }}</div>
            </div>
          </div>
        </main>

        <!-- 帮助 -->
        <div class="help-footer">
          <p>💡 测试说话音量是否足够清晰</p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * VoiceTestFlow.vue — 移动端麦克风测试全屏组件
 *
 * PR #5: 独立组件（不用 el-dialog + CSS 全屏）
 * - 实时音量可视化（20 根 bar 高度变化）
 * - 录音 + 播放 + 重录
 * - 错误处理：NotAllowedError / NotFoundError 区分提示
 * - ASR 集成（可选，识别说话内容）
 *
 * 关键修复（CLAUDE.md 教训）：
 * - getUserMedia 和 AudioContext 各自独立 try/catch
 * - 错误信息精确区分（NotAllowedError / NotFoundError / Other）
 * -webkitAudioContext 前缀兼容 + resume() 处理 suspended
 */

import { ref, computed, onUnmounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

// 录音状态
const recording = ref(false)
const recordedBlob = ref(null)
const recordedUrl = ref('')
let mediaRecorder = null
let audioChunks = []
let audioContext = null
let analyser = null
let mediaStream = null
let rafId = null

// 音量可视化
const volume = ref(0)
const bars = ref(new Array(20).fill(0))

// 错误
const permissionError = ref('')

// ASR 识别结果（可选）
const asrResult = ref('')

const statusText = computed(() => {
  if (recording.value) return '正在录音...'
  if (recordedBlob.value) return '录制完成'
  return '准备就绪'
})

function getBarHeight(idx) {
  if (!recording.value) return 8
  // 根据当前 volume + 位置产生波动
  const offset = (Date.now() / 100 + idx) % 1
  const target = volume.value * 100 * (0.5 + Math.sin(offset * Math.PI * 2) * 0.5)
  return Math.max(8, target + 8)
}

// ============================================================================
// 权限与初始化
// ============================================================================
async function retryPermission() {
  permissionError.value = ''
  await initAudio()
}

async function initAudio() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch (e) {
    handleMediaError(e)
    return false
  }

  // AudioContext（独立 try/catch）
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    audioContext = new Ctx()
    if (audioContext.state === 'suspended') {
      await audioContext.resume()
    }
    const source = audioContext.createMediaStreamSource(mediaStream)
    analyser = audioContext.createAnalyser()
    analyser.fftSize = 256
    source.connect(analyser)
  } catch (e) {
    // AudioContext 失败不影响录音，只是不显示音量可视化
    console.warn('AudioContext 初始化失败:', e)
  }

  return true
}

function handleMediaError(e) {
  if (e.name === 'NotAllowedError') {
    permissionError.value = '麦克风权限被拒绝。请在浏览器/系统设置中允许访问麦克风后重试。'
  } else if (e.name === 'NotFoundError') {
    permissionError.value = '未检测到麦克风设备。请检查麦克风是否连接。'
  } else {
    permissionError.value = '麦克风访问失败：' + (e.message || '未知错误')
  }
}

// ============================================================================
// 录音控制
// ============================================================================
async function startTest() {
  const ok = await initAudio()
  if (!ok) return

  recording.value = true
  audioChunks = []

  try {
    mediaRecorder = new MediaRecorder(mediaStream)
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data)
    }
    mediaRecorder.onstop = () => {
      recordedBlob.value = new Blob(audioChunks, { type: 'audio/webm' })
      recordedUrl.value = URL.createObjectURL(recordedBlob.value)
      audioChunks = []
    }
    mediaRecorder.start()
  } catch (e) {
    permissionError.value = '录音启动失败：' + e.message
    recording.value = false
    return
  }

  // 开始音量检测
  monitorVolume()
}

function stopTest() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
  }
  recording.value = false
  stopVolumeMonitor()
}

function discard() {
  if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)
  recordedBlob.value = null
  recordedUrl.value = ''
  asrResult.value = ''
}

function onClose() {
  cleanup()
  emit('update:modelValue', false)
}

// ============================================================================
// 音量监测
// ============================================================================
function monitorVolume() {
  if (!analyser) return
  const data = new Uint8Array(analyser.frequencyBinCount)

  function tick() {
    if (!recording.value) return
    analyser.getByteFrequencyData(data)
    // 计算平均音量
    let sum = 0
    for (let i = 0; i < data.length; i++) sum += data[i]
    volume.value = sum / data.length / 255
    // 更新 20 根 bar
    bars.value = bars.value.map((_, i) => {
      const idx = Math.floor((i / 20) * data.length)
      return data[idx] / 255
    })
    rafId = requestAnimationFrame(tick)
  }
  tick()
}

function stopVolumeMonitor() {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = null
  volume.value = 0
  bars.value = new Array(20).fill(0)
}

// ============================================================================
// 清理
// ============================================================================
function cleanup() {
  stopVolumeMonitor()
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    try { mediaRecorder.stop() } catch { /* ignore */ }
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop())
  }
  if (audioContext && audioContext.state !== 'closed') {
    audioContext.close().catch(() => {})
  }
  if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)

  mediaRecorder = null
  mediaStream = null
  audioContext = null
  analyser = null
  audioChunks = []
  recording.value = false
  recordedBlob.value = null
  recordedUrl.value = ''
  volume.value = 0
  bars.value = new Array(20).fill(0)
  permissionError.value = ''
  asrResult.value = ''
}

onBeforeUnmount(cleanup)
onUnmounted(cleanup)
</script>

<style scoped>
.test-flow-root {
  position: fixed;
  inset: 0;
  z-index: 5000;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
  padding-top: var(--sat);
}
[data-theme="dark"] .test-flow-root {
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

/* 主内容 */
.flow-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

.error-state {
  text-align: center;
  padding: 40px 20px;
}
.big-icon {
  font-size: 64px;
  margin-bottom: 16px;
}
.error-state h3 {
  font-size: 18px;
  color: var(--color-text-primary);
  margin: 0 0 12px;
}
.error-hint {
  font-size: 14px;
  color: var(--color-text-regular);
  line-height: 1.6;
  margin-bottom: 24px;
  white-space: pre-line;
}

/* 可视化 */
.visualizer-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 32px;
}
.visualizer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 160px;
  padding: 0 16px;
  margin-bottom: 20px;
}
.bar {
  width: 6px;
  background: linear-gradient(180deg, var(--color-primary), var(--color-primary-light));
  border-radius: 3px;
  transition: height 50ms ease;
  min-height: 8px;
}
.volume-display {
  display: flex;
  align-items: baseline;
  gap: 4px;
  color: var(--color-primary);
}
.volume-num {
  font-size: 48px;
  font-weight: var(--font-weight-bold, 700);
  font-variant-numeric: tabular-nums;
  line-height: 1;
}
.volume-unit {
  font-size: 20px;
  font-weight: var(--font-weight-medium, 500);
}

/* 状态 */
.status-display {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--color-text-regular);
  margin-bottom: 40px;
}
.rec-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-danger, #F56C6C);
  animation: pulse 1s infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

/* 控制 */
.controls {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.big-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: 200px;
  height: 200px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: white;
  font-size: 16px;
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(255, 122, 92, 0.3);
  -webkit-tap-highlight-color: transparent;
}
.big-btn:active { transform: scale(0.97); }
.big-btn.stop {
  background: linear-gradient(135deg, var(--color-danger, #F56C6C), #FF8888);
  box-shadow: 0 8px 24px rgba(245, 108, 108, 0.3);
}
.big-btn-icon { font-size: 56px; }

.result-controls {
  width: 100%;
}
.audio-player {
  width: 100%;
  margin-bottom: 16px;
}
.btn-row {
  display: flex;
  gap: 12px;
}
.btn-primary, .btn-secondary {
  flex: 1;
  padding: 12px;
  border-radius: var(--radius-md);
  border: none;
  font-size: 14px;
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.btn-primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: white;
}
.btn-secondary {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  color: var(--color-text-primary);
}

/* ASR 结果 */
.asr-result {
  width: 100%;
  margin-top: 24px;
  padding: 12px 16px;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
}
.asr-label {
  font-size: 11px;
  color: var(--color-text-secondary);
  margin-bottom: 4px;
}
.asr-text {
  font-size: 15px;
  color: var(--color-text-primary);
  line-height: 1.5;
}

/* 帮助 */
.help-footer {
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.help-footer p { margin: 0; }

/* 进出动画 */
.test-flow-enter-active, .test-flow-leave-active {
  transition: opacity 0.3s ease;
}
.test-flow-enter-from, .test-flow-leave-to { opacity: 0; }
</style>
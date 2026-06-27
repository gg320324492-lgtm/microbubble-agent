<template>
  <Teleport to="body">
    <Transition name="test-flow">
      <div v-if="modelValue" class="test-flow-root">
        <!-- Header -->
        <div class="flow-header">
          <button
            id="voice-test-close"
            type="button"
            class="header-btn"
            name="voice-test-close"
            aria-label="关闭"
            title="关闭"
            @click="onClose"
          >✕</button>
          <h2 class="flow-title">声纹识别测试</h2>
          <div class="header-spacer" />
        </div>

        <main class="flow-main">
          <!-- 权限错误 -->
          <div v-if="permissionError" class="error-state">
            <div class="big-icon">⚠️</div>
            <h3>无法访问麦克风</h3>
            <p class="error-hint">{{ permissionError }}</p>
            <button
              id="voice-test-retry-permission"
              type="button"
              name="voice-test-retry-permission"
              aria-label="重新尝试"
              title="重新尝试"
              class="btn-primary"
              @click="retryPermission"
            >
              重新尝试
            </button>
          </div>

          <!-- 录音 + 结果 -->
          <div v-else class="test-state">
            <!-- 可视化（仅录音中） -->
            <div v-if="state === 'recording'" class="visualizer-wrap">
              <div class="visualizer">
                <div
                  v-for="i in 20"
                  :key="i"
                  class="bar"
                  :style="{ height: getBarHeight(i) + 'px' }"
                />
              </div>
              <div class="volume-display">
                <div class="volume-num">{{ recordingTime }}</div>
                <div class="volume-unit">s / 5s</div>
              </div>
            </div>

            <!-- 状态文字 -->
            <div class="status-display">
              <span class="rec-dot" v-if="state === 'recording'" />
              <span class="rec-dot spinner-dot" v-else-if="state === 'testing'" />
              <span>{{ statusText }}</span>
            </div>

            <!-- 录音控制：idle 或 recording -->
            <div v-if="state === 'idle' || state === 'recording'" class="controls">
              <button
                v-if="state === 'idle'"
                id="voice-test-start"
                type="button"
                name="voice-test-start"
                aria-label="开始录音"
                title="开始录音"
                class="big-btn record"
                @click="startTest"
              >
                <span class="big-btn-icon">🎤</span>
                <span>开始录音</span>
              </button>

              <button
                v-else
                id="voice-test-stop"
                type="button"
                name="voice-test-stop"
                aria-label="停止录音"
                title="停止录音"
                class="big-btn stop"
                @click="stopTest"
              >
                <span class="big-btn-icon">⏹</span>
                <span>停止</span>
              </button>
            </div>

            <!-- 录完未测试：重录 / 测一下 -->
            <div v-else-if="state === 'recorded'" class="result-controls">
              <audio :src="recordedUrl" controls class="audio-player" />
              <div class="btn-row">
                <button
                  id="voice-test-retry"
                  type="button"
                  name="voice-test-retry"
                  aria-label="重录"
                  title="重录"
                  class="btn-secondary"
                  @click="discard"
                >重录</button>
                <button
                  id="voice-test-submit"
                  type="button"
                  name="voice-test-submit"
                  aria-label="测试声纹识别"
                  title="测试声纹识别"
                  class="btn-primary"
                  :disabled="testing"
                  @click="submitTest"
                >
                  {{ testing ? '测试中...' : '🔍 测试识别' }}
                </button>
              </div>
            </div>

            <!-- 测试中 -->
            <div v-else-if="state === 'testing'" class="testing-area">
              <div class="spinner" />
              <p>正在分析音频...</p>
            </div>

            <!-- 结果展示 -->
            <div v-else-if="state === 'result'" class="result-area">
              <!-- 步骤列表 -->
              <div class="steps-list">
                <div v-for="(step, idx) in testResult.steps" :key="idx" class="step-row">
                  <div class="step-icon">
                    <span v-if="step.status === 'ok'" class="icon-ok">✅</span>
                    <span v-else-if="step.status === 'warn'" class="icon-warn">⚠️</span>
                    <span v-else class="icon-error">❌</span>
                  </div>
                  <div class="step-info">
                    <div class="step-name">{{ step.name }}</div>
                    <div class="step-detail" :class="`status-${step.status}`">{{ step.detail }}</div>
                  </div>
                </div>
              </div>

              <!-- 最终结果 -->
              <div v-if="testResult.success" class="final-result success">
                <div class="result-badge success">🎉 识别成功</div>
                <div class="result-speaker">{{ testResult.speaker }}</div>
                <div class="result-confidence">置信度: {{ Math.round((testResult.confidence || 0) * 100) }}%</div>
                <div v-if="testResult.transcript" class="result-transcript">"{{ testResult.transcript }}"</div>
              </div>
              <div v-else class="final-result fail">
                <div class="result-badge fail">未成功识别</div>
                <p v-if="testResult.transcript" class="result-hint">
                  语音内容: "{{ testResult.transcript }}"
                </p>
                <p class="result-hint">
                  请检查：麦克风是否正常、是否已录入声纹、说话是否清晰
                </p>
              </div>

              <button
                id="voice-test-restart"
                type="button"
                name="voice-test-restart"
                aria-label="再测一次"
                title="再测一次"
                class="btn-primary full"
                @click="resetTest"
              >
                再测一次
              </button>
            </div>
          </div>
        </main>

        <!-- 帮助 -->
        <div class="help-footer">
          <p>💡 说完 3-5 秒，系统会先解码 → 静音检测 → VAD → 语音识别 → 声纹匹配</p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * VoiceTestFlow.vue — 移动端声纹识别测试全屏组件
 *
 * 关键点（CLAUDE.md 教训）：
 * - 这是「声纹识别测试」不是「麦克风测试」——录音完必须 POST /api/v1/voiceprint/test
 *   让后端跑完整 5 步链路（解码/静音检测/VAD/ASR/声纹识别），返回 speaker + confidence
 * - 之前版本只测麦克风能不能录音 + 音量可视化 → 用户测完了"我能不能被识别"毫无头绪
 * - getUserMedia 和 AudioContext 各自独立 try/catch
 * - 错误信息精确区分（NotAllowedError / NotFoundError / Other）
 * -webkitAudioContext 前缀兼容 + resume() 处理 suspended
 * - 不要手动设 Content-Type，让 axios 自动处理 multipart boundary
 */

import { ref, computed, onUnmounted, onBeforeUnmount } from 'vue'
import axios from 'axios'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])

// 状态机：idle → recording → recorded → testing → result
const state = ref('idle')
const recordingTime = ref(0)
const testing = ref(false)
const testResult = ref({
  steps: [],
  success: false,
  speaker: null,
  confidence: 0,
  transcript: '',
})

// 录音资源
const recordedBlob = ref(null)
const recordedUrl = ref('')
let mediaRecorder = null
let audioChunks = []
let audioContext = null
let analyser = null
let mediaStream = null
let rafId = null
let timerInterval = null

// 音量可视化
const volume = ref(0)

// 错误
const permissionError = ref('')

const statusText = computed(() => {
  if (state.value === 'recording') return '正在录音...'
  if (state.value === 'recorded') return '录制完成'
  if (state.value === 'testing') return '正在分析音频...'
  if (state.value === 'result') return testResult.value.success
    ? `识别为：${testResult.value.speaker}`
    : '未成功识别'
  return '点击按钮开始测试'
})

function getBarHeight(idx) {
  if (!recording.value) return 8
  const offset = (Date.now() / 100 + idx) % 1
  const target = volume.value * 100 * (0.5 + Math.sin(offset * Math.PI * 2) * 0.5)
  return Math.max(8, target + 8)
}

// Vue 3.5 模板里需要响应式 ref（不是普通变量）
const recording = computed(() => state.value === 'recording')

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

  state.value = 'recording'
  recordingTime.value = 0
  audioChunks = []

  try {
    // iOS Safari 兼容：尝试 webm，失败回退默认
    const mimeType = MediaRecorder.isTypeSupported('audio/webm')
      ? 'audio/webm'
      : (MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : '')
    mediaRecorder = mimeType ? new MediaRecorder(mediaStream, { mimeType }) : new MediaRecorder(mediaStream)
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data)
    }
    mediaRecorder.onstop = () => {
      const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || 'audio/webm' })
      if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)
      recordedBlob.value = blob
      recordedUrl.value = URL.createObjectURL(blob)
      audioChunks = []
      state.value = 'recorded'
    }
    mediaRecorder.start()
  } catch (e) {
    permissionError.value = '录音启动失败：' + e.message
    state.value = 'idle'
    return
  }

  // 5 秒自动停止（与桌面端一致）
  timerInterval = setInterval(() => {
    recordingTime.value++
    if (recordingTime.value >= 5) {
      stopTest()
    }
  }, 1000)

  // 开始音量检测
  monitorVolume()
}

function stopTest() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
  }
  stopVolumeMonitor()
  // 注意：state 不在这里改，等 onstop 回调里改（避免 blob 还没好就切换 UI）
}

function discard() {
  if (recordedUrl.value) URL.revokeObjectURL(recordedUrl.value)
  recordedBlob.value = null
  recordedUrl.value = ''
  testResult.value = { steps: [], success: false, speaker: null, confidence: 0, transcript: '' }
  state.value = 'idle'
}

// ============================================================================
// 提交声纹识别测试
// ============================================================================
async function submitTest() {
  if (!recordedBlob.value || testing.value) return
  testing.value = true
  state.value = 'testing'

  try {
    const formData = new FormData()
    formData.append('audio', recordedBlob.value, 'test.webm')
    // 不要手动设 Content-Type，让 axios 自动加 boundary（CLAUDE.md 教训）

    const resp = await axios.post('/api/v1/voiceprint/test', formData)
    testResult.value = resp.data || testResult.value
    state.value = 'result'
  } catch (e) {
    // 后端 4xx/5xx 时仍要保持有步骤信息，让用户知道错在哪
    const detail = e.response?.data?.detail || e.message
    testResult.value = {
      steps: [
        { name: '测试请求', status: 'error', detail: `测试请求失败：${detail}` },
      ],
      success: false,
      speaker: null,
      confidence: 0,
      transcript: '',
    }
    state.value = 'result'
  } finally {
    testing.value = false
  }
}

function resetTest() {
  discard()
}

// ============================================================================
// 音量监测
// ============================================================================
function monitorVolume() {
  if (!analyser) return
  const data = new Uint8Array(analyser.frequencyBinCount)

  function tick() {
    if (state.value !== 'recording') return
    analyser.getByteFrequencyData(data)
    let sum = 0
    for (let i = 0; i < data.length; i++) sum += data[i]
    volume.value = sum / data.length / 255
    rafId = requestAnimationFrame(tick)
  }
  tick()
}

function stopVolumeMonitor() {
  if (rafId) cancelAnimationFrame(rafId)
  rafId = null
  volume.value = 0
}

function onClose() {
  cleanup()
  emit('update:modelValue', false)
}

// ============================================================================
// 清理
// ============================================================================
function cleanup() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
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
  state.value = 'idle'
  recordedBlob.value = null
  recordedUrl.value = ''
  recordingTime.value = 0
  testing.value = false
  volume.value = 0
  permissionError.value = ''
  testResult.value = { steps: [], success: false, speaker: null, confidence: 0, transcript: '' }
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
  overflow-y: auto;
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
  margin-bottom: 24px;
}
.rec-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--color-danger, #F56C6C);
  animation: pulse 1s infinite;
}
.rec-dot.spinner-dot {
  background: var(--color-primary);
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
  /* stylelint-disable-next-line color-named */
  color: white;
  font-size: 16px;
  font-weight: var(--font-weight-medium, 500);
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(var(--color-primary-rgb), 0.3);
  -webkit-tap-highlight-color: transparent;
}
.big-btn:active { transform: scale(0.97); }
.big-btn.stop {
  background: linear-gradient(135deg, var(--color-danger, #F56C6C), #FF8888);
  box-shadow: 0 8px 24px rgba(245, 108, 108, 0.3);
}
.big-btn:disabled { opacity: 0.6; cursor: not-allowed; }
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
  /* stylelint-disable-next-line color-named */
  color: white;
}
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  color: var(--color-text-primary);
}
.btn-primary.full { width: 100%; margin-top: 16px; }

/* 测试中 */
.testing-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 40px 0;
}
.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #eee;
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* 结果 */
.result-area {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.steps-list {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 12px 16px;
}
.step-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border-light);
}
.step-row:last-child { border-bottom: none; }
.step-icon { font-size: 18px; line-height: 1; flex-shrink: 0; }
.step-info { flex: 1; }
.step-name { font-weight: 600; font-size: 14px; color: var(--color-text-primary); }
.step-detail { font-size: 13px; margin-top: 2px; }
.step-detail.status-ok { color: var(--color-success, #52c41a); }
.step-detail.status-warn { color: var(--color-warning, #faad14); }
.step-detail.status-error { color: var(--color-danger, #ff4d4f); }

.final-result {
  margin-top: 8px;
  text-align: center;
  padding: 16px;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
}
.result-badge {
  display: inline-block;
  padding: 4px 16px;
  border-radius: 20px;
  font-weight: 600;
  font-size: 15px;
}
.result-badge.success { background: rgba(82, 196, 26, 0.1); color: var(--color-success); border: 1px solid #b7eb8f; }
.result-badge.fail { background: rgba(255, 77, 79, 0.1); color: var(--color-danger); border: 1px solid #ffccc7; }
.result-speaker { font-size: 22px; font-weight: 700; margin-top: 8px; color: var(--color-text-primary); }
.result-confidence { font-size: 14px; color: var(--color-text-secondary); margin-top: 4px; }
.result-transcript { font-size: 14px; color: var(--color-text-regular); margin-top: 8px; font-style: italic; overflow-wrap: anywhere; }
.result-hint { font-size: 13px; color: var(--color-text-secondary); margin-top: 8px; }

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

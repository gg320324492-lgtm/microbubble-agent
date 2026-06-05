<template>
  <el-dialog
    v-model="visible"
    title="🎤 声纹全链路测试"
    width="500px"
    :close-on-click-modal="false"
    @close="onClose"
  >
    <div class="voice-test">
      <!-- 状态说明 -->
      <div class="test-hint" v-if="state === 'idle'">
        <p>点击下方按钮，对着麦克风说一句话（3-5 秒）</p>
        <p class="hint-sub">系统将自动检测：麦克风 → 语音活动 → 语音识别 → 声纹匹配</p>
      </div>

      <!-- 录音区域 -->
      <div class="record-area" v-if="state === 'idle' || state === 'recording'">
        <div class="mic-button" :class="{ recording: state === 'recording' }" @click="toggleRecord">
          <el-icon :size="48"><Microphone /></el-icon>
          <!-- 录音中的脉冲光晕 -->
          <div v-if="state === 'recording'" class="mic-pulse" />
        </div>
        <div class="timer" v-if="state === 'recording'">{{ recordingTime }}s / 5s</div>

        <!-- Canvas 波形动画 -->
        <canvas
          v-if="state === 'recording'"
          ref="waveformRef"
          class="waveform-canvas"
          width="400"
          height="80"
        />
      </div>

      <!-- 测试中 -->
      <div class="testing-area" v-if="state === 'testing'">
        <div class="spinner"></div>
        <p>正在分析音频...</p>
      </div>

      <!-- 结果 -->
      <div class="result-area" v-if="state === 'result'">
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

        <!-- 最终结果 -->
        <div class="final-result" v-if="testResult.success">
          <div class="result-badge success">🎉 识别成功</div>
          <div class="result-speaker">{{ testResult.speaker }}</div>
          <div class="result-confidence">置信度: {{ Math.round(testResult.confidence * 100) }}%</div>
          <div class="result-transcript">"{{ testResult.transcript }}"</div>
        </div>
        <div class="final-result" v-else>
          <div class="result-badge fail">未成功识别</div>
          <p class="result-hint" v-if="testResult.transcript">
            语音内容: "{{ testResult.transcript }}"
          </p>
          <p class="result-hint">
            请检查：麦克风是否正常、是否已录入声纹、说话是否清晰
          </p>
        </div>

        <el-button type="primary" @click="resetTest" style="margin-top: 16px; width: 100%;">
          重新测试
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
import { Microphone } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const visible = defineModel('visible', { default: false })

const state = ref('idle') // idle | recording | testing | result
const recordingTime = ref(0)
const testResult = ref({ steps: [], success: false, speaker: null, confidence: 0, transcript: '' })

let mediaStream = null
let audioContext = null
let workletNode = null
let mediaRecorder = null
let audioChunks = []
let timerInterval = null
let animFrameId = null
let analyserNode = null
let freqDataArray = null

// 平滑后的频率数据（用于衰减动画）
let smoothedData = null

const waveformRef = ref(null)

async function toggleRecord() {
  if (state.value === 'recording') {
    stopRecord()
    return
  }
  await startRecord()
}

async function startRecord() {
  // 1. 获取麦克风权限（单独 try/catch，错误信息精确）
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: { sampleRate: { ideal: 16000 }, channelCount: 1, echoCancellation: true, noiseSuppression: true }
    })
  } catch (e) {
    if (e.name === 'NotAllowedError') {
      ElMessage.error('请允许麦克风权限后再试')
    } else if (e.name === 'NotFoundError') {
      ElMessage.error('未检测到麦克风设备')
    } else {
      ElMessage.error('麦克风访问失败: ' + e.message)
    }
    return
  }

  // 2. 音量可视化（AudioContext 失败不影响录音）
  try {
    audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 })
    if (audioContext.state === 'suspended') {
      await audioContext.resume()
    }
    const source = audioContext.createMediaStreamSource(mediaStream)
    analyserNode = audioContext.createAnalyser()
    analyserNode.fftSize = 256
    analyserNode.smoothingTimeConstant = 0.8
    source.connect(analyserNode)

    freqDataArray = new Uint8Array(analyserNode.frequencyBinCount)
    smoothedData = new Float32Array(analyserNode.frequencyBinCount).fill(0)

    // 启动 Canvas 波形动画
    drawWaveform()
  } catch (e) {
    console.warn('AudioContext 初始化失败（不影响录音）:', e)
  }

  // 3. 录音（支持多格式兜底）
  const mimeType = MediaRecorder.isTypeSupported('audio/webm')
    ? 'audio/webm'
    : (MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : '')
  try {
    mediaRecorder = new MediaRecorder(mediaStream, mimeType ? { mimeType } : undefined)
    audioChunks = []
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data)
    }
    mediaRecorder.onstop = onRecordStop
    mediaRecorder.start()

    state.value = 'recording'
    recordingTime.value = 0
    timerInterval = setInterval(() => {
      recordingTime.value++
      if (recordingTime.value >= 5) {
        stopRecord()
      }
    }, 1000)
  } catch (e) {
    ElMessage.error('录音启动失败: ' + e.message)
    stopRecord()
  }
}

function stopRecord() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
  }
  clearInterval(timerInterval)
  cancelAnimationFrame(animFrameId)
  animFrameId = null
  analyserNode = null
  freqDataArray = null
  smoothedData = null
  if (mediaStream) {
    mediaStream.getTracks().forEach(t => t.stop())
  }
  if (audioContext) {
    audioContext.close()
  }
}

// ===== Canvas 波形绘制 =====

function drawWaveform() {
  if (state.value !== 'recording') return

  const canvas = waveformRef.value
  if (!canvas || !analyserNode || !freqDataArray) return

  const ctx = canvas.getContext('2d')
  const W = canvas.width
  const H = canvas.height

  // 获取频率数据
  analyserNode.getByteFrequencyData(freqDataArray)

  // 平滑衰减
  const decay = 0.7
  const attack = 0.3
  for (let i = 0; i < freqDataArray.length; i++) {
    const target = freqDataArray[i] / 255
    smoothedData[i] = smoothedData[i] * decay + target * attack
  }

  // 清除画布
  ctx.clearRect(0, 0, W, H)

  // 采样点数（取中间频段，跳过高频噪声）
  const usableBins = Math.floor(freqDataArray.length * 0.7)
  const pointCount = Math.min(usableBins, 64)
  const step = Math.floor(usableBins / pointCount)

  const points = []
  for (let i = 0; i < pointCount; i++) {
    const idx = i * step
    const value = smoothedData[idx] || 0
    points.push({
      x: (i / (pointCount - 1)) * W,
      y: H - value * H * 0.85 - H * 0.05
    })
  }

  // 绘制填充区域（渐变）
  const gradient = ctx.createLinearGradient(0, 0, 0, H)
  gradient.addColorStop(0, 'rgba(255, 122, 92, 0.6)')
  gradient.addColorStop(0.5, 'rgba(255, 179, 71, 0.3)')
  gradient.addColorStop(1, 'rgba(255, 122, 92, 0.05)')

  ctx.beginPath()
  ctx.moveTo(0, H)

  // 用贝塞尔曲线平滑连接
  for (let i = 0; i < points.length; i++) {
    if (i === 0) {
      ctx.lineTo(points[i].x, points[i].y)
    } else {
      const prev = points[i - 1]
      const cpx = (prev.x + points[i].x) / 2
      ctx.bezierCurveTo(cpx, prev.y, cpx, points[i].y, points[i].x, points[i].y)
    }
  }

  ctx.lineTo(W, H)
  ctx.closePath()
  ctx.fillStyle = gradient
  ctx.fill()

  // 绘制顶部曲线描边
  ctx.beginPath()
  for (let i = 0; i < points.length; i++) {
    if (i === 0) {
      ctx.moveTo(points[i].x, points[i].y)
    } else {
      const prev = points[i - 1]
      const cpx = (prev.x + points[i].x) / 2
      ctx.bezierCurveTo(cpx, prev.y, cpx, points[i].y, points[i].x, points[i].y)
    }
  }
  ctx.strokeStyle = '#FF7A5C'
  ctx.lineWidth = 2
  ctx.stroke()

  // 发光效果
  ctx.shadowColor = 'rgba(255, 122, 92, 0.4)'
  ctx.shadowBlur = 8
  ctx.stroke()
  ctx.shadowBlur = 0

  animFrameId = requestAnimationFrame(drawWaveform)
}

async function onRecordStop() {
  const blob = new Blob(audioChunks, { type: 'audio/webm' })
  if (blob.size < 1000) {
    ElMessage.warning('录音太短，请重试')
    state.value = 'idle'
    return
  }

  state.value = 'testing'

  try {
    const formData = new FormData()
    formData.append('audio', blob, 'test.webm')

    const resp = await axios.post('/api/v1/voiceprint/test', formData)
    testResult.value = resp.data
    state.value = 'result'
  } catch (e) {
    ElMessage.error('测试请求失败: ' + (e.response?.data?.detail || e.message))
    state.value = 'idle'
  }
}

function resetTest() {
  state.value = 'idle'
  testResult.value = { steps: [], success: false, speaker: null, confidence: 0, transcript: '' }
}

function onClose() {
  if (state.value === 'recording') {
    stopRecord()
  }
  resetTest()
}

onUnmounted(() => {
  if (state.value === 'recording') {
    stopRecord()
  }
})
</script>

<style scoped>
.voice-test {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  padding: 10px 0;
}

.test-hint {
  text-align: center;
  color: #666;
}
.test-hint p { margin: 4px 0; }
.hint-sub { font-size: 13px; color: #999; }

.record-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.mic-button {
  position: relative;
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #FF7A5C, #FFB347);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  color: white;
  box-shadow: 0 4px 15px rgba(255, 122, 92, 0.4);
}
.mic-button:hover { transform: scale(1.05); }
.mic-button.recording {
  animation: pulse 1.2s infinite;
  background: linear-gradient(135deg, #ff4444, #ff6b6b);
  box-shadow: 0 4px 20px rgba(255, 68, 68, 0.5);
}

@keyframes pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.08); }
}

.timer {
  font-size: 18px;
  font-weight: 600;
  color: #FF7A5C;
}

.waveform-canvas {
  width: 100%;
  max-width: 400px;
  height: 80px;
  border-radius: var(--radius-md);
}

.mic-pulse {
  position: absolute;
  inset: -8px;
  border-radius: 50%;
  border: 2px solid rgba(255, 122, 92, 0.4);
  animation: mic-pulse-ring 1.5s ease-out infinite;
}

@keyframes mic-pulse-ring {
  0% { transform: scale(1); opacity: 0.6; }
  100% { transform: scale(1.3); opacity: 0; }
}

.testing-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.spinner {
  width: 40px;
  height: 40px;
  border: 4px solid #eee;
  border-top-color: #FF7A5C;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.result-area {
  width: 100%;
}

.step-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}
.step-icon { font-size: 18px; line-height: 1; flex-shrink: 0; }
.step-info { flex: 1; }
.step-name { font-weight: 600; font-size: 14px; color: #333; }
.step-detail { font-size: 13px; margin-top: 2px; }
.step-detail.status-ok { color: #52c41a; }
.step-detail.status-warn { color: #faad14; }
.step-detail.status-error { color: #ff4d4f; }

.final-result {
  margin-top: 16px;
  text-align: center;
  padding: 16px;
  background: #fafafa;
  border-radius: 12px;
}
.result-badge {
  display: inline-block;
  padding: 4px 16px;
  border-radius: 20px;
  font-weight: 600;
  font-size: 15px;
}
.result-badge.success { background: #f6ffed; color: #52c41a; border: 1px solid #b7eb8f; }
.result-badge.fail { background: #fff2f0; color: #ff4d4f; border: 1px solid #ffccc7; }
.result-speaker { font-size: 22px; font-weight: 700; margin-top: 8px; color: #333; }
.result-confidence { font-size: 14px; color: #888; margin-top: 4px; }
.result-transcript { font-size: 14px; color: #666; margin-top: 8px; font-style: italic; }
.result-hint { font-size: 13px; color: #999; margin-top: 8px; }
</style>

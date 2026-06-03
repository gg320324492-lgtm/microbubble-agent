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
        </div>
        <div class="timer" v-if="state === 'recording'">{{ recordingTime }}s / 5s</div>

        <!-- 实时音量条 -->
        <div class="level-bars" v-if="state === 'recording'">
          <div
            v-for="i in 20"
            :key="i"
            class="level-bar"
            :style="{ height: getBarHeight(i) + '%' }"
            :class="{ active: getBarHeight(i) > 30 }"
          ></div>
        </div>
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
let currentLevel = ref(0)

function getBarHeight(i) {
  const base = currentLevel.value * 100
  const offset = (i % 4) * 0.1
  return Math.max(5, Math.min(100, base + offset * 100))
}

async function toggleRecord() {
  if (state.value === 'recording') {
    stopRecord()
    return
  }
  await startRecord()
}

async function startRecord() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: { sampleRate: { ideal: 16000 }, channelCount: 1, echoCancellation: true, noiseSuppression: true }
    })

    // 音量检测
    audioContext = new AudioContext({ sampleRate: 16000 })
    const source = audioContext.createMediaStreamSource(mediaStream)
    const analyser = audioContext.createAnalyser()
    analyser.fftSize = 256
    source.connect(analyser)

    const dataArray = new Uint8Array(analyser.frequencyBinCount)
    const updateLevel = () => {
      if (state.value !== 'recording') return
      analyser.getByteFrequencyData(dataArray)
      const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length / 255
      currentLevel.value = avg
      requestAnimationFrame(updateLevel)
    }
    updateLevel()

    // 录音（用 MediaRecorder 收集 webm）
    mediaRecorder = new MediaRecorder(mediaStream, { mimeType: 'audio/webm' })
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
    ElMessage.error('麦克风权限被拒绝')
  }
}

function stopRecord() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
  }
  clearInterval(timerInterval)
  if (mediaStream) {
    mediaStream.getTracks().forEach(t => t.stop())
  }
  if (audioContext) {
    audioContext.close()
  }
  currentLevel.value = 0
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

.level-bars {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 50px;
}
.level-bar {
  width: 8px;
  min-height: 4px;
  background: #ddd;
  border-radius: 4px;
  transition: height 0.1s;
}
.level-bar.active {
  background: linear-gradient(180deg, #FF7A5C, #FFB347);
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

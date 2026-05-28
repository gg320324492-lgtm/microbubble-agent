<template>
  <div class="call-screen" :class="{ active: isCallActive }">
    <!-- 粒子背景 -->
    <div class="particles">
      <span v-for="i in 20" :key="i" class="particle" :style="particleStyle(i)" />
    </div>

    <!-- 顶部信息 -->
    <div class="top-bar">
      <span class="meeting-label">{{ meetingTitle || '声纹会议' }}</span>
      <span v-if="isCallActive" class="timer">{{ formatDuration(duration) }}</span>
    </div>

    <!-- 中央发言者区域 -->
    <div class="center-stage">
      <!-- 涟漪波纹 -->
      <div v-if="currentSpeaker" class="ripple-container">
        <span class="ripple" :style="{ animationDelay: '0s' }" />
        <span class="ripple" :style="{ animationDelay: '0.5s' }" />
        <span class="ripple" :style="{ animationDelay: '1s' }" />
      </div>

      <!-- 频谱跳动 -->
      <div v-if="currentSpeaker" class="spectrum">
        <span v-for="i in 7" :key="i" class="bar" :style="barStyle(i)" />
      </div>

      <!-- 头像 -->
      <div class="avatar-ring" :class="{ speaking: !!currentSpeaker }">
        <el-avatar
          :size="100"
          :style="{ background: currentSpeaker ? speakerColor(currentSpeaker) : '#334155' }"
        >
          <span class="avatar-text">{{ currentSpeaker ? currentSpeaker[0] : '?' }}</span>
        </el-avatar>
      </div>

      <div class="speaker-name-lg">{{ currentSpeaker || '等待加入' }}</div>
      <div class="speaker-status-lg">
        <template v-if="isCallActive">
          <span v-if="currentSpeaker" class="speaking-badge">
            <span class="dot-pulse" /> 正在发言
            <span class="confidence">{{ lastConfidence }}%</span>
          </span>
          <span v-else class="listening-badge">聆听中<span class="dots">...</span></span>
        </template>
        <span v-else class="idle-badge">点击下方按钮开始</span>
      </div>
    </div>

    <!-- 转写面板 (右侧毛玻璃) -->
    <Transition name="panel">
      <div v-if="isCallActive && entries.length > 0" class="transcript-glass">
        <div class="transcript-inner" ref="transcriptPanel">
          <div v-for="(entry, i) in entries" :key="i" class="tx-line">
            <span class="tx-time">{{ formatTime(entry.start) }}</span>
            <span
              class="tx-speaker"
              :style="{ color: speakerColor(entry.speaker) }"
            >{{ entry.speaker }}</span>
            <span class="tx-text">{{ entry.text }}</span>
          </div>
        </div>
      </div>
    </Transition>

    <!-- 底部操控栏 (毛玻璃) -->
    <div class="bottom-bar">
      <div class="controls">
        <button
          class="ctrl-btn"
          :class="{ muted: isMuted }"
          :disabled="!isCallActive"
          @click="toggleMute"
        >
          <span class="icon">{{ isMuted ? '🔇' : '🎤' }}</span>
        </button>

        <button
          v-if="!isCallActive"
          class="ctrl-btn start-btn"
          @click="startCall"
        >
          <span class="icon">📞</span>
        </button>
        <button
          v-else
          class="ctrl-btn hangup-btn"
          @click="stopCall"
        >
          <span class="icon">📞</span>
        </button>

        <button
          class="ctrl-btn"
          :disabled="!isCallActive"
          @click="callAI"
        >
          <span class="icon">🤖</span>
        </button>
      </div>
      <div class="btn-labels">
        <span>静音</span>
        <span>{{ isCallActive ? '挂断' : '开始' }}</span>
        <span>呼叫小气</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted, nextTick, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useAudioCapture } from '@/composables/useAudioCapture'

const props = defineProps({
  meetingId: { type: [Number, String], required: true },
  meetingTitle: { type: String, default: '' },
})
const emit = defineEmits(['meeting-ended'])

const { start: startAudio, stop: stopAudio } = useAudioCapture()

const isCallActive = ref(false)
const isMuted = ref(false)
const duration = ref(0)
const currentSpeaker = ref('')
const lastConfidence = ref(0)
const entries = ref([])
const transcriptPanel = ref(null)

let ws = null, durationTimer = null, speakerTimeout = null

const speakerColors = {}
const palette = ['#FF7A5C', '#60A5FA', '#4ADE80', '#FBBF24', '#F87171', '#A78BFA', '#22D3EE', '#FB923C']
function speakerColor(n) {
  if (!speakerColors[n]) speakerColors[n] = palette[Object.keys(speakerColors).length % palette.length]
  return speakerColors[n]
}

function particleStyle(i) {
  const hue = 15 + (i * 17)
  return {
    left: `${(i * 47 + 13) % 100}%`,
    animationDuration: `${8 + (i % 5) * 3}s`,
    animationDelay: `${(i * 1.7) % 10}s`,
    background: `hsl(${hue}, 70%, 60%)`,
  }
}

function barStyle(i) {
  const d = 0.3 + Math.random() * 0.6
  const delay = i * 0.1
  return { animationDuration: `${d}s`, animationDelay: `${delay}s`, height: `${20 + Math.random() * 30}px` }
}

async function startCall() {
  try {
    const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const token = localStorage.getItem('access_token') || ''
    ws = new WebSocket(`${wsProtocol}//${location.host}/api/v1/ws/meeting/${props.meetingId}/live?token=${encodeURIComponent(token)}`)

    ws.onopen = async () => {
      if (durationTimer) clearInterval(durationTimer)
      isCallActive.value = true
      duration.value = 0
      durationTimer = setInterval(() => { duration.value++ }, 1000)
      await startAudio(onAudioChunk)
    }

    ws.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data)
        if (d.type === 'transcript') {
          entries.value.push({ speaker: d.speaker || '未知', speaker_confidence: d.speaker_confidence || 0, text: d.text || '', start: d.start || 0 })
          if (d.speaker_confidence > 0.4) {
            currentSpeaker.value = d.speaker
            lastConfidence.value = Math.round((d.speaker_confidence || 0) * 100)
            if (speakerTimeout) clearTimeout(speakerTimeout)
            speakerTimeout = setTimeout(() => { currentSpeaker.value = '' }, 3500)
          }
          nextTick(() => { if (transcriptPanel.value) transcriptPanel.value.scrollTop = transcriptPanel.value.scrollHeight })
        } else if (d.type === 'ai_reply') {
          entries.value.push({ speaker: d.speaker || '小气助手', speaker_confidence: 1, text: d.text || '', start: duration.value, is_ai: true })
          ElMessage.success('小气助手已回复')
        }
      } catch {}
    }
    ws.onerror = () => { ElMessage.error('连接失败'); stopCall() }
  } catch (e) { ElMessage.error('启动失败: ' + e.message) }
}

function onAudioChunk(float32Array) {
  if (!ws || ws.readyState !== WebSocket.OPEN || isMuted.value) return
  const int16 = new Int16Array(float32Array.length)
  for (let i = 0; i < float32Array.length; i++) int16[i] = Math.max(-32768, Math.min(32767, Math.round(float32Array[i] * 32767)))
  ws.send(int16.buffer)
}

function stopCall() {
  stopAudio()
  if (ws) { ws.close(); ws = null }
  if (durationTimer) { clearInterval(durationTimer); durationTimer = null }
  if (speakerTimeout) { clearTimeout(speakerTimeout); speakerTimeout = null }
  isCallActive.value = false
  currentSpeaker.value = ''
  emit('meeting-ended', entries.value)
}

function toggleMute() { isMuted.value = !isMuted.value }

async function callAI() {
  if (!ws) return
  ws.send(JSON.stringify({ type: 'ai_chat', text: '小气，总结一下目前的讨论' }))
}

function formatDuration(sec) {
  const m = Math.floor(sec / 60), s = sec % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
function formatTime(sec) {
  if (sec == null) return ''
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

onUnmounted(() => { if (isCallActive.value) stopCall() })
</script>

<style scoped>
.call-screen {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  background: linear-gradient(160deg, #0f1724 0%, #1a1a2e 40%, #16213e 100%);
  border-radius: 16px;
  overflow: hidden;
  user-select: none;
}

/* === 粒子背景 === */
.particles { position: absolute; inset: 0; pointer-events: none; overflow: hidden; }
.particle {
  position: absolute; bottom: -6px; width: 4px; height: 4px; border-radius: 50%;
  opacity: 0; animation: float-up linear infinite;
}
@keyframes float-up {
  0% { transform: translateY(0) scale(1); opacity: 0; }
  10% { opacity: 0.7; }
  90% { opacity: 0.1; }
  100% { transform: translateY(-100vh) scale(0); opacity: 0; }
}

/* === 顶部 === */
.top-bar {
  position: absolute; top: 0; left: 0; right: 0; z-index: 10;
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 24px;
  background: linear-gradient(to bottom, rgba(0,0,0,0.3), transparent);
}
.meeting-label { color: rgba(255,255,255,0.6); font-size: 13px; }
.timer { color: #FF7A5C; font-size: 18px; font-family: 'Courier New', monospace; font-weight: bold; }

/* === 中央区域 === */
.center-stage {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 16px; z-index: 5; position: relative;
}

/* 涟漪 */
.ripple-container { position: absolute; width: 180px; height: 180px; }
.ripple {
  position: absolute; inset: 0; border-radius: 50%;
  border: 2px solid rgba(255,122,92,0.4);
  animation: ripple-out 1.5s ease-out infinite;
}
@keyframes ripple-out {
  0% { transform: scale(0.6); opacity: 0.8; }
  100% { transform: scale(1.3); opacity: 0; }
}

/* 频谱 */
.spectrum {
  position: absolute; bottom: -50px; display: flex; gap: 4px; align-items: flex-end; height: 40px;
}
.bar {
  width: 4px; border-radius: 2px; background: #FF7A5C;
  animation: bar-jump ease-in-out infinite alternate;
}
@keyframes bar-jump {
  0% { transform: scaleY(0.3); opacity: 0.4; }
  100% { transform: scaleY(1); opacity: 1; }
}

/* 头像环 */
.avatar-ring {
  padding: 6px; border-radius: 50%;
  border: 3px solid transparent; transition: border-color 0.4s;
}
.avatar-ring.speaking {
  border-color: #FF7A5C;
  box-shadow: 0 0 30px rgba(255,122,92,0.4), 0 0 60px rgba(255,122,92,0.15);
}

.avatar-text { font-size: 40px; font-weight: bold; color: #fff; }

.speaker-name-lg { font-size: 28px; font-weight: 700; color: #fff; letter-spacing: 2px; }
.speaker-status-lg { font-size: 14px; }

.speaking-badge { display: flex; align-items: center; gap: 6px; color: #4ADE80; }
.dot-pulse { width: 8px; height: 8px; border-radius: 50%; background: #4ADE80; animation: pulse-dot 0.8s infinite; }
@keyframes pulse-dot {
  0%, 100% { box-shadow: 0 0 0 0 rgba(74,222,128,0.6); }
  50% { box-shadow: 0 0 0 10px rgba(74,222,128,0); }
}
.confidence { color: rgba(255,255,255,0.4); font-size: 12px; margin-left: 4px; }

.listening-badge { color: rgba(255,255,255,0.4); }
.listening-badge .dots::after { content: ''; animation: dots 1.5s steps(3) infinite; }
@keyframes dots { 0% { content: ''; } 33% { content: '.'; } 66% { content: '..'; } 100% { content: '...'; } }
.idle-badge { color: rgba(255,255,255,0.3); }

/* === 转写面板 (毛玻璃) === */
.transcript-glass {
  position: absolute; right: 16px; top: 60px; bottom: 100px; width: 320px; z-index: 8;
  background: rgba(15,23,36,0.75); backdrop-filter: blur(16px);
  border-radius: 16px; border: 1px solid rgba(255,255,255,0.08);
  overflow: hidden;
}
.transcript-inner { padding: 12px 16px; height: 100%; overflow-y: auto; }
.tx-line {
  padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05);
  font-size: 13px; line-height: 1.5; color: rgba(255,255,255,0.8);
}
.tx-time { color: rgba(255,255,255,0.3); font-family: monospace; font-size: 11px; margin-right: 8px; }
.tx-speaker { font-weight: 600; margin-right: 6px; }
.tx-text { word-break: break-word; }

.panel-enter-active, .panel-leave-active { transition: all 0.4s ease; }
.panel-enter-from, .panel-leave-to { opacity: 0; transform: translateX(20px); }

/* === 底部栏 === */
.bottom-bar {
  position: absolute; bottom: 0; left: 0; right: 0; z-index: 10;
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 20px 0 24px;
  background: linear-gradient(to top, rgba(0,0,0,0.5), transparent);
}
.controls { display: flex; gap: 32px; align-items: center; }
.ctrl-btn {
  width: 56px; height: 56px; border-radius: 50%; border: none;
  background: rgba(255,255,255,0.1); backdrop-filter: blur(8px);
  font-size: 22px; cursor: pointer; transition: all 0.2s;
  display: flex; align-items: center; justify-content: center;
}
.ctrl-btn:hover { background: rgba(255,255,255,0.2); transform: scale(1.05); }
.ctrl-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.ctrl-btn.muted { background: rgba(239,68,68,0.3); }
.start-btn { background: rgba(74,222,128,0.3); width: 64px; height: 64px; font-size: 26px; }
.start-btn:hover { background: rgba(74,222,128,0.5); }
.hangup-btn { background: rgba(239,68,68,0.4); width: 64px; height: 64px; font-size: 26px; }
.hangup-btn:hover { background: rgba(239,68,68,0.7); }
.icon { line-height: 1; }

.btn-labels { display: flex; gap: 72px; font-size: 11px; color: rgba(255,255,255,0.3); }
@media (max-width: 768px) {
  .transcript-glass { right: 4px; width: calc(100% - 8px); top: 50%; }
  .speaker-name-lg { font-size: 22px; }
}
</style>

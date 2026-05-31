<template>
  <div class="call-screen" :class="{ active: isCallActive }">
    <!-- 顶部状态栏 -->
    <div class="top-bar">
      <span class="meeting-label">{{ meetingTitle || '声纹会议' }}</span>
      <div v-if="isCallActive" class="listening-status">
        <span class="pulse-dot" :class="listeningState" />
        <span>{{ listeningText }}</span>
      </div>
      <span v-if="isCallActive" class="timer">{{ formatDuration(duration) }}</span>
    </div>

    <!-- 实时转写面板（居中主区域） -->
    <div class="transcript-main" ref="transcriptPanel">
      <div v-if="!isCallActive" class="standby">
        <div class="standby-icon">🎙</div>
        <h3>声纹创建会议</h3>
        <p>点击下方按钮开始，小气将实时转录并识别发言人</p>
      </div>
      <div v-else-if="entries.length === 0" class="listening-hint">
        <div class="wave-animation">
          <span v-for="i in 5" :key="i" class="wave-bar" :style="{ animationDelay: `${i * 0.1}s` }" />
        </div>
        <p>小气正在聆听...</p>
      </div>
      <div v-for="(entry, i) in entries" :key="i" class="tx-entry">
        <span class="tx-speaker" :style="{ color: speakerColor(entry.speaker) }">{{ entry.speaker }}</span>
        <span class="tx-time">{{ formatTime(entry.start) }}</span>
        <span class="tx-text">{{ entry.text }}</span>
      </div>
    </div>

    <!-- 当前发言人 -->
    <div v-if="currentSpeaker && isCallActive" class="speaker-bar">
      <el-avatar :size="32" :style="{ background: speakerColor(currentSpeaker) }">{{ currentSpeaker[0] }}</el-avatar>
      <span class="speaker-name">{{ currentSpeaker }}</span>
      <span class="speaker-conf">{{ lastConfidence }}%</span>
    </div>

    <!-- 底部操作 -->
    <div class="bottom-bar">
      <button class="ctrl-btn" :class="{ muted: isMuted }" :disabled="!isCallActive" @click="toggleMute">
        <span>{{ isMuted ? '🔇' : '🎤' }}</span>
        <small>{{ isMuted ? '已静音' : '静音' }}</small>
      </button>
      <button v-if="!isCallActive" class="ctrl-btn start-btn" @click="startCall">
        <span>🎙</span><small>开始会议</small>
      </button>
      <button v-else class="ctrl-btn hangup-btn" @click="stopCall">
        <span>📞</span><small>结束会议</small>
      </button>
      <button class="ctrl-btn" :disabled="!isCallActive" @click="callAI">
        <span>🤖</span><small>呼叫小气</small>
      </button>
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
const listeningState = ref('listening')
const transcriptPanel = ref(null)

let ws = null, durationTimer = null, speakerTimeout = null

const speakerColors = {}
const palette = ['#FF7A5C', '#60A5FA', '#4ADE80', '#FBBF24', '#F87171', '#A78BFA', '#22D3EE', '#FB923C']
function speakerColor(n) {
  if (!speakerColors[n]) speakerColors[n] = palette[Object.keys(speakerColors).length % palette.length]
  return speakerColors[n]
}

const listeningText = computed(() => {
  if (entries.value.length === 0) return '小气正在聆听...'
  return `已转写 ${entries.value.length} 条`
})

async function startCall() {
  try {
    const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const token = localStorage.getItem('access_token') || ''
    ws = new WebSocket(`${wsProtocol}//${location.host}/api/v1/ws/meeting/${props.meetingId}/live?token=${encodeURIComponent(token)}`)

    ws.onopen = async () => {
      if (durationTimer) clearInterval(durationTimer)
      isCallActive.value = true; duration.value = 0; entries.value = []
      durationTimer = setInterval(() => { duration.value++ }, 1000)
      await startAudio(onAudioChunk)
    }

    ws.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data)
        if (d.type === 'transcript') {
          entries.value.push({ speaker: d.speaker || '未知', speaker_confidence: d.speaker_confidence || 0, text: d.text || '', start: d.start || 0 })
          if (d.speaker_confidence > 0.4) {
            currentSpeaker.value = d.speaker; lastConfidence.value = Math.round((d.speaker_confidence || 0) * 100)
            if (speakerTimeout) clearTimeout(speakerTimeout)
            speakerTimeout = setTimeout(() => { currentSpeaker.value = '' }, 3500)
          }
          nextTick(() => { if (transcriptPanel.value) transcriptPanel.value.scrollTop = transcriptPanel.value.scrollHeight })
        } else if (d.type === 'ai_reply') {
          entries.value.push({ speaker: '小气助手', speaker_confidence: 1, text: d.text || '', start: duration.value, is_ai: true })
        } else if (d.type === 'meeting_ended') {
          ElMessage.success('会议已自动分析完成')
          emit('meeting-ended', { meetingId: props.meetingId, entries: entries.value, analysis: d.analysis })
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
  isCallActive.value = false; currentSpeaker.value = ''
}

function toggleMute() { isMuted.value = !isMuted.value }

async function callAI() {
  if (!ws) return
  ws.send(JSON.stringify({ type: 'ai_chat', text: '小气，总结一下目前的讨论' }))
}

function formatDuration(sec) { const m = Math.floor(sec/60), s = sec%60; return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}` }
function formatTime(sec) { if (sec == null) return ''; const m = Math.floor(sec/60), s = Math.floor(sec%60); return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}` }

onUnmounted(() => { if (isCallActive.value) stopCall() })
</script>

<style scoped>
.call-screen {
  display: flex; flex-direction: column; height: 100%;
  background: linear-gradient(160deg, #0f1724, #1a1a2e, #16213e);
  border-radius: 16px; overflow: hidden;
}

/* 顶栏 */
.top-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 20px; background: rgba(0,0,0,0.3); flex-shrink: 0;
}
.meeting-label { color: rgba(255,255,255,0.6); font-size: 13px; }
.listening-status { display: flex; align-items: center; gap: 8px; color: #4ADE80; font-size: 13px; }
.pulse-dot { width: 8px; height: 8px; border-radius: 50%; background: #4ADE80; animation: pulse-dot 0.8s infinite; }
@keyframes pulse-dot { 0%,100% { box-shadow: 0 0 0 0 rgba(74,222,128,0.6); } 50% { box-shadow: 0 0 0 10px rgba(74,222,128,0); } }
.timer { color: #FF7A5C; font-family: monospace; font-size: 18px; font-weight: bold; }

/* 转写面板 */
.transcript-main {
  flex: 1; overflow-y: auto; padding: 16px 20px;
  display: flex; flex-direction: column; gap: 4px;
}
.standby, .listening-hint {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  color: rgba(255,255,255,0.4); gap: 12px;
}
.standby-icon { font-size: 48px; }
.standby h3 { color: #fff; margin: 0; font-size: 20px; }
.standby p { margin: 0; font-size: 14px; }

.wave-animation { display: flex; gap: 3px; align-items: flex-end; height: 30px; }
.wave-bar { width: 4px; border-radius: 2px; background: #4ADE80; animation: wave 0.6s ease-in-out infinite alternate; }
@keyframes wave { 0% { height: 6px; opacity: 0.4; } 100% { height: 24px; opacity: 1; } }

.tx-entry { padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.04); font-size: 13px; line-height: 1.5; }
.tx-speaker { font-weight: 600; margin-right: 8px; }
.tx-time { color: rgba(255,255,255,0.25); font-family: monospace; font-size: 11px; margin-right: 8px; }
.tx-text { color: rgba(255,255,255,0.8); word-break: break-word; }

/* 发言人条 */
.speaker-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 20px; background: rgba(255,255,255,0.05); flex-shrink: 0;
}
.speaker-name { color: #fff; font-weight: 600; font-size: 14px; }
.speaker-conf { color: rgba(255,255,255,0.3); font-size: 12px; margin-left: auto; }

/* 底部 */
.bottom-bar {
  display: flex; justify-content: center; gap: 32px;
  padding: 16px 0 20px; background: rgba(0,0,0,0.3); flex-shrink: 0;
}
.ctrl-btn {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  background: rgba(255,255,255,0.08); border: none; border-radius: 12px;
  padding: 10px 18px; color: #fff; cursor: pointer; transition: all 0.2s;
  font-size: 20px;
}
.ctrl-btn:hover { background: rgba(255,255,255,0.15); }
.ctrl-btn:disabled { opacity: 0.3; cursor: not-allowed; }
.ctrl-btn.muted { background: rgba(239,68,68,0.3); }
.ctrl-btn small { font-size: 10px; color: rgba(255,255,255,0.5); }
.start-btn { background: rgba(74,222,128,0.3); padding: 14px 24px; }
.start-btn:hover { background: rgba(74,222,128,0.5); }
.hangup-btn { background: rgba(239,68,68,0.4); padding: 14px 24px; }
.hangup-btn:hover { background: rgba(239,68,68,0.7); }
</style>

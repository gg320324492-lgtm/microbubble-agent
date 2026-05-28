<template>
  <div class="meeting-room">
    <!-- 顶部状态栏 -->
    <div class="room-header">
      <div class="room-status">
        <span :class="['status-dot', isCallActive ? 'live' : '']"></span>
        <span class="status-text">{{ isCallActive ? '通话中' : '未开始' }}</span>
        <span v-if="isCallActive" class="duration">{{ formatDuration(duration) }}</span>
      </div>
      <div class="room-actions">
        <el-button
          v-if="!isCallActive"
          type="primary"
          :icon="Phone"
          @click="startCall"
        >
          开始通话
        </el-button>
        <template v-else>
          <el-button :icon="Mute" :type="isMuted ? 'danger' : ''" circle @click="toggleMute" />
          <el-button type="danger" :icon="Phone" circle @click="stopCall" />
        </template>
      </div>
    </div>

    <!-- 当前发言者指示 -->
    <div v-if="isCallActive" class="speaking-indicator">
      <div v-if="currentSpeaker" class="current-speaker">
        <el-avatar :size="48" :style="{ background: speakerColor(currentSpeaker) }">
          {{ currentSpeaker[0] }}
        </el-avatar>
        <div class="speaker-info">
          <div class="speaker-name">{{ currentSpeaker }}</div>
          <div class="speaker-status">正在发言...</div>
        </div>
      </div>
      <div v-else class="current-speaker idle">
        <span class="idle-text">聆听中...</span>
      </div>
    </div>

    <!-- 实时转写面板 -->
    <div class="transcript-panel" ref="transcriptPanel">
      <div v-if="entries.length === 0 && isCallActive" class="empty-state">
        <el-icon :size="32"><Microphone /></el-icon>
        <p>等待发言...</p>
      </div>
      <div v-else-if="entries.length === 0" class="empty-state">
        <p>点击「开始通话」开启实时声纹转写</p>
      </div>

      <div v-for="(entry, i) in entries" :key="i" class="transcript-entry">
        <div class="entry-time">{{ formatTime(entry.start) }}</div>
        <div class="entry-speaker">
          <el-tag
            :color="speakerColor(entry.speaker)"
            effect="dark"
            size="small"
          >
            {{ entry.speaker }}
          </el-tag>
          <span v-if="entry.speaker_confidence > 0" class="conf">
            {{ Math.round(entry.speaker_confidence * 100) }}%
          </span>
        </div>
        <div class="entry-text">{{ entry.text }}</div>
      </div>
    </div>

    <!-- AI 对话栏 -->
    <div v-if="isCallActive" class="ai-bar">
      <el-input
        v-model="aiInput"
        placeholder="呼叫小气助手..."
        :prefix-icon="ChatDotSquare"
        @keyup.enter="callAI"
      >
        <template #append>
          <el-button :icon="Promotion" @click="callAI" :loading="aiLoading">
            呼叫
          </el-button>
        </template>
      </el-input>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Phone, Mute, Microphone, ChatDotSquare, Promotion } from '@element-plus/icons-vue'
import { useAudioCapture } from '@/composables/useAudioCapture'

const props = defineProps({
  meetingId: { type: [Number, String], required: true },
  meetingTitle: { type: String, default: '' },
})

const emit = defineEmits(['meeting-ended'])

const { start: startAudio, stop: stopAudio, isActive } = useAudioCapture()

const isCallActive = ref(false)
const isMuted = ref(false)
const duration = ref(0)
const currentSpeaker = ref('')
const entries = ref([])
const aiInput = ref('')
const aiLoading = ref(false)
const transcriptPanel = ref(null)

let ws = null
let durationTimer = null
let speakerTimeout = null

const speakerColors = {}
const colorPalette = [
  '#FF7A5C', '#409EFF', '#67C23A', '#E6A23C', '#F56C6C',
  '#909399', '#8B5CF6', '#06B6D4', '#F97316',
]

function speakerColor(name) {
  if (!speakerColors[name]) {
    speakerColors[name] = colorPalette[Object.keys(speakerColors).length % colorPalette.length]
  }
  return speakerColors[name]
}

async function startCall() {
  try {
    const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const token = localStorage.getItem('access_token') || ''
    const wsUrl = `${wsProtocol}//${location.host}/api/v1/ws/meeting/${props.meetingId}/live?token=${encodeURIComponent(token)}`
    ws = new WebSocket(wsUrl)

    ws.onopen = async () => {
      isCallActive.value = true
      duration.value = 0
      entries.value = []
      durationTimer = setInterval(() => duration.value++, 1000)

      await startAudio(onAudioChunk)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.type === 'transcript') {
          entries.value.push({
            speaker: data.speaker || '未知',
            speaker_confidence: data.speaker_confidence || 0,
            text: data.text || '',
            start: data.start || 0,
            end: data.end || 0,
          })

          if (data.speaker_confidence > 0.4) {
            currentSpeaker.value = data.speaker
            if (speakerTimeout) clearTimeout(speakerTimeout)
            speakerTimeout = setTimeout(() => {
              currentSpeaker.value = ''
            }, 3000)
          }

          nextTick(() => {
            if (transcriptPanel.value) {
              transcriptPanel.value.scrollTop = transcriptPanel.value.scrollHeight
            }
          })
        } else if (data.type === 'ai_reply') {
          entries.value.push({
            speaker: data.speaker || '小气助手',
            speaker_confidence: 1,
            text: data.text || '',
            start: duration.value,
            end: duration.value,
            is_ai: true,
          })
          ElMessage.success('小气助手已回复')
        } else if (data.type === 'meeting_ended') {
          ElMessage.success(`通话结束，共 ${data.entries || entries.value.length} 条记录`)
        }
      } catch (e) {
        // 忽略解析错误
      }
    }

    ws.onerror = () => {
      ElMessage.error('连接失败')
      stopCall()
    }
  } catch (e) {
    ElMessage.error('启动失败: ' + e.message)
  }
}

function onAudioChunk(float32Array) {
  if (!ws || ws.readyState !== WebSocket.OPEN || isMuted.value) return

  // Float32 → Int16 → ArrayBuffer
  const int16 = new Int16Array(float32Array.length)
  for (let i = 0; i < float32Array.length; i++) {
    int16[i] = Math.max(-32768, Math.min(32767, Math.round(float32Array[i] * 32767)))
  }
  ws.send(int16.buffer)
}

function stopCall() {
  stopAudio()
  if (ws) {
    ws.close()
    ws = null
  }
  if (durationTimer) {
    clearInterval(durationTimer)
    durationTimer = null
  }
  if (speakerTimeout) {
    clearTimeout(speakerTimeout)
    speakerTimeout = null
  }
  isCallActive.value = false
  currentSpeaker.value = ''
  emit('meeting-ended', entries.value)
}

function toggleMute() {
  isMuted.value = !isMuted.value
}

async function callAI() {
  const text = aiInput.value.trim()
  if (!text || !ws) return
  aiLoading.value = true
  try {
    ws.send(JSON.stringify({ type: 'ai_chat', text }))
    aiInput.value = ''
  } finally {
    aiLoading.value = false
  }
}

function formatDuration(sec) {
  const m = Math.floor(sec / 60)
  const s = sec % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function formatTime(sec) {
  if (sec == null) return ''
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

onUnmounted(() => {
  if (isCallActive.value) stopCall()
})
</script>

<style scoped>
.meeting-room {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.room-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--color-bg-page);
  border-bottom: 1px solid var(--color-border);
}
.room-status { display: flex; align-items: center; gap: 8px; }
.status-dot { width: 10px; height: 10px; border-radius: 50%; background: var(--color-info); }
.status-dot.live { background: var(--color-success); animation: blink 1.2s infinite; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
.status-text { font-size: var(--font-size-sm); color: var(--color-text-regular); }
.duration { font-family: monospace; font-weight: bold; color: var(--color-text-primary); }
.room-actions { display: flex; gap: 8px; }

.speaking-indicator {
  padding: 16px;
  border-bottom: 1px solid var(--color-border);
}
.current-speaker {
  display: flex;
  align-items: center;
  gap: 12px;
}
.current-speaker.idle { justify-content: center; }
.idle-text { color: var(--color-text-secondary); font-size: var(--font-size-sm); }
.speaker-name { font-weight: bold; color: var(--color-text-primary); }
.speaker-status { font-size: var(--font-size-xs); color: var(--color-success); }

.transcript-panel {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  max-height: 400px;
}
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 150px;
  color: var(--color-text-secondary);
}
.transcript-entry {
  display: flex;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border);
  align-items: flex-start;
}
.entry-time {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  font-family: monospace;
  white-space: nowrap;
  min-width: 50px;
}
.entry-speaker { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.conf { font-size: 10px; color: var(--color-text-secondary); }
.entry-text { font-size: var(--font-size-sm); color: var(--color-text-primary); line-height: 1.5; flex: 1; }

.ai-bar {
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-page);
}
</style>

<template>
  <div class="meeting-room">
    <!-- 顶部状态栏 -->
    <div class="top-bar">
      <div class="title">{{ meetingTitle }}</div>
      <div class="status">
        <span v-if="reconnecting" class="status-reconnecting">⟳ 重连中...</span>
        <span v-else-if="connected" class="status-connected">● 已连接</span>
        <span v-else class="status-disconnected">● 未连接</span>
      </div>
      <div class="duration">{{ formattedDuration }}</div>
    </div>

    <!-- 发言者条 -->
    <SpeakerStrip
      :speakers="participants"
      :active-speaker-id="activeSpeaker"
      :audio-levels="audioLevels"
    />

    <!-- 转录面板 -->
    <TranscriptPanel
      :entries="entries"
      :font-size="fontSize"
      @user-scroll="onUserScroll"
    />

    <!-- AI 助手浮窗 -->
    <AIFloatButton />

    <!-- 底部控制 -->
    <div class="control-bar">
      <el-button @click="toggleMute" :type="muted ? 'danger' : 'default'" circle>
        <el-icon><Microphone v-if="!muted" /><Mute v-else /></el-icon>
      </el-button>
      <el-button @click="confirmHangup" type="danger" circle>
        <el-icon><Phone /></el-icon>
      </el-button>
    </div>

    <!-- 二次确认弹窗 -->
    <el-dialog v-model="hangupConfirmVisible" title="确认挂断" width="400px">
      <p>挂断后系统将自动生成会议纪要。</p>
      <template #footer>
        <el-button @click="hangupConfirmVisible = false">取消</el-button>
        <el-button type="danger" @click="doHangup">确认挂断</el-button>
      </template>
    </el-dialog>

    <!-- 未识别发言人弹窗 -->
    <SpeakerUnidentifiedDialog
      v-model:visible="unidentified.visible"
      :candidates="unidentified.candidates"
      :transcript="unidentified.transcript"
      @claim="onSpeakerClaim"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Microphone, Mute, Phone } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useAudioCapture } from '@/composables/useAudioCapture'
import { useMeetingRoomWS } from '@/composables/useMeetingRoomWS'
import { useTranscript } from '@/composables/useTranscript'
import { useAutoScroll } from '@/composables/useAutoScroll'
import SpeakerStrip from './meeting-room/SpeakerStrip.vue'
import TranscriptPanel from './meeting-room/TranscriptPanel.vue'
import AIFloatButton from './meeting-room/AIFloatButton.vue'
import SpeakerUnidentifiedDialog from './meeting-room/SpeakerUnidentifiedDialog.vue'

const props = defineProps({
  meetingId: { type: Number, required: true },
  meetingTitle: { type: String, default: '会议' },
  participants: { type: Array, default: () => [] },
})
const emit = defineEmits(['call-ended'])

const userStore = useUserStore()
const muted = ref(false)
const hangupConfirmVisible = ref(false)
const startTime = ref(Date.now())
const formattedDuration = ref('00:00')
const activeSpeaker = ref(null)
const audioLevels = ref({})  // { memberId: 0-1 }
const unidentified = ref({
  visible: false,
  segmentId: null,
  speakerLabel: null,
  candidates: [],
  transcript: '',
})

let durationTimer = null

// 转录状态机
const { entries, addOriginal, applyPolished, markError, fontSize } = useTranscript()

// WS
const {
  connect: wsConnect,
  disconnect: wsDisconnect,
  sendAudio,
  sendHangup,
  sendSpeakerClaim,
  connected,
  reconnecting,
  onTranscript,
  onPolished,
  onError,
  onMessage,
  onSpeakerUnidentified,
  onSpeakerClaimAck,
} = useMeetingRoomWS()

// 音频采集
const audioCapture = useAudioCapture()

onMounted(async () => {
  // 启动时长计时
  durationTimer = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime.value) / 1000)
    const m = String(Math.floor(elapsed / 60)).padStart(2, '0')
    const s = String(elapsed % 60).padStart(2, '0')
    formattedDuration.value = `${m}:${s}`
  }, 1000)

  // 注册 WS 回调
  onTranscript.value = (msg) => {
    addOriginal({
      segment_id: msg.segment_id,
      speaker: msg.speaker,
      text: msg.text,
      ts: msg.ts,
    })
  }
  onPolished.value = (msg) => {
    applyPolished({
      segment_id: msg.segment_id,
      polished: msg.polished,
      key_points: msg.key_points,
    })
  }
  onError.value = (msg) => {
    if (msg.segment_id) {
      markError({ segment_id: msg.segment_id, error: msg.error || msg.message })
    } else {
      ElMessage.error(msg.message || '连接错误')
    }
  }

  // 通用消息处理（audio_level 等）
  onMessage.value = (msg) => {
    if (msg.type === 'audio_level') {
      // 找到当前 active speaker，更新其 level
      const activeId = activeSpeaker.value
      if (activeId !== null) {
        audioLevels.value = { ...audioLevels.value, [activeId]: msg.level }
      }
    }
  }

  // 弹窗选人
  onSpeakerUnidentified.value = (msg) => {
    unidentified.value = {
      visible: true,
      segmentId: msg.segment_id,
      speakerLabel: msg.speaker_label,
      candidates: msg.candidates,
      transcript: msg.transcript_text,
    }
  }

  // 用户在弹窗选了人
  onSpeakerClaimAck.value = (msg) => {
    // 后端确认写入后，关闭弹窗（已经在 onSpeakerClaim 中提前关闭，这里做兜底）
    unidentified.value.visible = false
  }

  // 连接 WS
  const token = localStorage.getItem('access_token')
  wsConnect(props.meetingId, token)

  // 启动音频采集
  try {
    await audioCapture.start((float32) => {
      if (muted.value) return
      // Float32 → Int16 转换（useAudioCapture 输出 Float32，WS 期望 Int16 PCM）
      const int16 = new Int16Array(float32.length)
      for (let i = 0; i < float32.length; i++) {
        int16[i] = Math.max(-32768, Math.min(32767, Math.round(float32[i] * 32767)))
      }
      sendAudio(int16.buffer)
    })
  } catch (e) {
    ElMessage.error('麦克风权限被拒绝')
  }
})

// 用户在弹窗选了人
function onSpeakerClaim(memberId) {
  sendSpeakerClaim(unidentified.value.segmentId, memberId, unidentified.value.speakerLabel)
  unidentified.value.visible = false
}

onUnmounted(() => {
  if (durationTimer) clearInterval(durationTimer)
  audioCapture.stop()
  wsDisconnect()
})

function toggleMute() {
  muted.value = !muted.value
}

function confirmHangup() {
  hangupConfirmVisible.value = true
}

function doHangup() {
  hangupConfirmVisible.value = false
  sendHangup()
  audioCapture.stop()
  emit('call-ended')
}

function onUserScroll() {
  // 由 TranscriptPanel 内部处理
}
</script>

<style scoped>
.meeting-room {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: white;
}
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: rgba(0, 0, 0, 0.3);
}
.title {
  font-size: 18px;
  font-weight: 500;
}
.status-connected { color: #67c23a; }
.status-reconnecting { color: #ff7a5c; }
.status-disconnected { color: #f56c6c; }
.duration {
  font-family: monospace;
  font-size: 16px;
}
.control-bar {
  display: flex;
  justify-content: center;
  gap: 24px;
  padding: 20px;
  background: rgba(0, 0, 0, 0.3);
}
</style>

<template>
  <div class="meeting-room">
    <!-- TopBar（保留） -->
    <div class="top-bar">
      <div class="title">{{ meetingTitle }}</div>
      <div class="status">
        <span v-if="reconnecting" class="status-reconnecting">⟳ 重连中...</span>
        <span v-else-if="connected" class="status-connected">● 已连接</span>
        <span v-else class="status-disconnected">● 未连接</span>
      </div>
      <div class="duration">{{ formattedDuration }}</div>
    </div>

    <!-- NetworkStatusBar（Wave 3b 新增） -->
    <NetworkStatusBar />

    <!-- 左侧面板：议程 + 统计 -->
    <div class="left-panel">
      <AgendaPanel
        :meeting-id="meetingId"
        :agenda="agendaItems"
        @update="onAgendaUpdate"
      />
      <SpeakerStatsLive :meeting-id="meetingId" />
    </div>

    <!-- 右侧面板：大头像 + 转录 + 时间轴 -->
    <div class="right-panel">
      <LiveSpeakerPanel
        :participants="effectiveParticipants"
        :active-speaker-id="activeSpeaker"
        :audio-levels="audioLevels"
      />
      <TranscriptPanel
        :entries="entries"
        :display-entries="displayEntries"
        :has-any-polished="hasAnyPolished"
        :view-mode="viewMode"
        @update:view-mode="(v) => viewMode = v"
        :font-size="fontSize"
        @user-scroll="onUserScroll"
      />
      <TimelineScrubber
        :current-ts="currentTs"
        :duration="meetingDuration"
        @jump="onJumpTs"
      />
    </div>

    <!-- 静音遮罩 -->
    <MuteOverlay :visible="muted" />

    <!-- AI 助手浮窗（保留） -->
    <AIFloatButton
      ref="aiFloatButtonRef"
      :on-send-a-i-command="sendAICommand"
      @air-reply="onAIReply"
    />

    <!-- 底部控制 -->
    <div class="control-bar">
      <el-button @click="toggleMute" :type="muted ? 'danger' : 'default'" circle>
        <el-icon><Microphone v-if="!muted" /><Mute v-else /></el-icon>
      </el-button>
      <el-button @click="confirmHangup" type="danger" circle>
        <el-icon><Phone /></el-icon>
      </el-button>
      <!-- 声纹状态指示灯 -->
      <div class="voiceprint-status" :title="voiceprintStatusText">
        <span class="vp-dot" :class="voiceprintStatusClass"></span>
        <span class="vp-label">{{ voiceprintStatusText }}</span>
      </div>
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
import { useNetworkStatus } from '@/composables/useNetworkStatus'
// Wave 3b: 6 个新组件
import LiveSpeakerPanel from './meeting-room/LiveSpeakerPanel.vue'
import AgendaPanel from './meeting-room/AgendaPanel.vue'
import SpeakerStatsLive from './meeting-room/SpeakerStatsLive.vue'
import TimelineScrubber from './meeting-room/TimelineScrubber.vue'
import MuteOverlay from './meeting-room/MuteOverlay.vue'
import NetworkStatusBar from './meeting-room/NetworkStatusBar.vue'
// 保留旧组件
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

// 参会人员列表（优先用 prop，否则从 API 自行拉取）
const localParticipants = ref([])
const effectiveParticipants = computed(() => {
  if (props.participants && props.participants.length > 0) return props.participants
  return localParticipants.value
})
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
const aiFloatButtonRef = ref(null)

// 2026-06-03 声纹状态指示
const voiceprintEnrolledCount = ref(-1)  // -1=未知, 0=无人录入, >0=已录入人数
const voiceprintStatusClass = computed(() => {
  if (voiceprintEnrolledCount.value === -1) return 'vp-unknown'
  if (voiceprintEnrolledCount.value === 0) return 'vp-none'
  return 'vp-ok'
})
const voiceprintStatusText = computed(() => {
  if (voiceprintEnrolledCount.value === -1) return '声纹检查中...'
  if (voiceprintEnrolledCount.value === 0) return '未录入声纹'
  return `${voiceprintEnrolledCount.value} 人已录入`
})

// Wave 3b: 议程 + 时间轴
const agendaItems = ref([])
const currentTs = ref(0)
const meetingDuration = ref(0)

let durationTimer = null

// 转录状态机
const {
  entries, viewMode, displayEntries, hasAnyPolished,
  addOriginal, applyPolished, applyBatchPolished, applyFullPolished,
  markError, fontSize,
} = useTranscript()

// WS（Wave 3b: 暴露 setPendingCountCallback + pendingCount）
const {
  connect: wsConnect,
  disconnect: wsDisconnect,
  sendAudio,
  sendHangup,
  sendSpeakerClaim,
  sendAICommand,
  setPendingCountCallback,
  pendingCount,
  connected,
  reconnecting,
  onTranscript,
  onPolished,        // 兼容旧
  onBatchPolished,   // 2026-06-02 L2
  onFullPolished,    // 2026-06-02 L3
  onError,
  onMessage,
  onSpeakerUnidentified,
  onSpeakerClaimAck,
  onAIReply,
  onTranscriptOthers,
  onAIReplyOthers,
  onTranscriptHistory,
  onTTSAudio,
} = useMeetingRoomWS()

// 网络状态（Wave 3b: wire pending count）
const network = useNetworkStatus()
watch(pendingCount, (n) => network.setPendingCount(n))

// 音频采集
const audioCapture = useAudioCapture()

onMounted(async () => {
  // 启动时长计时（2026-06-02 修复：meetingDuration 改用 MAX_MEETING_DURATION_SEC 兜底）
  durationTimer = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime.value) / 1000)
    currentTs.value = elapsed
    // meetingDuration 实际语义是 el-slider 的 max，给个合理上限（30 分钟 = 1800s）
    // 之前用 elapsed 自己导致 max=currentTs，slider 无法拖到未来时间点
    meetingDuration.value = Math.max(MAX_MEETING_DURATION_SEC, elapsed + 60)
    const m = String(Math.floor(elapsed / 60)).padStart(2, '0')
    const s = String(elapsed % 60).padStart(2, '0')
    formattedDuration.value = `${m}:${s}`
  }, 1000)

  // 拉取会议详情（含 agenda + participants）
  try {
    const resp = await fetch(`/api/v1/meetings/${props.meetingId}`, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
    })
    if (resp.ok) {
      const data = await resp.json()
      agendaItems.value = data.agenda || []
      // 提取参会人员（API 返回 {member_id, name, role, avatar}，映射为 {id, name, avatar}）
      if (data.participants && data.participants.length > 0) {
        localParticipants.value = data.participants.map(p => ({
          id: p.member_id,
          name: p.name,
          avatar: p.avatar || null,
        }))
      }
    }
  } catch (e) {
    console.warn('加载会议详情失败', e)
  }

  // 注册 WS 回调
  onTranscript.value = (msg) => {
    // Wave 3b 修复：speaker_confidence > 0.45 时切换 activeSpeaker
    if (msg.member_id && typeof msg.speaker_confidence === 'number' && msg.speaker_confidence > 0.45) {
      activeSpeaker.value = msg.member_id
    }
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
  // 2026-06-02 L2 聚批润色
  // 2026-06-03 优化：首批 L2 结果到达时自动切换到 polished 模式
  let autoSwitchedToPolished = false
  onBatchPolished.value = (msg) => {
    applyBatchPolished({
      segment_ids: msg.segment_ids || [],
      polished: msg.polished || [],
      key_points: msg.key_points || [],
    })
    // 首批 L2 结果到达时自动切换到 polished 模式
    if (!autoSwitchedToPolished && viewMode.value === 'raw') {
      autoSwitchedToPolished = true
      viewMode.value = 'polished'
      ElMessage.success('AI 润色版已就绪，已自动切换')
    }
  }
  // 2026-06-02 L3 全文精润色
  onFullPolished.value = (msg) => {
    applyFullPolished(msg.polished_segments || [])
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
      const activeId = activeSpeaker.value
      // 2026-06-02 修复：解耦 audioLevels 与 activeSpeaker
      // 之前：只在 activeSpeaker !== null 时更新 audioLevels，但 activeSpeaker 只在收到
      // transcript 且 speaker_confidence > 0.45 时才设置。如果后端没发出 transcript
      // （比如 VAD 没检测到语音段），activeSpeaker 永远 null，audioLevels 永远不更新，
      // 5 根声波条不跳动。修复：activeSpeaker 为 null 时也用 "self" 槽位更新，
      // 这样只要 WS 保持连接且后端推 audio_level 消息，前端就能看到波动
      const key = activeId !== null ? String(activeId) : 'self'
      audioLevels.value = { ...audioLevels.value, [key]: msg.level }
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
    unidentified.value.visible = false
  }

  // AI 回复（含 TTS）处理
  onAIReply.value = (msg) => {
    if (aiFloatButtonRef.value) {
      aiFloatButtonRef.value.addHistoryItem({
        action: msg.action,
        text: msg.text,
        original: msg.original,
      })
    }
    ElMessage.success(`小气: ${msg.text?.substring(0, 30) || ''}...`)
  }

  // TTS 二进制帧播放
  onTTSAudio.value = (arrayBuffer) => {
    const blob = new Blob([arrayBuffer], { type: 'audio/mpeg' })
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    audio.play().catch(() => {})
  }

  // 多设备同步
  onTranscriptOthers.value = (msg) => {
    addOriginal({
      segment_id: msg.data.segment_id,
      speaker: msg.data.speaker,
      text: msg.data.text,
      ts: msg.data.ts,
    })
  }
  onAIReplyOthers.value = (msg) => {
    if (aiFloatButtonRef.value) {
      aiFloatButtonRef.value.addHistoryItem({
        action: msg.data.action,
        text: msg.data.text,
        fromOther: true,
      })
    }
  }

  // 历史拉取
  onTranscriptHistory.value = (msg) => {
    for (const entry of msg.entries || []) {
      addOriginal({
        segment_id: entry.segment_id,
        speaker: entry.speaker,
        text: entry.text,
        ts: entry.ts,
      })
    }
  }

  // 连接 WS
  const token = localStorage.getItem('access_token')
  wsConnect(props.meetingId, token)

  // 2026-06-03 声纹状态检查：进入通话时检查已录入声纹成员数
  // 修复：后端返回 {"members": [...]}，不是数组
  try {
    const vpResp = await fetch('/api/v1/voiceprint/enrolled', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    if (vpResp.ok) {
      const vpData = await vpResp.json()
      const members = vpData.members || []
      const count = Array.isArray(members) ? members.length : 0
      voiceprintEnrolledCount.value = count
      if (count === 0) {
        ElMessage.warning({ message: '尚无声纹录入，发言人将显示为"未识别"。请在成员管理页面录入声纹。', duration: 8000 })
      } else {
        ElMessage.info({ message: `已录入 ${count} 位成员声纹`, duration: 3000 })
      }
    }
  } catch (e) {
    voiceprintEnrolledCount.value = 0
  }

  // 启动音频采集
  try {
    await audioCapture.start((float32) => {
      if (muted.value) return
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

function onSpeakerClaim(memberId) {
  sendSpeakerClaim(unidentified.value.segmentId, memberId, unidentified.value.speakerLabel)
  unidentified.value.visible = false
}

// Wave 3b: 议程更新
function onAgendaUpdate(updated) {
  agendaItems.value = updated
}

// Wave 3b: 时间轴跳转
// 2026-06-02 修复：之前 meetingDuration 永远等于 currentTs（elapsed），
// 导致 el-slider 的 max=currentTs，用户无法拖到未来时间点。
// 修复：meetingDuration 改为「预估总时长」（30 分钟兜底），currentTs 是 elapsed 实际秒数
// duration 实际语义是「slider 最大值」— 给个合理上限 30 分钟
const MAX_MEETING_DURATION_SEC = 30 * 60
const meetingStartTime = Date.now()  // 记录会议开始时间
function onJumpTs(ts) {
  // 跳转后 currentTs 不再是 elapsed 而是用户跳转到的 ts
  currentTs.value = ts
  const m = Math.floor(ts / 60)
  const s = String(ts % 60).padStart(2, '0')
  ElMessage.info(`跳转到 ${m}:${s}`)
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
  position: relative;
  overflow: hidden;
}
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  background: rgba(0, 0, 0, 0.3);
  flex-shrink: 0;
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

.left-panel {
  width: 100%;
  max-height: 35vh;
  overflow-y: auto;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  flex-shrink: 0;
}
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.control-bar {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 24px;
  padding: 20px;
  background: rgba(0, 0, 0, 0.3);
  flex-shrink: 0;
}
.voiceprint-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #aaa;
}
.vp-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.vp-ok { background: #67c23a; }
.vp-none { background: #f56c6c; }
.vp-unknown { background: #909399; animation: vp-blink 1.5s infinite; }
@keyframes vp-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}
.vp-label { white-space: nowrap; }

/* 桌面端：左右分栏 */
@media (min-width: 900px) {
  .meeting-room { display: grid; grid-template-columns: 320px 1fr; grid-template-rows: auto auto 1fr auto; }
  .top-bar { grid-column: 1 / -1; }
  .network-bar { grid-column: 1 / -1; }
  .left-panel {
    grid-column: 1;
    grid-row: 3;
    width: 320px;
    max-height: none;
    border-bottom: none;
    border-right: 1px solid rgba(255,255,255,0.1);
    overflow-y: auto;
  }
  .right-panel {
    grid-column: 2;
    grid-row: 3;
  }
  .control-bar { grid-column: 1 / -1; grid-row: 4; }
}

/* 移动端横屏：左右分栏 */
@media (max-width: 900px) and (orientation: landscape) {
  .meeting-room { display: grid; grid-template-columns: 30% 70%; grid-template-rows: auto auto 1fr auto; }
  .top-bar { grid-column: 1 / -1; }
  .network-bar { grid-column: 1 / -1; }
  .left-panel {
    grid-column: 1;
    grid-row: 3;
    width: 100%;
    max-height: none;
    border-bottom: none;
    border-right: 1px solid rgba(255,255,255,0.1);
  }
  .right-panel {
    grid-column: 2;
    grid-row: 3;
  }
  .control-bar { grid-column: 1 / -1; grid-row: 4; }
}
</style>

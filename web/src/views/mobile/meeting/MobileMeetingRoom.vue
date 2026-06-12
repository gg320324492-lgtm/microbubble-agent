<template>
  <div class="mobile-meeting-room">
    <PageHeader
      :title="pageTitle"
      show-back
      @back="handleBack"
    >
      <template #right>
        <button
          type="button"
          class="header-action"
          :aria-label="'帮助'"
          title="帮助"
          @click="showHelp = true"
        >❓</button>
      </template>
    </PageHeader>

    <!-- 录音状态横幅 -->
    <div v-if="recording" class="rec-banner">
      <span class="rec-dot" />
      <span class="rec-text">正在听会 · {{ formatDuration(duration) }}</span>
    </div>

    <!-- 转录实时滚动区 -->
    <main class="room-main" ref="mainRef">
      <div v-if="transcript.length === 0" class="empty-state">
        <div class="empty-illustration">
          <div class="empty-icon">🎙️</div>
        </div>
        <h3>准备就绪</h3>
        <p class="empty-hint">点击下方麦克风开始录音</p>
        <p class="empty-hint">实时转录将显示在此处</p>
      </div>

      <div v-else class="transcript-stream">
        <div
          v-for="(seg, i) in transcript"
          :key="seg.id || i"
          class="stream-segment"
        >
          <div class="seg-header">
            <span class="seg-speaker">{{ seg.speaker || '发言人' }}</span>
            <span class="seg-time">{{ formatTime(seg.timestamp) }}</span>
          </div>
          <div class="seg-text">{{ seg.text }}</div>
        </div>
      </div>
    </main>

    <!-- 底部控制条（sticky） -->
    <footer class="room-controls" :style="{ paddingBottom: 'var(--sab, 0px)' }">
      <div class="control-row">
        <button
          type="button"
          class="control-btn secondary"
          :disabled="!recording"
          aria-label="静音"
          title="静音"
          @click="toggleMute"
        >
          {{ muted ? '🔇' : '🎤' }}
        </button>

        <button
          type="button"
          class="control-btn record"
          :class="{ active: recording }"
          :aria-label="recording ? '停止' : '开始录音'"
          :title="recording ? '停止' : '开始录音'"
          @click="toggleRecording"
        >
          <span class="record-icon">{{ recording ? '⏹' : '●' }}</span>
        </button>

        <button
          type="button"
          class="control-btn secondary"
          aria-label="结束听会"
          title="结束"
          @click="handleHangup"
        >📞</button>
      </div>
      <div class="control-hint">
        <span v-if="recording">点击中间按钮停止录音</span>
        <span v-else>点击中间按钮开始录音</span>
      </div>
    </footer>

    <!-- 帮助 Sheet -->
    <Teleport to="body">
      <Transition name="help-sheet">
        <div v-if="showHelp" class="help-overlay" @click.self="showHelp = false">
          <div class="help-panel">
            <div class="help-header">
              <h3>使用说明</h3>
              <button type="button" @click="showHelp = false">✕</button>
            </div>
            <div class="help-content">
              <div class="help-item">
                <div class="help-num">1</div>
                <div class="help-text">
                  <strong>点击中间按钮开始录音</strong>
                  <p>系统会请求麦克风权限</p>
                </div>
              </div>
              <div class="help-item">
                <div class="help-num">2</div>
                <div class="help-text">
                  <strong>实时转录显示在中央</strong>
                  <p>说话内容会自动识别并显示</p>
                </div>
              </div>
              <div class="help-item">
                <div class="help-num">3</div>
                <div class="help-text">
                  <strong>点击红色按钮停止</strong>
                  <p>音频会自动上传并生成会议纪要</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup>
/**
 * MobileMeetingRoom.vue — 移动端听会房间
 *
 * PR #4:
 * - 顶部 sticky 录音状态横幅
 * - 中央转录实时滚动（简化版：保留显示 transcript，未集成 WS 实时流）
 * - 底部 sticky 控制条（静音 / 录音 / 挂断）
 * - 点击中央大按钮触发桌面 AudioRecorder（沿用录音能力）
 *
 * 简化：当前实现使用 desktop AudioRecorder 通过 DOM 引用调用，
 * 完整实时转录依赖 WS 联调，作为后续 PR #4+ 增强项。
 */

import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/mobile/PageHeader.vue'

const props = defineProps({
  meetingId: { type: Number, default: null },
})

const emit = defineEmits(['call-ended'])

const recording = ref(false)
const muted = ref(false)
const duration = ref(0)
const transcript = ref([])
const showHelp = ref(false)
const mainRef = ref(null)
let durationTimer = null

const pageTitle = computed(() => {
  if (props.meetingId) return `听会 #${props.meetingId}`
  return '开始听会'
})

function formatDuration(s) {
  const m = Math.floor(s / 60)
  const sec = s % 60
  return `${m.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`
}

function formatTime(t) {
  const d = new Date(t)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

function toggleRecording() {
  if (recording.value) {
    stopRecording()
  } else {
    startRecording()
  }
}

function startRecording() {
  recording.value = true
  duration.value = 0
  durationTimer = setInterval(() => {
    duration.value += 1
  }, 1000)
  // 占位转录（实际由 AudioRecorder + WS 提供）
  simulateTranscript()
  ElMessage.success('开始听会')
}

function stopRecording() {
  if (durationTimer) {
    clearInterval(durationTimer)
    durationTimer = null
  }
  recording.value = false
  ElMessage.info('录音已停止，后台处理中...')
}

function toggleMute() {
  muted.value = !muted.value
  ElMessage.info(muted.value ? '已静音' : '已取消静音')
}

function handleHangup() {
  if (recording.value) {
    ElMessageBox.confirm?.('确定结束听会？录音会保存').catch(() => {})
  }
  emit('call-ended', props.meetingId)
}

function handleBack() {
  if (recording.value) {
    ElMessage.warning('录音中，请先停止或挂断')
    return
  }
  emit('call-ended', props.meetingId)
}

// 占位转录模拟（5 秒一段，实际由后端 WS 推送）
let transcriptTimer = null
function simulateTranscript() {
  const samples = [
    { speaker: '杜同贺', text: '我们先讨论本周的研究进展' },
    { speaker: '王五', text: '上周的微纳米气泡实验数据出来了' },
    { speaker: '杜同贺', text: '嗯，zeta 电位的测量结果怎么样？' },
    { speaker: '王五', text: '在 -25mV 左右，比预期略低' },
    { speaker: '杜同贺', text: '好的，下一步调整一下浓度配比' },
  ]
  let idx = 0
  transcriptTimer = setInterval(() => {
    if (!recording.value) return
    if (idx < samples.length) {
      transcript.value.push({
        id: Date.now() + idx,
        speaker: samples[idx].speaker,
        text: samples[idx].text,
        timestamp: new Date().toISOString(),
      })
      idx += 1
      // 自动滚动到底部
      nextTick(() => {
        if (mainRef.value) {
          mainRef.value.scrollTop = mainRef.value.scrollHeight
        }
      })
    } else {
      clearInterval(transcriptTimer)
      transcriptTimer = null
    }
  }, 5000)
}

onMounted(() => {
  // 可在此处连接后端 WS 获取实时转录
})

onBeforeUnmount(() => {
  if (durationTimer) clearInterval(durationTimer)
  if (transcriptTimer) clearInterval(transcriptTimer)
})
</script>

<style scoped>
.mobile-meeting-room {
  min-height: 100vh;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
}

.rec-banner {
  background: var(--color-danger, #F56C6C);
  color: white;
  padding: 8px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: var(--font-weight-medium, 500);
}
.rec-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: white;
  animation: pulse 1s infinite;
}
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }

/* 主区 */
.room-main {
  flex: 1;
  overflow-y: auto;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
  -webkit-overflow-scrolling: touch;
}

.empty-state {
  text-align: center;
  padding: 80px 20px;
}
.empty-illustration {
  margin-bottom: 16px;
}
.empty-icon {
  font-size: 64px;
}
.empty-state h3 {
  font-size: 18px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  margin: 0 0 8px;
}
.empty-hint {
  font-size: 13px;
  color: var(--color-text-secondary);
  margin: 4px 0;
}

/* 转录流 */
.transcript-stream {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.stream-segment {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 12px;
  animation: slide-in 0.3s ease;
}
@keyframes slide-in {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.seg-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.seg-speaker {
  font-size: 12px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-primary);
}
.seg-time {
  font-size: 11px;
  color: var(--color-text-secondary);
}
.seg-text {
  font-size: 14px;
  color: var(--color-text-primary);
  line-height: 1.6;
}

/* 控制条 */
.room-controls {
  position: sticky;
  bottom: 0;
  background: var(--color-bg-card);
  border-top: 1px solid var(--color-border);
  padding: 16px var(--mobile-padding-x, 16px) 12px;
  backdrop-filter: blur(12px);
}
[data-theme="dark"] .room-controls {
  background: rgba(42, 45, 53, 0.95);
}
.control-row {
  display: flex;
  align-items: center;
  justify-content: space-around;
  gap: 12px;
  margin-bottom: 8px;
}
.control-btn {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: none;
  background: var(--color-bg-page);
  font-size: 22px;
  color: var(--color-text-regular);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  -webkit-tap-highlight-color: transparent;
}
.control-btn:active { transform: scale(0.95); }
.control-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.control-btn.record {
  width: 72px;
  height: 72px;
  background: var(--color-text-regular);
  color: white;
  font-size: 28px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
}
.control-btn.record.active {
  background: var(--color-danger, #F56C6C);
  animation: record-pulse 2s infinite;
}
.record-icon {
  font-weight: bold;
}
@keyframes record-pulse {
  0%, 100% { box-shadow: 0 4px 16px rgba(245, 108, 108, 0.4); }
  50% { box-shadow: 0 4px 24px rgba(245, 108, 108, 0.7); }
}
.control-hint {
  text-align: center;
  font-size: 11px;
  color: var(--color-text-secondary);
}

/* Header action */
.header-action {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.header-action:active { background: var(--color-primary-bg); }

/* 帮助 Sheet */
.help-overlay {
  position: fixed;
  inset: 0;
  z-index: 4000;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
}
.help-panel {
  width: 100%;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 16px 16px calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px));
}
.help-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border);
}
.help-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: var(--font-weight-semibold, 600);
}
.help-header button {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
}
.help-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.help-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
}
.help-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-primary);
  color: white;
  font-size: 13px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.help-text strong {
  font-size: 14px;
  color: var(--color-text-primary);
  display: block;
  margin-bottom: 4px;
}
.help-text p {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin: 0;
}

.help-sheet-enter-active, .help-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.help-sheet-enter-active .help-panel, .help-sheet-leave-active .help-panel {
  transition: transform 0.3s ease;
}
.help-sheet-enter-from, .help-sheet-leave-to { opacity: 0; }
.help-sheet-enter-from .help-panel, .help-sheet-leave-to .help-panel {
  transform: translateY(100%);
}
</style>
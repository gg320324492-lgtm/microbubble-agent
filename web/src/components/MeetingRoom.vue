<template>
  <div class="meeting-room">
    <!-- 顶部栏 -->
    <header class="room-header glass glass-lg">
      <span class="room-title">{{ pageTitle }}</span>
    </header>

    <!-- 主内容 -->
    <main class="room-main">
      <AudioRecorder
        ref="recorderRef"
        :prepare-recording="prepareRecording"
        @recording-start-failed="onRecordingStartFailed"
        @recording-stop="onRecordingStop"
        @audio-ready="onAudioReady"
      />
    </main>

    <!-- 处理进度弹窗 -->
    <ProcessingDialog
      v-if="showProgress"
      :meeting-id="meetingId"
      @close="onProgressClose"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import AudioRecorder from '@/components/AudioRecorder.vue'
import ProcessingDialog from '@/components/ProcessingDialog.vue'
import { useRecordingState } from '@/composables/useRecordingState'
import { useMeetingRecordingStart } from '@/composables/useMeetingRecordingStart'

const props = defineProps({
  meetingId: { type: Number, default: null },
  meetingTitle: { type: String, default: '' },
})

const emit = defineEmits(['call-ended'])

const { startRecording, stopRecording } = useRecordingState()
const { prepareRecording, onRecordingStartFailed: onRecordingStartFailedHelper } = useMeetingRecordingStart(meetingId)

const recorderRef = ref(null)
const meetingId = ref(props.meetingId)
const showProgress = ref(false)

const pageTitle = computed(() => {
  if (meetingId.value) return `正在听会（ID ${meetingId.value}）`
  return '开始听会'
})

function onRecordingStartFailed() {
  // MediaRecorder 启动失败：清掉刚创建的会议 ID 和右下角胶囊，避免假录音态。
  onRecordingStartFailedHelper()
}

function onRecordingStop() {
  // AudioRecorder 内部处理
}

async function onAudioReady(blob) {
  if (!meetingId.value) return

  // 立即显示进度弹窗（不阻塞 UI）
  showProgress.value = true

  // 使用 setTimeout 延迟上传，不阻塞 UI
  setTimeout(async () => {
    try {
      // 上传音频
      const fd = new FormData()
      fd.append('file', blob, `recording_${meetingId.value}.webm`)
      await axios.post(`/api/v1/meetings/${meetingId.value}/upload-audio`, fd)

      // 停止录音，触发后处理
      await axios.post(`/api/v1/meetings/${meetingId.value}/stop-recording`)
    } catch (err) {
      ElMessage.error('上传失败: ' + (err.response?.data?.detail || err.message))
    }
  }, 0)
}

function onProgressClose() {
  showProgress.value = false
  stopRecording()
  emit('call-ended', meetingId.value)
}
</script>

<style scoped>
/* v77: dark mode 背景跟随主题 (3 处硬编码浅色→token) */
.meeting-room {
  display: flex; flex-direction: column;
  height: 100%; min-height: 400px;
  background: var(--color-bg-card);
  border-radius: var(--radius-lg, 12px); overflow: hidden;
}
.room-header {
  display: flex; align-items: center; justify-content: center;
  padding: 12px 20px; border-bottom: 1px solid var(--color-border-base);
}
.room-title { font-size: 15px; font-weight: 600; color: var(--color-text-primary); }
.room-main { flex: 1; display: flex; align-items: center; justify-content: center; background: var(--color-bg-page); }
</style>

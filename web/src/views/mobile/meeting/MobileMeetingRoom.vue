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
          aria-label="帮助"
          title="帮助"
          @click="showHelp = true"
        >❓</button>
      </template>
    </PageHeader>

    <!-- 录音器（复用桌面端 AudioRecorder，模式：录完一次性上传 → 后台离线分析） -->
    <main class="room-main">
      <AudioRecorder
        ref="recorderRef"
        @recording-start="onRecordingStart"
        @recording-stop="onRecordingStop"
        @audio-ready="onAudioReady"
      />
    </main>

    <!-- 后台处理进度（移动端底部 sheet，2026-06-25 从 ProcessingDialog 切换到 ProcessingSheet） -->
    <ProcessingSheet
      v-if="showProgress"
      :meeting-id="meetingId"
      @close="onProgressClose"
    />

    <!-- 帮助 Sheet -->
    <Teleport to="body">
      <Transition name="help-sheet">
        <div v-if="showHelp" class="help-overlay" @click.self="showHelp = false">
          <div class="help-panel">
            <div class="help-header">
              <h3>使用说明</h3>
              <button type="button" aria-label="关闭" @click="showHelp = false">✕</button>
            </div>
            <div class="help-content">
              <div class="help-item">
                <div class="help-num">1</div>
                <div class="help-text">
                  <strong>点击「开始听会」开始录音</strong>
                  <p>系统会请求麦克风权限</p>
                </div>
              </div>
              <div class="help-item">
                <div class="help-num">2</div>
                <div class="help-text">
                  <strong>录音过程仅本机进行</strong>
                  <p>无实时转录推送，转录与纪要在停止后由后台分析</p>
                </div>
              </div>
              <div class="help-item">
                <div class="help-num">3</div>
                <div class="help-text">
                  <strong>点「结束听会」停止</strong>
                  <p>音频会自动上传 + 触发后台 ASR/声纹/纪要分析</p>
                </div>
              </div>
              <div class="help-item">
                <div class="help-num">4</div>
                <div class="help-text">
                  <strong>过程中请勿息屏 / 切走 App</strong>
                  <p>移动端浏览器后台会暂停录音；如需长时间录音建议用桌面端浏览器</p>
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
 * 2026-06-15 重写：与桌面端 MeetingRoom.vue 共用同一组逻辑组件（AudioRecorder + ProcessingDialog）
 * 模式：录音 → 停止 → 一次性上传 → 触发后台 ASR/声纹/纪要离线分析（不走 WS 实时转录）
 *
 * 链路：
 *   handleStart() → AudioRecorder.start()
 *   → onRecordingStart() → POST /api/v1/meetings/start-recording 拿 meetingId
 *   → 用户录音
 *   → 用户停止 → onAudioReady(blob)
 *   → POST /api/v1/meetings/{id}/upload-audio （上传 webm）
 *   → POST /api/v1/meetings/{id}/stop-recording （触发 Celery 后处理）
 *   → ProcessingDialog 显示进度
 *   → 完成 → onProgressClose → router.replace(`/meetings/{id}`)
 */

import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import AudioRecorder from '@/components/AudioRecorder.vue'
import ProcessingSheet from '@/components/mobile/ProcessingSheet.vue'
import PageHeader from '@/components/mobile/PageHeader.vue'
import { useRecordingState } from '@/composables/useRecordingState'
import { useGlobalRecorder } from '@/composables/useGlobalRecorder'

const router = useRouter()
const { startRecording, stopRecording, recordingMeetingId, checkActiveRecording } = useRecordingState()
const { isActive: isGlobalRecorderActive } = useGlobalRecorder()

const recorderRef = ref(null)
const meetingId = ref(null)
const showProgress = ref(false)
const showHelp = ref(false)

const pageTitle = computed(() => {
  if (meetingId.value) return `正在听会（ID ${meetingId.value}）`
  return '开始听会'
})

async function onRecordingStart() {
  // 录音真实开始后，创建会议拿 meetingId（与桌面端 MeetingRoom 同款链路）
  if (meetingId.value) {
    startRecording(meetingId.value, `正在听会（ID ${meetingId.value}）`)
    ElMessage.success('继续听会')
    return
  }
  try {
    const res = await axios.post('/api/v1/meetings/start-recording')
    meetingId.value = res.data.id
    startRecording(res.data.id, res.data.title || `正在听会（ID ${res.data.id}）`)
    ElMessage.success('开始听会')
  } catch (err) {
    ElMessage.error('创建会议失败: ' + (err.response?.data?.detail || err.message))
  }
}

function onRecordingStop() {
  // AudioRecorder 内部已处理 UI 状态切换；这里不做事
}

async function onAudioReady(blob) {
  if (!meetingId.value) {
    ElMessage.error('会议未创建，无法上传')
    return
  }
  // 立即弹进度，不阻塞 UI
  showProgress.value = true
  try {
    const fd = new FormData()
    fd.append('file', blob, `recording_${meetingId.value}.webm`)
    await axios.post(`/api/v1/meetings/${meetingId.value}/upload-audio`, fd)
    await axios.post(`/api/v1/meetings/${meetingId.value}/stop-recording`)
  } catch (err) {
    ElMessage.error('上传失败: ' + (err.response?.data?.detail || err.message))
    // 上传失败时关闭进度弹窗，让用户可以重试
    showProgress.value = false
  }
}

function onProgressClose() {
  showProgress.value = false
  stopRecording()
  // 跳转到会议详情页，让用户继续看结果
  if (meetingId.value) {
    router.replace(`/meetings/${meetingId.value}`)
  } else {
    router.replace('/meetings')
  }
}

async function handleBack() {
  // 录音中点返回 → 提示用户：录音会继续在后台跑（浮动胶囊可见），不会丢
  if (isGlobalRecorderActive()) {
    try {
      await ElMessageBox.confirm(
        '正在录音中。返回后录音会继续在后台进行（右下角胶囊提示），稍后可再次进入此页停止上传。',
        '录音中',
        {
          confirmButtonText: '返回（录音继续）',
          cancelButtonText: '留在此页',
          type: 'warning',
        }
      )
      router.back()
    } catch {
      return  // 用户取消
    }
  } else {
    router.back()
  }
}

// 恢复模式：用户从浮动胶囊或其他页面跳回 → 复用 sessionStorage / 后端的 meetingId
// 这样停止录音时能 POST 到正确的 /meetings/{id}/upload-audio
onMounted(async () => {
  await checkActiveRecording()  // 异步校验后端 recording 状态
  if (recordingMeetingId.value && !meetingId.value) {
    meetingId.value = recordingMeetingId.value
  }
})
</script>

<style scoped>
.mobile-meeting-room {
  min-height: 100vh;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
}

.room-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  padding-bottom: calc(16px + var(--sab, 0px));
  -webkit-overflow-scrolling: touch;
}

/* 顶栏右侧按钮 */
.header-action {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  font-size: 18px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: background 0.2s;
}
.header-action:active {
  background: rgba(0, 0, 0, 0.05);
}

/* 帮助 Sheet */
.help-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 2000;
  display: flex;
  align-items: flex-end;
  backdrop-filter: blur(4px);
}
.help-panel {
  width: 100%;
  background: var(--color-bg-card, #fff);
  border-radius: 16px 16px 0 0;
  padding: 16px;
  padding-bottom: calc(16px + var(--sab, 0px));
  max-height: 80vh;
  overflow-y: auto;
}
.help-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-border-light, #eee);
  margin-bottom: 16px;
}
.help-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: var(--font-weight-semibold, 600);
}
.help-header button {
  background: none;
  border: none;
  font-size: 20px;
  cursor: pointer;
  width: 32px;
  height: 32px;
}
.help-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.help-item {
  display: flex;
  gap: 12px;
}
.help-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #FF7A5C, #FF9D85);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: var(--font-weight-bold, 700);
  font-size: 14px;
  flex-shrink: 0;
}
.help-text strong {
  display: block;
  font-size: 14px;
  margin-bottom: 4px;
  color: var(--color-text-primary);
}
.help-text p {
  margin: 0;
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.5;
}

/* Transition */
.help-sheet-enter-active,
.help-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.help-sheet-enter-active .help-panel,
.help-sheet-leave-active .help-panel {
  transition: transform 0.3s cubic-bezier(0.2, 0.7, 0.2, 1);
}
.help-sheet-enter-from,
.help-sheet-leave-to {
  opacity: 0;
}
.help-sheet-enter-from .help-panel,
.help-sheet-leave-to .help-panel {
  transform: translateY(100%);
}
</style>

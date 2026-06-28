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
const {
  isActive: isGlobalRecorderActive,
  start: startGlobalRecorder,
  resumeFromStartedAt,
  setChunkStartIndex,
} = useGlobalRecorder()

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
      // 录音中"返回（录音继续）"跳到录音计时页 /meetings/room，与底部"正在听会"
      // 浮动胶囊的最终目标一致（见 MainLayout.goToRecording + MobileMeetingView.onMounted
      // 的 ?resume= 拦截逻辑）。Vue Router 4 在当前已处于 /meetings/room 时
      // short-circuit → 等价于关闭弹窗后留在原页（计时器+波形+录音不间断）。
      // 用户反馈 2026-06-26：原 /meetings/{id} 跳到静态详情页失去了实时
      // 计时器+音频波形视图，期望的是"和胶囊一样"留在录音室。
      router.replace('/meetings/room')
    } catch {
      return  // 用户取消
    }
  } else {
    router.back()  // 未录音场景保留 router.back()：真正的"返回"语义，跳回来源页
  }
}

// 恢复模式：用户从浮动胶囊或其他页面跳回 → 复用 sessionStorage / 后端的 meetingId
// 这样停止录音时能 POST 到正确的 /meetings/{id}/upload-audio
//
// 2026-06-27 v3 镜像：刷新后接续录音（与桌面端 MeetingRoomView 同款逻辑）。
// 1) 校验后端 recording 状态（checkActiveRecording）→ 拿到 recordingMeetingId
// 2) 同步本地 meetingId 给 onAudioReady 上传用
// 3) 并行 fetch /meetings/{id} 和 /upload-status：
//    - recording_started_at → resumeFromStartedAt 回填 elapsed
//    - last_chunk_index → setChunkStartIndex(+1) 续传不覆盖
// 4) await startGlobalRecorder() 启动 MediaRecorder（v2 同款）
onMounted(async () => {
  await checkActiveRecording()  // 异步校验后端 recording 状态
  if (recordingMeetingId.value && !meetingId.value) {
    meetingId.value = recordingMeetingId.value
  }

  // 仅当有 active recording 时才回填 + 自动启动（避免空跑）
  if (recordingMeetingId.value) {
    const id = recordingMeetingId.value
    try {
      const [meetingRes, uploadRes] = await Promise.all([
        axios.get(`/api/v1/meetings/${id}`),
        axios.get(`/api/v1/meetings/${id}/upload-status`).catch(() => null),
      ])
      if (meetingRes.data?.recording_started_at) {
        resumeFromStartedAt(meetingRes.data.recording_started_at)
      }
      const lastChunk = uploadRes?.data?.last_chunk_index ?? -1
      if (lastChunk >= 0) {
        setChunkStartIndex(lastChunk + 1)
      }
    } catch (err) {
      console.warn('[MobileMeetingRoom] 取回填数据失败:', err.message)
    }

    // 镜像桌面端 v2：自动启动 MediaRecorder 接续录音
    try {
      await startGlobalRecorder()
      console.warn('[MobileMeetingRoom] 自动启动 MediaRecorder 成功, meetingId =', id)
    } catch (err) {
      console.warn('[MobileMeetingRoom] 自动启动 MediaRecorder 失败 (可能麦克风权限):', err.message)
    }
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
  /* v59 (2026-06-26) 抬到 5000：旧 2000 被 TabBar (z=2500) + 录音胶囊 (z=2900)
     覆盖，底部 sheet 看起来被遮挡。与 ProcessingSheet (4500) / VoiceTestFlow (5000)
     同档，确保 sheet 完全浮在所有元素之上。 */
  z-index: 5000;
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
  background: linear-gradient(135deg, var(--color-primary), var(--color-warning));
  color: var(--color-bg-card);
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
  transition: transform 0.3s var(--ease-spring);
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

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped） -->
<style>
/* 全屏听会底色 + 头像 + 波形条 + 状态徽章在 dark 模式适配 */
[data-theme="dark"] .mobile-meeting-room {
  background: var(--color-bg-page);
}
[data-theme="dark"] .room-toolbar {
  background: var(--color-bg-card);
  border-bottom: 1px solid var(--color-border-light);
}
[data-theme="dark"] .toolbar-btn {
  color: var(--color-text-regular);
}
[data-theme="dark"] .toolbar-btn.active {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
[data-theme="dark"] .speaker-avatar {
  border: 2px solid var(--color-primary);
}
[data-theme="dark"] .speaker-name {
  color: var(--color-text-primary);
}
[data-theme="dark"] .help-panel {
  background: var(--color-bg-card);
  color: var(--color-text-regular);
}
</style>

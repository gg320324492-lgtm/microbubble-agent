<template>
  <div class="desktop-meeting-room">
    <!-- 顶部栏（桌面端：用 el-page-header 替代移动端 PageHeader） -->
    <header class="room-header">
      <el-page-header :icon="ArrowLeft" @back="handleBack">
        <template #content>
          <span class="room-title">{{ pageTitle }}</span>
          <span v-if="recordingMeetingId && meetingId" class="resume-badge">
            正在听会（ID {{ meetingId }}）
          </span>
        </template>
      </el-page-header>
      <div class="header-actions">
        <el-button
          text
          :icon="QuestionFilled"
          @click="showHelp = true"
          aria-label="使用帮助"
          title="使用帮助"
        />
      </div>
    </header>

    <!-- 主内容 -->
    <main class="room-main">
      <AudioRecorder
        ref="recorderRef"
        @recording-start="onRecordingStart"
        @recording-stop="onRecordingStop"
        @audio-ready="onAudioReady"
      />
    </main>

    <!-- 后台处理进度 -->
    <ProcessingDialog
      v-if="showProgress"
      :meeting-id="meetingId"
      @close="onProgressClose"
    />

    <!-- 使用帮助（桌面端用 el-dialog 而非移动端底部 sheet） -->
    <el-dialog
      v-model="showHelp"
      title="使用说明"
      width="540px"
      :close-on-click-modal="true"
    >
      <ol class="help-list">
        <li>
          <strong>点击「开始听会」开始录音</strong>
          <p>系统会请求麦克风权限</p>
        </li>
        <li>
          <strong>录音过程仅本机进行</strong>
          <p>无实时转录推送，转录与纪要在停止后由后台分析</p>
        </li>
        <li>
          <strong>点「结束听会」停止</strong>
          <p>音频会自动上传 + 触发后台 ASR/声纹/纪要分析</p>
        </li>
        <li>
          <strong>导航到其他页面录音继续</strong>
          <p>右下角胶囊持续提示，返回此页可查看 / 停止</p>
        </li>
      </ol>
    </el-dialog>
  </div>
</template>

<script setup>
/**
 * MeetingRoomView.vue — 桌面端听会房间
 *
 * 2026-06-18 新建：镜像 MobileMeetingRoom.vue，把桌面 MeetingView 的 dialog 模式
 * 改成全屏页面，避免"正在听会"点击后弹窗 UX 不一致的问题。
 *
 * 与 MobileMeetingRoom 的关键差异：
 *   ① 顶栏用 el-page-header（非移动端 PageHeader 组件）
 *   ② 帮助用 el-dialog（非移动端底部 sheet）
 *   ③ onMounted 同样调 checkActiveRecording()，复用 useRecordingState.recordingMeetingId
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
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, QuestionFilled } from '@element-plus/icons-vue'
import axios from 'axios'
import AudioRecorder from '@/components/AudioRecorder.vue'
import ProcessingDialog from '@/components/ProcessingDialog.vue'
import { useRecordingState } from '@/composables/useRecordingState'
import { useGlobalRecorder } from '@/composables/useGlobalRecorder'

const router = useRouter()
const route = useRoute()
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
  // 恢复模式：已有 meetingId，跳过创建（与桌面端 MeetingRoom.vue 同款逻辑）
  if (meetingId.value) {
    startRecording(meetingId.value, `正在听会（ID ${meetingId.value}）`)
    ElMessage.success('继续听会')
    return
  }
  // 新建模式：创建会议拿 meetingId
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
    showProgress.value = false
  }
}

function onProgressClose() {
  showProgress.value = false
  stopRecording()
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
      // 浮动胶囊的最终目标一致（见 MainLayout.goToRecording + MeetingView.onMounted
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
// 桌面端原本 MeetingView.resumeRecording() 是开 dialog，现在改成导航到本页走同一逻辑
//
// 2026-06-27 修：三层防御修复"显示开始听会"bug。
//   1) 优先用 query.resume（来自 MainLayout.goToRecording → MeetingView.resumeRecording
//      显式传入），不依赖 useRecordingState 状态机
//   2) 强制重新查后端（绕过 initialized 短路），保证 sessionStorage / 后端 / 模块级 ref 三者一致
//   3) 兜底：useRecordingState 同步后的值覆盖到本地 ref（仅当本地还没值时）
onMounted(async () => {
  // 1) 优先用 query 显式 ID（不依赖 useRecordingState 状态机）
  const resumeFromQuery = route.query.resume
  if (resumeFromQuery && !meetingId.value) {
    const id = Number(resumeFromQuery)
    if (!Number.isNaN(id) && id > 0) {
      meetingId.value = id
      // 同步到全局状态，保证顶部胶囊、MainLayout 状态一致
      startRecording(id, `正在听会（ID ${id}）`)
      console.warn('[MeetingRoomView] 优先使用 query.resume 初始化 meetingId =', id)
    }
  }
  // 2) 强制重新查后端（绕过 initialized 短路），保证 sessionStorage / 后端 / 模块级 ref 三者一致
  await checkActiveRecording({ force: true })
  // 3) 兜底：useRecordingState 同步后的值覆盖到本地 ref（仅当本地还没值时）
  if (recordingMeetingId.value && !meetingId.value) {
    meetingId.value = recordingMeetingId.value
  }
})
</script>

<style scoped>
.desktop-meeting-room {
  min-height: 100vh;
  background: var(--color-bg-page, #f5f7fa);
  display: flex;
  flex-direction: column;
}

.room-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  position: sticky;
  top: 0;
  z-index: 10;
}

.room-header :deep(.el-page-header) {
  flex: 1;
}

.room-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary, #2D2D2D);
  margin-left: 8px;
}

.resume-badge {
  display: inline-block;
  margin-left: 12px;
  padding: 2px 10px;
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  /* stylelint-disable-next-line color-named */
  color: var(--color-bg-card);
  font-size: 12px;
  font-weight: 600;
  border-radius: 12px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.room-main {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.help-list {
  margin: 0;
  padding-left: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  line-height: 1.6;
}

.help-list li strong {
  display: block;
  font-size: 14px;
  color: var(--color-text-primary, #2D2D2D);
  margin-bottom: 4px;
}

.help-list li p {
  margin: 0;
  font-size: 13px;
  color: var(--color-text-secondary, #909399);
  line-height: 1.5;
}
</style>
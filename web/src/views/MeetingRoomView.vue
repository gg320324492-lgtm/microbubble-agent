<template>
  <div class="desktop-meeting-room">
    <!-- 顶部栏（桌面端：用 el-page-header 替代移动端 PageHeader） -->
    <header class="room-header glass glass-lg">
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
        :meeting-id="meetingId"
        :meeting-title="pageTitle"
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
 *   ③ onMounted 优先用 route.query.resume 初始化 meetingId + startRecording 同步到 store
 *     （不调 checkActiveRecording 避免后端 title 覆盖触发 reactive storm）
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
const { startRecording, stopRecording, recordingMeetingId } = useRecordingState()
const {
  start: startGlobalRecorder,
  isActive: isGlobalRecorderActive,
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
// 2026-06-27 v1 修：三层防御修复 pageTitle 显示"开始听会"bug。
//   1) 优先用 query.resume（来自 MainLayout.goToRecording → MeetingView.resumeRecording
//      显式传入），不依赖 useRecordingState 状态机
//   2) 强制重新查后端（绕过 initialized 短路），保证 sessionStorage / 后端 / 模块级 ref 三者一致
//   3) 兜底：useRecordingState 同步后的值覆盖到本地 ref（仅当本地还没值时）
//
// 2026-06-27 v2 修：自动启动 MediaRecorder 接续录音。
//   v1 修好后 pageTitle 显示"正在听会（ID 140）"，但 AudioRecorder 按钮仍显示"开始听会"
//   （因为 isActive() 检查 useGlobalRecorder.state，浏览器刷新后 state 回到 idle），
//   用户需手动再点按钮 → UX 不符合"点胶囊即接续"的预期。
//   本次 v2 在 query.resume 命中后自动 await startGlobalRecorder()，让 MediaRecorder 启动，
//   AudioRecorder 状态从 idle → recording，按钮自动切到"录音中"+ 暂停/结束控件。
//
// 2026-06-27 v3 修：刷新后接续录音（计时器 + chunk 续传不覆盖）。
//   v2 修好后：MediaRecorder 启动成功，pageTitle 显示"正在听会（ID 152）"，
//   但 elapsed 永远从 0 开始（useGlobalRecorder 是模块级单例，刷新即重置），
//   且新 MediaRecorder 的 chunkIndex 从 0 起，会覆盖 MinIO 上已上传的旧 chunks。
//   修复：在 startGlobalRecorder() 之前并行拉取：
//     a) GET /api/v1/meetings/{id} → recording_started_at (ISO) → resumeFromStartedAt
//        计算 (now - start) / 1000 秒数并设给 elapsed，setInterval 启动后从该值 +1
//     b) GET /api/v1/meetings/{id}/upload-status → last_chunk_index → setChunkStartIndex(+1)
//        让 ondataavailable 从正确 index 开始上传，merge 时拼回完整录音
//   两个新 API 都必须在 start() 之前同步调用（JS 单线程 + MediaRecorder.start(1000) 1s 缓冲保护）。
onMounted(async () => {
  // 1) 优先用 query 显式 ID（不依赖 useRecordingState 状态机）
  const resumeFromQuery = route.query.resume
  if (resumeFromQuery && !meetingId.value) {
    const id = Number(resumeFromQuery)
    if (!Number.isNaN(id) && id > 0) {
      // 仅当 store 没值或值不同时才调 startRecording，避免与 MainLayout 已 set 的状态冲突
      // 重复 set 同一值会触发 Vue 3 notify 链 → set value → trigger → notify 循环
      // (因为 startRecording 内部 set recordingMeetingTitle，placeholder 与后端真实 title
      // 不同时 hasChanged 检测到变化 → element-plus 内部 ref cascade → console 风暴)
      meetingId.value = id
      if (recordingMeetingId.value !== id) {
        startRecording(id, `正在听会（ID ${id}）`)
      }
      console.warn('[MeetingRoomView] 优先使用 query.resume 初始化 meetingId =', id)

      // === v3: 刷新后接续录音（计时器 + chunk 续传） ===
      // 必须先 setElapsed + setChunkStartIndex，再 startGlobalRecorder()
      try {
        const [meetingRes, uploadRes] = await Promise.all([
          axios.get(`/api/v1/meetings/${id}`),
          axios.get(`/api/v1/meetings/${id}/upload-status`).catch(() => null),
        ])
        // 计时器：从 recording_started_at 计算已录制秒数
        if (meetingRes.data?.recording_started_at) {
          resumeFromStartedAt(meetingRes.data.recording_started_at)
        }
        // chunk 续传：从 last_chunk_index + 1 继续上传
        const lastChunk = uploadRes?.data?.last_chunk_index ?? -1
        if (lastChunk >= 0) {
          setChunkStartIndex(lastChunk + 1)
        }
      } catch (err) {
        console.warn('[MeetingRoomView] 取回填数据失败 (使用默认 elapsed=0, chunk=0):', err.message)
      }

      // v2: 自动启动 MediaRecorder 接续录音
      try {
        await startGlobalRecorder()
        console.warn('[MeetingRoomView] 自动启动 MediaRecorder 成功, meetingId =', id)
      } catch (err) {
        console.warn('[MeetingRoomView] 自动启动 MediaRecorder 失败 (可能麦克风权限), 用户需手动点开始:', err.message)
        ElMessage.warning('请点击"开始听会"按钮手动启动录音（可能需要授权麦克风权限）')
      }
    }
  }
  // 移除 v1 的 layer 2/3 (checkActiveRecording({ force:true }) + fallback re-assign)：
  //   layer 2 会用后端真实 title 重新 set recordingMeetingTitle（与 layer 1 的 placeholder 不同），
  //   触发 Vue 3 notify 链 → set value → trigger → notify 循环（reactive storm），
  //   console 出现大量 element-plus-desktop stack trace。
  //   修复依据：layer 1 已足以让 pageTitle 显示"正在听会（ID 149）"且 recordingMeetingId
  //   在 store 里可用。MainLayout.onMounted 早已初始化 store (initialized=true)，
  //   后续非 force 调用会 short-circuit 不会重复 fetch。
  // 兜底：MeetingRoomView template 仍读 recordingMeetingId.value 显示 resume-badge，
  //   假设 store 正确（MainLayout 处理过）。
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
  /* v77 P2.5.1: backdrop-filter + 半透 background 由 .glass 工具类提供 (assets/glass.css)
     删硬编码 rgba(255,255,255,0.92) 解决 dark mode 白戳一坨 + 6 主题不跟随 */
  border-bottom: 1px solid var(--color-border-light);
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
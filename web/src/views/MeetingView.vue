<template>
  <div class="meeting-view">
    <!-- 顶部操作栏 -->
    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :xs="12" :sm="6" :md="4">
          <el-date-picker
            v-model="dateFrom"
            name="meeting-list-date-from"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            placeholder="开始日期"
            style="width: 100%"
            :clearable="true"
            @change="fetchMeetings"
          />
        </el-col>
        <el-col :xs="12" :sm="6" :md="4">
          <el-date-picker
            v-model="dateTo"
            name="meeting-list-date-to"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            placeholder="结束日期"
            style="width: 100%"
            :clearable="true"
            @change="fetchMeetings"
          />
        </el-col>
        <el-col :xs="24" :sm="12" :md="8">
          <el-input
            v-model="keyword"
            name="meeting-list-keyword"
            placeholder="搜索会议主题"
            clearable
            @keyup.enter="fetchMeetings"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :xs="24" :sm="12" :md="8">
          <div class="top-actions">
            <el-button type="primary" @click="showCreateDialog = true">
              <el-icon><Plus /></el-icon> 手动创建
            </el-button>
            <el-button type="success" @click="pasteAnalyzeDialogRef?.open()">
              <el-icon><Document /></el-icon> 粘贴转录分析
            </el-button>
            <el-button type="warning" @click="startLiveCall">
              <el-icon><Microphone /></el-icon> 开始听会
            </el-button>
            <el-button @click="showVoiceTest = true">
              🎤 测试
            </el-button>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 会议列表 -->
    <el-card class="meeting-list-card">
      <div v-if="meetings.length === 0" class="empty-state">
        <el-empty description="暂无会议记录" />
      </div>

      <div v-else class="meeting-list">
        <div
          v-for="meeting in meetings"
          :key="meeting.id"
          class="meeting-item"
          @click="viewMeeting(meeting)"
        >
          <div class="meeting-time-block">
            <div class="time-month">{{ formatMonth(meeting.start_time) }}</div>
            <div class="time-day">{{ formatDay(meeting.start_time) }}</div>
            <div class="time-hour">{{ formatHour(meeting.start_time) }}</div>
          </div>

          <div class="meeting-info">
            <div class="meeting-title">{{ meeting.title }}</div>
            <div class="meeting-meta">
              <span class="status-dot-wrap">
                <span class="status-dot" :class="'status-' + meeting.status" />
                <el-tag :type="getStatusType(meeting.status)" size="small">
                  {{ getStatusLabel(meeting.status) }}
                </el-tag>
              </span>
              <span v-if="meeting.location" class="meeting-location">
                <el-icon><Location /></el-icon>
                {{ meeting.location }}
              </span>
              <span v-if="meeting.audio_url" class="meeting-has-audio" title="有录音">
                🎙️
              </span>
            </div>
            <div class="meeting-participants-row">
              <ParticipantAvatars
                :participants="meeting.participants || []"
                :max-display="4"
                :size="24"
              />
            </div>
            <div v-if="meeting.summary" class="meeting-summary">
              {{ meeting.summary.substring(0, 100) }}...
            </div>
          </div>

          <div class="meeting-actions">
            <el-button type="primary" size="small" @click.stop="viewMeeting(meeting)">
              查看详情
            </el-button>
            <el-popconfirm title="确定删除此会议？" @confirm="deleteMeeting(meeting.id)">
              <template #reference>
                <el-button type="danger" size="small" @click.stop>删除</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </div>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="fetchMeetings"
        />
      </div>
    </el-card>

    <!-- 创建会议对话框 -->
    <!-- 创建/编辑会议对话框 -->
    <MeetingCreateDialog
      v-model:visible="showCreateDialog"
      :is-mobile="isMobile"
      :editing-id="editingMeetingId"
      :editing-data="editingMeetingData"
      :templates="templates"
      @success="onMeetingSaved"
    />

    <!-- 2026-06-03 新增：模板编辑对话框 — v77 P2.6-F.2: 抽到 MeetingTemplateDialog 子组件 -->
    <MeetingTemplateDialog
      v-model="showTemplateDialog"
      :editing-template="editingTemplate"
      :members="members"
      :is-mobile="isMobile"
      @saved="onTemplateSaved"
    />

    <!-- 实时转写对话框（已废弃，录音机模式无需实时转写） -->

    <!-- 会议纪要对话框 — v77 P2.6-F.2: 抽到 MeetingMinutesDialog 子组件 -->
    <MeetingMinutesDialog
      v-model="showMinutesDialog"
      :meeting="currentMeeting"
      :is-mobile="isMobile"
    />

    <!-- 听会对话框 -->
    <el-dialog
      v-model="showLiveCallDialog"
      title="听会"
      :width="isMobile ? '95vw' : '800px'"
      top="3vh"
      :close-on-click-modal="false"
      @close="onLiveCallEnd"
    >
      <MeetingRoom
        v-if="showLiveCallDialog"
        ref="meetingRoomRef"
        :meeting-id="liveCallMeeting?.id || null"
        @call-ended="onCallEnded"
        style="height: 500px"
      />
    </el-dialog>

    <!-- 粘贴转录分析对话框 -->
    <PasteAnalyzeDialog ref="pasteAnalyzeDialogRef" @saved="fetchMeetings" />

    <!-- 声纹测试对话框 -->
    <VoiceTestDialog v-model:visible="showVoiceTest" />

    <!-- 挂断后会后处理进度对话框 -->
    <ProcessingDialog
      v-if="processingDialogVisible && processingMeetingId"
      :meeting-id="processingMeetingId"
      @close="processingDialogVisible = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import { formatDateTime } from '@/utils/format'
import { getStatusType, getStatusLabel } from '@/utils/task'
import { useMemberStore } from '@/stores/member'
import { useMeeting } from '@/composables/useMeeting'
import { useRecordingState } from '@/composables/useRecordingState'
import { useGlobalRecorder } from '@/composables/useGlobalRecorder'
import MeetingCreateDialog from './meeting/MeetingCreateDialog.vue'
import PasteAnalyzeDialog from '@/components/PasteAnalyzeDialog.vue'
import MeetingRoom from '@/components/MeetingRoom.vue'
import ProcessingDialog from '@/components/ProcessingDialog.vue'
import VoiceTestDialog from '@/components/VoiceTestDialog.vue'
import ParticipantAvatars from '@/components/ParticipantAvatars.vue'
import MeetingMinutesDialog from '@/components/meeting/MeetingMinutesDialog.vue'
import MeetingTemplateDialog from '@/components/meeting/MeetingTemplateDialog.vue'
import { Delete, Document, Plus, Microphone, Location, Search } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const memberStore = useMemberStore()

// 全局录音状态
const { recordingMeetingId: globalRecordingId, startRecording, stopRecording } = useRecordingState()
const { stop: stopGlobalRecorder, isActive: isRecorderActive } = useGlobalRecorder()
const members = computed(() => memberStore.members)

// 使用 composable
const {
  meetings, total, currentPage, pageSize, loading,
  keyword, dateFrom, dateTo, currentMeeting,
  fetchMeetings, createMeeting, updateMeeting, deleteMeeting: deleteMeetingApi
} = useMeeting()

const isMobile = ref(window.innerWidth <= 768)
const showCreateDialog = ref(false)
const showMinutesDialog = ref(false)
const pasteAnalyzeDialogRef = ref(null)
const meetingRoomRef = ref(null)

// 声纹通话
const showLiveCallDialog = ref(false)
const liveCallMeeting = ref(null)
const showVoiceTest = ref(false)

// 挂断后处理进度弹窗
const processingDialogVisible = ref(false)
const processingMeetingId = ref(null)

function onCallEnded(meetingId) {
  // 关闭听会弹窗，刷新列表
  showLiveCallDialog.value = false
  liveCallMeeting.value = null
  stopRecording()
  fetchMeetings()
  if (meetingId) {
    router.push(`/meetings/${meetingId}`)
  }
}

// 编辑会议
const editMeeting = (meeting) => {
  meetingForm.value = {
    templateId: null,
    title: meeting.title,
    start_time: meeting.start_time,
    location: meeting.location || '',
    participants: meeting.participants?.map(p => p.member_id) || [],
    description: meeting.description || '',
    summary: meeting.summary || '',
    key_points: meeting.key_points ? [...meeting.key_points] : [],
    decisions: meeting.decisions ? [...meeting.decisions] : [],
    agenda: meeting.agenda ? [...meeting.agenda] : [],
    remindBefore: meeting.remind_before !== false,
  }
  editingMeetingId.value = meeting.id
  showCreateDialog.value = true
}

const editingMeetingId = ref(null)

const deleteMeeting = async (id) => {
  try {
    await deleteMeetingApi(id)
    ElMessage.success('会议已删除')
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// 编辑会议数据
const editingMeetingData = computed(() => {
  if (!editingMeetingId.value) return null
  return meetings.value.find(m => m.id === editingMeetingId.value)
})

// 会议保存成功回调
const onMeetingSaved = () => {
  editingMeetingId.value = null
  fetchMeetings()
}

const startLiveCall = () => {
  liveCallMeeting.value = null
  showLiveCallDialog.value = true
  // 录音 ID 会在 MeetingRoom 的 onRecordingStart 回调中设置
}

// 弹窗被关闭（用户点 X 或 ESC）
async function onLiveCallEnd() {
  // 如果录音还在进行中，停止录音并上传
  if (isRecorderActive()) {
    const blob = await stopGlobalRecorder()
    const mid = liveCallMeeting.value?.id || globalRecordingId.value
    if (blob && mid) {
      try {
        const fd = new FormData()
        fd.append('file', blob, `recording_${mid}.webm`)
        await axios.post(`/api/v1/meetings/${mid}/upload-audio`, fd)
        await axios.post(`/api/v1/meetings/${mid}/stop-recording`)
        ElMessage.success('录音已保存')
      } catch (err) {
        ElMessage.error('录音保存失败: ' + (err.response?.data?.detail || err.message))
      }
    }
  }
  showLiveCallDialog.value = false
  liveCallMeeting.value = null
  stopRecording()
  fetchMeetings()
}

// 从全局状态恢复录音：2026-06-18 改为跳到 /meetings/room 全屏页面（与移动端同款）
// 之前是打开 el-dialog 嵌套 MeetingRoom，但弹窗 UX 与移动端页面不一致，
// 用户点击"正在听会"胶囊后看不到明确的"继续听会"提示。新建 MeetingRoomView.vue
// 桌面端用 el-page-header 全屏布局 + onMounted 自动 checkActiveRecording()，
// 与 MobileMeetingRoom 镜像对齐
//
// 2026-06-27 修：把 resumeId 通过 ?resume=X 显式传给 /meetings/room，
// 即使 useRecordingState.checkActiveRecording() 因 initialized 短路没同步到 meetingId，
// MeetingRoomView 也能从 query 拿到正确 ID 显示"正在听会（ID N）"
// 修复场景：桌面端"正在听会"胶囊点击后跳到 /meetings/room 显示"开始听会"的 bug
const resumeRecording = (meetingId) => {
  router.replace({ path: '/meetings/room', query: { resume: meetingId } })
}

const meetingForm = ref({
  templateId: null,
  title: '', start_time: '', location: '', participants: [], description: '',
  summary: '', key_points: [], decisions: [],
  agenda: [],  // Wave 3b: 会议议程
  remindBefore: true,
})

// === 2026-06-03 重构：会议模板内嵌到 MeetingView ===
// v77 P2.6-F.2 Step 1: builtinTemplates/customTemplates/applyTemplate 已删（MeetingCreateDialog 有自己的副本）
const templates = ref([])

async function loadTemplates() {
  try {
    const resp = await axios.get('/api/v1/meeting-templates')
    if (resp.status === 200) templates.value = resp.data
  } catch (e) {
    console.warn('加载会议模板失败', e)
  }
}

// === 模板 CRUD（v77 P2.6-F.2: 抽到 MeetingTemplateDialog 子组件） ===
// 父 MeetingView 只保留 dialog 开关 + 当前编辑模板引用，表单 + submit + reset 都搬到子组件
const showTemplateDialog = ref(false)
const editingTemplate = ref(null)

const onTemplateSaved = async () => {
  editingTemplate.value = null
  await loadTemplates()
}

// 关闭会议创建对话框时清理 templateId 高亮
function onCreateDialogClose() {
  editingMeetingId.value = null
  meetingForm.value.templateId = null
}

// 获取成员列表（使用 store）
const fetchMembers = () => memberStore.fetchMembers()

// 查看会议详情 → 跳转全屏详情页
const viewMeeting = (meeting) => {
  router.push(`/meetings/${meeting.id}`)
}

// v77 P2.6-F.2 Step 1: viewMinutes / startTranscript / onTranscriptComplete / generateMinutes 已删（0 调用方）

// 辅助函数（数据库存 UTC，显示北京时间 UTC+8）
const formatMonth = (date) => dayjs(date).add(8, 'hour').format('M月')
const formatDay = (date) => dayjs(date).add(8, 'hour').format('D')
const formatHour = (date) => dayjs(date).add(8, 'hour').format('HH:mm')
// v77 P2.6-F.2 Step 2: formatDate 删（纪要 dialog 搬到 MeetingMinutesDialog 内部有自己的 formatDate）

onMounted(() => {
  fetchMeetings()
  fetchMembers()
  loadTemplates()  // Wave 3b

  // 支持从全局录音指示器跳转回来：2026-06-18 改为跳到 /meetings/room 全屏页
  // （与 MobileMeetingView:325-328 镜像），不要再"清理 query 后留 /meetings"
  // —— 那会让 URL 永远停在 /meetings + MeetingView 持续重渲 = "会议管理界面不断刷新"
  const resumeId = route.query.resume
  if (resumeId) {
    resumeRecording(Number(resumeId))
    // resumeRecording 内部已 router.replace('/meetings/room')，不要在这里再 replace
  }
})
</script>

<style scoped>
.meeting-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
  overflow: hidden;
  animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;
}

.filter-card {
  flex-shrink: 0;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

.filter-card :deep(.el-card__body) {
  padding: var(--space-4) var(--space-5);
}

.top-actions { display: flex; gap: 8px; flex-wrap: wrap; }

.meeting-list-card {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) 80ms both;
}

.meeting-list-card :deep(.el-card__body) {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.meeting-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.meeting-item {
  display: flex;
  gap: var(--space-5);
  padding: var(--space-4);
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}

.meeting-item:hover {
  border-color: var(--color-primary);
  box-shadow: var(--shadow-primary);
  transform: translateY(-2px);
}

.meeting-time-block {
  min-width: 80px;
  text-align: center;
  padding: var(--space-2);
  background: var(--color-bg-page);
  border-radius: var(--radius-md);
}

.time-month {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
}

.time-day {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-bold);
  color: var(--color-primary);
  line-height: 1.2;
}

.time-hour {
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
}

.meeting-info {
  flex: 1;
}

.meeting-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-2);
}

.meeting-meta {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.meeting-location {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.meeting-summary {
  font-size: var(--font-size-sm);
  color: var(--color-text-regular);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.meeting-participants-row {
  margin: var(--space-2) 0;
}

.status-dot-wrap {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-dot.status-scheduled { background: var(--color-info, #909399); }
.status-dot.status-recording { background: var(--color-primary, #FF7A5C); animation: dot-pulse 1.2s infinite; }
.status-dot.status-processing { background: var(--color-warning, #E6A23C); animation: dot-pulse 1.5s infinite; }
.status-dot.status-completed { background: var(--color-success, #67C23A); }
.status-dot.status-cancelled { background: var(--color-info, #909399); opacity: 0.5; }
.status-dot.status-error { background: var(--color-danger, #F56C6C); }

.meeting-has-audio {
  font-size: 14px;
  line-height: 1;
}

.meeting-actions {
  display: flex;
  flex-direction: row;
  gap: 6px;
  align-items: center;
  flex-shrink: 0;
}

.action-btn {
  width: 34px !important;
  height: 34px !important;
  padding: 0 !important;
  border: 1.5px solid var(--color-border) !important;
  background: var(--color-bg-card) !important;
  transition: var(--transition-all-normal) ease !important;
}
.action-btn:hover {
  transform: translateY(-1px);
}
.action-phone { color: var(--color-primary) !important; border-color: rgba(var(--color-primary-rgb),0.3) !important; }
.action-phone:hover { background: var(--color-primary) !important; color: var(--el-color-white) !important; border-color: var(--color-primary) !important; box-shadow: 0 2px 8px rgba(var(--color-primary-rgb),0.3); }

.action-view { color: var(--color-primary) !important; border-color: rgba(var(--color-primary-rgb),0.3) !important; }
.action-view:hover { background: var(--color-primary) !important; color: var(--el-color-white) !important; border-color: var(--color-primary) !important; box-shadow: 0 2px 8px rgba(var(--color-primary-rgb),0.3); }

.action-generate { color: var(--color-success) !important; border-color: rgba(103,194,58,0.3) !important; }
.action-generate:hover { background: var(--color-success) !important; color: var(--el-color-white) !important; border-color: var(--color-success) !important; box-shadow: 0 2px 8px rgba(103,194,58,0.3); }

.action-edit { color: var(--color-info) !important; border-color: rgba(144,147,153,0.3) !important; }
.action-edit:hover { background: var(--color-info) !important; color: var(--el-color-white) !important; border-color: var(--color-info) !important; box-shadow: 0 2px 8px rgba(144,147,153,0.3); }

.action-delete { color: var(--color-danger) !important; border-color: rgba(245,108,108,0.3) !important; }
.action-delete:hover { background: var(--color-danger) !important; color: var(--el-color-white) !important; border-color: var(--color-danger) !important; box-shadow: 0 2px 8px rgba(245,108,108,0.3); }

/* 纪要编辑列表 */
.minutes-textarea :deep(.el-textarea__inner) { border-radius: var(--radius-md); border-color: var(--color-border); }
.item-list { display: flex; flex-direction: column; gap: 8px; }
.item-row {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 10px; background: var(--color-bg-page); border-radius: var(--radius-md);
  border: 1px solid transparent; transition: var(--transition-all-normal);
}
.item-row:hover, .item-row:focus-within {
  border-color: var(--color-primary-border); background: var(--color-primary-bg);
}
.item-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  background: var(--color-primary);
}
.decision-dot { background: var(--color-warning); }
.item-row .el-input { flex: 1; }
.item-del { opacity: 0; transition: opacity 0.2s; }
.item-row:hover .item-del { opacity: 1; }
.item-add { width: 100%; justify-content: center; border-style: dashed; }
.decision-add { color: var(--color-warning); border-color: var(--color-warning); }

/* 2026-06-03 新增：模板卡片选择器样式（替代独立 MeetingTemplatesView） */
.template-picker {
  background: var(--color-bg-page, #fafafa);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
}
.template-picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.template-picker-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
}
.template-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
}
.template-card {
  border: 1px solid var(--color-border, #e4e7ed);
  border-radius: 6px;
  padding: 10px 12px;
  background: var(--color-bg-card);
  cursor: pointer;
  transition: var(--transition-all-fast) ease;
  position: relative;
}
.template-card:hover {
  border-color: var(--color-primary, #FF7A5C);
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), 0.12);
  transform: translateY(-1px);
}
.template-card.active {
  border-color: var(--color-primary, #FF7A5C);
  background: linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.04), rgba(var(--color-accent-rgb), 0.04));
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), 0.18);
}
.template-card-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
  justify-content: space-between;
}
.template-card-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
  line-height: 1.4;
  margin-bottom: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.template-card-meta {
  display: flex;
  gap: 10px;
  font-size: 11px;
  color: var(--color-text-placeholder);
}
.template-card-meta span {
  display: flex;
  align-items: center;
  gap: 2px;
}
.template-card-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.15s;
}
.template-card.custom:hover .template-card-actions { opacity: 1; }
.tpl-action {
  cursor: pointer;
  padding: 2px;
  border-radius: 3px;
  color: var(--color-text-secondary);
}
.tpl-action:hover { background: var(--color-bg-page, #fafafa); }
.tpl-action.danger { color: var(--color-danger); }
.template-empty {
  grid-column: 1 / -1;
  text-align: center;
  color: var(--color-text-placeholder);
  font-size: 12px;
  padding: 16px 0;
}
.form-hint {
  font-size: 11px;
  color: var(--color-text-placeholder);
  margin-left: 8px;
}

@media (max-width: 768px) {
  .meeting-actions { flex-wrap: wrap; }
}

.pagination {
  flex-shrink: 0;
  margin-top: var(--space-4);
  padding-top: var(--space-3);
  border-top: 1px solid var(--color-border);
  display: flex;
  justify-content: flex-end;
}

.minutes-content h3 {
  margin-bottom: var(--space-2);
}

.minutes-time {
  color: var(--color-text-secondary);
  margin-bottom: var(--space-5);
}

.minutes-section {
  margin-bottom: var(--space-5);
}

.minutes-section h4 {
  margin-bottom: var(--space-2);
  color: var(--color-text-primary);
  font-weight: var(--font-weight-semibold);
}

.minutes-section ul {
  padding-left: var(--space-5);
}

.minutes-section li {
  margin-bottom: var(--space-2);
  line-height: 1.5;
  color: var(--color-text-regular);
}

.transcript-dialog-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.meeting-info-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--color-border);
}

.meeting-info-bar h3 {
  margin: 0;
  font-size: var(--font-size-lg);
  color: var(--color-text-primary);
}

@media (max-width: 768px) {
  .meeting-item {
    flex-direction: column;
    gap: var(--space-3);
  }
  .meeting-time-block {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    min-width: unset;
  }
  .meeting-actions {
    flex-direction: row;
    flex-wrap: wrap;
  }
}
</style>

<style>
/* v69 P1b: dark mode 覆盖（v60-v67 教训：必须非 scoped） */
[data-theme="dark"] .meeting-item {
  background: var(--color-bg-card);
  border-color: var(--color-border);
}
[data-theme="dark"] .meeting-time-block {
  background: var(--color-bg-page);
}
[data-theme="dark"] .item-row {
  background: var(--color-bg-page);
}
[data-theme="dark"] .action-btn {
  background: var(--color-bg-card) !important;
  border-color: var(--color-border) !important;
}
[data-theme="dark"] .action-phone {
  border-color: rgba(var(--color-primary-rgb), 0.4) !important;
}
[data-theme="dark"] .action-phone:hover {
  color: var(--el-color-white) !important;
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), 0.4);
}
[data-theme="dark"] .action-view {
  color: var(--color-primary) !important;
  border-color: rgba(64, 158, 255, 0.4) !important;
}
/* v77 P2.5.4: fix --color-primary (橙) → --color-info (蓝) - 之前 dark hover 蓝按钮跳橙是 bug */
[data-theme="dark"] .action-view:hover {
  background: var(--color-info) !important;
  color: var(--el-color-white) !important;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.4);
}
[data-theme="dark"] .action-generate {
  color: var(--color-success) !important;
  border-color: rgba(103, 194, 58, 0.4) !important;
}
[data-theme="dark"] .action-generate:hover {
  background: var(--color-success) !important;
  color: var(--el-color-white) !important;
  box-shadow: 0 2px 8px rgba(103, 194, 58, 0.4);
}
[data-theme="dark"] .action-edit {
  color: var(--color-text-secondary) !important;
  border-color: rgba(144, 147, 153, 0.4) !important;
}
[data-theme="dark"] .action-edit:hover {
  background: var(--color-info) !important;
  color: var(--el-color-white) !important;
  box-shadow: 0 2px 8px rgba(144, 147, 153, 0.4);
}
[data-theme="dark"] .action-delete {
  color: var(--color-danger) !important;
  border-color: rgba(245, 108, 108, 0.4) !important;
}
[data-theme="dark"] .action-delete:hover {
  background: var(--color-danger) !important;
  color: var(--el-color-white) !important;
  box-shadow: 0 2px 8px rgba(245, 108, 108, 0.4);
}
[data-theme="dark"] .template-picker {
  background: var(--color-bg-page);
}
[data-theme="dark"] .template-card {
  background: var(--color-bg-card);
  border-color: var(--color-border);
}
[data-theme="dark"] .template-card.active {
  background: linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.08), rgba(var(--color-accent-rgb), 0.08));
}
[data-theme="dark"] .tpl-action:hover {
  background: var(--color-bg-page);
}
[data-theme="dark"] .meeting-info-bar {
  border-bottom-color: var(--color-border);
}

/* v77 P2.6-D: ocean / forest 主题 dialog header 装饰 + 模板卡选中态 */
[data-accent="ocean"] .el-dialog__header,
[data-accent="forest"] .el-dialog__header {
  background: var(--color-primary-bg);
  border-bottom: 1px solid var(--color-primary-border);
  border-top-left-radius: var(--radius-lg);
  border-top-right-radius: var(--radius-lg);
}
[data-theme="dark"][data-accent="ocean"] .el-dialog__header,
[data-theme="dark"][data-accent="forest"] .el-dialog__header {
  background: rgba(var(--color-primary-rgb), 0.10);
}
</style>

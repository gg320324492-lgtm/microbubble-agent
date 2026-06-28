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
            <el-button type="warning" @click="handleStartLiveCall">
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
// v77 P2.6-F.2 Step 4: 485 行 CSS 拆到独立 meeting-view.css
import './meeting/meeting-view.css'
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
import MeetingCreateDialog from './meeting/MeetingCreateDialog.vue'
import PasteAnalyzeDialog from '@/components/PasteAnalyzeDialog.vue'
import ProcessingDialog from '@/components/ProcessingDialog.vue'
import VoiceTestDialog from '@/components/VoiceTestDialog.vue'
import ParticipantAvatars from '@/components/ParticipantAvatars.vue'
import MeetingMinutesDialog from '@/components/meeting/MeetingMinutesDialog.vue'
import MeetingTemplateDialog from '@/components/meeting/MeetingTemplateDialog.vue'
import { Delete, Document, Plus, Microphone, Location, Search } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const memberStore = useMemberStore()

// 全局录音状态（v77 P2.6-F.2 Step 4: 听会流程改走 /meetings/room 全屏 MeetingRoomView，仅保留 startRecording/stopRecording 用于 onMounted 恢复检查）
const { recordingMeetingId: globalRecordingId, startRecording, stopRecording } = useRecordingState()
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

// 声纹通话测试
const showVoiceTest = ref(false)

// 挂断后处理进度弹窗
const processingDialogVisible = ref(false)
const processingMeetingId = ref(null)

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

// v77 P2.6-F.2 Step 4: 听会 UI 改全屏（与移动端对齐），MeetingRoomView.onRecordingStart 已支持无 meetingId 自动建会 (line 124-140)
// 桌面端 UX: 点开始听会 → 跳 /meetings/room → MeetingRoomView 接管录音/上传/后处理
const handleStartLiveCall = () => {
  router.replace('/meetings/room')
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

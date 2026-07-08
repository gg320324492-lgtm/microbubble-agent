<template>
  <div class="meeting-view">
    <!-- 铁律 31: tab 统一用 <TabStrip> -->
    <div class="tab-strip-wrapper">
      <TabStrip v-model="activeTab" :items="tabItems" aria-label="会议视图切换" />
    </div>

    <!-- Tab 1: 会议列表 (原内容) -->
    <div v-show="activeTab === 'meetings'" role="tabpanel"
      :aria-labelledby="`tab-strip-meetings`" class="tab-panel">
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
            <!-- 删除按钮 (修复 click 事件冒泡 + el-popconfirm @confirm 不触发) -->
            <!-- 2026-07-03 修复: el-popconfirm 用 ElTooltip trigger="click" 时,
                 reference 按钮的 click 实际被 ElTooltip 自己监听触发 popover,
                 而不是通过 Vue @click. 即便加 @click.stop 也挡不住 ElTooltip
                 内部的 reference click listener. 表现:
                 1. 点删除按钮 → click 仍冒泡到外层 meeting-item @click="viewMeeting"
                    → 用户被跳转到详情页, popconfirm 看起来"没反应"
                 2. 即便 popconfirm 弹出, 用户点确定后 confirm() emit("@confirm") 在某些
                    jsdom / 部分浏览器下不触发, 因为 popper 的 click 路径与原生 click
                    handler 冲突.
                 修复方案: 用 el-popover + 手动 ref 控制, 完全绕过 el-popconfirm.
                 点击外部自动关闭, 不依赖 trigger="click" 的隐式 click listener.
                 2026-07-08 二次修复: 原方案用 ref + popover.show() 控制弹框, 但
                 Element Plus 2.4.4 的 el-popover __expose 只暴露 popperRef + hide,
                 不暴露 show(). 调 popoverRef?.show?.() 返回 undefined, "确定删除"
                 弹框永远不弹, 用户看到"点了删除按钮没反应". 改用 :visible + @update:visible
                 受控 prop 范式:visible 在 el-popover props/emits 都有定义, 转发到
                 内层 ElTooltip 走 useTooltipModelToggle 受控路径, 不依赖 ref 暴露. -->
            <el-popover
              :width="220"
              placement="top"
              trigger="manual"
              :show-arrow="false"
              popper-class="delete-meeting-popover"
              :visible="!!deletePopoverVisible[meeting.id]"
              @update:visible="(v) => onDeletePopoverVisibleChange(meeting.id, v)"
            >
              <template #reference>
                <el-button
                  type="danger"
                  size="small"
                  :data-delete-ref-id="meeting.id"
                  @click.stop="openDeletePopover(meeting.id)"
                >删除</el-button>
              </template>
              <div class="delete-popover-content">
                <p class="delete-popover-title">确定删除此会议？</p>
                <div class="delete-popover-actions">
                  <el-button size="small" @click.stop="closeDeletePopover(meeting.id)">取消</el-button>
                  <el-button type="danger" size="small" @click.stop="confirmDelete(meeting.id)">确定删除</el-button>
                </div>
              </div>
            </el-popover>
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
    </div>

      <!-- 创建会议对话框 -->
    <!-- 创建/编辑会议对话框 (2026-07-03: 模板管理删除, 不再传 :templates) -->
    <MeetingCreateDialog
      v-model:visible="showCreateDialog"
      :is-mobile="isMobile"
      :editing-id="editingMeetingId"
      :editing-data="editingMeetingData"
      @success="onMeetingSaved"
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
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import { VideoCamera, Document } from '@element-plus/icons-vue'
import { getStatusType, getStatusLabel } from '@/utils/task'
import { useMemberStore } from '@/stores/member'
import { useMeeting } from '@/composables/useMeeting'
import { useRecordingState } from '@/composables/useRecordingState'
import TabStrip from '@/components/common/TabStrip.vue'
import MeetingCreateDialog from './meeting/MeetingCreateDialog.vue'
import PasteAnalyzeDialog from '@/components/PasteAnalyzeDialog.vue'
import ProcessingDialog from '@/components/ProcessingDialog.vue'
import VoiceTestDialog from '@/components/VoiceTestDialog.vue'
import ParticipantAvatars from '@/components/ParticipantAvatars.vue'
import MeetingMinutesDialog from '@/components/meeting/MeetingMinutesDialog.vue'
import { Delete, Plus, Microphone, Location, Search } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'

const router = useRouter()
const route = useRoute()
const memberStore = useMemberStore()

// v78 UI redesign: 模板管理 tab 已删除 (2026-07-03 用户决策), 现在只剩 1 tab "会议列表"
// 保留 VALID_TABS / tabItems / TabStrip 框架, 方便未来加新 tab
const VALID_TABS = ['meetings']
const activeTab = ref(
  route.query.tab && VALID_TABS.includes(String(route.query.tab))
    ? String(route.query.tab)
    : 'meetings'
)

// 铁律 30: EP 图标 named import + 通过 props 传入
const tabItems = [
  { key: 'meetings',  label: '会议列表', icon: VideoCamera },
]

// 铁律 29: tab → URL 同步（router.replace 不污染 history, 合并其他 query）
watch(activeTab, (tab) => {
  router.replace({ query: { ...route.query, tab } })
})

// 铁律 29: URL → tab 反向同步（浏览器前进/后退）
watch(() => route.query.tab, (t) => {
  if (t && VALID_TABS.includes(String(t)) && String(t) !== activeTab.value) {
    activeTab.value = String(t)
  }
})

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

// 删除按钮 popover 控制 (2026-07-08 修复: 见 template 注释)
// 改用 :visible 受控 prop 范式, 不用 ref.show() (EP 2.4.4 el-popover __expose 不暴露 show)
const deletePopoverVisible = reactive({})

// 当前打开的 popover meeting id (用于外部 click 关闭 + 互斥单开)
const activeDeletePopoverId = ref(null)

function onDeletePopoverVisibleChange(id, v) {
  deletePopoverVisible[id] = v
  // 弹框被关闭 (包括点外部/ESC/取消) 时清空 active 标记
  if (!v && activeDeletePopoverId.value === id) {
    activeDeletePopoverId.value = null
  }
}

function openDeletePopover(id) {
  // 关闭其他 popover
  Object.keys(deletePopoverVisible).forEach((mid) => {
    if (Number(mid) !== id) deletePopoverVisible[mid] = false
  })
  activeDeletePopoverId.value = id
  deletePopoverVisible[id] = true
}

function closeDeletePopover(id) {
  activeDeletePopoverId.value = null
  deletePopoverVisible[id] = false
}

async function confirmDelete(id) {
  // 立即关闭 popover
  closeDeletePopover(id)
  try {
    await deleteMeetingApi(id)
    ElMessage.success('会议已删除')
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// 保留旧函数名作为 alias, 以防其他代码引用 (向后兼容)
const deleteMeeting = confirmDelete

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
  templateId: null,  // 保留兼容旧数据, 不再写入 (2026-07-03 模板管理删除)
  title: '', start_time: '', location: '', participants: [], description: '',
  summary: '', key_points: [], decisions: [],
  agenda: [],  // Wave 3b: 会议议程
  remindBefore: true,
})

// 关闭会议创建对话框时清理编辑状态
function onCreateDialogClose() {
  editingMeetingId.value = null
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

  // 2026-07-03 修复: 删除 popover 外部点击关闭
  // el-popover trigger="manual" 不自动关闭, 需要手动监听 document click
  // 排除: ① popover 内部 ② 删除按钮 reference 本身
  const handleDocClick = (e) => {
    if (!activeDeletePopoverId.value) return
    const popoverEl = document.querySelector('.delete-meeting-popover')
    const target = e.target
    const inPopover = popoverEl?.contains(target)
    // 检查是否点击当前 reference 按钮 (通过 data-meeting-id 标记)
    const refBtn = target.closest?.(`[data-delete-ref-id="${activeDeletePopoverId.value}"]`)
    if (!inPopover && !refBtn) {
      closeDeletePopover(activeDeletePopoverId.value)
    }
  }
  document.addEventListener('click', handleDocClick)
  onUnmounted(() => document.removeEventListener('click', handleDocClick))

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

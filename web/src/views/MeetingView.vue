<template>
  <div class="meeting-view">
    <!-- 顶部操作栏 -->
    <el-card class="filter-card">
      <el-row :gutter="16" align="middle">
        <el-col :xs="24" :sm="12" :md="8">
          <el-date-picker
            v-model="dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            @change="fetchMeetings"
          />
        </el-col>
        <el-col :xs="24" :sm="12" :md="8">
          <el-input
            v-model="keyword"
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
          <el-button type="primary" @click="showCreateDialog = true">
            <el-icon><Plus /></el-icon>
            创建会议
          </el-button>
          <el-button type="success" @click="pasteAnalyzeDialogRef?.open()">
            <el-icon><Document /></el-icon>
            粘贴转录分析
          </el-button>
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
              <el-tag :type="getStatusType(meeting.status)" size="small">
                {{ getStatusLabel(meeting.status) }}
              </el-tag>
              <span v-if="meeting.location" class="meeting-location">
                <el-icon><Location /></el-icon>
                {{ meeting.location }}
              </span>
            </div>
            <div v-if="meeting.summary" class="meeting-summary">
              {{ meeting.summary.substring(0, 100) }}...
            </div>
          </div>

          <div class="meeting-actions">
            <el-button
              v-if="meeting.status === 'scheduled'"
              type="primary"
              size="small"
              @click.stop="startTranscript(meeting)"
            >
              <el-icon><VideoCamera /></el-icon>
              开始转写
            </el-button>
            <el-button
              v-if="meeting.status === 'recording'"
              type="warning"
              size="small"
              @click.stop="startTranscript(meeting)"
            >
              <el-icon><VideoCamera /></el-icon>
              继续转写
            </el-button>
            <el-button
              v-if="meeting.transcript && !meeting.summary"
              type="success"
              size="small"
              @click.stop="generateMinutes(meeting)"
            >
              生成纪要
            </el-button>
            <el-button
              type="primary"
              size="small"
              @click.stop="startLiveCall(meeting)"
            >
              <el-icon><Phone /></el-icon>
              声纹通话
            </el-button>
            <el-button
              v-if="meeting.summary"
              size="small"
              @click.stop="viewMinutes(meeting)"
            >
              查看纪要
            </el-button>
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
    <el-dialog v-model="showCreateDialog" title="创建会议" :width="isMobile ? '90vw' : '500px'" top="8vh">
      <el-form :model="meetingForm" label-width="80px">
        <el-form-item label="会议主题" required>
          <el-input v-model="meetingForm.title" placeholder="请输入会议主题" />
        </el-form-item>
        <el-form-item label="会议时间" required>
          <el-date-picker
            v-model="meetingForm.start_time"
            type="datetime"
            placeholder="选择会议时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="会议地点">
          <el-input v-model="meetingForm.location" placeholder="请输入会议地点" />
        </el-form-item>
        <el-form-item label="参会人员">
          <el-select
            v-model="meetingForm.participants"
            multiple
            placeholder="选择参会人员"
          >
            <el-option
              v-for="member in members"
              :key="member.id"
              :label="member.name"
              :value="member.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="会议说明">
          <el-input
            v-model="meetingForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入会议说明"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="createMeeting">创建</el-button>
      </template>
    </el-dialog>

    <!-- 实时转写对话框 -->
    <el-dialog v-model="showTranscriptDialog" title="会议实时转写" :width="isMobile ? '95vw' : '800px'" :close-on-click-modal="false" top="5vh">
      <div v-if="currentMeeting" class="transcript-dialog-content">
        <div class="meeting-info-bar">
          <h3>{{ currentMeeting.title }}</h3>
          <el-tag :type="getStatusType(currentMeeting.status)">
            {{ getStatusLabel(currentMeeting.status) }}
          </el-tag>
        </div>
        <LiveTranscript
          ref="liveTranscriptRef"
          :meeting-id="currentMeeting.id"
          @transcript-complete="onTranscriptComplete"
          style="height: 500px"
        />
      </div>
    </el-dialog>

    <!-- 会议纪要对话框 -->
    <el-dialog v-model="showMinutesDialog" title="会议纪要" :width="isMobile ? '90vw' : '600px'" top="5vh">
      <div v-if="currentMeeting" class="minutes-content">
        <h3>{{ currentMeeting.title }}</h3>
        <div class="minutes-time">
          {{ formatDate(currentMeeting.start_time) }}
        </div>

        <div v-if="currentMeeting.summary" class="minutes-section">
          <h4>会议摘要</h4>
          <p>{{ currentMeeting.summary }}</p>
        </div>

        <div v-if="currentMeeting.key_points?.length" class="minutes-section">
          <h4>讨论要点</h4>
          <ul>
            <li v-for="(point, i) in currentMeeting.key_points" :key="i">{{ point }}</li>
          </ul>
        </div>

        <div v-if="currentMeeting.decisions?.length" class="minutes-section">
          <h4>决议事项</h4>
          <ul>
            <li v-for="(decision, i) in currentMeeting.decisions" :key="i">{{ decision }}</li>
          </ul>
        </div>
      </div>
    </el-dialog>

    <!-- 声纹通话对话框 -->
    <el-dialog
      v-model="showLiveCallDialog"
      :title="liveCallMeeting?.title || '声纹通话'"
      :width="isMobile ? '95vw' : '800px'"
      top="3vh"
      :close-on-click-modal="false"
      fullscreen
      @close="onLiveCallEnd"
    >
      <MeetingRoom
        v-if="showLiveCallDialog && liveCallMeeting"
        ref="meetingRoomRef"
        :meeting-id="liveCallMeeting.id"
        :meeting-title="liveCallMeeting.title"
        @meeting-ended="onLiveCallEnd"
        style="height: 70vh"
      />
    </el-dialog>

    <!-- 粘贴转录分析对话框 -->
    <PasteAnalyzeDialog ref="pasteAnalyzeDialogRef" @saved="fetchMeetings" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import { formatDateTime } from '@/utils/format'
import { getStatusType, getStatusLabel } from '@/utils/task'
import { useMemberStore } from '@/stores/member'
import LiveTranscript from '@/components/LiveTranscript.vue'
import PasteAnalyzeDialog from '@/components/PasteAnalyzeDialog.vue'
import MeetingRoom from '@/components/MeetingRoom.vue'
import { Phone } from '@element-plus/icons-vue'

const memberStore = useMemberStore()
const members = computed(() => memberStore.members)

const isMobile = ref(window.innerWidth <= 768)
const meetings = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const dateRange = ref([])
const keyword = ref('')
const showCreateDialog = ref(false)
const showMinutesDialog = ref(false)
const showTranscriptDialog = ref(false)
const currentMeeting = ref(null)
const liveTranscriptRef = ref(null)
const pasteAnalyzeDialogRef = ref(null)
const meetingRoomRef = ref(null)

// 声纹通话
const showLiveCallDialog = ref(false)
const liveCallMeeting = ref(null)

const startLiveCall = (meeting) => {
  liveCallMeeting.value = meeting
  showLiveCallDialog.value = true
}

const onLiveCallEnd = () => {
  showLiveCallDialog.value = false
  liveCallMeeting.value = null
  fetchMeetings()
}

const meetingForm = ref({
  title: '',
  start_time: '',
  location: '',
  participants: [],
  description: ''
})

// 获取会议列表
const fetchMeetings = async () => {
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      keyword: keyword.value
    }
    if (dateRange.value?.length === 2) {
      params.date_from = dateRange.value[0]
      params.date_to = dateRange.value[1]
    }
    const res = await axios.get('/api/v1/meetings', { params })
    meetings.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    console.error('获取会议失败:', e)
  }
}

// 获取成员列表（使用 store）
const fetchMembers = () => memberStore.fetchMembers()

// 创建会议
const createMeeting = async () => {
  if (!meetingForm.value.title || !meetingForm.value.start_time) {
    ElMessage.warning('请填写必填项')
    return
  }

  try {
    await axios.post('/api/v1/meetings', meetingForm.value)
    ElMessage.success('会议创建成功')
    showCreateDialog.value = false
    meetingForm.value = { title: '', start_time: '', location: '', participants: [], description: '' }
    fetchMeetings()
  } catch (e) {
    ElMessage.error('创建失败')
  }
}

// 查看会议详情
const viewMeeting = (meeting) => {
  currentMeeting.value = meeting
}

// 查看纪要
const viewMinutes = (meeting) => {
  currentMeeting.value = meeting
  showMinutesDialog.value = true
}

// 开始实时转写
const startTranscript = (meeting) => {
  currentMeeting.value = meeting
  showTranscriptDialog.value = true
}

// 转写完成回调
const onTranscriptComplete = async (transcriptItems) => {
  console.log('转写完成，共', transcriptItems.length, '条记录')
  ElMessage.success(`转写完成，共 ${transcriptItems.length} 条记录`)
  showTranscriptDialog.value = false
  fetchMeetings()
}

// 生成纪要
const generateMinutes = async (meeting) => {
  try {
    ElMessage.info('正在生成会议纪要...')
    await axios.post(`/api/v1/meetings/${meeting.id}/generate-minutes`)
    ElMessage.success('会议纪要生成成功')
    fetchMeetings()
  } catch (e) {
    ElMessage.error('生成失败')
  }
}

// 辅助函数
const formatMonth = (date) => dayjs(date).format('M月')
const formatDay = (date) => dayjs(date).format('D')
const formatHour = (date) => dayjs(date).format('HH:mm')
const formatDate = (date) => formatDateTime(date)

onMounted(() => {
  fetchMeetings()
  fetchMembers()
})
</script>

<style scoped>
.meeting-view {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  height: 100%;
  overflow-y: auto;
  animation: fadeSlideUp var(--duration-slower) var(--ease-out) both;
}

.filter-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) both;
}

.filter-card :deep(.el-card__body) {
  padding: var(--space-4) var(--space-5);
}

.meeting-list-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  animation: fadeSlideUp var(--duration-slow) var(--ease-out) 80ms both;
}

.meeting-list {
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
}

.meeting-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  justify-content: center;
}

.meeting-actions .el-button {
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}

.meeting-actions .el-button:hover {
  transform: scale(1.02);
}

.pagination {
  margin-top: var(--space-5);
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

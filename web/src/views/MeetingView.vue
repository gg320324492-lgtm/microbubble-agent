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
    <el-dialog v-model="showCreateDialog" title="创建会议" :width="isMobile ? '90vw' : '500px'">
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
    <el-dialog v-model="showTranscriptDialog" title="会议实时转写" :width="isMobile ? '95vw' : '800px'" :close-on-click-modal="false">
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
    <el-dialog v-model="showMinutesDialog" title="会议纪要" :width="isMobile ? '90vw' : '600px'">
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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import LiveTranscript from '@/components/LiveTranscript.vue'

const isMobile = ref(window.innerWidth <= 768)
const meetings = ref([])
const members = ref([])
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

// 获取成员列表
const fetchMembers = async () => {
  try {
    const res = await axios.get('/api/v1/members')
    members.value = res.data.items || []
  } catch (e) {
    console.error('获取成员失败:', e)
  }
}

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
const formatDate = (date) => dayjs(date).format('YYYY-MM-DD HH:mm')

const getStatusType = (status) => {
  const map = { scheduled: 'info', recording: 'warning', completed: 'success' }
  return map[status] || 'info'
}

const getStatusLabel = (status) => {
  const map = { scheduled: '待开始', recording: '录制中', completed: '已完成' }
  return map[status] || status
}

onMounted(() => {
  fetchMeetings()
  fetchMembers()
})
</script>

<style scoped>
.meeting-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.meeting-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.meeting-item {
  display: flex;
  gap: 20px;
  padding: 16px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #ebeef5;
  cursor: pointer;
  transition: all 0.3s;
}

.meeting-item:hover {
  border-color: #409eff;
  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.1);
}

.meeting-time-block {
  min-width: 80px;
  text-align: center;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 8px;
}

.time-month {
  font-size: 12px;
  color: #909399;
}

.time-day {
  font-size: 28px;
  font-weight: bold;
  color: #409eff;
  line-height: 1.2;
}

.time-hour {
  font-size: 14px;
  color: #606266;
}

.meeting-info {
  flex: 1;
}

.meeting-title {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
  margin-bottom: 8px;
}

.meeting-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.meeting-location {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: #909399;
}

.meeting-summary {
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

.meeting-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  justify-content: center;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.minutes-content h3 {
  margin-bottom: 8px;
}

.minutes-time {
  color: #909399;
  margin-bottom: 20px;
}

.minutes-section {
  margin-bottom: 20px;
}

.minutes-section h4 {
  margin-bottom: 10px;
  color: #303133;
}

.minutes-section ul {
  padding-left: 20px;
}

.minutes-section li {
  margin-bottom: 8px;
  line-height: 1.5;
}

.transcript-dialog-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.meeting-info-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;
}

.meeting-info-bar h3 {
  margin: 0;
  font-size: 18px;
  color: #303133;
}

@media (max-width: 768px) {
  .meeting-item {
    flex-direction: column;
    gap: 12px;
  }
  .meeting-time-block {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: unset;
  }
  .meeting-actions {
    flex-direction: row;
    flex-wrap: wrap;
  }
}
</style>

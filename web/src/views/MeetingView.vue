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
          <div class="top-actions">
            <el-button type="primary" @click="showCreateDialog = true">
              <el-icon><Plus /></el-icon> 手动创建
            </el-button>
            <el-button type="success" @click="pasteAnalyzeDialogRef?.open()">
              <el-icon><Document /></el-icon> 粘贴转录分析
            </el-button>
            <el-button type="warning" @click="startVoiceCreate">
              <el-icon><Microphone /></el-icon> 声纹创建会议
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
    <el-dialog v-model="showCreateDialog" :title="editingMeetingId ? '编辑会议' : '创建会议'" :width="isMobile ? '90vw' : '500px'" top="8vh" @close="editingMeetingId = null">
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
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <el-select v-model="meetingForm.participants" multiple filterable collapse-tags collapse-tags-tooltip placeholder="选择参会人员" style="flex:1;min-width:200px">
              <el-option v-for="member in members" :key="member.id" :label="member.name" :value="member.id" />
            </el-select>
            <el-button size="small" @click="meetingForm.participants = members.map(m=>m.id)">全选</el-button>
          </div>
        </el-form-item>
        <el-form-item label="会议说明">
          <el-input
            v-model="meetingForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入会议说明"
          />
        </el-form-item>

        <!-- 编辑已有会议时显示纪要字段 -->
        <template v-if="editingMeetingId">
          <el-divider content-position="left">
            <el-icon><Document /></el-icon> 会议纪要
          </el-divider>
          <el-form-item label="摘要">
            <el-input
              v-model="meetingForm.summary"
              type="textarea"
              :rows="3"
              placeholder="会议摘要..."
              class="minutes-textarea"
            />
          </el-form-item>
          <el-form-item label="讨论要点">
            <div class="item-list">
              <div v-for="(point, i) in meetingForm.key_points" :key="'kp'+i" class="item-row">
                <span class="item-dot" />
                <el-input v-model="meetingForm.key_points[i]" size="default" placeholder="输入要点..." />
                <el-button :icon="Delete" circle size="small" class="item-del" @click="meetingForm.key_points.splice(i, 1)" />
              </div>
              <el-button dashed size="small" class="item-add" @click="meetingForm.key_points.push('')">
                <el-icon><Plus /></el-icon> 添加要点
              </el-button>
            </div>
          </el-form-item>
          <el-form-item label="决议事项">
            <div class="item-list">
              <div v-for="(d, i) in meetingForm.decisions" :key="'dc'+i" class="item-row decision">
                <span class="item-dot decision-dot" />
                <el-input v-model="meetingForm.decisions[i]" size="default" placeholder="输入决议..." />
                <el-button :icon="Delete" circle size="small" class="item-del" @click="meetingForm.decisions.splice(i, 1)" />
              </div>
              <el-button dashed size="small" class="item-add decision-add" @click="meetingForm.decisions.push('')">
                <el-icon><Plus /></el-icon> 添加决议
              </el-button>
            </div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="submitMeeting">{{ editingMeetingId ? '保存' : '创建' }}</el-button>
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
        @call-ended="onCallEnded(liveCallMeeting.id)"
        style="height: 70vh"
      />
    </el-dialog>

    <!-- 粘贴转录分析对话框 -->
    <PasteAnalyzeDialog ref="pasteAnalyzeDialogRef" @saved="fetchMeetings" />

    <!-- 挂断后会后处理进度对话框 -->
    <ProcessingDialog
      v-if="processingDialogVisible && processingMeetingId"
      :meeting-id="processingMeetingId"
      @close="processingDialogVisible = false"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()
import axios from 'axios'
import dayjs from 'dayjs'
import { formatDateTime } from '@/utils/format'
import { getStatusType, getStatusLabel } from '@/utils/task'
import { useMemberStore } from '@/stores/member'
import LiveTranscript from '@/components/LiveTranscript.vue'
import PasteAnalyzeDialog from '@/components/PasteAnalyzeDialog.vue'
import MeetingRoom from '@/components/MeetingRoom.vue'
import ProcessingDialog from '@/components/ProcessingDialog.vue'
import { Phone, Edit, Delete, Document, MagicStick, Plus, Microphone } from '@element-plus/icons-vue'

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

// 挂断后处理进度弹窗
const processingDialogVisible = ref(false)
const processingMeetingId = ref(null)

function onCallEnded(meetingId) {
  // 关闭通话弹窗，弹出会后处理进度对话框
  showLiveCallDialog.value = false
  liveCallMeeting.value = null
  fetchMeetings()
  if (meetingId) {
    processingMeetingId.value = meetingId
    processingDialogVisible.value = true
  }
}

// 编辑会议
const editMeeting = (meeting) => {
  meetingForm.value = {
    title: meeting.title,
    start_time: meeting.start_time,
    location: meeting.location || '',
    participants: meeting.participants?.map(p => p.member_id) || [],
    description: meeting.description || '',
    summary: meeting.summary || '',
    key_points: meeting.key_points ? [...meeting.key_points] : [],
    decisions: meeting.decisions ? [...meeting.decisions] : [],
  }
  editingMeetingId.value = meeting.id
  showCreateDialog.value = true
}

const editingMeetingId = ref(null)

const deleteMeeting = async (id) => {
  try {
    await axios.delete(`/api/v1/meetings/${id}`)
    ElMessage.success('会议已删除')
    fetchMeetings()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

// 创建/更新会议
const submitMeeting = async () => {
  if (!meetingForm.value.title || !meetingForm.value.start_time) {
    ElMessage.warning('请填写必填项')
    return
  }
  try {
    if (editingMeetingId.value) {
      await axios.put(`/api/v1/meetings/${editingMeetingId.value}`, meetingForm.value)
      ElMessage.success('会议已更新')
    } else {
      await axios.post('/api/v1/meetings', meetingForm.value)
      ElMessage.success('会议创建成功')
    }
    showCreateDialog.value = false
    editingMeetingId.value = null
    meetingForm.value = { title: '', start_time: '', location: '', participants: [], description: '', summary: '', key_points: [], decisions: [] }
    fetchMeetings()
  } catch (e) {
    ElMessage.error(editingMeetingId.value ? '更新失败' : '创建失败')
  }
}

// 声纹创建会议 (从顶栏点击，先快速创建占位会议再开始通话)
const startVoiceCreate = async () => {
  try {
    const res = await axios.post('/api/v1/meetings', {
      title: '声纹会议 ' + dayjs().format('MM-DD HH:mm'),
      start_time: dayjs().format('YYYY-MM-DD HH:mm:ss'),
    })
    liveCallMeeting.value = res.data
    showLiveCallDialog.value = true
    fetchMeetings()
  } catch (e) {
    ElMessage.error('创建会议失败')
  }
}

const startLiveCall = (meeting) => {
  liveCallMeeting.value = meeting
  showLiveCallDialog.value = true
}

const meetingForm = ref({
  title: '', start_time: '', location: '', participants: [], description: '',
  summary: '', key_points: [], decisions: [],
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

// 查看会议详情 → 跳转全屏详情页
const viewMeeting = (meeting) => {
  router.push(`/meetings/${meeting.id}`)
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
  background: #fff !important;
  transition: all 0.2s ease !important;
}
.action-btn:hover {
  transform: translateY(-1px);
}
.action-phone { color: var(--color-primary) !important; border-color: rgba(255,122,92,0.3) !important; }
.action-phone:hover { background: var(--color-primary) !important; color: #fff !important; border-color: var(--color-primary) !important; box-shadow: 0 2px 8px rgba(255,122,92,0.3); }

.action-view { color: #409EFF !important; border-color: rgba(64,158,255,0.3) !important; }
.action-view:hover { background: #409EFF !important; color: #fff !important; border-color: #409EFF !important; box-shadow: 0 2px 8px rgba(64,158,255,0.3); }

.action-generate { color: #67C23A !important; border-color: rgba(103,194,58,0.3) !important; }
.action-generate:hover { background: #67C23A !important; color: #fff !important; border-color: #67C23A !important; box-shadow: 0 2px 8px rgba(103,194,58,0.3); }

.action-edit { color: #909399 !important; border-color: rgba(144,147,153,0.3) !important; }
.action-edit:hover { background: #909399 !important; color: #fff !important; border-color: #909399 !important; box-shadow: 0 2px 8px rgba(144,147,153,0.3); }

.action-delete { color: #F56C6C !important; border-color: rgba(245,108,108,0.3) !important; }
.action-delete:hover { background: #F56C6C !important; color: #fff !important; border-color: #F56C6C !important; box-shadow: 0 2px 8px rgba(245,108,108,0.3); }

/* 纪要编辑列表 */
.minutes-textarea :deep(.el-textarea__inner) { border-radius: var(--radius-md); border-color: var(--color-border); }
.item-list { display: flex; flex-direction: column; gap: 8px; }
.item-row {
  display: flex; align-items: center; gap: 10px;
  padding: 6px 10px; background: var(--color-bg-page); border-radius: var(--radius-md);
  border: 1px solid transparent; transition: all 0.2s;
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

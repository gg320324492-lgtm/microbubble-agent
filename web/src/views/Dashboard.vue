<template>
  <div class="dashboard">
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <div class="welcome-left">
        <div class="greeting">{{ greeting }}，{{ username }}！</div>
        <div class="date-time">
          <span class="date">{{ currentDate }}</span>
          <span class="time">{{ currentTime }}</span>
        </div>
        <div class="quick-tip" v-if="dashboardData.summary">
          <template v-if="dashboardData.summary.overdue_tasks > 0">
            <el-badge :value="dashboardData.summary.overdue_tasks" type="danger">
              <span class="tip-text">您有 {{ dashboardData.summary.overdue_tasks }} 项逾期任务</span>
            </el-badge>
          </template>
          <template v-else-if="dashboardData.summary.in_progress_tasks > 0">
            <span class="tip-text success">🎯 您有 {{ dashboardData.summary.in_progress_tasks }} 项任务进行中</span>
          </template>
          <template v-else>
            <span class="tip-text">今日任务已完成，继续保持！</span>
          </template>
        </div>
      </div>
      <div class="welcome-right">
        <el-button type="primary" size="large" @click="$router.push('/chat')">
          <el-icon><ChatDotRound /></el-icon>
          开始对话
        </el-button>
        <el-button size="large" @click="showCreateTask = true">
          <el-icon><Plus /></el-icon>
          创建任务
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <el-col :xs="12" :sm="6">
        <div class="stat-card total">
          <div class="stat-ring">
            <el-progress type="circle" :percentage="completionRate" :width="80" :stroke-width="8"
              :color="completionColor">
              <template #default>
                <div class="ring-value">{{ dashboardData.summary?.done_tasks || 0 }}</div>
                <div class="ring-label">已完成</div>
              </template>
            </el-progress>
          </div>
          <div class="stat-detail">
            <div class="stat-title">总任务数</div>
            <div class="stat-number">{{ dashboardData.summary?.total_tasks || 0 }}</div>
            <div class="stat-sub">进行中 {{ dashboardData.summary?.in_progress_tasks || 0 }}</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card in-progress">
          <div class="stat-icon-lg">
            <el-icon size="32"><Clock /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboardData.summary?.in_progress_tasks || 0 }}</div>
            <div class="stat-label">进行中</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card done">
          <div class="stat-icon-lg">
            <el-icon size="32"><CircleCheck /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboardData.summary?.done_tasks || 0 }}</div>
            <div class="stat-label">已完成</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="6">
        <div class="stat-card overdue" :class="{ 'has-overdue': dashboardData.summary?.overdue_tasks > 0 }">
          <div class="stat-icon-lg">
            <el-icon size="32"><Warning /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboardData.summary?.overdue_tasks || 0 }}</div>
            <div class="stat-label">已逾期</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 进行中任务（合并待办+进行中，按负责人分组） -->
    <el-card class="content-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>🚀 进行中任务</span>
          <el-badge :value="inProgressTasks.length" type="primary" :hidden="inProgressTasks.length === 0" />
          <el-button text @click="$router.push('/tasks')">查看全部 →</el-button>
        </div>
      </template>
      <div v-if="inProgressTasks.length === 0" class="empty-state">
        <el-empty description="暂无进行中任务" :image-size="60" />
      </div>
      <div v-else class="task-groups">
        <div v-for="group in groupedTasks" :key="group.assignee_id" class="task-group">
          <!-- 负责人头部 -->
          <div class="group-header">
            <el-avatar
              v-if="memberStore.getMemberAvatar(group.assignee_id)"
              :src="memberStore.getMemberAvatar(group.assignee_id)"
              :size="40"
              class="group-avatar"
            />
            <el-avatar
              v-else
              :size="40"
              style="background: #409eff"
              class="group-avatar"
            >
              {{ memberStore.getMemberName(group.assignee_id).charAt(0) }}
            </el-avatar>
            <div class="group-info">
              <span class="group-name">{{ memberStore.getMemberName(group.assignee_id) }}</span>
              <el-tag size="small" type="info">{{ group.tasks.length }} 项任务</el-tag>
            </div>
          </div>
          <!-- 任务列表 -->
          <div class="group-tasks">
            <div
              v-for="task in group.tasks"
              :key="task.id"
              class="task-row"
              :class="{ overdue: isOverdue(task.due_date) }"
            >
              <el-checkbox
                :model-value="task.status === 'done'"
                @change="toggleTaskStatus(task)"
                size="large"
              />
              <div class="task-content">
                <div class="task-title">{{ task.title }}</div>
                <div class="task-meta">
                  <el-tag :type="getPriorityType(task.priority)" size="small" effect="plain">
                    {{ getPriorityLabel(task.priority) }}
                  </el-tag>
                  <el-tag v-if="task.status === 'in_progress'" size="small" type="warning">进行中</el-tag>
                </div>
              </div>
              <div class="task-due" :class="{ overdue: isOverdue(task.due_date) }">
                <el-icon v-if="isOverdue(task.due_date)" color="#f56c6c"><Warning /></el-icon>
                {{ formatDate(task.due_date) }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 即将到期任务 -->
    <el-card class="upcoming-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>⏰ 即将到期</span>
          <el-tag size="small" type="warning">未来3天</el-tag>
        </div>
      </template>
      <div v-if="upcomingDeadlines.length === 0" class="empty-state-sm">
        <el-empty description="未来3天没有即将到期的任务" :image-size="40" />
      </div>
      <div v-else class="upcoming-list">
        <div v-for="task in upcomingDeadlines" :key="task.id" class="upcoming-item" :class="{ 'overdue': isOverdue(task.due_date) }">
          <div class="upcoming-left">
            <el-checkbox :model-value="task.status === 'done'" @change="toggleTaskStatus(task)" size="large" />
            <div class="upcoming-info">
              <div class="upcoming-title">{{ task.title }}</div>
              <div class="upcoming-meta">
                <el-tag :type="getPriorityType(task.priority)" size="small" effect="plain">
                  {{ getPriorityLabel(task.priority) }}
                </el-tag>
                <span class="upcoming-assignee">{{ memberStore.getMemberName(task.assignee_id) }}</span>
              </div>
            </div>
          </div>
          <div class="upcoming-right">
            <div class="due-days" :class="{ urgent: getDaysLeft(task.due_date) <= 1 }">
              {{ getDaysLeftText(task.due_date) }}
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 最近会议 -->
    <el-card class="content-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>📅 最近会议</span>
          <el-button text @click="$router.push('/meetings')">查看全部 →</el-button>
        </div>
      </template>
      <div v-if="recentMeetings.length === 0" class="empty-state">
        <el-empty description="暂无会议记录" :image-size="60" />
      </div>
      <div v-else class="meeting-list">
        <div v-for="meeting in recentMeetings" :key="meeting.id" class="meeting-item">
          <div class="meeting-date">
            <div class="date-box">
              <span class="month">{{ formatMonth(meeting.start_time) }}</span>
              <span class="day">{{ formatDay(meeting.start_time) }}</span>
            </div>
          </div>
          <div class="meeting-info">
            <div class="meeting-title">{{ meeting.title }}</div>
            <div class="meeting-meta">
              <span class="meeting-time">
                <el-icon><Clock /></el-icon>
                {{ formatMeetingTime(meeting.start_time) }}
              </span>
              <el-tag :type="getStatusTagType(meeting.status)" size="small">
                {{ getMeetingStatusLabel(meeting.status) }}
              </el-tag>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 创建任务对话框 -->
    <el-dialog v-model="showCreateTask" title="创建任务" :width="isMobile ? '90vw' : '500px'">
      <el-form :model="newTask" label-width="80px">
        <el-form-item label="任务标题" required>
          <el-input v-model="newTask.title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="newTask.assignee_id" placeholder="选择负责人" clearable>
            <el-option v-for="member in members" :key="member.id" :label="member.name" :value="member.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="newTask.priority">
            <el-radio label="high">高</el-radio>
            <el-radio label="medium">中</el-radio>
            <el-radio label="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker v-model="newTask.due_date" type="datetime" placeholder="选择截止日期和时间"
            format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input v-model="newTask.description" type="textarea" :rows="3" placeholder="请输入任务描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateTask = false">取消</el-button>
        <el-button type="primary" @click="createTask">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import { formatCompactDate } from '@/utils/format'
import { getStatusType, getStatusLabel, getPriorityType, getPriorityLabel } from '@/utils/task'
import { useMemberStore } from '@/stores/member'
import { useUserStore } from '@/stores/user'

const memberStore = useMemberStore()
const userStore = useUserStore()
const members = computed(() => memberStore.members)

const dashboardData = ref({})
const inProgressTasks = ref([])
const recentMeetings = ref([])
const upcomingDeadlines = ref([])
const showCreateTask = ref(false)
const isMobile = ref(window.innerWidth <= 768)
const currentTime = ref('')
const currentDate = ref('')

const handleResize = () => { isMobile.value = window.innerWidth <= 768 }
const updateTime = () => {
  const now = dayjs()
  currentTime.value = now.format('HH:mm:ss')
  currentDate.value = now.format('YYYY年MM月DD日 dddd')
}

onUnmounted(() => { window.removeEventListener('resize', handleResize) })

const newTask = ref({ title: '', assignee_id: null, priority: 'medium', due_date: '', description: '' })

const username = computed(() => userStore.username || '用户')

const greeting = computed(() => {
  const hour = dayjs().hour()
  if (hour < 12) return '早上好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const completionRate = computed(() => {
  const total = dashboardData.value.summary?.total_tasks || 0
  const done = dashboardData.value.summary?.done_tasks || 0
  if (total === 0) return 0
  return Math.round((done / total) * 100)
})

const completionColor = computed(() => {
  const rate = completionRate.value
  if (rate >= 80) return '#67c23a'
  if (rate >= 50) return '#409eff'
  if (rate >= 30) return '#e6a23c'
  return '#f56c6c'
})

const fetchDashboardStats = async () => {
  try {
    const res = await axios.get('/api/v1/dashboard/stats')
    dashboardData.value = res.data
  } catch (e) { console.error('获取仪表盘数据失败:', e) }
}

// 获取进行中任务（合并待办+进行中）
const fetchInProgressTasks = async () => {
  try {
    // 并行获取 todo 和 in_progress 任务
    const [todoRes, inProgressRes] = await Promise.all([
      axios.get('/api/v1/tasks', { params: { status: 'todo', page_size: 20 } }),
      axios.get('/api/v1/tasks', { params: { status: 'in_progress', page_size: 20 } })
    ])
    const todoItems = todoRes.data.items || []
    const inProgressItems = inProgressRes.data.items || []
    // 合并并排序：优先按状态（进行中 > 待办），再按创建日期（最新在前）
    const allTasks = [...todoItems, ...inProgressItems]
    allTasks.sort((a, b) => {
      // 第一优先：状态（in_progress 排前面）
      if (a.status === 'in_progress' && b.status !== 'in_progress') return -1
      if (a.status !== 'in_progress' && b.status === 'in_progress') return 1
      // 第二优先：创建日期（最新的在前）
      return dayjs(b.created_at).diff(dayjs(a.created_at))
    })
    inProgressTasks.value = allTasks
  } catch (e) { console.error('获取进行中任务失败:', e) }
}

// 按负责人分组
const groupedTasks = computed(() => {
  const groups = {}
  for (const task of inProgressTasks.value) {
    const id = task.assignee_id || 'unassigned'
    if (!groups[id]) {
      groups[id] = { assignee_id: id, tasks: [] }
    }
    groups[id].tasks.push(task)
  }
  return Object.values(groups).sort((a, b) => {
    // 按时长逾期分组显示
    const aHasOverdue = a.tasks.some(t => isOverdue(t.due_date))
    const bHasOverdue = b.tasks.some(t => isOverdue(t.due_date))
    if (aHasOverdue && !bHasOverdue) return -1
    if (!aHasOverdue && bHasOverdue) return 1
    // 按任务数量降序
    return b.tasks.length - a.tasks.length
  })
})

const fetchRecentMeetings = async () => {
  try {
    const res = await axios.get('/api/v1/meetings', { params: { page_size: 5 } })
    recentMeetings.value = res.data.items || []
  } catch (e) { console.error('获取会议失败:', e) }
}

const fetchUpcomingDeadlines = async () => {
  try {
    const now = dayjs()
    const threeDaysLater = now.add(3, 'day').endOf('day').toISOString()
    const res = await axios.get('/api/v1/tasks', {
      params: {
        page_size: 10,
        status: 'in_progress',
        due_before: threeDaysLater
      }
    })
    upcomingDeadlines.value = res.data.items || []
  } catch (e) { console.error('获取即将到期任务失败:', e) }
}

const fetchMembers = () => memberStore.fetchMembers()

const createTask = async () => {
  if (!newTask.value.title) { ElMessage.warning('请输入任务标题'); return }
  try {
    await axios.post('/api/v1/tasks', newTask.value)
    ElMessage.success('任务创建成功')
    showCreateTask.value = false
    newTask.value = { title: '', assignee_id: null, priority: 'medium', due_date: '', description: '' }
    fetchInProgressTasks()
    fetchDashboardStats()
    fetchUpcomingDeadlines()
  } catch (e) { ElMessage.error('创建任务失败') }
}

const toggleTaskStatus = async (task) => {
  const newStatus = task.status === 'done' ? 'todo' : 'done'
  try {
    await axios.put(`/api/v1/tasks/${task.id}`, { status: newStatus })
    fetchInProgressTasks()
    fetchDashboardStats()
    fetchUpcomingDeadlines()
  } catch (e) { ElMessage.error('更新失败') }
}

const formatDate = (date) => formatCompactDate(date, '无截止')
const formatDay = (date) => date ? dayjs(date).format('DD') : '--'
const formatMonth = (date) => date ? dayjs(date).format('MM月') : '--'
const formatMeetingTime = (date) => date ? dayjs(date).format('HH:mm') : '--'
const getStatusTagType = (status) => {
  const map = { scheduled: 'info', recording: 'warning', completed: 'success', cancelled: 'info' }
  return map[status] || 'info'
}
const getMeetingStatusLabel = (status) => {
  const map = { scheduled: '已安排', recording: '录制中', completed: '已完成', cancelled: '已取消' }
  return map[status] || status
}

const isOverdue = (date) => date && dayjs(date).isBefore(dayjs())

const getDaysLeft = (date) => {
  if (!date) return null
  return dayjs(date).diff(dayjs(), 'day')
}

const getDaysLeftText = (date) => {
  const days = getDaysLeft(date)
  if (days < 0) return '已逾期'
  if (days === 0) return '今天到期'
  if (days === 1) return '明天到期'
  return `${days}天后到期`
}

onMounted(() => {
  updateTime()
  setInterval(updateTime, 1000)
  fetchDashboardStats()
  fetchInProgressTasks()
  fetchUpcomingDeadlines()
  fetchRecentMeetings()
  memberStore.refreshMembers() // 强制刷新获取最新头像
  window.addEventListener('resize', handleResize)
})
</script>

<style scoped>
.dashboard { max-width: 1400px; padding-bottom: 30px; }

/* 欢迎区 */
.welcome-section {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  padding: 28px 32px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #fff;
  box-shadow: 0 8px 32px rgba(102, 126, 234, 0.3);
}
.welcome-left { flex: 1; }
.greeting { font-size: 28px; font-weight: bold; margin-bottom: 8px; }
.date-time { display: flex; gap: 16px; margin-bottom: 12px; opacity: 0.9; font-size: 14px; }
.quick-tip { font-size: 14px; }
.tip-text { padding: 4px 12px; background: rgba(255,255,255,0.2); border-radius: 20px; }
.tip-text.success { background: rgba(103, 194, 58, 0.3); }
.welcome-right { display: flex; gap: 12px; }
@media (max-width: 768px) {
  .welcome-section { flex-direction: column; gap: 16px; padding: 20px; }
  .greeting { font-size: 22px; }
  .welcome-right { width: 100%; }
  .welcome-right .el-button { flex: 1; }
}

/* 统计卡片 */
.stats-row { margin-bottom: 16px; }
.stat-card {
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  background: #fff;
  transition: all 0.3s ease;
  margin-bottom: 12px;
}
.stat-card:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
.stat-card.total { background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%); }
.stat-card.in-progress { background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%); }
.stat-card.done { background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); }
.stat-card.overdue { background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); }
.stat-card.overdue.has-overdue { border: 2px solid #f56c6c; }
.stat-ring { flex-shrink: 0; }
.ring-value { font-size: 24px; font-weight: bold; color: #303133; line-height: 1.2; }
.ring-label { font-size: 12px; color: #909399; }
.stat-icon-lg { width: 56px; height: 56px; border-radius: 12px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.in-progress .stat-icon-lg { background: #409eff; color: #fff; }
.done .stat-icon-lg { background: #67c23a; color: #fff; }
.overdue .stat-icon-lg { background: #f56c6c; color: #fff; }
.stat-info { flex: 1; min-width: 0; }
.stat-value { font-size: 32px; font-weight: bold; color: #303133; line-height: 1.1; }
.stat-label { font-size: 14px; color: #909399; margin-top: 4px; }
.stat-title { font-size: 14px; color: #606266; margin-bottom: 4px; }
.stat-number { font-size: 28px; font-weight: bold; color: #303133; }
.stat-sub { font-size: 12px; color: #909399; margin-top: 2px; }

/* 通用卡片 */
.content-card { border-radius: 12px; margin-bottom: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; font-weight: 600; font-size: 15px; gap: 10px; }
.empty-state { display: flex; justify-content: center; align-items: center; padding: 40px 0; }
.empty-state-sm { display: flex; justify-content: center; align-items: center; padding: 20px 0; }

/* 进行中任务 - 分组展示 */
.task-groups { display: flex; flex-direction: column; gap: 16px; }
.task-group {
  border: 1px solid #ebeef5;
  border-radius: 10px;
  overflow: hidden;
  transition: box-shadow 0.2s;
}
.task-group:hover { box-shadow: 0 2px 12px rgba(0,0,0,0.06); }
.task-group:first-child { margin-top: 0; }
.group-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #f5f7fa 0%, #eef1f5 100%);
  border-bottom: 1px solid #ebeef5;
}
.group-avatar { flex-shrink: 0; }
.group-info { display: flex; align-items: center; gap: 10px; }
.group-name { font-size: 15px; font-weight: 600; color: #303133; }
.group-tasks { display: flex; flex-direction: column; }
.task-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid #f5f5f5;
  transition: background 0.2s;
}
.task-row:last-child { border-bottom: none; }
.task-row:hover { background: #fafafa; }
.task-row.overdue { background: #fff5f5; }
.task-row.overdue:hover { background: #fff0f0; }
.task-content { flex: 1; min-width: 0; }
.task-row .task-title { font-size: 14px; color: #303133; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.task-row .task-meta { display: flex; align-items: center; gap: 8px; }
.task-row .task-due { font-size: 12px; color: #909399; display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.task-row .task-due.overdue { color: #f56c6c; font-weight: 600; }

/* 即将到期 */
.upcoming-card { border-radius: 12px; margin-bottom: 16px; }
.upcoming-list { display: flex; flex-direction: column; }
.upcoming-item { display: flex; align-items: center; justify-content: space-between; padding: 14px 0; border-bottom: 1px solid #f0f0f0; }
.upcoming-item:last-child { border-bottom: none; }
.upcoming-item.overdue { background: #fef5f5; }
.upcoming-left { display: flex; align-items: center; gap: 12px; flex: 1; }
.upcoming-info { flex: 1; min-width: 0; }
.upcoming-title { font-size: 14px; color: #303133; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.upcoming-meta { display: flex; align-items: center; gap: 8px; }
.upcoming-assignee { font-size: 12px; color: #909399; }
.upcoming-right { flex-shrink: 0; }
.due-days { font-size: 13px; color: #909399; padding: 4px 10px; background: #f5f5f5; border-radius: 12px; }
.due-days.urgent { color: #f56c6c; background: #fef0f0; font-weight: 600; }

/* 底部内容区 */
.content-row { margin-bottom: 16px; }
.content-card { border-radius: 12px; height: 100%; }
.content-card :deep(.el-card__header) { padding: 16px 20px; border-bottom: none; }

/* 会议列表 */
.meeting-list { display: flex; flex-direction: column; }
.meeting-item { display: flex; gap: 16px; padding: 14px 0; border-bottom: 1px solid #f0f0f0; }
.meeting-item:last-child { border-bottom: none; }
.date-box { width: 50px; height: 50px; background: linear-gradient(135deg, #409eff, #67c23a); border-radius: 10px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #fff; }
.month { font-size: 11px; opacity: 0.9; }
.day { font-size: 18px; font-weight: bold; line-height: 1.2; }
.meeting-info { flex: 1; display: flex; flex-direction: column; justify-content: center; }
.meeting-title { font-size: 14px; color: #303133; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.meeting-meta { display: flex; align-items: center; gap: 12px; }
.meeting-time { font-size: 12px; color: #909399; display: flex; align-items: center; gap: 4px; }

/* 成员任务 */
.member-card { border-radius: 12px; }
.member-header { display: flex; align-items: center; gap: 10px; font-size: 15px; }
.member-name { font-weight: 600; }
.no-tasks { text-align: center; color: #909399; padding: 20px; }
.member-task-list { display: flex; flex-direction: column; }
.member-task-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #f0f0f0; }
.member-task-item:last-child { border-bottom: none; }
.member-task-info { flex: 1; min-width: 0; }
.member-task-title { font-size: 14px; color: #303133; display: block; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.member-task-meta { display: flex; align-items: center; gap: 8px; }
.member-task-due { font-size: 12px; color: #909399; display: flex; align-items: center; gap: 4px; }
.member-task-due.overdue { color: #f56c6c; font-weight: 600; }
</style>

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

    <!-- 图表区域 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :sm="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>任务状态分布</span>
              <el-tag size="small" type="info">共 {{ dashboardData.summary?.total_tasks || 0 }} 项</el-tag>
            </div>
          </template>
          <div class="chart-container">
            <v-chart :option="taskStatusOption" autoresize style="height: 220px" />
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12">
        <el-card class="chart-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>任务优先级分布</span>
            </div>
          </template>
          <div class="chart-container">
            <v-chart :option="taskPriorityOption" autoresize style="height: 220px" />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 项目进度 -->
    <el-card class="progress-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>📊 项目进度概览</span>
        </div>
      </template>
      <div class="progress-list">
        <div v-for="project in dashboardData.project_stats" :key="project.name" class="progress-item">
          <div class="progress-name">{{ project.name }}</div>
          <div class="progress-bar-wrapper">
            <el-progress :percentage="project.progress" :stroke-width="12" :color="getProgressColor(project.progress)" />
          </div>
          <div class="progress-value">{{ project.progress }}%</div>
        </div>
        <div v-if="!dashboardData.project_stats?.length" class="empty-progress">
          暂无项目数据
        </div>
      </div>
    </el-card>

    <!-- 底部双栏 -->
    <el-row :gutter="16" class="content-row">
      <!-- 待办任务 -->
      <el-col :xs="24" :sm="12">
        <el-card class="content-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>📋 待办任务</span>
              <el-button text @click="$router.push('/tasks')">查看全部 →</el-button>
            </div>
          </template>
          <div v-if="todoTasks.length === 0" class="empty-state">
            <el-empty description="暂无待办任务" :image-size="60" />
          </div>
          <div v-else class="task-list">
            <div v-for="task in todoTasks" :key="task.id" class="task-item" :class="{ overdue: isOverdue(task.due_date) }">
              <el-checkbox
                :model-value="task.status === 'done'"
                @change="toggleTaskStatus(task)"
                size="large"
              />
              <div class="task-info">
                <div class="task-title">{{ task.title }}</div>
                <div class="task-meta">
                  <el-tag :type="getPriorityType(task.priority)" size="small" effect="plain">
                    {{ getPriorityLabel(task.priority) }}
                  </el-tag>
                  <span class="task-assignee">{{ memberStore.getMemberName(task.assignee_id) }}</span>
                </div>
              </div>
              <div class="task-due" :class="{ overdue: isOverdue(task.due_date) }">
                <el-icon v-if="isOverdue(task.due_date)"><Warning /></el-icon>
                {{ formatDate(task.due_date) }}
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 最近会议 -->
      <el-col :xs="24" :sm="12">
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
                    {{ getStatusLabel(meeting.status) }}
                  </el-tag>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 成员任务统计 -->
    <el-card class="member-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>👥 成员任务统计</span>
        </div>
      </template>
      <div class="member-chart">
        <v-chart :option="memberTaskOption" autoresize style="height: 200px" />
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
import { formatCompactDate, formatTime } from '@/utils/format'
import { getStatusType, getPriorityType, getPriorityLabel } from '@/utils/task'
import { useMemberStore } from '@/stores/member'
import { useUserStore } from '@/stores/user'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart, LineChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent, GridComponent } from 'echarts/components'

use([CanvasRenderer, PieChart, BarChart, LineChart, TitleComponent, TooltipComponent, LegendComponent, GridComponent])

const memberStore = useMemberStore()
const userStore = useUserStore()
const members = computed(() => memberStore.members)

const dashboardData = ref({})
const todoTasks = ref([])
const recentMeetings = ref([])
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

const getProgressColor = (progress) => {
  if (progress >= 80) return '#67c23a'
  if (progress >= 50) return '#409eff'
  if (progress >= 30) return '#e6a23c'
  return '#f56c6c'
}

// 任务状态图表
const taskStatusOption = computed(() => {
  const statusMap = { todo: '待办', in_progress: '进行中', blocked: '阻塞', review: '评审中', done: '已完成', cancelled: '已取消' }
  const colorMap = { todo: '#909399', in_progress: '#409eff', blocked: '#f56c6c', review: '#e6a23c', done: '#67c23a', cancelled: '#c0c4cc' }
  const data = Object.entries(dashboardData.value.task_status || {}).map(([key, value]) => ({
    name: statusMap[key] || key, value, itemStyle: { color: colorMap[key] || '#409eff' }
  }))
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', right: 10, top: 'center', textStyle: { fontSize: 12 } },
    series: [{ type: 'pie', radius: ['45%', '70%'], center: ['35%', '50%'], avoidLabelOverlap: false,
      itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
      label: { show: false }, emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      labelLine: { show: false }, data }]
  }
})

// 优先级图表
const taskPriorityOption = computed(() => {
  const priorityMap = { high: '高', medium: '中', low: '低' }
  const colorMap = { high: '#f56c6c', medium: '#e6a23c', low: '#909399' }
  const data = Object.entries(dashboardData.value.task_priority || {}).map(([key, value]) => ({
    name: priorityMap[key] || key, value, itemStyle: { color: colorMap[key] || '#409eff' }
  }))
  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { orient: 'vertical', right: 10, top: 'center', textStyle: { fontSize: 12 } },
    series: [{ type: 'pie', radius: ['45%', '70%'], center: ['35%', '50%'],
      itemStyle: { borderRadius: 8, borderColor: '#fff', borderWidth: 2 },
      label: { show: false }, emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      labelLine: { show: false }, data }]
  }
})

// 成员任务统计
const memberTaskOption = computed(() => {
  const memberStats = dashboardData.value.member_stats || []
  const names = memberStats.map(m => m.name)
  const inProgressData = memberStats.map(m => m.in_progress)
  const doneData = memberStats.map(m => m.done)
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['进行中', '已完成'], bottom: 0 },
    grid: { left: '3%', right: '4%', bottom: '15%', top: '10%', containLabel: true },
    xAxis: { type: 'value' },
    yAxis: { type: 'category', data: names, axisLabel: { fontSize: 11 } },
    series: [
      { name: '进行中', type: 'bar', data: inProgressData, itemStyle: { color: '#409eff' }, barMaxWidth: 30 },
      { name: '已完成', type: 'bar', data: doneData, itemStyle: { color: '#67c23a' }, barMaxWidth: 30 }
    ]
  }
})

const fetchDashboardStats = async () => {
  try {
    const res = await axios.get('/api/v1/dashboard/stats')
    dashboardData.value = res.data
  } catch (e) { console.error('获取仪表盘数据失败:', e) }
}

const fetchTodoTasks = async () => {
  try {
    const res = await axios.get('/api/v1/tasks', { params: { status: 'todo', page_size: 5 } })
    todoTasks.value = res.data.items || []
  } catch (e) { console.error('获取任务失败:', e) }
}

const fetchRecentMeetings = async () => {
  try {
    const res = await axios.get('/api/v1/meetings', { params: { page_size: 5 } })
    recentMeetings.value = res.data.items || []
  } catch (e) { console.error('获取会议失败:', e) }
}

const fetchMembers = () => memberStore.fetchMembers()

const createTask = async () => {
  if (!newTask.value.title) { ElMessage.warning('请输入任务标题'); return }
  try {
    await axios.post('/api/v1/tasks', newTask.value)
    ElMessage.success('任务创建成功')
    showCreateTask.value = false
    newTask.value = { title: '', assignee_id: null, priority: 'medium', due_date: '', description: '' }
    fetchTodoTasks()
    fetchDashboardStats()
  } catch (e) { ElMessage.error('创建任务失败') }
}

const toggleTaskStatus = async (task) => {
  const newStatus = task.status === 'done' ? 'todo' : 'done'
  try {
    await axios.put(`/api/v1/tasks/${task.id}`, { status: newStatus })
    fetchTodoTasks()
    fetchDashboardStats()
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

const isOverdue = (date) => date && dayjs(date).isBefore(dayjs())

onMounted(() => {
  updateTime()
  setInterval(updateTime, 1000)
  fetchDashboardStats()
  fetchTodoTasks()
  fetchRecentMeetings()
  fetchMembers()
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

/* 图表区域 */
.chart-row { margin-bottom: 16px; }
.chart-card { border-radius: 12px; }
.chart-card :deep(.el-card__header) { padding: 16px 20px; border-bottom: none; }
.card-header { display: flex; justify-content: space-between; align-items: center; font-weight: 600; font-size: 15px; }
.chart-container { display: flex; justify-content: center; }

/* 项目进度 */
.progress-card { border-radius: 12px; margin-bottom: 16px; }
.progress-list { display: flex; flex-direction: column; gap: 16px; }
.progress-item { display: flex; align-items: center; gap: 16px; }
.progress-name { width: 120px; font-size: 14px; color: #606266; flex-shrink: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.progress-bar-wrapper { flex: 1; }
.progress-value { width: 50px; text-align: right; font-size: 14px; font-weight: 600; color: #303133; flex-shrink: 0; }
.empty-progress { text-align: center; color: #909399; padding: 20px; }

/* 底部内容区 */
.content-row { margin-bottom: 16px; }
.content-card { border-radius: 12px; height: 100%; }
.content-card :deep(.el-card__header) { padding: 16px 20px; border-bottom: none; }
.empty-state { display: flex; justify-content: center; align-items: center; padding: 40px 0; }

/* 待办任务 */
.task-list { display: flex; flex-direction: column; }
.task-item { display: flex; align-items: center; gap: 12px; padding: 14px 0; border-bottom: 1px solid #f0f0f0; transition: background 0.2s; }
.task-item:hover { background: #fafafa; border-radius: 8px; padding-left: 8px; padding-right: 8px; }
.task-item:last-child { border-bottom: none; }
.task-item.overdue { background: #fef5f5; }
.task-info { flex: 1; min-width: 0; }
.task-title { font-size: 14px; color: #303133; margin-bottom: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.task-meta { display: flex; align-items: center; gap: 8px; }
.task-assignee { font-size: 12px; color: #909399; }
.task-due { font-size: 12px; color: #909399; display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.task-due.overdue { color: #f56c6c; font-weight: 600; }

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

/* 成员统计 */
.member-card { border-radius: 12px; }
.member-chart { display: flex; justify-content: center; }
</style>

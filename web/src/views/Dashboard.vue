<template>
  <div class="dashboard">
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <div class="welcome-text">
        <h1>你好，{{ username }}，欢迎使用小气助手！</h1>
        <p>微纳米气泡课题组智能管理系统</p>
      </div>
      <div class="quick-actions">
        <el-button type="primary" @click="$router.push('/chat')">
          <el-icon><ChatDotRound /></el-icon>
          开始对话
        </el-button>
        <el-button @click="showCreateTask = true">
          <el-icon><Plus /></el-icon>
          创建任务
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #409eff">
            <el-icon size="24"><List /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboardData.summary?.total_tasks || 0 }}</div>
            <div class="stat-label">总任务数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #67c23a">
            <el-icon size="24"><CircleCheck /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboardData.summary?.done_tasks || 0 }}</div>
            <div class="stat-label">已完成</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #e6a23c">
            <el-icon size="24"><Clock /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboardData.summary?.in_progress_tasks || 0 }}</div>
            <div class="stat-label">进行中</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-icon" style="background: #f56c6c">
            <el-icon size="24"><Warning /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ dashboardData.summary?.overdue_tasks || 0 }}</div>
            <div class="stat-label">已逾期</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="chart-row">
      <!-- 任务状态分布 -->
      <el-col :span="8">
        <el-card class="chart-card">
          <template #header>
            <span>任务状态分布</span>
          </template>
          <v-chart class="chart" :option="taskStatusOption" autoresize />
        </el-card>
      </el-col>

      <!-- 任务优先级分布 -->
      <el-col :span="8">
        <el-card class="chart-card">
          <template #header>
            <span>任务优先级分布</span>
          </template>
          <v-chart class="chart" :option="taskPriorityOption" autoresize />
        </el-card>
      </el-col>

      <!-- 成员任务统计 -->
      <el-col :span="8">
        <el-card class="chart-card">
          <template #header>
            <span>成员任务统计</span>
          </template>
          <v-chart class="chart" :option="memberTaskOption" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <!-- 项目进度 -->
    <el-row :gutter="20" class="chart-row">
      <el-col :span="24">
        <el-card class="chart-card">
          <template #header>
            <span>项目进度</span>
          </template>
          <v-chart class="chart-wide" :option="projectProgressOption" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <!-- 主要内容区 -->
    <el-row :gutter="20">
      <!-- 待办任务 -->
      <el-col :span="12">
        <el-card class="content-card">
          <template #header>
            <div class="card-header">
              <span>待办任务</span>
              <el-button text @click="$router.push('/tasks')">查看全部</el-button>
            </div>
          </template>

          <div v-if="todoTasks.length === 0" class="empty-state">
            <el-empty description="暂无待办任务" :image-size="80" />
          </div>

          <div v-else class="task-list">
            <div
              v-for="task in todoTasks"
              :key="task.id"
              class="task-item"
            >
              <div class="task-info">
                <div class="task-title">{{ task.title }}</div>
                <div class="task-meta">
                  <el-tag :type="getPriorityType(task.priority)" size="small">
                    {{ task.priority }}
                  </el-tag>
                  <span class="task-assignee">{{ task.assignee_name || '未分配' }}</span>
                </div>
              </div>
              <div class="task-due" :class="{ overdue: isOverdue(task.due_date) }">
                {{ formatDate(task.due_date) }}
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 最近会议 -->
      <el-col :span="12">
        <el-card class="content-card">
          <template #header>
            <div class="card-header">
              <span>最近会议</span>
              <el-button text @click="$router.push('/meetings')">查看全部</el-button>
            </div>
          </template>

          <div v-if="recentMeetings.length === 0" class="empty-state">
            <el-empty description="暂无会议记录" :image-size="80" />
          </div>

          <div v-else class="meeting-list">
            <div
              v-for="meeting in recentMeetings"
              :key="meeting.id"
              class="meeting-item"
            >
              <div class="meeting-time">
                <div class="time-day">{{ formatDay(meeting.start_time) }}</div>
                <div class="time-hour">{{ formatHour(meeting.start_time) }}</div>
              </div>
              <div class="meeting-info">
                <div class="meeting-title">{{ meeting.title }}</div>
                <div class="meeting-status">
                  <el-tag :type="getStatusType(meeting.status)" size="small">
                    {{ meeting.status }}
                  </el-tag>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 创建任务对话框 -->
    <el-dialog v-model="showCreateTask" title="创建任务" width="500px">
      <el-form :model="newTask" label-width="80px">
        <el-form-item label="任务标题" required>
          <el-input v-model="newTask.title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="newTask.assignee_id" placeholder="选择负责人" clearable>
            <el-option
              v-for="member in members"
              :key="member.id"
              :label="member.name"
              :value="member.id"
            />
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
          <el-date-picker
            v-model="newTask.due_date"
            type="date"
            placeholder="选择截止日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input
            v-model="newTask.description"
            type="textarea"
            :rows="3"
            placeholder="请输入任务描述"
          />
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
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import dayjs from 'dayjs'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
} from 'echarts/components'

use([
  CanvasRenderer,
  PieChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent
])

const dashboardData = ref({})
const todoTasks = ref([])
const recentMeetings = ref([])
const members = ref([])
const showCreateTask = ref(false)

const newTask = ref({
  title: '',
  assignee_id: null,
  priority: 'medium',
  due_date: '',
  description: ''
})

// 获取当前用户名
const username = computed(() => {
  const userInfo = JSON.parse(localStorage.getItem('user_info') || '{}')
  return userInfo.name || '用户'
})

// 任务状态图表配置
const taskStatusOption = computed(() => {
  const statusMap = {
    todo: '待办',
    in_progress: '进行中',
    blocked: '阻塞',
    review: '评审中',
    done: '已完成',
    cancelled: '已取消'
  }
  const colorMap = {
    todo: '#909399',
    in_progress: '#409eff',
    blocked: '#f56c6c',
    review: '#e6a23c',
    done: '#67c23a',
    cancelled: '#c0c4cc'
  }

  const data = Object.entries(dashboardData.value.task_status || {}).map(([key, value]) => ({
    name: statusMap[key] || key,
    value,
    itemStyle: { color: colorMap[key] || '#409eff' }
  }))

  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 10, borderColor: '#fff', borderWidth: 2 },
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      labelLine: { show: false },
      data
    }]
  }
})

// 任务优先级图表配置
const taskPriorityOption = computed(() => {
  const priorityMap = { high: '高', medium: '中', low: '低' }
  const colorMap = { high: '#f56c6c', medium: '#e6a23c', low: '#909399' }

  const data = Object.entries(dashboardData.value.task_priority || {}).map(([key, value]) => ({
    name: priorityMap[key] || key,
    value,
    itemStyle: { color: colorMap[key] || '#409eff' }
  }))

  return {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie',
      radius: '70%',
      data,
      emphasis: {
        itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' }
      }
    }]
  }
})

// 成员任务统计图表配置
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
      { name: '进行中', type: 'bar', stack: 'total', data: inProgressData, itemStyle: { color: '#409eff' } },
      { name: '已完成', type: 'bar', stack: 'total', data: doneData, itemStyle: { color: '#67c23a' } }
    ]
  }
})

// 项目进度图表配置
const projectProgressOption = computed(() => {
  const projectStats = dashboardData.value.project_stats || []
  const names = projectStats.map(p => p.name)
  const progressData = projectStats.map(p => p.progress)

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, formatter: '{b}: {c}%' },
    grid: { left: '3%', right: '4%', bottom: '10%', top: '10%', containLabel: true },
    xAxis: { type: 'category', data: names, axisLabel: { rotate: 15, fontSize: 11 } },
    yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    series: [{
      type: 'bar',
      data: progressData,
      itemStyle: {
        color: (params) => {
          const val = params.value
          if (val >= 80) return '#67c23a'
          if (val >= 50) return '#409eff'
          if (val >= 30) return '#e6a23c'
          return '#f56c6c'
        },
        borderRadius: [4, 4, 0, 0]
      },
      label: { show: true, position: 'top', formatter: '{c}%', fontSize: 12 }
    }]
  }
})

// 获取仪表盘数据
const fetchDashboardStats = async () => {
  try {
    const res = await axios.get('/api/v1/dashboard/stats')
    dashboardData.value = res.data
  } catch (e) {
    console.error('获取仪表盘数据失败:', e)
  }
}

// 获取待办任务
const fetchTodoTasks = async () => {
  try {
    const res = await axios.get('/api/v1/tasks', {
      params: { status: 'todo', page_size: 5 }
    })
    todoTasks.value = res.data.items || []
  } catch (e) {
    console.error('获取任务失败:', e)
  }
}

// 获取最近会议
const fetchRecentMeetings = async () => {
  try {
    const res = await axios.get('/api/v1/meetings', {
      params: { page_size: 5 }
    })
    recentMeetings.value = res.data.items || []
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

// 创建任务
const createTask = async () => {
  if (!newTask.value.title) {
    ElMessage.warning('请输入任务标题')
    return
  }

  try {
    await axios.post('/api/v1/tasks', newTask.value)
    ElMessage.success('任务创建成功')
    showCreateTask.value = false
    newTask.value = { title: '', assignee_id: null, priority: 'medium', due_date: '', description: '' }
    fetchTodoTasks()
    fetchDashboardStats()
  } catch (e) {
    ElMessage.error('创建任务失败')
  }
}

// 格式化函数
const formatDate = (date) => {
  if (!date) return '无截止日期'
  return dayjs(date).format('MM/DD')
}

const formatDay = (date) => dayjs(date).format('MM/DD')
const formatHour = (date) => dayjs(date).format('HH:mm')

const isOverdue = (date) => {
  if (!date) return false
  return dayjs(date).isBefore(dayjs())
}

const getPriorityType = (priority) => {
  const map = { high: 'danger', medium: 'warning', low: 'info' }
  return map[priority] || 'info'
}

const getStatusType = (status) => {
  const map = { scheduled: 'info', recording: 'warning', completed: 'success' }
  return map[status] || 'info'
}

onMounted(() => {
  fetchDashboardStats()
  fetchTodoTasks()
  fetchRecentMeetings()
  fetchMembers()
})
</script>

<style scoped>
.dashboard {
  max-width: 1400px;
}

.welcome-section {
  background: linear-gradient(135deg, #409eff 0%, #67c23a 100%);
  border-radius: 12px;
  padding: 30px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #fff;
}

.welcome-text h1 {
  font-size: 24px;
  margin-bottom: 8px;
}

.welcome-text p {
  opacity: 0.9;
}

.quick-actions {
  display: flex;
  gap: 12px;
}

.stats-row {
  margin-bottom: 20px;
}

.chart-row {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 0;
}

.stat-card :deep(.el-card__body) {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
}

.stat-icon {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
}

.stat-info {
  flex: 1;
}

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.chart-card {
  margin-bottom: 0;
}

.chart {
  height: 300px;
}

.chart-wide {
  height: 350px;
}

.content-card {
  height: 400px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.task-list, .meeting-list {
  max-height: 320px;
  overflow-y: auto;
}

.task-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #ebeef5;
}

.task-item:last-child {
  border-bottom: none;
}

.task-title {
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.task-assignee {
  font-size: 12px;
  color: #909399;
}

.task-due {
  font-size: 12px;
  color: #909399;
}

.task-due.overdue {
  color: #f56c6c;
  font-weight: bold;
}

.meeting-item {
  display: flex;
  gap: 16px;
  padding: 12px 0;
  border-bottom: 1px solid #ebeef5;
}

.meeting-item:last-child {
  border-bottom: none;
}

.meeting-time {
  text-align: center;
  min-width: 50px;
}

.time-day {
  font-size: 14px;
  font-weight: bold;
  color: #409eff;
}

.time-hour {
  font-size: 12px;
  color: #909399;
}

.meeting-info {
  flex: 1;
}

.meeting-title {
  font-size: 14px;
  color: #303133;
  margin-bottom: 4px;
}

.empty-state {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 200px;
}
</style>

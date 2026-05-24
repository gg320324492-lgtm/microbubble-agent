<template>
  <div class="dashboard">
    <!-- 欢迎区域 -->
    <div class="welcome-section slide-down-fade">
      <!-- 装饰光晕 -->
      <div class="welcome-glow glow-1"></div>
      <div class="welcome-glow glow-2"></div>
      <div class="welcome-left">
        <div class="greeting">{{ greeting }}，{{ username }}！</div>
        <div class="date-time">
          <span class="date">{{ currentDate }}</span>
          <span class="separator">|</span>
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
        <el-button type="primary" size="large" class="btn-welcome" @click="$router.push('/chat')">
          <el-icon><ChatDotRound /></el-icon>
          开始对话
        </el-button>
        <el-button size="large" class="btn-welcome-secondary" @click="showCreateTask = true">
          <el-icon><Plus /></el-icon>
          创建任务
        </el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <!-- 骨架屏 -->
      <template v-if="loadingStats">
        <el-col :xs="12" :sm="6" v-for="i in 4" :key="i">
          <div class="stat-card skeleton-card">
            <div class="skeleton skeleton-icon"></div>
            <div class="skeleton-content">
              <div class="skeleton skeleton-text" style="width: 60%"></div>
              <div class="skeleton skeleton-text" style="width: 40%; height: 28px; margin: 8px 0"></div>
              <div class="skeleton skeleton-text" style="width: 50%"></div>
            </div>
          </div>
        </el-col>
      </template>
      <!-- 真实数据 -->
      <template v-else>
        <el-col :xs="12" :sm="6">
          <div class="stat-card stat-card-primary fade-slide-up stagger-1">
            <div class="stat-icon-wrap" style="background: linear-gradient(135deg, #FFF0ED 0%, #FFE4DC 100%)">
              <el-icon size="28" style="color: #FF7A5C"><Clock /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-label">进行中</div>
              <div class="stat-value" :ref="el => animateNumber(el, dashboardData.summary?.in_progress_tasks || 0)">0</div>
              <div class="stat-hint">任务执行中</div>
            </div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-card stat-card-success fade-slide-up stagger-2">
            <div class="stat-icon-wrap" style="background: linear-gradient(135deg, #F0F9EB 0%, #DCFCE7 100%)">
              <el-icon size="28" style="color: #67C23A"><CircleCheck /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-label">已完成</div>
              <div class="stat-value" :ref="el => animateNumber(el, dashboardData.summary?.done_tasks || 0)">0</div>
              <div class="stat-hint">任务完成</div>
            </div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-card stat-card-warning fade-slide-up stagger-3">
            <div class="stat-icon-wrap" style="background: linear-gradient(135deg, #FDF6EC 0%, #FDF3E3 100%)">
              <el-icon size="28" style="color: #E6A23C"><Bell /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-label">即将到期</div>
              <div class="stat-value" :ref="el => animateNumber(el, upcomingCount)">0</div>
              <div class="stat-hint">未来3天</div>
            </div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-card stat-card-danger fade-slide-up stagger-4" :class="{ 'has-danger': dashboardData.summary?.overdue_tasks > 0 }">
            <div class="stat-icon-wrap" style="background: linear-gradient(135deg, #FEF0F0 0%, #FEE2E2 100%)">
              <el-icon size="28" style="color: #F56C6C"><Warning /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-label">已逾期</div>
              <div class="stat-value" :ref="el => animateNumber(el, dashboardData.summary?.overdue_tasks || 0)">0</div>
              <div class="stat-hint">需要处理</div>
            </div>
          </div>
        </el-col>
      </template>
    </el-row>

    <!-- 进行中任务（合并待办+进行中，按负责人分组） -->
    <el-card class="content-card card fade-slide-up stagger-2" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">
            <span class="card-icon">🚀</span>
            进行中任务
          </span>
          <div class="card-actions">
            <el-badge :value="inProgressTasks.length" type="primary" :hidden="inProgressTasks.length === 0" />
            <el-button text class="view-all-btn" @click="$router.push('/tasks')">查看全部 →</el-button>
          </div>
        </div>
      </template>
      <!-- 骨架屏 -->
      <div v-if="loadingTasks" class="task-groups">
        <div v-for="i in 2" :key="i" class="task-group skeleton-group">
          <div class="group-header skeleton-group-header">
            <div class="skeleton skeleton-circle" style="width: 40px; height: 40px"></div>
            <div style="flex: 1">
              <div class="skeleton skeleton-text" style="width: 80px; height: 16px"></div>
            </div>
          </div>
          <div class="group-tasks">
            <div v-for="j in 2" :key="j" class="task-row skeleton-task-row">
              <div class="skeleton" style="width: 20px; height: 20px; border-radius: 4px"></div>
              <div class="skeleton-content" style="flex: 1">
                <div class="skeleton skeleton-text" style="width: 60%"></div>
                <div class="skeleton skeleton-text" style="width: 30%; margin-top: 6px"></div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div v-else-if="inProgressTasks.length === 0" class="empty-state">
        <el-empty description="暂无进行中任务" :image-size="60" />
      </div>
      <div v-else class="task-groups">
        <div v-for="(group, gIdx) in groupedTasks" :key="group.assignee_id" class="task-group" :class="'fade-slide-up'" :style="{ animationDelay: `${(gIdx + 3) * 80}ms` }">
          <!-- 负责人头部（可点击折叠） -->
          <div class="group-header" @click="toggleGroup(group.assignee_id)">
            <el-avatar
              v-if="memberStore.getMemberAvatar(group.assignee_id)"
              :src="memberStore.getMemberAvatar(group.assignee_id)"
              :size="40"
              class="avatar group-avatar"
            />
            <el-avatar
              v-else
              :size="40"
              style="background: var(--color-primary)"
              class="avatar group-avatar"
            >
              {{ memberStore.getMemberName(group.assignee_id).charAt(0) }}
            </el-avatar>
            <div class="group-info">
              <span class="group-name">{{ memberStore.getMemberName(group.assignee_id) }}</span>
              <el-tag size="small" type="info">{{ group.tasks.length }} 项任务</el-tag>
            </div>
            <el-icon class="collapse-icon" :class="{ collapsed: collapsedGroups[group.assignee_id] }"><ArrowDown /></el-icon>
          </div>
          <!-- 任务列表 -->
          <div v-show="!collapsedGroups[group.assignee_id]" class="group-tasks">
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
              <div class="task-actions">
                <el-button text type="success" size="small" class="btn-success" @click="completeTask(task)">完成</el-button>
                <el-button text type="primary" size="small" @click="openEditDialog(task)">编辑</el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 即将到期任务 -->
    <el-card class="upcoming-card card fade-slide-up stagger-3" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">
            <span class="card-icon">⏰</span>
            即将到期
          </span>
          <el-tag size="small" type="warning">未来3天</el-tag>
        </div>
      </template>
      <!-- 骨架屏 -->
      <div v-if="loadingUpcoming" class="upcoming-list">
        <div v-for="i in 3" :key="i" class="upcoming-item skeleton-upcoming">
          <div class="upcoming-left">
            <div class="skeleton" style="width: 20px; height: 20px; border-radius: 4px"></div>
            <div class="upcoming-info" style="flex: 1">
              <div class="skeleton skeleton-text" style="width: 70%"></div>
              <div class="skeleton skeleton-text" style="width: 40%; margin-top: 6px"></div>
            </div>
          </div>
          <div class="upcoming-right">
            <div class="skeleton" style="width: 70px; height: 28px; border-radius: 14px"></div>
          </div>
        </div>
      </div>
      <div v-else-if="upcomingDeadlines.length === 0" class="empty-state-sm">
        <el-empty description="未来3天没有即将到期的任务" :image-size="40" />
      </div>
      <div v-else class="upcoming-list">
        <div v-for="task in upcomingDeadlines" :key="task.id" class="upcoming-item" :class="{ 'overdue': isOverdue(task.due_date), 'urgent': getDaysLeft(task.due_date) <= 1 }">
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
            <div class="task-actions">
              <el-button text type="success" size="small" class="btn-success" @click="completeTask(task)">完成</el-button>
              <el-button text type="primary" size="small" @click="openEditDialog(task)">编辑</el-button>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 最近会议 -->
    <el-card class="content-card card fade-slide-up stagger-4" shadow="hover">
      <template #header>
        <div class="card-header">
          <span class="card-title">
            <span class="card-icon">📅</span>
            最近会议
          </span>
          <el-button text class="view-all-btn" @click="$router.push('/meetings')">查看全部 →</el-button>
        </div>
      </template>
      <!-- 骨架屏 -->
      <div v-if="loadingMeetings" class="meeting-list">
        <div v-for="i in 3" :key="i" class="meeting-item skeleton-meeting">
          <div class="skeleton" style="width: 50px; height: 50px; border-radius: 10px; flex-shrink: 0"></div>
          <div class="meeting-info" style="flex: 1">
            <div class="skeleton skeleton-text" style="width: 60%"></div>
            <div class="skeleton skeleton-text" style="width: 40%; margin-top: 8px"></div>
          </div>
        </div>
      </div>
      <div v-else-if="recentMeetings.length === 0" class="empty-state">
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

    <!-- 编辑任务对话框 -->
    <el-dialog v-model="showEditDialog" title="编辑任务" :width="isMobile ? '90vw' : '500px'">
      <el-form :model="editForm" label-width="80px">
        <el-form-item label="任务标题" required>
          <el-input v-model="editForm.title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="editForm.assignee_id" placeholder="选择负责人" clearable>
            <el-option v-for="member in members" :key="member.id" :label="member.name" :value="member.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="editForm.priority">
            <el-radio label="high">高</el-radio>
            <el-radio label="medium">中</el-radio>
            <el-radio label="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status">
            <el-option label="待办" value="todo" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="阻塞" value="blocked" />
            <el-option label="已完成" value="done" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker v-model="editForm.due_date" type="datetime" placeholder="选择截止日期和时间"
            format="YYYY-MM-DD HH:mm" value-format="YYYY-MM-DD HH:mm:ss" style="width: 100%" />
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input v-model="editForm.description" type="textarea" :rows="3" placeholder="请输入任务描述" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
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

// 骨架屏加载状态
const loadingStats = ref(true)
const loadingTasks = ref(true)
const loadingUpcoming = ref(true)
const loadingMeetings = ref(true)

// 分组折叠状态
const collapsedGroups = ref({})
const toggleGroup = (assigneeId) => {
  collapsedGroups.value[assigneeId] = !collapsedGroups.value[assigneeId]
}

// 数字计数器动画
const animateNumber = (el, target) => {
  if (!el || target === undefined || target === null) return
  const targetNum = Number(target)
  if (isNaN(targetNum)) return
  const duration = 500
  const startTime = performance.now()
  const animate = (currentTime) => {
    const elapsed = currentTime - startTime
    const progress = Math.min(elapsed / duration, 1)
    const eased = 1 - Math.pow(1 - progress, 3) // ease-out cubic
    el.textContent = Math.round(eased * targetNum)
    if (progress < 1) requestAnimationFrame(animate)
  }
  requestAnimationFrame(animate)
}

// 即将到期数量
const upcomingCount = computed(() => upcomingDeadlines.value.length)

const handleResize = () => { isMobile.value = window.innerWidth <= 768 }
const updateTime = () => {
  const now = dayjs()
  currentTime.value = now.format('HH:mm:ss')
  currentDate.value = now.format('YYYY年MM月DD日 dddd')
}

onUnmounted(() => { window.removeEventListener('resize', handleResize) })

const newTask = ref({ title: '', assignee_id: null, priority: 'medium', due_date: '', description: '' })

// 编辑相关
const editingTask = ref(null)
const showEditDialog = ref(false)
const editForm = ref({ title: '', assignee_id: null, priority: 'medium', status: 'todo', due_date: '', description: '', reminders: [] })

const openEditDialog = (task) => {
  editingTask.value = task
  editForm.value = { ...task, reminders: task.reminders ? [...task.reminders] : [] }
  showEditDialog.value = true
}

const saveEdit = async () => {
  if (!editForm.value.title) { ElMessage.warning('请输入任务标题'); return }
  try {
    await axios.put(`/api/v1/tasks/${editingTask.value.id}`, editForm.value)
    ElMessage.success('任务更新成功')
    showEditDialog.value = false
    editingTask.value = null
    fetchInProgressTasks()
    fetchUpcomingDeadlines()
    fetchDashboardStats()
  } catch (e) { ElMessage.error('更新任务失败') }
}

const completeTask = async (task) => {
  try {
    await axios.put(`/api/v1/tasks/${task.id}`, { status: 'done' })
    ElMessage.success('任务已完成')
    fetchInProgressTasks()
    fetchUpcomingDeadlines()
    fetchDashboardStats()
  } catch (e) { ElMessage.error('操作失败') }
}

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
  loadingStats.value = false
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
  loadingTasks.value = false
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
  loadingMeetings.value = false
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
  loadingUpcoming.value = false
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

/* ===== 欢迎区 ===== */
.welcome-section {
  background: linear-gradient(135deg, #FF7A5C 0%, #FFB347 100%);
  border-radius: var(--radius-xl);
  padding: 28px 32px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #fff;
  box-shadow: var(--shadow-primary);
  position: relative;
  overflow: hidden;
}

.welcome-glow {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  pointer-events: none;
}
.glow-1 {
  width: 200px;
  height: 200px;
  top: -80px;
  right: 80px;
  animation: pulse 3s ease-in-out infinite;
}
.glow-2 {
  width: 140px;
  height: 140px;
  bottom: -60px;
  right: 200px;
  animation: pulse 3s ease-in-out infinite 1s;
}

.welcome-left { flex: 1; position: relative; z-index: 1; }
.greeting { font-size: var(--font-size-2xl); font-weight: var(--font-weight-bold); margin-bottom: 8px; }
.date-time { display: flex; gap: 12px; margin-bottom: 12px; opacity: 0.9; font-size: var(--font-size-sm); }
.separator { opacity: 0.5; }
.quick-tip { font-size: var(--font-size-sm); }
.tip-text { padding: 4px 12px; background: rgba(255,255,255,0.2); border-radius: var(--radius-full); display: inline-block; }
.tip-text.success { background: rgba(103, 194, 58, 0.3); }

.welcome-right { display: flex; gap: 12px; position: relative; z-index: 1; }

.btn-welcome {
  background: #fff !important;
  color: var(--color-primary) !important;
  border: none !important;
  font-weight: var(--font-weight-semibold);
  box-shadow: var(--shadow-md);
}
.btn-welcome:hover {
  transform: translateY(-2px) scale(1.02);
  box-shadow: var(--shadow-lg) !important;
  filter: brightness(0.97);
}

.btn-welcome-secondary {
  background: rgba(255,255,255,0.15) !important;
  color: #fff !important;
  border: 1px solid rgba(255,255,255,0.3) !important;
  backdrop-filter: blur(8px);
}
.btn-welcome-secondary:hover {
  background: rgba(255,255,255,0.25) !important;
  transform: translateY(-2px);
}

@media (max-width: 768px) {
  .welcome-section { flex-direction: column; gap: 16px; padding: 20px; }
  .greeting { font-size: var(--font-size-xl); }
  .welcome-right { width: 100%; }
  .welcome-right .el-button { flex: 1; }
}

/* ===== 统计卡片 ===== */
.stats-row { margin-bottom: 16px; }

.stat-card {
  border-radius: var(--radius-lg);
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
  transition: transform var(--duration-normal) var(--ease-out),
              box-shadow var(--duration-normal) var(--ease-out);
  margin-bottom: 12px;
}
.stat-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow-md);
}

.stat-icon-wrap {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-content { flex: 1; min-width: 0; }
.stat-label { font-size: var(--font-size-sm); color: var(--color-text-secondary); margin-bottom: 4px; }
.stat-value { font-size: var(--font-size-3xl); font-weight: var(--font-weight-bold); color: var(--color-text-primary); line-height: 1.1; }
.stat-hint { font-size: var(--font-size-xs); color: var(--color-text-placeholder); margin-top: 4px; }

.stat-card-primary { border-left: 4px solid var(--color-primary); }
.stat-card-success { border-left: 4px solid var(--color-success); }
.stat-card-warning { border-left: 4px solid var(--color-warning); }
.stat-card-danger { border-left: 4px solid var(--color-danger); }
.stat-card-danger.has-danger { border: 2px solid var(--color-danger); background: var(--color-danger-bg); }

/* 骨架屏统计卡片 */
.skeleton-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  margin-bottom: 12px;
}
.skeleton-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-lg);
  flex-shrink: 0;
}
.skeleton-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* ===== 通用卡片 ===== */
.content-card { border-radius: var(--radius-lg); margin-bottom: 16px; }
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: var(--font-weight-semibold);
  font-size: var(--font-size-md);
  gap: 10px;
  padding: 16px 20px;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.card-icon { font-size: 18px; }
.card-actions { display: flex; align-items: center; gap: 12px; }
.view-all-btn { color: var(--color-primary); font-weight: var(--font-weight-medium); }
.view-all-btn:hover { color: var(--color-primary-dark); }

.empty-state { display: flex; justify-content: center; align-items: center; padding: 40px 0; }
.empty-state-sm { display: flex; justify-content: center; align-items: center; padding: 20px 0; }

/* ===== 进行中任务分组 ===== */
.task-groups { display: flex; flex-direction: column; gap: 16px; }

.task-group {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: box-shadow var(--duration-normal) var(--ease-out);
}
.task-group:hover { box-shadow: var(--shadow-md); }

/* 骨架屏分组 */
.skeleton-group {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}
.skeleton-group-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--color-bg-warm);
  border-bottom: 1px solid var(--color-border);
}
.skeleton-task-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: linear-gradient(135deg, var(--color-bg-warm) 0%, var(--color-primary-bg) 100%);
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  user-select: none;
  transition: background var(--duration-normal) var(--ease-out);
  position: relative;
}
.group-header:hover {
  background: linear-gradient(135deg, var(--color-primary-bg) 0%, #FFE4DC 100%);
}
.group-header::before {
  content: '';
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  background: var(--color-primary);
  border-radius: 0 4px 4px 0;
  transition: all var(--duration-normal) var(--ease-out);
}
.group-header:hover::before {
  width: 4px;
  height: 24px;
}

.group-avatar { flex-shrink: 0; }
.group-info { display: flex; align-items: center; gap: 10px; flex: 1; }
.group-name { font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); color: var(--color-text-primary); }

.collapse-icon {
  margin-left: auto;
  transition: transform var(--duration-normal) var(--ease-out);
  color: var(--color-text-secondary);
}
.collapse-icon.collapsed { transform: rotate(-90deg); }

.group-tasks { display: flex; flex-direction: column; }

.task-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border-light);
  transition: background var(--duration-fast) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}
.task-row:last-child { border-bottom: none; }
.task-row:hover { background: var(--color-bg-warm); }
.task-row.overdue { background: #FEF8F7; }
.task-row.overdue:hover { background: #FEF0ED; }

.task-content { flex: 1; min-width: 0; }
.task-title {
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-meta { display: flex; align-items: center; gap: 8px; }
.task-due {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  min-width: 80px;
}
.task-due.overdue { color: var(--color-danger); font-weight: var(--font-weight-semibold); }
.task-actions { display: flex; gap: 4px; flex-shrink: 0; }

.btn-success { color: var(--color-success) !important; }
.btn-success:hover { background: var(--color-success-bg) !important; }

/* ===== 即将到期 ===== */
.upcoming-card { border-radius: var(--radius-lg); margin-bottom: 16px; }
.upcoming-list { display: flex; flex-direction: column; }

/* 骨架屏即将到期 */
.skeleton-upcoming {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 0;
  border-bottom: 1px solid var(--color-border-light);
}

.upcoming-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 0;
  border-bottom: 1px solid var(--color-border-light);
  transition: background var(--duration-fast) var(--ease-out);
}
.upcoming-item:last-child { border-bottom: none; }
.upcoming-item:hover { background: var(--color-bg-warm); padding-left: 8px; padding-right: 8px; margin: 0 -8px; }
.upcoming-item.overdue { background: #FEF8F7; }
.upcoming-item.urgent {
  border-left: 4px solid var(--color-warning);
  padding-left: 12px;
  margin-left: -12px;
}
.upcoming-item.urgent.overdue {
  border-left-color: var(--color-danger);
}

.upcoming-left { display: flex; align-items: center; gap: 12px; flex: 1; }
.upcoming-info { flex: 1; min-width: 0; }
.upcoming-title {
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.upcoming-meta { display: flex; align-items: center; gap: 8px; }
.upcoming-assignee { font-size: var(--font-size-xs); color: var(--color-text-secondary); }
.upcoming-right {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}
.due-days {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  padding: 4px 12px;
  background: var(--color-info-bg);
  border-radius: var(--radius-full);
  font-weight: var(--font-weight-medium);
}
.due-days.urgent {
  color: var(--color-danger);
  background: var(--color-danger-bg);
  font-weight: var(--font-weight-semibold);
}

/* ===== 会议列表 ===== */
.meeting-list { display: flex; flex-direction: column; }

/* 骨架屏会议 */
.skeleton-meeting {
  display: flex;
  gap: 16px;
  padding: 14px 0;
  border-bottom: 1px solid var(--color-border-light);
}

.meeting-item {
  display: flex;
  gap: 16px;
  padding: 14px 0;
  border-bottom: 1px solid var(--color-border-light);
  transition: background var(--duration-fast) var(--ease-out);
}
.meeting-item:last-child { border-bottom: none; }
.meeting-item:hover { background: var(--color-bg-warm); padding-left: 8px; padding-right: 8px; margin: 0 -8px; }

.date-box {
  width: 50px;
  height: 50px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
  box-shadow: var(--shadow-primary);
}
.month { font-size: 11px; opacity: 0.9; }
.day { font-size: 18px; font-weight: var(--font-weight-bold); line-height: 1.2; }
.meeting-info { flex: 1; display: flex; flex-direction: column; justify-content: center; }
.meeting-title {
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.meeting-meta { display: flex; align-items: center; gap: 12px; }
.meeting-time { font-size: var(--font-size-xs); color: var(--color-text-secondary); display: flex; align-items: center; gap: 4px; }

/* ===== 通用覆盖 ===== */
.content-card :deep(.el-card__header) { padding: 16px 20px; border-bottom: none; }
</style>

<template>
  <div class="dashboard">
    <!-- 欢迎区域 = 兔子的小窝 -->
    <div class="welcome-section slide-down-fade">
      <!-- 云朵和太阳 -->
      <div class="welcome-cloud cloud-1"></div>
      <div class="welcome-cloud cloud-2"></div>
      <div class="welcome-sun"></div>
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
              <span class="tip-text">⚠️ 团队共有 {{ dashboardData.summary.overdue_tasks }} 项逾期任务</span>
            </el-badge>
          </template>
          <template v-else-if="dashboardData.summary.in_progress_tasks > 0">
            <span class="tip-text success">🎯 团队共有 {{ dashboardData.summary.in_progress_tasks }} 项任务进行中</span>
          </template>
          <template v-else>
            <span class="tip-text">今日任务已完成，继续保持！</span>
          </template>
        </div>
      </div>

      <!-- 🐰 两只兔子 -->
      <div class="welcome-pets">
        <DashboardPet
          type="personal"
          :username="userStore.username"
          :overdue-count="dashboardData.summary?.overdue_tasks ?? 0"
          :in-progress-count="dashboardData.summary?.in_progress_tasks ?? 0"
          :total-tasks="dashboardData.summary?.total_tasks ?? 0"
        />
        <DashboardPet
          type="group"
          :username="userStore.username"
          :total-tasks="dashboardData.summary?.done_tasks ?? 0"
          :group-xp="groupPetStats.total_xp"
          :group-level="groupPetStats.level"
        />
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

      <!-- 草地 -->
      <div class="welcome-grass">
        <span class="grass-item" v-for="i in 8" :key="i" :style="{ left: (i * 12 - 5) + '%', animationDelay: (i * 0.3) + 's' }">🌿</span>
      </div>
    </div>

    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stats-row">
      <!-- 骨架屏 -->
      <template v-if="loadingStats">
        <el-col :xs="12" :sm="6" v-for="i in 3" :key="i">
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
            <div class="stat-icon-wrap stat-icon-wrap--in-progress">
              <el-icon size="28" style="color: var(--color-primary)"><Clock /></el-icon>
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
            <div class="stat-icon-wrap stat-icon-wrap--done">
              <el-icon size="28" style="color: var(--color-success)"><CircleCheck /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-label">已完成</div>
              <div class="stat-value" :ref="el => animateNumber(el, dashboardData.summary?.done_tasks || 0)">0</div>
              <div class="stat-hint">任务完成</div>
            </div>
          </div>
        </el-col>
        <el-col :xs="12" :sm="6">
          <div class="stat-card stat-card-danger fade-slide-up stagger-4 clickable" :class="{ 'has-danger': dashboardData.summary?.overdue_tasks > 0 }" @click="$router.push('/tasks?overdue=true')">
            <div class="stat-icon-wrap stat-icon-wrap--overdue">
              <el-icon size="28" style="color: var(--color-danger)"><Warning /></el-icon>
            </div>
            <div class="stat-content">
              <div class="stat-label">已逾期</div>
              <div class="stat-value" :ref="el => animateNumber(el, dashboardData.summary?.overdue_tasks || 0)">0</div>
              <div class="stat-hint">点击查看逾期任务</div>
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
          <div class="group-header" :class="{ 'unassigned-group': group.assignee_id === 'unassigned' }" @click="toggleGroup(group.assignee_id)">
            <el-avatar
              v-if="group.assignee_id === 'unassigned'"
              :size="40"
              style="background: var(--color-primary)"
              class="avatar group-avatar"
              alt="系统"
            >
              <el-icon size="20"><VideoCamera /></el-icon>
            </el-avatar>
            <el-avatar
              v-else-if="memberStore.getMemberAvatar(group.assignee_id)"
              :src="memberStore.getMemberAvatar(group.assignee_id)"
              :size="40"
              class="avatar group-avatar"
              :alt="`${memberStore.getMemberName(group.assignee_id)}的头像`"
            />
            <el-avatar
              v-else
              :size="40"
              style="background: var(--color-primary)"
              class="avatar group-avatar"
              :alt="`${memberStore.getMemberName(group.assignee_id)}的头像`"
            >
              {{ memberStore.getMemberName(group.assignee_id).charAt(0) }}
            </el-avatar>
            <div class="group-info">
              <span class="group-name" :class="{ 'unassigned-label': group.assignee_id === 'unassigned' }">{{ group.assignee_id === 'unassigned' ? '会议创建的任务' : memberStore.getMemberName(group.assignee_id) }}</span>
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
              <div class="task-content">
                <div class="task-title">{{ task.title }}</div>
                <div class="task-meta">
                  <el-tag :type="getPriorityType(task.priority)" size="small" effect="plain">
                    {{ getPriorityLabel(task.priority) }}
                  </el-tag>
                  <el-tag v-if="task.status === 'in_progress'" size="small" type="warning">进行中</el-tag>
                  <el-tag v-if="task.source === 'meeting'" size="small" type="primary" effect="dark">会议创建</el-tag>
                </div>
              </div>
              <div class="task-due" :class="{ overdue: isOverdue(task.due_date) }">
                <el-icon v-if="isOverdue(task.due_date)" color="#f56c6c"><Warning /></el-icon>
                {{ formatDate(task.due_date) }}
              </div>
              <div class="task-actions">
                <el-button type="success" size="small" round @click="completeTask(task)">✓ 完成</el-button>
                <el-button text type="primary" size="small" @click="openEditDialog(task)">编辑</el-button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-card>

    <!-- 创建任务对话框 -->
    <el-dialog v-model="showCreateTask" title="创建任务" :width="isMobile ? '90vw' : '500px'">
      <el-form :model="newTask" label-width="80px">
        <el-form-item label="任务标题" required>
          <el-input v-model="newTask.title" name="newTask-title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="newTask.assignee_id" name="newTask-assignee_id" placeholder="选择负责人" clearable>
            <el-option v-for="member in members" :key="member.id" :label="member.name" :value="member.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="newTask.priority">
            <el-radio value="high">高</el-radio>
            <el-radio value="medium">中</el-radio>
            <el-radio value="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker
            v-model="newTask.due_date"
            name="newTask-due_date"
            type="datetime"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择截止日期和时间"
            style="width: 100%"
            :clearable="true"
          />
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input v-model="newTask.description" name="newTask-description" type="textarea" :rows="3" placeholder="请输入任务描述" />
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
          <el-input v-model="editForm.title" name="editForm-title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="editForm.assignee_id" name="editForm-assignee_id" placeholder="选择负责人" clearable>
            <el-option v-for="member in members" :key="member.id" :label="member.name" :value="member.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="editForm.priority">
            <el-radio value="high">高</el-radio>
            <el-radio value="medium">中</el-radio>
            <el-radio value="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" name="editForm-status">
            <el-option label="进行中" value="in_progress" />
            <el-option label="阻塞" value="blocked" />
            <el-option label="已完成" value="done" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker
            v-model="editForm.due_date"
            name="editForm-due_date"
            type="datetime"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm:ss"
            placeholder="选择截止日期和时间"
            style="width: 100%"
            :clearable="true"
          />
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input v-model="editForm.description" name="editForm-description" type="textarea" :rows="3" placeholder="请输入任务描述" />
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
import { ArrowDown, VideoCamera, Clock, CircleCheck, Warning, ChatDotRound, Plus } from '@element-plus/icons-vue'
import axios from 'axios'
import dayjs from 'dayjs'
import { formatCompactDate } from '@/utils/format'
import { getPriorityType, getPriorityLabel } from '@/utils/task'
import { useMemberStore } from '@/stores/member'
import { useUserStore } from '@/stores/user'
import DashboardPet from '@/components/DashboardPet.vue'

const memberStore = useMemberStore()
const userStore = useUserStore()
const members = computed(() => memberStore.members)

const dashboardData = ref({})
const groupPetStats = ref({ total_xp: 0, level: 1, tasks_completed: 0 })
const inProgressTasks = ref([])
const showCreateTask = ref(false)
const isMobile = ref(window.innerWidth <= 768)
const currentTime = ref('')
const currentDate = ref('')

// 骨架屏加载状态
const loadingStats = ref(true)
const loadingTasks = ref(true)

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

const handleResize = () => { isMobile.value = window.innerWidth <= 768 }
const updateTime = () => {
  const now = dayjs()
  currentTime.value = now.format('HH:mm:ss')
  currentDate.value = now.format('YYYY年MM月DD日 dddd')
}

onUnmounted(() => { window.removeEventListener('resize', handleResize) })

const newTask = ref({ title: '', assignee_id: null, priority: 'medium', due_date: null, description: '' })

// 编辑相关
const editingTask = ref(null)
const showEditDialog = ref(false)
const editForm = ref({ title: '', assignee_id: null, priority: 'medium', status: 'in_progress', due_date: null, description: '', reminders: [] })

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
    fetchDashboardStats()
  } catch (e) { ElMessage.error('更新任务失败') }
}

const completeTask = async (task) => {
  try {
    await axios.put(`/api/v1/tasks/${task.id}`, { status: 'done' })
    ElMessage.success('任务已完成')
    fetchInProgressTasks()
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

const fetchDashboardStats = async () => {
  try {
    const res = await axios.get('/api/v1/dashboard/stats')
    dashboardData.value = res.data
  } catch (e) { console.error('获取仪表盘数据失败:', e) }
  loadingStats.value = false
}

// 获取进行中任务（待办+进行中+阻塞，与任务管理"进行中"定义一致）
const fetchInProgressTasks = async () => {
  try {
    const res = await axios.get('/api/v1/tasks', { params: { page_size: 100 } })
    const allTasks = (res.data.items || []).filter(t => t.status !== 'done')
    // 排序：未分配优先 → 优先级（高>中>低）→ 截止时间（早→晚）
    allTasks.sort((a, b) => {
      // 未分配任务排最前
      const aUnassigned = !a.assignee_id ? 0 : 1
      const bUnassigned = !b.assignee_id ? 0 : 1
      if (aUnassigned !== bUnassigned) return aUnassigned - bUnassigned
      const priorityOrder = { high: 3, medium: 2, low: 1 }
      const pDiff = (priorityOrder[b.priority] || 0) - (priorityOrder[a.priority] || 0)
      if (pDiff !== 0) return pDiff
      if (!a.due_date && !b.due_date) return 0
      if (!a.due_date) return 1
      if (!b.due_date) return -1
      return dayjs(a.due_date).diff(dayjs(b.due_date))
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
    // 未分配任务始终排在最前
    if (a.assignee_id === 'unassigned' && b.assignee_id !== 'unassigned') return -1
    if (b.assignee_id === 'unassigned' && a.assignee_id !== 'unassigned') return 1
    // 按时长逾期分组显示
    const aHasOverdue = a.tasks.some(t => isOverdue(t.due_date))
    const bHasOverdue = b.tasks.some(t => isOverdue(t.due_date))
    if (aHasOverdue && !bHasOverdue) return -1
    if (!aHasOverdue && bHasOverdue) return 1
    // 按任务数量降序
    return b.tasks.length - a.tasks.length
  })
})

const fetchMembers = () => memberStore.fetchMembers()

const createTask = async () => {
  if (!newTask.value.title) { ElMessage.warning('请输入任务标题'); return }
  try {
    await axios.post('/api/v1/tasks', newTask.value)
    ElMessage.success('任务创建成功')
    showCreateTask.value = false
    newTask.value = { title: '', assignee_id: null, priority: 'medium', due_date: null, description: '' }
    fetchInProgressTasks()
    fetchDashboardStats()
  } catch (e) { ElMessage.error('创建任务失败') }
}

const formatDate = (date) => formatCompactDate(date, '无截止')
const isOverdue = (date) => date && dayjs(date).isBefore(dayjs())

onMounted(() => {
  updateTime()
  setInterval(updateTime, 1000)
  fetchDashboardStats()
  fetchInProgressTasks()
  memberStore.refreshMembers() // 强制刷新获取最新头像
  window.addEventListener('resize', handleResize)
})
</script>

<style scoped>

.dashboard { max-width: 1400px; padding-bottom: 30px; }

/* ===== 欢迎区 ===== */
.welcome-section {
  background: var(--gradient-welcome-hero); /* v69 P0: 用 CSS 变量，dark 模式自动压暗 */
  border-radius: var(--radius-xl);
  padding: 28px 32px;
  margin-bottom: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: var(--el-color-white);
  box-shadow: var(--shadow-primary);
  position: relative;
  overflow: visible;
}

/* 云朵 */
.welcome-cloud {
  position: absolute;
  background: rgba(255, 255, 255, 0.25);
  border-radius: 50%;
  pointer-events: none;
  filter: blur(8px);
}
.cloud-1 {
  width: 120px; height: 50px;
  top: 8px; right: 60px;
  animation: pet-cloud-drift 20s ease-in-out infinite;
}
.cloud-2 {
  width: 80px; height: 35px;
  top: 20px; right: 200px;
  animation: pet-cloud-drift 25s ease-in-out infinite 5s;
}
/* 太阳 */
.welcome-sun {
  position: absolute;
  top: 12px; right: 30px;
  width: 32px; height: 32px;
  background: rgba(255, 220, 100, 0.8);
  border-radius: 50%;
  box-shadow: 0 0 30px rgba(255, 200, 80, 0.6), 0 0 70px rgba(255, 180, 60, 0.3);
  pointer-events: none;
  animation: pet-sun-glow 3s ease-in-out infinite;
}
/* 宠物区域 — 填充中间空间，给兔子最大活动范围 */
.welcome-pets {
  flex: 1;
  display: flex;
  gap: 20px;
  align-items: center;
  justify-content: center;
  position: relative;
  z-index: 4;
  min-height: 120px;
  height: 100%;
  padding-bottom: 4px;
  align-self: stretch;
}

/* 草地 */
.welcome-grass {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  height: 36px;
  background: linear-gradient(to top, rgba(129, 199, 132, 0.45), transparent);
  border-radius: 0 0 var(--radius-xl) var(--radius-xl);
  z-index: 1;
  pointer-events: none;
  overflow: hidden;
}
.grass-item {
  position: absolute;
  bottom: 4px;
  font-size: 16px;
  z-index: 2;
  animation: pet-grass-sway 3s ease-in-out infinite;
  pointer-events: none;
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
  background: var(--color-bg-card) !important;
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
  color: var(--el-color-white) !important;
  border: 1px solid rgba(255,255,255,0.3) !important;
  backdrop-filter: blur(8px);
}
.btn-welcome-secondary:hover {
  background: rgba(255,255,255,0.25) !important;
  transform: translateY(-2px);
}

@media (max-width: 768px) {
  .welcome-section { flex-direction: column; gap: 12px; padding: 16px 20px; }
  .greeting { font-size: var(--font-size-xl); }
  .welcome-pets { gap: 8px; min-height: 90px; transform: scale(0.75); transform-origin: center bottom; }
  .welcome-right { width: 100%; }
  .welcome-right .el-button { flex: 1; }
  .welcome-grass { height: 24px; }
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
.stat-card.clickable { cursor: pointer; }
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
/* v69 P0: stat-icon 渐变改用 CSS 变量（dark 模式变量已在 variables.css 中切换到 rgba 透明） */
.stat-icon-wrap--in-progress { background: var(--gradient-stat-in-progress); }
.stat-icon-wrap--done        { background: var(--gradient-stat-done); }
.stat-icon-wrap--overdue     { background: var(--gradient-stat-overdue); }

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

.group-header.unassigned-group {
  background: rgba(64,158,255,0.06) !important;
  border: 1px solid rgba(64,158,255,0.2);
  border-radius: var(--radius-lg);
}
.unassigned-label { color: var(--color-primary); font-weight: var(--font-weight-bold); }
.group-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--gradient-group-header); /* v69 P0: 用 CSS 变量，dark 模式自动切深灰→半透明橙 */
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  user-select: none;
  transition: background var(--duration-normal) var(--ease-out);
  position: relative;
}
.group-header:hover {
  background: linear-gradient(135deg, var(--color-primary-bg) 0%, #FFE4DC 100%);
}
[data-theme="dark"] .group-header:hover {
  background: linear-gradient(135deg, var(--color-bg-hover) 0%, var(--color-primary-bg) 100%);
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
.task-row.overdue { background: var(--color-primary-bg); }
.task-row.overdue:hover { background: var(--color-primary-bg); }

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

/* ===== 通用覆盖 ===== */
.content-card :deep(.el-card__header) { padding: 16px 20px; border-bottom: none; }
</style>

<!-- v69 P0: Dashboard dark mode 覆盖（v60-v67 教训：dark 跨组件规则必须非 scoped） -->
<style>
  /* === 状态卡 === */
  [data-theme="dark"] .stat-card {
    background: var(--color-bg-card);
    border-color: var(--color-border-base);
    box-shadow: var(--shadow-sm);
  }
  [data-theme="dark"] .stat-card:hover {
    box-shadow: var(--shadow-md);
    border-color: var(--color-primary-border);
  }
  [data-theme="dark"] .stat-value { color: var(--color-text-primary); }
  [data-theme="dark"] .stat-label { color: var(--color-text-secondary); }
  [data-theme="dark"] .stat-hint { color: var(--color-text-placeholder); }
  [data-theme="dark"] .stat-card-danger.has-danger { background: var(--color-danger-bg); border-color: rgba(247, 137, 137, 0.5); }

  /* === 任务配对卡 group-header（已在 scoped 改用变量，dark 块仅保 hover） === */
  [data-theme="dark"] .group-header {
    border-bottom-color: var(--color-border-light);
  }
  [data-theme="dark"] .group-name { color: var(--color-text-primary); }
  [data-theme="dark"] .group-info .task-count { color: var(--color-text-secondary); }

  /* === task-row（子任务） === */
  [data-theme="dark"] .task-row { border-bottom-color: var(--color-border-light); }
  [data-theme="dark"] .task-row:hover { background: var(--color-bg-hover); }
  [data-theme="dark"] .task-row.overdue { background: rgba(247, 137, 137, 0.08); }
  [data-theme="dark"] .task-row.overdue:hover { background: rgba(247, 137, 137, 0.15); }
  [data-theme="dark"] .task-title { color: var(--color-text-primary); }
  [data-theme="dark"] .task-due { color: var(--color-text-regular); } /* v69 提亮（之前 #909399 太暗） */
  [data-theme="dark"] .task-due.overdue { color: var(--color-danger); }

  /* === 章节标题 + 查看全部 === */
  [data-theme="dark"] .section-title { color: var(--color-text-primary); }
  [data-theme="dark"] .view-all-btn { color: var(--color-primary); }
  [data-theme="dark"] .view-all-btn:hover { color: var(--color-primary-light); }

  /* === unassigned / 空状态 === */
  [data-theme="dark"] .group-header.unassigned-group {
    background: var(--color-bg-card);
    border-color: var(--color-border-base);
  }
  [data-theme="dark"] .unassigned-label { color: var(--color-text-regular); }
  [data-theme="dark"] .empty-state,
  [data-theme="dark"] .no-data { color: var(--color-text-secondary); }

  /* === 加载/骨架 === */
  [data-theme="dark"] .skeleton-card,
  [data-theme="dark"] .skeleton-group-header,
  [data-theme="dark"] .skeleton-task-row {
    background: var(--color-bg-card);
    border-color: var(--color-border-base);
  }

  /* === 动画相关（hero 在 dark 模式文字保持白色） === */
  [data-theme="dark"] .welcome-text { color: var(--color-bg-card); }
  [data-theme="dark"] .tip-text { color: rgba(255, 255, 255, 0.9); }
  [data-theme="dark"] .btn-welcome { color: var(--color-bg-card); }
  [data-theme="dark"] .btn-welcome-secondary { color: var(--color-bg-card); background: rgba(255, 255, 255, 0.15); border: 1px solid rgba(255, 255, 255, 0.3); }
</style>

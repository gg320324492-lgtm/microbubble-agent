<template>
  <div class="task-view">
    <!-- Tab 切换：任务列表 / 垃圾桶 -->
    <el-tabs v-model="activeTab" class="task-tabs">
      <el-tab-pane label="任务列表" name="tasks">
        <!-- 顶部操作栏 -->
        <el-card class="filter-card card fade-slide-up stagger-1">
          <el-row :gutter="16" align="middle">
            <el-col :xs="12" :sm="12" :md="6">
              <el-select v-model="filters.status" name="filters-status" placeholder="任务状态" clearable>
                <el-option label="进行中" value="in_progress" />
                <el-option label="阻塞" value="blocked" />
                <el-option label="已完成" value="done" />
              </el-select>
            </el-col>
            <el-col :xs="12" :sm="12" :md="6">
              <el-select v-model="filters.assignee_id" name="filters-assignee_id" placeholder="负责人" clearable>
                <el-option
                  v-for="member in members"
                  :key="member.id"
                  :label="member.name"
                  :value="member.id"
                />
              </el-select>
            </el-col>
            <el-col :xs="12" :sm="12" :md="6">
              <el-select v-model="filters.priority" name="filters-priority" placeholder="优先级" clearable>
                <el-option label="高" value="high" />
                <el-option label="中" value="medium" />
                <el-option label="低" value="low" />
              </el-select>
            </el-col>
            <el-col :xs="12" :sm="12" :md="6">
              <el-button type="primary" class="btn btn-primary" @click="showCreateDialog = true">
                <el-icon><Plus /></el-icon>
                创建任务
              </el-button>
            </el-col>
          </el-row>
        </el-card>

        <!-- 任务列表 -->
        <el-card class="task-list-card card fade-slide-up stagger-2">
          <el-row :gutter="16">
            <el-col :span="12">
              <!-- 未完成 Section -->
              <div class="task-section">
            <div class="section-header">
              <span class="section-title">📋 进行中</span>
              <el-badge :value="activeTasks.length" type="warning" />
            </div>
            <div v-if="activeTasks.length === 0" class="empty-section">
              <span>暂无进行中任务</span>
            </div>
            <div v-else class="task-groups">
              <div v-for="(group, gIdx) in groupedActiveTasks" :key="group.assignee_id" class="task-group fade-slide-up" :style="{ animationDelay: `${(gIdx + 2) * 80}ms` }">
                <!-- 负责人头部（可点击折叠） -->
                <div class="group-header" @click="toggleGroup(group.assignee_id)">
                  <el-avatar
                    v-if="memberStore.getMemberAvatar(group.assignee_id)"
                    :src="memberStore.getMemberAvatar(group.assignee_id)"
                    :size="36"
                    class="group-avatar"
                  />
                  <el-avatar v-else :size="36" style="background: var(--color-primary)" class="group-avatar">
                    {{ memberStore.getMemberName(group.assignee_id).charAt(0) }}
                  </el-avatar>
                  <span class="group-name">{{ memberStore.getMemberName(group.assignee_id) }}</span>
                  <el-tag size="small" type="info">{{ group.tasks.length }}项</el-tag>
                  <el-icon class="collapse-icon" :class="{ collapsed: collapsedGroups[group.assignee_id] }"><ArrowDown /></el-icon>
                </div>
                <!-- 任务列表 -->
                <div v-show="!collapsedGroups[group.assignee_id]" class="group-tasks">
                  <div
                    v-for="task in group.tasks"
                    :key="task.id"
                    class="task-row"
                    :class="{ overdue: isOverdue(task) }"
                  >
                    <el-button
                      circle
                      size="default"
                      class="complete-btn complete-btn--outline"
                      @click="toggleTaskStatus(task)"
                      title="标记完成"
                    >
                      <el-icon size="18"><Check /></el-icon>
                    </el-button>
                    <div class="task-content">
                      <div class="task-title">{{ task.title }}</div>
                      <div class="task-meta">
                        <el-tag :type="getPriorityType(task.priority)" size="small" effect="plain">
                          {{ getPriorityLabel(task.priority) }}
                        </el-tag>
                        <el-tag v-if="task.status === 'in_progress'" size="small" type="warning">进行中</el-tag>
                        <el-tag v-else-if="task.status === 'blocked'" size="small" type="danger">阻塞</el-tag>
                      </div>
                    </div>
                    <div class="task-due" :class="{ overdue: isOverdue(task) }">
                      <el-icon v-if="isOverdue(task)" color="var(--color-danger)"><Warning /></el-icon>
                      {{ formatDate(task.due_date) }}
                    </div>
                    <div class="task-actions">
                      <template v-if="isAdmin || task.created_by === currentUserId || task.assignee_id === currentUserId">
                        <el-button text type="primary" @click="editTask(task)">
                          <el-icon><Edit /></el-icon>
                          编辑
                        </el-button>
                        <el-button text type="danger" @click="deleteTask(task)">
                          <el-icon><Delete /></el-icon>
                          删除
                        </el-button>
                      </template>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
            </el-col>
            <el-col :span="12">
              <!-- 已完成 Section -->
          <div class="task-section done-section">
            <div class="section-header">
              <span class="section-title">✅ 已完成</span>
              <el-badge :value="doneTasks.length" type="success" />
            </div>
            <div v-if="doneTasks.length === 0" class="empty-section">
              <span>暂无已完成任务</span>
            </div>
            <div v-else class="task-groups">
              <div v-for="(group, gIdx) in groupedDoneTasks" :key="group.assignee_id" class="task-group done-group fade-slide-up" :style="{ animationDelay: `${(gIdx + 3) * 80}ms` }">
                <!-- 负责人头部（可点击折叠） -->
                <div class="group-header" @click="toggleGroup(group.assignee_id)">
                  <el-avatar
                    v-if="memberStore.getMemberAvatar(group.assignee_id)"
                    :src="memberStore.getMemberAvatar(group.assignee_id)"
                    :size="36"
                    class="group-avatar"
                  />
                  <el-avatar v-else :size="36" style="background: var(--color-success)" class="group-avatar">
                    {{ memberStore.getMemberName(group.assignee_id).charAt(0) }}
                  </el-avatar>
                  <span class="group-name">{{ memberStore.getMemberName(group.assignee_id) }}</span>
                  <el-tag size="small" type="info">{{ group.tasks.length }}项</el-tag>
                  <el-icon class="collapse-icon" :class="{ collapsed: collapsedGroups[group.assignee_id] }"><ArrowDown /></el-icon>
                </div>
                <!-- 任务列表 -->
                <div v-show="!collapsedGroups[group.assignee_id]" class="group-tasks">
                  <div
                    v-for="task in group.tasks"
                    :key="task.id"
                    class="task-row done-row"
                  >
                    <el-button
                      circle
                      size="default"
                      class="complete-btn complete-btn--done"
                      @click="toggleTaskStatus(task)"
                      title="取消完成"
                    >
                      <el-icon size="18"><Check /></el-icon>
                    </el-button>
                    <div class="task-content">
                      <div class="task-title task-done">{{ task.title }}</div>
                      <div class="task-meta">
                        <el-tag size="small" type="success">已完成</el-tag>
                      </div>
                    </div>
                    <div class="task-actions">
                      <template v-if="isAdmin || task.created_by === currentUserId || task.assignee_id === currentUserId">
                        <el-button text type="danger" @click="deleteTask(task)">
                          <el-icon><Delete /></el-icon>
                          删除
                        </el-button>
                      </template>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
            </el-col>
          </el-row>
        </el-card>
      </el-tab-pane>

      <el-tab-pane name="trash">
        <template #label>
          <span>垃圾桶 <el-badge :value="trashCount" :hidden="trashCount === 0" class="trash-badge" /></span>
        </template>
        <!-- 垃圾桶列表 -->
        <el-card class="task-list-card">
          <div style="overflow-x: auto">
          <el-table :data="trashTasks" stripe style="width: 100%">
            <el-table-column prop="title" label="任务标题" min-width="200">
              <template #default="{ row }">
                <div class="task-title-cell">
                  <el-icon color="#909399"><Delete /></el-icon>
                  <span class="task-deleted">{{ row.title }}</span>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="assignee_id" label="负责人" width="150">
              <template #default="{ row }">
                <div class="assignee-cell">
                  <el-avatar v-if="memberStore.getMemberAvatar(row.assignee_id)" :src="memberStore.getMemberAvatar(row.assignee_id)" :size="24" />
                  <el-avatar v-else :size="24" style="background: #409eff">{{ memberStore.getMemberName(row.assignee_id).charAt(0) }}</el-avatar>
                  <span>{{ memberStore.getMemberName(row.assignee_id) }}</span>
                </div>
              </template>
            </el-table-column>

            <el-table-column prop="status" label="原状态" width="120">
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)" size="small">
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column label="删除时间" width="140">
              <template #default="{ row }">
                <span class="deleted-time">{{ formatDate(row.deleted_at) }}</span>
              </template>
            </el-table-column>

            <el-table-column label="自动删除" width="170">
              <template #default="{ row }">
                <div v-if="row.auto_delete_at" class="auto-delete-cell">
                  <div :class="['auto-delete-relative', getAutoDeleteClass(row.auto_delete_at)]">
                    <el-icon v-if="getAutoDeleteIcon(row.auto_delete_at)" class="auto-delete-icon">
                      <Clock />
                    </el-icon>
                    {{ getAutoDeleteText(row.auto_delete_at) }}
                  </div>
                  <div class="auto-delete-absolute">
                    {{ formatAutoDeleteExact(row.auto_delete_at) }} {{ isAutoDeleteOverdue(row.auto_delete_at) ? '到期' : '删除' }}
                  </div>
                </div>
                <span v-else class="auto-delete-none">—</span>
              </template>
            </el-table-column>

            <el-table-column label="操作" width="220" fixed="right">
              <template #default="{ row }">
                <div class="task-actions">
                  <template v-if="isAdmin || row.created_by === currentUserId || row.assignee_id === currentUserId">
                    <el-button text type="success" @click="restoreTask(row)">
                      <el-icon><RefreshRight /></el-icon>
                      恢复
                    </el-button>
                    <el-button text type="danger" @click="permanentDeleteTask(row)">
                      <el-icon><DeleteFilled /></el-icon>
                      永久删除
                    </el-button>
                  </template>
                  <span v-else class="no-permission">--</span>
                </div>
              </template>
            </el-table-column>
          </el-table>
          </div>

          <!-- 分页 -->
          <div class="pagination">
            <el-pagination
              v-model:current-page="trashPage"
              v-model:page-size="trashPageSize"
              :page-sizes="[10, 20, 50]"
              :total="trashTotal"
              layout="total, sizes, prev, pager, next"
              @size-change="fetchTrashTasks"
              @current-change="fetchTrashTasks"
            />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 创建/编辑任务对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingTask ? '编辑任务' : '创建任务'"
      :width="isMobile ? '90vw' : '500px'"
      top="8vh"
    >
      <el-form :model="taskForm" label-width="80px">
        <el-form-item label="任务标题" required>
          <el-input v-model="taskForm.title" name="taskForm-title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-if="isAdmin" v-model="taskForm.assignee_id" name="taskForm-assignee_id" placeholder="选择负责人" clearable>
            <el-option
              v-for="member in members"
              :key="member.id"
              :label="member.name"
              :value="member.id"
            />
          </el-select>
          <el-select v-else v-model="taskForm.assignee_id" name="taskForm-assignee_id" disabled>
            <el-option :label="userStore.userInfo?.name" :value="currentUserId" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-radio-group v-model="taskForm.priority">
            <el-radio label="high">高</el-radio>
            <el-radio label="medium">中</el-radio>
            <el-radio label="low">低</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="状态" v-if="editingTask">
          <el-select v-model="taskForm.status" name="taskForm-status">
            <el-option label="进行中" value="in_progress" />
            <el-option label="阻塞" value="blocked" />
            <el-option label="已完成" value="done" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期">
          <input
    :value="taskForm.due_date"
    name="taskForm-due_date"
    type="datetime-local"
    class="native-date-input"
    placeholder="选择截止日期和时间"
    @change="(e) => { const v = e.target.value; taskForm.due_date = v ? v.replace('T', ' ') + ':00' : ''; }"
  />
        </el-form-item>
        <el-form-item label="提醒设置">
          <div v-for="(reminder, index) in taskForm.reminders" :key="index" class="reminder-item">
            <input
    :value="reminder.remind_at"
    name="reminder-remind_at"
    type="datetime-local"
    class="native-date-input"
    placeholder="选择提醒时间"
    style="width: 200px"
    @change="(e) => { const v = e.target.value; reminder.remind_at = v ? v.replace('T', ' ') + ':00' : ''; }"
  />
            <el-select v-model="reminder.remind_type" name="reminder-remind_type" style="width: 90px; margin-left: 8px;">
              <el-option label="微信" value="wechat" />
              <el-option label="邮件" value="email" />
            </el-select>
            <el-button text type="danger" @click="taskForm.reminders.splice(index, 1)" style="margin-left: 4px;">
              删除
            </el-button>
          </div>
          <el-button text type="primary" @click="taskForm.reminders.push({ remind_at: '', remind_type: 'wechat' })">
            + 添加提醒
          </el-button>
          <div class="reminder-hint">不设置则使用默认提醒（截止前2天 + 截止当天9点）</div>
        </el-form-item>
        <el-form-item label="任务描述">
          <el-input
            v-model="taskForm.description" name="taskForm-description"
            type="textarea"
            :rows="3"
            placeholder="请输入任务描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveTask">{{ editingTask ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Check, Edit, Delete, RefreshRight, DeleteFilled, Clock } from '@element-plus/icons-vue'
import axios from 'axios'

const route = useRoute()
import dayjs from 'dayjs'
import { formatDate } from '@/utils/format'
import { getStatusType, getPriorityType, getStatusLabel, getPriorityLabel } from '@/utils/task'
import { useUserStore } from '@/stores/user'
import { useMemberStore } from '@/stores/member'

const userStore = useUserStore()
const memberStore = useMemberStore()
const members = computed(() => memberStore.members)
const isAdmin = computed(() => {
  const role = userStore.userInfo?.role
  return role === 'admin' || role === 'leader'
})
const currentUserId = computed(() => userStore.userInfo?.id)

const isMobile = ref(window.innerWidth <= 768)
const activeTab = ref('tasks')
const tasks = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(100)
const showCreateDialog = ref(false)
const editingTask = ref(null)
const trashTasks = ref([])
const trashTotal = ref(0)
const trashPage = ref(1)
const trashPageSize = ref(20)
const trashCount = ref(0)

// 2026-06-03：实时倒计时驱动器
// `now` 每 30s 刷新一次，触发 getAutoDeleteText 等 computed 重新计算，
// 用户停留在垃圾桶 tab 时看到的时间不会"卡住"
const now = ref(dayjs())
let autoDeleteTimer = null
onMounted(() => {
  autoDeleteTimer = setInterval(() => {
    now.value = dayjs()
  }, 30 * 1000)
})
onUnmounted(() => {
  if (autoDeleteTimer) {
    clearInterval(autoDeleteTimer)
    autoDeleteTimer = null
  }
})

const filters = ref({
  status: '',
  assignee_id: '',
  priority: ''
})

// 分组折叠状态
const collapsedGroups = ref({})
const toggleGroup = (assigneeId) => {
  collapsedGroups.value[assigneeId] = !collapsedGroups.value[assigneeId]
}

// 按状态分离任务
const activeTasks = computed(() => {
  return tasks.value.filter(t => t.status !== 'done')
})

const doneTasks = computed(() => {
  return tasks.value.filter(t => t.status === 'done')
})

// 按负责人分组
function groupTasksByAssignee(taskList) {
  const groups = {}
  for (const task of taskList) {
    const id = task.assignee_id || 'unassigned'
    if (!groups[id]) {
      groups[id] = { assignee_id: id, tasks: [] }
    }
    groups[id].tasks.push(task)
  }
  // 组内按优先级（高>中>低），同优先级按截止时间（早→晚）
  const priorityOrder = { high: 3, medium: 2, low: 1 }
  for (const g of Object.values(groups)) {
    g.tasks.sort((a, b) => {
      const pDiff = (priorityOrder[b.priority] || 0) - (priorityOrder[a.priority] || 0)
      if (pDiff !== 0) return pDiff
      if (!a.due_date && !b.due_date) return 0
      if (!a.due_date) return 1
      if (!b.due_date) return -1
      return dayjs(a.due_date).diff(dayjs(b.due_date))
    })
  }
  return Object.values(groups).sort((a, b) => {
    // 组间按任务数量降序
    return b.tasks.length - a.tasks.length
  })
}

const groupedActiveTasks = computed(() => groupTasksByAssignee(activeTasks.value))
const groupedDoneTasks = computed(() => groupTasksByAssignee(doneTasks.value))

const taskForm = ref({
  title: '',
  assignee_id: null,
  priority: 'medium',
  status: 'in_progress',
  due_date: null,
  description: '',
  reminders: []
})

// 获取任务列表
const fetchTasks = async () => {
  try {
    // 过滤掉空值参数，避免 FastAPI 422 验证错误
    const activeFilters = Object.fromEntries(
      Object.entries(filters.value).filter(([_, v]) => v !== '' && v !== null && v !== undefined)
    )
    const params = {
      page: currentPage.value,
      page_size: pageSize.value,
      include_deleted: false,
      ...activeFilters
    }
    // 支持从 URL query 参数传入 overdue 过滤
    if (route.query.overdue === 'true') {
      params.overdue = true
    }
    const res = await axios.get('/api/v1/tasks', { params })
    tasks.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    console.error('获取任务失败:', e)
  }
}

// 获取垃圾桶任务
const fetchTrashTasks = async () => {
  try {
    const res = await axios.get('/api/v1/tasks', {
      params: {
        page: trashPage.value,
        page_size: trashPageSize.value,
        include_deleted: true
      }
    })
    trashTasks.value = res.data.items || []
    trashTotal.value = res.data.total || 0
    trashCount.value = res.data.total || 0
  } catch (e) {
    console.error('获取垃圾桶失败:', e)
  }
}

// 获取成员列表（使用 store）
const fetchMembers = () => memberStore.fetchMembers()

// 保存任务
const saveTask = async () => {
  if (!taskForm.value.title) {
    ElMessage.warning('请输入任务标题')
    return
  }

  try {
    if (editingTask.value) {
      await axios.put(`/api/v1/tasks/${editingTask.value.id}`, taskForm.value)
      ElMessage.success('任务更新成功')
    } else {
      await axios.post('/api/v1/tasks', taskForm.value)
      ElMessage.success('任务创建成功')
    }
    showCreateDialog.value = false
    editingTask.value = null
    resetForm()
    fetchTasks()
  } catch (e) {
    const msg = e.response?.data?.detail || '操作失败'
    ElMessage.error(msg)
  }
}

// 编辑任务
const editTask = (task) => {
  editingTask.value = task
  taskForm.value = {
    ...task,
    reminders: task.reminders ? [...task.reminders] : []
  }
  showCreateDialog.value = true
}

// 删除任务
const deleteTask = async (task) => {
  try {
    await ElMessageBox.confirm('确定要删除这个任务吗？删除后可从垃圾桶恢复。', '确认删除', {
      type: 'warning'
    })
    await axios.delete(`/api/v1/tasks/${task.id}`)
    ElMessage.success('任务已移入垃圾桶')
    fetchTasks()
    fetchTrashTasks()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 恢复任务
const restoreTask = async (task) => {
  try {
    await ElMessageBox.confirm('确定要恢复这个任务吗？', '确认恢复', {
      type: 'warning'
    })
    await axios.post(`/api/v1/tasks/${task.id}/restore`)
    ElMessage.success('任务已恢复')
    fetchTasks()
    fetchTrashTasks()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('恢复失败')
    }
  }
}

// 永久删除任务
const permanentDeleteTask = async (task) => {
  try {
    await ElMessageBox.confirm('确定要永久删除这个任务吗？此操作不可恢复！', '永久删除', {
      type: 'error',
      confirmButtonText: '永久删除',
      cancelButtonText: '取消'
    })
    await axios.delete(`/api/v1/tasks/${task.id}/permanent`)
    ElMessage.success('任务已永久删除')
    fetchTrashTasks()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('永久删除失败')
    }
  }
}

// 切换任务状态
const toggleTaskStatus = async (task) => {
  const newStatus = task.status === 'done' ? 'in_progress' : 'done'
  try {
    await axios.put(`/api/v1/tasks/${task.id}`, { status: newStatus })
    fetchTasks()
  } catch (e) {
    const msg = e.response?.data?.detail || '更新失败'
    ElMessage.error(msg)
  }
}

// 重置表单
const resetForm = () => {
  taskForm.value = {
    title: '',
    assignee_id: isAdmin.value ? null : currentUserId.value,
    priority: 'medium',
    status: 'in_progress',
    due_date: null,
    description: '',
    reminders: []
  }
}

// 辅助函数
const getMemberName = (id) => memberStore.getMemberName(id)

const isOverdue = (task) => {
  if (!task.due_date || task.status === 'done') return false
  return dayjs(task.due_date).isBefore(dayjs())
}

// 计算自动删除倒计时（2026-06-03 优化）
// 输入是后端预计算的 auto_delete_at = deleted_at + retention_days，
// 前端不再硬编码 retention 天数，与后端 TRASH_RETENTION_DAYS 配置保持同步
// `now` 是响应式 ref，每 30s 刷新以驱动实时倒计时
const getAutoDeleteText = (autoDeleteAt) => {
  if (!autoDeleteAt) return ''
  const expire = dayjs(autoDeleteAt)
  const diffMin = expire.diff(now.value, 'minute')
  const diffHour = expire.diff(now.value, 'hour')
  const diffDay = Math.floor(diffMin / (60 * 24))
  const remHourOfDay = Math.floor((diffMin % (60 * 24)) / 60)
  const remMin = diffMin % 60

  // 已过期：auto_delete_at 过了但 beat 还没到下次调度（1h 内会被清理）
  // 用「等待下次清理」代替「即将自动删除」，避免用户以为是 bug
  if (diffMin <= 0) return '等待下次清理'
  // < 1 小时：精确到分钟
  if (diffMin < 60) return `${diffMin} 分钟后删除`
  // < 1 天：X 小时 Y 分（如 "5 小时 23 分后删除"）
  if (diffMin < 24 * 60) {
    if (remMin > 0) return `${diffHour} 小时 ${remMin} 分后删除`
    return `${diffHour} 小时后删除`
  }
  // >= 1 天：X 天 Y 小时（如 "1 天 5 小时后删除"）
  if (remHourOfDay > 0) return `${diffDay} 天 ${remHourOfDay} 小时后删除`
  return `${diffDay} 天后删除`
}

// 工具：剩余小时数（用于颜色分级）
const getAutoDeleteHours = (autoDeleteAt) => {
  if (!autoDeleteAt) return Infinity
  return dayjs(autoDeleteAt).diff(now.value, 'hour', true)
}

// 是否已过期（用于副标题 "到期" vs "删除" 文案区分）
const isAutoDeleteOverdue = (autoDeleteAt) => {
  if (!autoDeleteAt) return false
  return dayjs(autoDeleteAt).isBefore(now.value)
}

// 颜色分级：< 6h 红 / 6-24h 橙 / 24-72h 黄 / > 72h 灰
const getAutoDeleteClass = (autoDeleteAt) => {
  const hours = getAutoDeleteHours(autoDeleteAt)
  if (hours <= 0) return 'auto-delete-imminent'
  if (hours <= 6) return 'auto-delete-urgent'
  if (hours <= 24) return 'auto-delete-warning'
  if (hours <= 72) return 'auto-delete-normal'
  return 'auto-delete-safe'
}

// 紧急时显示时钟图标
const getAutoDeleteIcon = (autoDeleteAt) => {
  return getAutoDeleteHours(autoDeleteAt) <= 24
}

// 准确删除时间（用于 tooltip）—— "06-04 14:30"
const formatAutoDeleteExact = (autoDeleteAt) => {
  return dayjs(autoDeleteAt).format('MM-DD HH:mm')
}

// 监听 Tab 切换
watch(activeTab, (newTab) => {
  if (newTab === 'tasks') {
    currentPage.value = 1
    fetchTasks()
  } else if (newTab === 'trash') {
    trashPage.value = 1
    fetchTrashTasks()
  }
})

watch(filters, () => {
  currentPage.value = 1
  fetchTasks()
}, { deep: true })

onMounted(() => {
  fetchTasks()
  fetchTrashTasks()
  fetchMembers()
})
</script>

<style scoped>

/* 2026-06-02 原生 date input 样式（绕过 el-date-picker 内部 input 缺 name 的 a11y 警告） */
.native-date-input {
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--color-border, #dcdfe6);
  border-radius: var(--radius-md, 4px);
  background: #fff;
  color: var(--color-text-primary, #303133);
  font-size: 14px;
  font-family: inherit;
  transition: border-color 0.2s;
}
.native-date-input:focus {
  outline: none;
  border-color: var(--color-primary, #FF7A5C);
}

.task-view {
  height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* ===== 筛选卡片 ===== */
.filter-card {
  margin-bottom: 0;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
  background: var(--color-bg-card);
  transition: box-shadow var(--duration-normal) var(--ease-out);
}
.filter-card:hover {
  box-shadow: var(--shadow-md);
}

/* ===== Tabs ===== */
.task-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
}
.task-tabs :deep(.el-tabs__header) {
  margin-bottom: 16px;
}
.task-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
  background: var(--color-border);
}
.task-tabs :deep(.el-tabs__item) {
  font-weight: var(--font-weight-medium);
  font-size: var(--font-size-md);
  color: var(--color-text-secondary);
  transition: color var(--duration-fast) var(--ease-out);
}
.task-tabs :deep(.el-tabs__item.is-active) {
  color: var(--color-primary);
  font-weight: var(--font-weight-semibold);
}
.task-tabs :deep(.el-tabs__active-bar) {
  background: var(--color-primary);
  height: 3px;
  border-radius: 2px;
}
.task-tabs :deep(.el-tabs__content) {
  padding: 0;
}

.trash-badge {
  margin-left: 4px;
}

.task-list-card {
  flex: 1;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
  background: var(--color-bg-card);
}

/* ===== 任务标题单元格 ===== */
.task-title-cell {
  display: flex;
  align-items: center;
  gap: 12px;
}

.task-done {
  text-decoration: line-through;
  color: var(--color-text-secondary);
}

.task-deleted {
  color: var(--color-text-secondary);
  text-decoration: line-through;
}

.deleted-time {
  color: var(--color-text-placeholder);
  font-size: var(--font-size-xs);
}

/* 自动删除倒计时 — 两行显示（2026-06-03 优化） */
.auto-delete-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.3;
}

.auto-delete-relative {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-variant-numeric: tabular-nums;  /* 数字等宽，倒计时不抖 */
}

.auto-delete-absolute {
  font-size: 11px;
  color: var(--color-text-placeholder);
  font-variant-numeric: tabular-nums;
}

.auto-delete-icon {
  font-size: 12px;
  animation: pulse-warning 2s ease-in-out infinite;
}

.auto-delete-none {
  color: var(--color-text-placeholder);
}

/* <= 0h：已过期，等待下次清理 */
.auto-delete-imminent {
  color: #d73838;
  font-weight: var(--font-weight-bold);
  animation: pulse-danger 1.2s ease-in-out infinite;
}

/* < 6h：紧急 */
.auto-delete-urgent {
  color: #e85a4f;
  font-weight: var(--font-weight-semibold);
}

/* 6-24h：警告 */
.auto-delete-warning {
  color: #f59e0b;
  font-weight: var(--font-weight-medium);
}

/* 24-72h：正常 */
.auto-delete-normal {
  color: var(--color-text-secondary);
}

/* > 72h：安全（短期不会清理） */
.auto-delete-safe {
  color: var(--color-text-placeholder);
}

@keyframes pulse-danger {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

@keyframes pulse-warning {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.reminder-item {
  display: flex;
  align-items: center;
  margin-bottom: var(--space-2);
}

.reminder-hint {
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  margin-top: 4px;
}

.assignee-cell {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

/* ===== 分组任务列表 ===== */
.task-section {
  margin-bottom: var(--space-6);
}
.task-section:last-child {
  margin-bottom: 0;
}

.done-section {
  border-left: 1px dashed var(--color-border);
  padding-left: var(--space-4);
}

.section-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 2px solid var(--color-primary);
}
.section-title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.empty-section {
  text-align: center;
  color: var(--color-text-secondary);
  padding: var(--space-8) 0;
  font-size: var(--font-size-sm);
  background: var(--color-bg-warm);
  border-radius: var(--radius-lg);
  border: 1px dashed var(--color-border);
}

.task-groups {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.task-group {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  transition: box-shadow var(--duration-normal) var(--ease-out),
              transform var(--duration-normal) var(--ease-out);
}
.task-group:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.done-group {
  border-color: var(--color-border-light);
}

.group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: linear-gradient(135deg, var(--color-bg-warm) 0%, var(--color-primary-bg) 100%);
  border-bottom: 1px solid var(--color-border);
  cursor: pointer;
  user-select: none;
  transition: background var(--duration-normal) var(--ease-out);
  position: relative;
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
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  transition: all var(--duration-normal) var(--ease-out);
}
.group-header:hover {
  background: linear-gradient(135deg, var(--color-primary-bg) 0%, #FFE4DC 100%);
}
.group-header:hover::before {
  width: 4px;
  height: 24px;
}

.collapse-icon {
  margin-left: auto;
  transition: transform var(--duration-normal) var(--ease-out);
  color: var(--color-text-secondary);
}
.collapse-icon.collapsed {
  transform: rotate(-90deg);
}

.group-avatar {
  flex-shrink: 0;
  border-radius: var(--radius-lg) !important;
  transition: transform var(--duration-normal) var(--ease-out);
}
.group-avatar:hover {
  transform: scale(1.08);
}

.group-name {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  flex: 1;
}

.group-tasks {
  display: flex;
  flex-direction: column;
}

.task-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-border-light);
  transition: background var(--duration-fast) var(--ease-out),
              transform var(--duration-fast) var(--ease-out);
}
.task-row:last-child {
  border-bottom: none;
}
.task-row:hover {
  background: var(--color-bg-warm);
}
.task-row.overdue {
  background: #FEF8F7;
}
.task-row.overdue:hover {
  background: #FEF0ED;
}

.done-row {
  background: var(--color-bg-warm);
}
.done-row:hover {
  background: #FFF0ED;
}

.task-content {
  flex: 1;
  min-width: 0;
}
.task-title {
  font-size: var(--font-size-base);
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 4px;
}
.task-done {
  text-decoration: line-through;
  color: var(--color-text-secondary);
}
.task-meta {
  display: flex;
  align-items: center;
  gap: 6px;
}
.task-due {
  font-size: var(--font-size-xs);
  color: var(--color-text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  min-width: 80px;
}
.task-due.overdue {
  color: var(--color-danger);
  font-weight: var(--font-weight-semibold);
}
.task-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}
.task-actions .el-button {
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
}
.task-actions .el-button:hover {
  transform: scale(1.05);
}

/* ===== 完成按钮 ===== */
.complete-btn {
  flex-shrink: 0;
  transition: all var(--duration-fast) var(--ease-out);
}
.complete-btn:hover {
  transform: scale(1.12);
}
.complete-btn:active {
  transform: scale(0.92);
}

/* 进行中 → 空心对勾 */
.complete-btn--outline {
  color: var(--color-text-placeholder);
  border-color: var(--color-border);
}
.complete-btn--outline:hover {
  color: var(--color-success);
  border-color: var(--color-success);
  background: rgba(103, 194, 58, 0.08);
}

/* 已完成 → 实心绿底白对勾 */
.complete-btn--done {
  color: #fff;
  background: var(--color-success);
  border-color: var(--color-success);
  box-shadow: 0 2px 8px rgba(103, 194, 58, 0.30);
}
.complete-btn--done:hover {
  background: #85CE61;
  border-color: #85CE61;
}

/* ===== 禁用提示 ===== */
.no-permission {
  color: var(--color-text-placeholder);
  font-size: var(--font-size-sm);
}
</style>

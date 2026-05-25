<template>
  <div class="task-view">
    <!-- Tab 切换：任务列表 / 垃圾桶 -->
    <el-tabs v-model="activeTab" class="task-tabs">
      <el-tab-pane label="任务列表" name="tasks">
        <!-- 顶部操作栏 -->
        <el-card class="filter-card card fade-slide-up stagger-1">
          <el-row :gutter="16" align="middle">
            <el-col :xs="12" :sm="12" :md="6">
              <el-select v-model="filters.status" placeholder="任务状态" clearable>
                <el-option label="待办" value="todo" />
                <el-option label="进行中" value="in_progress" />
                <el-option label="阻塞" value="blocked" />
                <el-option label="已完成" value="done" />
              </el-select>
            </el-col>
            <el-col :xs="12" :sm="12" :md="6">
              <el-select v-model="filters.assignee_id" placeholder="负责人" clearable>
                <el-option
                  v-for="member in members"
                  :key="member.id"
                  :label="member.name"
                  :value="member.id"
                />
              </el-select>
            </el-col>
            <el-col :xs="12" :sm="12" :md="6">
              <el-select v-model="filters.priority" placeholder="优先级" clearable>
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

            <el-table-column label="自动删除" width="120">
              <template #default="{ row }">
                <span :class="{ 'auto-delete-soon': getAutoDeleteDays(row.deleted_at) <= 1 }">
                  {{ getAutoDeleteText(row.deleted_at) }}
                </span>
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
          <el-input v-model="taskForm.title" placeholder="请输入任务标题" />
        </el-form-item>
        <el-form-item label="负责人">
          <el-select v-if="isAdmin" v-model="taskForm.assignee_id" placeholder="选择负责人" clearable>
            <el-option
              v-for="member in members"
              :key="member.id"
              :label="member.name"
              :value="member.id"
            />
          </el-select>
          <el-select v-else v-model="taskForm.assignee_id" disabled>
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
          <el-select v-model="taskForm.status">
            <el-option label="待办" value="todo" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="阻塞" value="blocked" />
            <el-option label="已完成" value="done" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期">
          <el-date-picker
            v-model="taskForm.due_date"
            type="datetime"
            placeholder="选择截止日期和时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DD HH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="提醒设置">
          <div v-for="(reminder, index) in taskForm.reminders" :key="index" class="reminder-item">
            <el-date-picker
              v-model="reminder.remind_at"
              type="datetime"
              placeholder="选择提醒时间"
              format="YYYY-MM-DD HH:mm"
              value-format="YYYY-MM-DD HH:mm:ss"
              style="width: 200px"
            />
            <el-select v-model="reminder.remind_type" style="width: 90px; margin-left: 8px;">
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
            v-model="taskForm.description"
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
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Check, Edit, Delete, RefreshRight, DeleteFilled } from '@element-plus/icons-vue'
import axios from 'axios'
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
  // 组内按创建时间降序
  for (const g of Object.values(groups)) {
    g.tasks.sort((a, b) => dayjs(b.created_at).diff(dayjs(a.created_at)))
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
  status: 'todo',
  due_date: '',
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
  const newStatus = task.status === 'done' ? 'todo' : 'done'
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
    status: 'todo',
    due_date: '',
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

// 计算自动删除倒计时
const getAutoDeleteDays = (deletedAt) => {
  if (!deletedAt) return 3
  const deleteDate = dayjs(deletedAt).add(3, 'day')
  const daysLeft = deleteDate.diff(dayjs(), 'day')
  // 确保最多显示3天
  return Math.max(0, Math.min(3, daysLeft))
}

const getAutoDeleteText = (deletedAt) => {
  const daysLeft = getAutoDeleteDays(deletedAt)
  if (daysLeft <= 0) return '即将删除'
  if (daysLeft === 1) return '明天自动删除'
  if (daysLeft === 2) return '后天自动删除'
  return `还有 ${daysLeft} 天`
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

.auto-delete-soon {
  color: var(--color-danger);
  font-weight: var(--font-weight-semibold);
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

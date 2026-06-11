<template>
  <div class="task-view">
    <!-- Tab 切换：任务列表 / 垃圾桶 -->
    <el-tabs v-model="activeTab" class="task-tabs">
      <el-tab-pane label="任务列表" name="tasks" lazy>
        <!-- 顶部操作栏 -->
        <el-card class="filter-card card fade-slide-up stagger-1">
          <el-row :gutter="16" align="middle">
            <el-col :xs="12" :sm="12" :md="6">
              <el-select v-model="filters.status" name="filters-status" placeholder="任务状态" aria-label="按任务状态筛选" clearable>
                <el-option label="进行中" value="in_progress" />
                <el-option label="阻塞" value="blocked" />
                <el-option label="已完成" value="done" />
              </el-select>
            </el-col>
            <el-col :xs="12" :sm="12" :md="6">
              <el-select v-model="filters.assignee_id" name="filters-assignee_id" placeholder="负责人" aria-label="按负责人筛选" clearable>
                <el-option
                  v-for="member in members"
                  :key="member.id"
                  :label="member.name"
                  :value="member.id"
                />
              </el-select>
            </el-col>
            <el-col :xs="12" :sm="12" :md="6">
              <el-select v-model="filters.priority" name="filters-priority" placeholder="优先级" aria-label="按优先级筛选" clearable>
                <el-option label="高" value="high" />
                <el-option label="中" value="medium" />
                <el-option label="低" value="low" />
              </el-select>
            </el-col>
            <el-col :xs="12" :sm="12" :md="6">
              <el-button type="primary" class="btn btn-primary" @click="openCreateDialog">
                <el-icon><Plus /></el-icon>
                创建任务
              </el-button>
            </el-col>
          </el-row>
        </el-card>

        <!-- 任务列表 — 按负责人配对：左进行中，右已完成 -->
        <el-card class="task-list-card card fade-slide-up stagger-2">
          <!-- 总表头 -->
          <div class="paired-header">
            <div class="paired-header-left">
              <span class="section-title">📋 进行中</span>
              <el-badge :value="activeTasks.length" type="warning" />
            </div>
            <div class="paired-header-right">
              <span class="section-title">✅ 已完成</span>
              <el-badge :value="doneTasks.length" type="success" />
              <template v-if="doneTasks.length > 0">
                <el-button v-if="!doneEditMode" size="small" text class="edit-mode-btn" @click="enterDoneEditMode">
                  <el-icon><Edit /></el-icon> 编辑
                </el-button>
                <el-button v-else size="small" text class="edit-mode-btn" @click="exitDoneEditMode">完成</el-button>
              </template>
              <template v-if="doneEditMode">
                <el-button size="small" text @click="toggleSelectAllDone">{{ isAllDoneSelected ? '取消全选' : '全选' }}</el-button>
                <el-button size="small" type="danger" :disabled="selectedDoneIds.size === 0" class="batch-btn" @click="batchDeleteDone">
                  <el-icon><Delete /></el-icon> {{ selectedDoneIds.size > 0 ? `删除(${selectedDoneIds.size})` : '删除' }}
                </el-button>
              </template>
            </div>
          </div>

          <div v-if="pairedGroups.length === 0" class="empty-section">
            <span>暂无任务</span>
          </div>

          <!-- 每人一行：左进行中，右已完成 -->
          <div v-for="(pair, pIdx) in pairedGroups" :key="pair.assignee_id" class="paired-row fade-slide-up" :style="{ animationDelay: `${(pIdx + 2) * 80}ms` }">
            <!-- 负责人头部 -->
            <div class="paired-avatar-col">
              <div class="group-header" @click="toggleGroup(pair.assignee_id)">
                <el-avatar
                  v-if="memberStore.getMemberAvatar(pair.assignee_id)"
                  :src="memberStore.getMemberAvatar(pair.assignee_id)"
                  :alt="`${memberStore.getMemberName(pair.assignee_id)}的头像`"
                  :size="36"
                  class="group-avatar"
                />
                <el-avatar v-else :size="36" style="background: var(--color-primary)" class="group-avatar">
                  {{ memberStore.getMemberName(pair.assignee_id).charAt(0) }}
                </el-avatar>
                <span class="group-name">{{ memberStore.getMemberName(pair.assignee_id) }}</span>
                <el-tag size="small" type="info">{{ pair.activeTasks.length + pair.doneTasks.length }}项</el-tag>
                <el-icon class="collapse-icon" :class="{ collapsed: collapsedGroups[pair.assignee_id] }"><ArrowDown /></el-icon>
              </div>
            </div>

            <div v-show="!collapsedGroups[pair.assignee_id]" class="paired-content">
              <!-- 左列：进行中 -->
              <div class="paired-col paired-col-left">
                <div v-if="pair.activeTasks.length === 0" class="empty-col">暂无进行中任务</div>
                <div
                  v-for="task in pair.activeTasks"
                  :key="task.id"
                  class="task-row"
                  :class="{ overdue: isOverdue(task) }"
                >
                  <el-button circle size="default" class="complete-btn complete-btn--outline" @click="toggleTaskStatus(task)" title="标记完成">
                    <el-icon size="18"><Check /></el-icon>
                  </el-button>
                  <div class="task-content">
                    <div class="task-title">{{ task.title }}</div>
                    <div class="task-meta">
                      <el-tag :type="getPriorityType(task.priority)" size="small" effect="plain">{{ getPriorityLabel(task.priority) }}</el-tag>
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
                      <el-button text type="primary" aria-label="编辑" @click="editTask(task)"><el-icon><Edit /></el-icon></el-button>
                      <el-button text type="danger" aria-label="删除" @click="deleteTask(task)"><el-icon><Delete /></el-icon></el-button>
                    </template>
                  </div>
                </div>
              </div>

              <!-- 右列：已完成 -->
              <div class="paired-col paired-col-right">
                <div v-if="pair.doneTasks.length === 0" class="empty-col">暂无已完成任务</div>
                <div
                  v-for="task in pair.doneTasks"
                  :key="task.id"
                  class="task-row done-row"
                  :class="{ 'is-selected': selectedDoneIds.has(task.id) }"
                >
                  <el-checkbox v-if="doneEditMode" :model-value="selectedDoneIds.has(task.id)" class="row-checkbox" @change="toggleSelectDone(task.id)" />
                  <el-button circle size="default" class="complete-btn complete-btn--done" @click="toggleTaskStatus(task)" title="取消完成">
                    <el-icon size="18"><Check /></el-icon>
                  </el-button>
                  <div class="task-content">
                    <div class="task-title task-done">{{ task.title }}</div>
                    <div class="task-meta">
                      <el-tag size="small" type="success">已完成</el-tag>
                    </div>
                  </div>
                  <div class="task-due">-</div>
                  <div class="task-actions">
                    <template v-if="isAdmin || task.created_by === currentUserId || task.assignee_id === currentUserId">
                      <el-button text type="danger" aria-label="删除" @click="deleteTask(task)"><el-icon><Delete /></el-icon></el-button>
                    </template>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane name="trash" lazy>
        <template #label>
          <span class="trash-tab-label">
            <el-icon :size="20"><Delete /></el-icon>
            <span>垃圾桶</span>
            <el-badge v-if="trashCount > 0" :value="trashCount" class="trash-badge" />
          </span>
        </template>
        <!-- 垃圾桶列表 -->
        <TaskTrash
          :trash-tasks="trashTasks"
          :trash-total="trashTotal"
          :trash-page="trashPage"
          :trash-page-size="trashPageSize"
          :loading="loading"
          :is-admin="isAdmin"
          :current-user-id="currentUserId"
          @restore="handleRestore"
          @permanent-delete="handlePermanentDelete"
          @batch-permanent-delete="handleBatchPermanentDelete"
          @page-change="handleTrashPageChange"
          @size-change="handleTrashSizeChange"
        />
      </el-tab-pane>
    </el-tabs>

    <!-- 创建/编辑弹窗 -->
    <TaskCreateDialog
      v-model:visible="showCreateDialog"
      :editing-task="editingTask"
      @success="onTaskSaved"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Check, Edit, Delete, Plus, Warning } from '@element-plus/icons-vue'
import axios from 'axios'
import dayjs from 'dayjs'
import { formatDate } from '@/utils/format'
import { getStatusType, getPriorityType, getStatusLabel, getPriorityLabel } from '@/utils/task'
import { useUserStore } from '@/stores/user'
import { useMemberStore } from '@/stores/member'
import { useTask } from '@/composables/useTask'
import TaskCreateDialog from './task/TaskCreateDialog.vue'
import TaskTrash from './task/TaskTrash.vue'

const route = useRoute()
const userStore = useUserStore()
const memberStore = useMemberStore()
const members = computed(() => memberStore.members)
const isAdmin = computed(() => {
  const role = userStore.userInfo?.role
  return role === 'admin' || role === 'leader'
})
const currentUserId = computed(() => userStore.userInfo?.id)

// 使用 composable
const {
  tasks, total, currentPage, pageSize, loading, filters,
  trashTasks, trashTotal, trashPage, trashPageSize, trashCount,
  activeTasks, doneTasks,
  fetchTasks, fetchTrashTasks, createTask, updateTask,
  deleteTask: deleteTaskApi, restoreTask: restoreTaskApi, permanentlyDeleteTask, batchPermanentDelete
} = useTask()

const isMobile = ref(window.innerWidth <= 768)
const activeTab = ref('tasks')
const showCreateDialog = ref(false)
const editingTask = ref(null)

// 2026-06-03：实时倒计时驱动器
const now = ref(dayjs())
let autoDeleteTimer = null
onMounted(() => {
  autoDeleteTimer = setInterval(() => {
    now.value = dayjs()
  }, 30 * 1000)

  // 从 URL query 读取筛选条件（如从成员管理跳转过来）
  if (route.query.assignee_id) {
    filters.value.assignee_id = Number(route.query.assignee_id)
  }
})
onUnmounted(() => {
  if (autoDeleteTimer) {
    clearInterval(autoDeleteTimer)
    autoDeleteTimer = null
  }
})

// 分组折叠状态
const collapsedGroups = ref({})
const toggleGroup = (assigneeId) => {
  collapsedGroups.value[assigneeId] = !collapsedGroups.value[assigneeId]
}

// 按负责人分组
function groupTasksByAssignee(taskList) {
  const groups = {}
  for (const task of taskList) {
    const id = task.assignee_id != null ? task.assignee_id : 'unassigned'
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
    return b.tasks.length - a.tasks.length
  })
}

const groupedActiveTasks = computed(() => groupTasksByAssignee(activeTasks.value))
const groupedDoneTasks = computed(() => groupTasksByAssignee(doneTasks.value))

// 统一配对：按负责人合并进行中+已完成，左右对齐
const pairedGroups = computed(() => {
  const activeMap = {}
  for (const g of groupedActiveTasks.value) activeMap[g.assignee_id] = g.tasks
  const doneMap = {}
  for (const g of groupedDoneTasks.value) doneMap[g.assignee_id] = g.tasks
  // 所有负责人（进行中优先排序）
  const allIds = [...new Set([...Object.keys(activeMap), ...Object.keys(doneMap)])]
  // 按进行中任务数排序，无进行中的排后面
  allIds.sort((a, b) => (activeMap[b]?.length || 0) - (activeMap[a]?.length || 0))
  return allIds.map(id => ({
    assignee_id: id,
    activeTasks: activeMap[id] || [],
    doneTasks: doneMap[id] || []
  }))
})

// 打开创建弹窗
const openCreateDialog = () => {
  editingTask.value = null
  showCreateDialog.value = true
}

// 编辑任务
const editTask = (task) => {
  editingTask.value = task
  showCreateDialog.value = true
}

// 任务保存成功回调
const onTaskSaved = () => {
  editingTask.value = null
  fetchTasks()
}

// 删除任务
const deleteTask = async (task) => {
  try {
    await ElMessageBox.confirm('确定要删除这个任务吗？删除后可从垃圾桶恢复。', '确认删除', {
      type: 'warning'
    })
    await deleteTaskApi(task.id)
    ElMessage.success('任务已移入垃圾桶')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 已完成任务多选状态 + 编辑模式
const doneEditMode = ref(false)
const selectedDoneIds = ref(new Set())
const isAllDoneSelected = computed(
  () => doneTasks.value.length > 0 && selectedDoneIds.value.size === doneTasks.value.length
)

const enterDoneEditMode = () => {
  doneEditMode.value = true
}

const exitDoneEditMode = () => {
  doneEditMode.value = false
  selectedDoneIds.value = new Set()  // 退出编辑模式时清空选择
}

const toggleSelectDone = (taskId) => {
  // 重新构造 Set 触发 ref 响应式（Set 的 add/delete 在 ref 包中也能触发，但赋值最稳）
  const next = new Set(selectedDoneIds.value)
  if (next.has(taskId)) {
    next.delete(taskId)
  } else {
    next.add(taskId)
  }
  selectedDoneIds.value = next
}

const toggleSelectAllDone = () => {
  if (isAllDoneSelected.value) {
    selectedDoneIds.value = new Set()
  } else {
    selectedDoneIds.value = new Set(doneTasks.value.map(t => t.id))
  }
}

const clearDoneSelection = () => {
  selectedDoneIds.value = new Set()
}

// 批量删除选中任务
const batchDeleteDone = async () => {
  const ids = Array.from(selectedDoneIds.value)
  if (ids.length === 0) return

  // 准备预览：最多列 5 条标题，超出显示「等」
  const previewMap = new Map(doneTasks.value.map(t => [t.id, t.title]))
  const previewLines = ids.slice(0, 5).map(id => `· ${previewMap.get(id) || `#${id}`}`)
  const more = ids.length > 5 ? `\n…等共 ${ids.length} 条` : ''
  const confirmMsg = `确定要删除以下 ${ids.length} 条已完成任务吗？\n删除后可从垃圾桶恢复。\n\n${previewLines.join('\n')}${more}`

  try {
    await ElMessageBox.confirm(confirmMsg, '批量删除（选择性）', {
      type: 'warning',
      confirmButtonText: `删除 ${ids.length} 条`,
      cancelButtonText: '取消',
      customStyle: { maxWidth: '480px', whiteSpace: 'pre-line' }
    })
    let success = 0
    let failed = 0
    const BATCH_DELAY_MS = 2500  // 每个请求间隔 2.5s，避免触发 write 限流（30次/分钟）
    for (let i = 0; i < ids.length; i++) {
      // 非首个请求加延迟，避免 429 Too Many Requests
      if (i > 0) {
        await new Promise(r => setTimeout(r, BATCH_DELAY_MS))
      }
      try {
        await deleteTaskApi(ids[i])
        success++
      } catch (e) {
        // 429 限流时提前终止，避免无意义重试
        if (e?.response?.status === 429) {
          failed += ids.length - i  // 剩余全部算失败
          ElMessage.warning(`触发限流，已暂停。成功删除 ${success} 条，剩余 ${ids.length - i} 条未删除`)
          break
        }
        failed++
      }
    }
    if (failed === 0) {
      ElMessage.success(`已删除 ${success} 条任务到垃圾桶`)
    } else if (failed > 0 && success > 0 && !ids.length) {
      // 已在 429 分支提示过，不再重复
    } else if (failed > 0) {
      ElMessage.warning(`已删除 ${success} 条，${failed} 条失败`)
    }
    selectedDoneIds.value = new Set()  // 清空选择
    doneEditMode.value = false  // 删除完成后退出编辑模式
    fetchTasks()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('批量删除失败')
    }
  }
}

// 恢复任务
const handleRestore = async (taskId) => {
  try {
    await ElMessageBox.confirm('确定要恢复这个任务吗？', '确认恢复', {
      type: 'warning'
    })
    await restoreTaskApi(taskId)
    ElMessage.success('任务已恢复')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('恢复失败')
    }
  }
}

// 永久删除任务
const handlePermanentDelete = async (taskId) => {
  try {
    await ElMessageBox.confirm('确定要永久删除这个任务吗？此操作不可恢复！', '永久删除', {
      type: 'error',
      confirmButtonText: '永久删除',
      cancelButtonText: '取消'
    })
    await permanentlyDeleteTask(taskId)
    ElMessage.success('任务已永久删除')
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('永久删除失败')
    }
  }
}

const handleBatchPermanentDelete = async (ids) => {
  if (!ids.length) return
  try {
    await ElMessageBox.confirm(`确定要永久删除 ${ids.length} 个任务吗？此操作不可恢复！`, '批量永久删除', {
      type: 'error',
      confirmButtonText: `永久删除 ${ids.length} 个`,
      cancelButtonText: '取消'
    })
    const deleted = await batchPermanentDelete(ids)
    ElMessage.success(`已永久删除 ${deleted} 个任务`)
    fetchTrashTasks()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error('批量永久删除失败')
    }
  }
}

// 垃圾桶分页
const handleTrashPageChange = (page) => {
  trashPage.value = page
  fetchTrashTasks()
}

const handleTrashSizeChange = (size) => {
  trashPageSize.value = size
  trashPage.value = 1
  fetchTrashTasks()
}

// 切换任务状态
const toggleTaskStatus = async (task) => {
  const newStatus = task.status === 'done' ? 'in_progress' : 'done'
  try {
    await updateTask(task.id, { status: newStatus })
  } catch (e) {
    const msg = e.response?.data?.error?.message || '更新失败'
    ElMessage.error(msg)
  }
}

// 辅助函数
const isOverdue = (task) => {
  if (!task.due_date || task.status === 'done') return false
  return dayjs(task.due_date).isBefore(dayjs())
}

// 计算自动删除倒计时
const getAutoDeleteText = (autoDeleteAt) => {
  if (!autoDeleteAt) return ''
  const expire = dayjs(autoDeleteAt)
  const diffMin = expire.diff(now.value, 'minute')
  const diffHour = expire.diff(now.value, 'hour')
  const diffDay = Math.floor(diffMin / (60 * 24))
  const remHourOfDay = Math.floor((diffMin % (60 * 24)) / 60)
  const remMin = diffMin % 60

  if (diffMin <= 0) return '等待下次清理'
  if (diffMin < 60) return `${diffMin} 分钟后删除`
  if (diffMin < 24 * 60) {
    if (remMin > 0) return `${diffHour} 小时 ${remMin} 分后删除`
    return `${diffHour} 小时后删除`
  }
  if (remHourOfDay > 0) return `${diffDay} 天 ${remHourOfDay} 小时后删除`
  return `${diffDay} 天后删除`
}

const getAutoDeleteHours = (autoDeleteAt) => {
  if (!autoDeleteAt) return Infinity
  return dayjs(autoDeleteAt).diff(now.value, 'hour', true)
}

const isAutoDeleteOverdue = (autoDeleteAt) => {
  if (!autoDeleteAt) return false
  return dayjs(autoDeleteAt).isBefore(now.value)
}

const getAutoDeleteClass = (autoDeleteAt) => {
  const hours = getAutoDeleteHours(autoDeleteAt)
  if (hours <= 0) return 'auto-delete-imminent'
  if (hours <= 6) return 'auto-delete-urgent'
  if (hours <= 24) return 'auto-delete-warning'
  if (hours <= 72) return 'auto-delete-normal'
  return 'auto-delete-safe'
}

const getAutoDeleteIcon = (autoDeleteAt) => {
  return getAutoDeleteHours(autoDeleteAt) <= 24
}

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
  memberStore.fetchMembers()
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
}

/* ===== 任务列表卡片 ===== */
.task-list-card {
  margin-bottom: 0;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  box-shadow: var(--shadow-sm);
  background: var(--color-bg-card);
}

/* ===== 配对布局：按负责人左右对齐 ===== */
.paired-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border-lighter, #ebeef5);
}
.paired-header-left,
.paired-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.paired-row {
  display: flex;
  flex-direction: column;
  border-bottom: 1px solid var(--color-border-lighter, #ebeef5);
  padding: 12px 0;
}
.paired-row:last-child {
  border-bottom: none;
}
.paired-avatar-col {
  flex-shrink: 0;
}
.paired-content {
  display: flex;
  gap: 16px;
  margin-top: 8px;
}
.paired-col {
  flex: 1;
  min-width: 0;
}
.paired-col-left {
  border-right: 1px solid var(--color-border-lighter, #ebeef5);
  padding-right: 16px;
}
.paired-col-right {
  padding-left: 0;
}
.empty-col {
  color: var(--color-text-placeholder);
  font-size: 13px;
  padding: 8px 0;
  text-align: center;
}

/* ===== 任务分组（旧样式保留兼容） ===== */
.task-section {
  padding: 0 8px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px 0;
  flex-wrap: wrap;
}
.batch-btn {
  margin-left: auto;
}
.selection-info {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: 500;
  background: rgba(144, 147, 153, 0.08);
  padding: 2px 8px;
  border-radius: var(--radius-sm);
}
.selection-info.is-active {
  color: var(--color-primary);
  background: rgba(255, 122, 92, 0.08);
  font-weight: 600;
}
.edit-mode-btn {
  margin-left: auto !important;
}
.edit-mode-btn:last-child {
  margin-right: 0;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.empty-section {
  text-align: center;
  padding: 40px 0;
  color: var(--color-text-secondary);
}

.task-groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.task-group {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  border: 1px solid var(--color-border);
  overflow: hidden;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--color-bg-card);
  cursor: pointer;
  transition: background-color 0.2s;
}

.group-header:hover {
  background: var(--color-bg-card-hover);
}

.group-avatar {
  flex-shrink: 0;
}

.group-name {
  font-weight: 600;
  color: var(--color-text-primary);
  flex: 1;
}

.collapse-icon {
  transition: transform 0.2s;
}

.collapse-icon.collapsed {
  transform: rotate(-90deg);
}

.group-tasks {
  padding: 0 16px 12px;
}

/* ===== 任务行 ===== */
.task-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--color-border);
}

.task-row:last-child {
  border-bottom: none;
}

.task-row.overdue {
  background: rgba(255, 77, 77, 0.05);
}

.task-row.done-row {
  opacity: 0.7;
}

.task-row.done-row.is-selected {
  opacity: 1;
  background: rgba(255, 122, 92, 0.08);
  border-left: 3px solid var(--color-primary);
  padding-left: 9px;  /* 补偿 border-left 3px，避免布局抖动 */
  margin-left: -3px;
}

.row-checkbox {
  flex-shrink: 0;
  margin-right: -4px;  /* 紧凑排列：与 complete-btn 视觉距离 */
}

.complete-btn {
  flex-shrink: 0;
}

.complete-btn--outline {
  border: 2px solid var(--color-border);
  background: transparent;
}

.complete-btn--outline:hover {
  border-color: var(--color-success);
  background: rgba(82, 196, 26, 0.1);
}

.complete-btn--done {
  background: var(--color-success);
  border-color: var(--color-success);
  color: white;
}

.task-content {
  flex: 1;
  min-width: 0;
}

.task-title {
  font-size: 14px;
  color: var(--color-text-primary);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-title.task-done {
  text-decoration: line-through;
  color: var(--color-text-secondary);
}

.task-meta {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.task-due {
  font-size: 12px;
  color: var(--color-text-secondary);
  white-space: nowrap;
}

.task-due.overdue {
  color: var(--color-danger);
  font-weight: 600;
}

.task-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

/* ===== 垃圾桶 Tab ===== */
.trash-tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 15px;
  font-weight: 500;
  padding: 6px 14px;
  border-radius: var(--radius-md, 8px);
  transition: all var(--duration-fast, 150ms);
}
.trash-tab-label:hover {
  background: rgba(144, 147, 153, 0.1);
}
:deep(.task-tabs) .el-tabs__item {
  font-size: 15px;
  padding: 0 20px;
  height: 44px;
  line-height: 44px;
}
.trash-badge {
  margin-left: 2px;
}

.auto-delete-none {
  color: var(--color-text-secondary);
}

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .task-row {
    flex-wrap: wrap;
  }

  .task-due {
    width: 100%;
    margin-top: 4px;
  }

  .task-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>

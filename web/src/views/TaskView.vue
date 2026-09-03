<template>
  <div class="task-view">
    <!-- 卷首档案头 (G 稿语言: 衬线标题 + mono 元信息 + 硬阴影边框卡) -->
    <div class="dossier-head fade-slide-up stagger-1">
      <span class="dh-tag">TASK DOSSIER · 任务卷宗</span>
      <h1 class="dh-title">任务管理</h1>
      <div class="dh-meta">
        <span class="dh-count"><b>{{ activeTasks.length }}</b> 进行中</span>
        <span class="dh-sep">·</span>
        <span class="dh-count"><b class="ok">{{ doneTasks.length }}</b> 已完成</span>
        <span class="dh-sep">·</span>
        <span class="dh-count"><b>{{ total }}</b> 总计</span>
        <span class="dh-date">{{ dossierDate }}</span>
      </div>
    </div>

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
              <span class="section-title">§ 进行中 <em>IN PROGRESS</em></span>
              <span class="head-cnt">{{ activeTasks.length }}</span>
              <span v-if="overdueCount > 0" class="overdue-seal">需处理 · {{ overdueCount }}</span>
            </div>
            <div class="paired-header-right">
              <span class="section-title">§ 已完成 <em>DONE</em></span>
              <span class="head-cnt ok">{{ doneTasks.length }}</span>
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
                <span class="group-cnt">{{ pair.activeTasks.length + pair.doneTasks.length }} ITEMS</span>
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
                      <span class="chip" :class="prClass(task.priority)">P-{{ getPriorityLabel(task.priority) }}</span>
                      <span v-if="task.status === 'in_progress'" class="chip st">进行中</span>
                      <span v-else-if="task.status === 'blocked'" class="chip bl">阻塞</span>
                    </div>
                  </div>
                  <div class="task-due" :class="{ overdue: isOverdue(task) }">
                    <el-icon v-if="isOverdue(task)" color="var(--color-danger)"><Warning /></el-icon>
                    {{ formatDate(task.due_date) }}
                  </div>
                  <div class="task-actions">
                    <template v-if="isAdmin || task.created_by === currentUserId || task.assignee_id === currentUserId">
                      <el-button circle size="default" class="task-action-btn task-action-btn--edit" aria-label="编辑" @click="editTask(task)">
                        <el-icon size="18"><Edit /></el-icon>
                      </el-button>
                      <el-button circle size="default" class="task-action-btn task-action-btn--delete" aria-label="删除" @click="deleteTask(task)">
                        <el-icon size="18"><Delete /></el-icon>
                      </el-button>
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
                      <span class="chip dn">已完成</span>
                    </div>
                  </div>
                  <div class="task-due">-</div>
                  <div class="task-actions">
                    <template v-if="isAdmin || task.created_by === currentUserId || task.assignee_id === currentUserId">
                      <el-button circle size="default" class="task-action-btn task-action-btn--delete" aria-label="删除" @click="deleteTask(task)">
                        <el-icon size="18"><Delete /></el-icon>
                      </el-button>
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
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowDown, Check, Edit, Delete, Plus, Warning } from '@element-plus/icons-vue'
import axios from 'axios'
import dayjs from 'dayjs'
import { formatDate } from '@/utils/format'
import { getPriorityLabel } from '@/utils/task'
import { groupTasksByAssignee } from '@/utils/taskGroup'  // 2026-06-26: 从本文件抽出，移动端按人分组视图复用
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

// G 稿档案皮肤: 优先级 chip 色 class + 卷首 mono 日期行
const prClass = (p) => ({ high: 'hi', medium: 'md', low: 'lo' }[p] || 'lo')
const dossierDate = dayjs().format('YYYY-MM-DD · HH:mm')
const overdueCount = computed(() => activeTasks.value.filter(isOverdue).length)
const activeTab = ref('tasks')
const showCreateDialog = ref(false)
const editingTask = ref(null)

// 2026-06-03：实时倒计时驱动器（autoDeleteTimer + now 是为兼容未来 TaskTrash 嵌入扩展保留）
// 注：垃圾桶 UI 已在 task/TaskTrash.vue 内独立实现（line 288+ helpers）
// 此处 onMounted 只读 URL query 筛选
onMounted(() => {
  // 从 URL query 读取筛选条件（从成员管理或 Dashboard 跳转过来）
  if (route.query.assignee_id) {
    filters.value.assignee_id = Number(route.query.assignee_id)
  }
  if (route.query.overdue === 'true') {
    filters.value.overdue = true
  }
})

// 分组折叠状态
const collapsedGroups = ref({})
const toggleGroup = (assigneeId) => {
  collapsedGroups.value[assigneeId] = !collapsedGroups.value[assigneeId]
}

// 2026-06-26: groupTasksByAssignee 已抽到 utils/taskGroup.js，这里直接 import

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
  border-bottom: 1px solid var(--color-border-light, #ebeef5);
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
  border-bottom: 1px solid var(--color-border-light, #ebeef5);
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
  border-right: 1px solid var(--color-border-light, #ebeef5);
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
  background: rgba(var(--color-primary-rgb), 0.08);
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
  background: rgba(var(--color-primary-rgb), 0.08);
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
  /* stylelint-disable-next-line color-named */
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

/* ===== 操作按钮（编辑/删除）===== */
.task-action-btn {
  flex-shrink: 0;
  border: 2px solid var(--color-border);
  background: rgba(var(--color-text-secondary-rgb, 144, 147, 153), 0.04);
  color: var(--color-text-secondary);
  transition: all var(--duration-fast, 150ms) ease;
}

.task-action-btn--edit:hover {
  border-color: var(--color-primary);
  background: rgba(var(--color-primary-rgb), 0.15);
  color: var(--color-primary);
}

.task-action-btn--delete:hover {
  border-color: var(--color-danger);
  background: rgba(var(--color-danger-rgb), 0.15);
  color: var(--color-danger);
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

/* =====================================================================
   G 稿「控制台档案」皮肤叠加层 (2026-09-04)
   视觉源 docs/design-proposals/layout-2026-09/G-console.html;
   只叠加不重写: 上面老规则保留, 本层用后置级联覆盖, 整段可摘除回滚
   ===================================================================== */
.task-view {
  --dg-card: #fdfefc; --dg-ink: #16232a; --dg-steel: #5a6b6a; --dg-fog: #8ba0a0;
  --dg-hair: #c9d2ca; --dg-teal: #0e766e; --dg-teal-soft: #dcece5;
  --dg-coral: #ef7256; --dg-green: #3d7a3d; --dg-amber: #c07f2e;
  --dg-paper: #f4f6f4; --dg-shadow: rgba(22, 35, 42, 0.14);
  --dg-mono: Consolas, 'Courier New', monospace;
  background: var(--dg-paper);
  border-radius: 14px;
  padding: 4px;
}

/* --- 卷首档案头 --- */
.dossier-head {
  position: relative;
  background: var(--dg-card);
  border: 1.5px solid var(--dg-ink);
  border-radius: 10px;
  box-shadow: 3px 3px 0 var(--dg-shadow);
  padding: 22px 24px 16px;
  margin: 2px;
}
.dh-tag {
  position: absolute; top: -11px; left: 20px;
  background: var(--dg-card); border: 1px solid var(--dg-teal); color: var(--dg-teal);
  font-family: var(--dg-mono); font-size: 9.5px; letter-spacing: 0.22em;
  padding: 3px 10px; border-radius: 3px;
}
.dh-title {
  font-family: Georgia, 'Songti SC', 'SimSun', serif;
  font-size: 26px; font-weight: 600; letter-spacing: 0.01em;
  color: var(--dg-ink); margin: 0;
}
.dh-meta {
  margin-top: 8px; display: flex; align-items: baseline; gap: 8px;
  font-size: 12.5px; color: var(--dg-steel);
}
.dh-count b { font-family: var(--dg-mono); font-size: 16px; color: var(--dg-teal); }
.dh-count b.ok { color: var(--dg-green); }
.dh-sep { color: var(--dg-fog); }
.dh-date {
  margin-left: auto; font-family: var(--dg-mono); font-size: 10.5px;
  letter-spacing: 0.12em; color: var(--dg-fog);
}

/* --- tabs 标本签化 --- */
.task-tabs :deep(.el-tabs__item) {
  font-family: var(--dg-mono); font-size: 12px; letter-spacing: 0.14em;
  color: var(--dg-fog);
}
.task-tabs :deep(.el-tabs__item.is-active),
.task-tabs :deep(.el-tabs__item:hover) { color: var(--dg-teal); }
.task-tabs :deep(.el-tabs__active-bar) { background: var(--dg-teal); }
.task-tabs :deep(.el-tabs__nav-wrap::after) { background: var(--dg-hair); }

/* --- 卡片: hair 边框 + 硬阴影 --- */
.filter-card, .task-list-card {
  background: var(--dg-card) !important;
  border: 1px solid var(--dg-hair) !important;
  border-radius: 10px !important;
  box-shadow: 3px 3px 0 var(--dg-shadow) !important;
}
.filter-card :deep(.el-button--primary) {
  background: var(--dg-card); color: var(--dg-ink);
  border: 1.5px solid var(--dg-ink); border-radius: 8px;
  box-shadow: 2px 2px 0 var(--dg-shadow);
  font-weight: 600; transition: transform 120ms ease;
}
.filter-card :deep(.el-button--primary:hover) {
  transform: translate(-1px, -1px);
  box-shadow: 3px 3px 0 var(--dg-shadow);
  color: var(--dg-teal); border-color: var(--dg-teal); background: var(--dg-card);
}

/* --- 配对表头 mono 化 --- */
.section-title { font-size: 14px; font-weight: 600; color: var(--dg-ink); }
.section-title em {
  font-style: normal; font-family: var(--dg-mono); font-size: 9.5px;
  letter-spacing: 0.18em; color: var(--dg-fog); margin-left: 6px;
}
.head-cnt {
  font-family: var(--dg-mono); font-size: 15px; font-weight: 700;
  color: var(--dg-teal); background: var(--dg-teal-soft);
  border-radius: 6px; padding: 1px 9px;
}
.head-cnt.ok { color: var(--dg-green); background: rgba(61, 122, 61, 0.12); }
.paired-header { border-bottom: 1px dashed var(--dg-hair); }

/* --- 负责人档案袋 --- */
.group-header { gap: 10px; }
.group-header :deep(.el-avatar) { border-radius: 8px !important; border: 1px solid var(--dg-hair); }
.group-name { color: var(--dg-ink); font-weight: 600; }
.group-cnt {
  font-family: var(--dg-mono); font-size: 9.5px; letter-spacing: 0.14em;
  color: var(--dg-fog); border: 1px solid var(--dg-hair);
  border-radius: 4px; padding: 2px 7px;
}
.paired-row { border-bottom: 1px solid var(--dg-hair); }
.paired-content { border-top: 1px dashed var(--dg-hair); padding-top: 6px; }
.paired-col-left { border-right: 1px dashed var(--dg-hair); }
.empty-col, .empty-section {
  font-family: var(--dg-mono); font-size: 11px; letter-spacing: 0.1em;
  color: var(--dg-fog);
}

/* --- 任务行 --- */
.task-row { padding: 10px 6px; }
.task-row:hover { background: var(--dg-paper); }
.task-row.overdue { background: rgba(239, 114, 86, 0.06); }
.task-title { color: var(--dg-ink); font-weight: 500; }
.task-due { font-family: var(--dg-mono); font-size: 11.5px; color: var(--dg-steel); }
.task-due.overdue { color: var(--dg-coral); font-weight: 700; }

/* --- mono 印章 chip (替 el-tag) --- */
.chip {
  font-family: var(--dg-mono); font-size: 10px; letter-spacing: 0.08em;
  border: 1px solid currentColor; border-radius: 4px; padding: 1px 7px;
  color: var(--dg-fog); white-space: nowrap;
}
.chip.hi { color: var(--dg-coral); font-weight: 700; }
.chip.md { color: var(--dg-amber); }
.chip.st { color: var(--dg-teal); }
.chip.bl { color: var(--dg-coral); background: rgba(239, 114, 86, 0.08); }
.chip.dn { color: var(--dg-green); }

/* --- 完成/操作按钮: teal 描边圆 --- */
.complete-btn--outline {
  border: 1px solid var(--dg-teal) !important; color: var(--dg-teal) !important;
  background: transparent !important;
}
.complete-btn--outline:hover { background: var(--dg-teal-soft) !important; }
.complete-btn--done {
  background: var(--dg-teal) !important; border-color: var(--dg-teal) !important;
  color: #fff !important;
}
.task-action-btn { color: var(--dg-fog) !important; }
.task-action-btn:hover { color: var(--dg-teal) !important; background: var(--dg-teal-soft) !important; }
.task-action-btn--delete:hover { color: var(--dg-coral) !important; background: rgba(239, 114, 86, 0.08) !important; }

/* --- 逾期批注印章 (paired-header 右侧, 有逾期任务时) --- */
.overdue-seal {
  font-family: var(--dg-mono); font-size: 10px; font-weight: 700; letter-spacing: 0.1em;
  color: var(--dg-coral); border: 1.5px solid var(--dg-coral);
  border-radius: 4px; padding: 2px 8px; transform: rotate(3deg);
  margin-left: 4px;
}

</style>

<style>
/* v69 P1b: dark mode 覆盖（v60-v67 教训：必须非 scoped） */
[data-theme="dark"] .filter-card {
  background: var(--color-bg-card);
  border-color: var(--color-border);
}
[data-theme="dark"] .task-list-card {
  background: var(--color-bg-card);
  border-color: var(--color-border);
}
[data-theme="dark"] .paired-header {
  border-bottom-color: var(--color-border);
}
[data-theme="dark"] .paired-row {
  border-bottom-color: var(--color-border);
}
[data-theme="dark"] .paired-col-left {
  border-right-color: var(--color-border);
}
[data-theme="dark"] .selection-info {
  background: rgba(144, 147, 153, 0.12);
  color: var(--color-text-secondary);
}
[data-theme="dark"] .selection-info.is-active {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
[data-theme="dark"] .task-group {
  background: var(--color-bg-card);
  border-color: var(--color-border);
}
[data-theme="dark"] .group-header {
  background: var(--color-bg-card);
}
[data-theme="dark"] .group-header:hover {
  background: var(--color-bg-hover);
}
[data-theme="dark"] .task-row {
  border-bottom-color: var(--color-border);
}
[data-theme="dark"] .task-row.overdue {
  background: rgba(255, 77, 77, 0.08);
}
[data-theme="dark"] .task-row.done-row.is-selected {
  background: var(--color-primary-bg);
  border-left-color: var(--color-primary);
}
[data-theme="dark"] .complete-btn--outline {
  border-color: var(--color-border);
}
[data-theme="dark"] .complete-btn--outline:hover {
  background: rgba(82, 196, 26, 0.12);
}
[data-theme="dark"] .complete-btn--done {
  color: var(--color-bg-card);
}
[data-theme="dark"] .task-action-btn {
  border-color: var(--color-border);
  color: var(--color-text-secondary);
}
[data-theme="dark"] .task-action-btn--edit:hover {
  background: rgba(var(--color-primary-rgb), 0.18);
}
[data-theme="dark"] .task-action-btn--delete:hover {
  background: rgba(var(--color-danger-rgb), 0.18);
}
[data-theme="dark"] .trash-tab-label:hover {
  background: rgba(144, 147, 153, 0.14);
}

  /* === G 稿档案皮肤 dark (2026-09-04, 对齐 shot-G 夜览态) === */
  [data-theme="dark"] .task-view {
    --dg-card: #18232a; --dg-ink: #dfe9e6; --dg-steel: #9ab0ae; --dg-fog: #6b8286;
    --dg-hair: #27363e; --dg-teal: #35c2a4; --dg-teal-soft: #12312b;
    --dg-coral: #ef7256; --dg-green: #6fbf6f; --dg-amber: #d9a257;
    --dg-paper: #10171b; --dg-shadow: rgba(0, 0, 0, 0.5);
    background: #0c1215;
  }
  [data-theme="dark"] .task-view .filter-card .el-button--primary {
    background: var(--dg-card); color: var(--dg-ink);
  }
  [data-theme="dark"] .task-view .head-cnt { color: var(--dg-teal); }
  [data-theme="dark"] .task-view .complete-btn--done { color: #0c1215 !important; }
</style>

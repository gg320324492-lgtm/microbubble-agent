<template>
  <div class="task-view">
    <!-- 头部 -->
    <header class="header">
      <div class="header-left">
        <h2>任务管理</h2>
        <p>管理团队所有任务，追踪项目进度</p>
      </div>
      <div class="header-right">
        <button class="btn btn-primary" @click="showCreateDialog = true">➕ 新建任务</button>
      </div>
    </header>

    <!-- 统计卡片 -->
    <section class="stats-grid">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">总任务数</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.in_progress }}</div>
        <div class="stat-label">进行中</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.done }}</div>
        <div class="stat-label">已完成</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.overdue }}</div>
        <div class="stat-label">已逾期</div>
      </div>
    </section>

    <!-- 筛选栏 -->
    <section class="filters">
      <button
        v-for="filter in statusFilters"
        :key="filter.value"
        class="filter-btn"
        :class="{ active: filters.status === filter.value }"
        @click="setFilters({ status: filter.value })"
      >
        {{ filter.label }}
      </button>
    </section>

    <!-- 任务列表 -->
    <section class="task-list-container">
      <div class="task-list-header">
        <div class="task-list-title">任务列表</div>
        <div class="task-list-actions">
          <button class="btn btn-ghost btn-small">排序</button>
          <button class="btn btn-ghost btn-small">筛选</button>
        </div>
      </div>

      <div v-if="loading" class="loading">
        <div v-for="i in 5" :key="i" class="task-item skeleton">
          <div class="skeleton-circle" style="width: 20px; height: 20px"></div>
          <div class="skeleton-content">
            <div class="skeleton-text" style="width: 60%"></div>
            <div class="skeleton-text" style="width: 40%"></div>
          </div>
        </div>
      </div>

      <div v-else-if="sortedTasks.length === 0" class="empty-state">
        <div class="icon">📝</div>
        <p>暂无任务</p>
        <button class="btn btn-secondary" @click="showCreateDialog = true">创建第一个任务</button>
      </div>

      <div v-else>
        <div
          v-for="task in sortedTasks"
          :key="task.id"
          class="task-item"
        >
          <div
            class="task-checkbox"
            :class="{ checked: task.status === 'done' }"
            @click="handleTaskComplete(task)"
          ></div>
          <div class="task-content">
            <div class="task-title" :class="{ completed: task.status === 'done' }">
              {{ task.title }}
            </div>
            <div class="task-meta">
              <span
                class="task-tag"
                :style="{ background: getPriorityBgColor(task.priority), color: getPriorityColor(task.priority) }"
              >
                {{ getPriorityLabel(task.priority) }}
              </span>
              <span
                class="task-tag"
                :style="{ background: getStatusBgColor(task.status), color: getStatusColor(task.status) }"
              >
                {{ getStatusLabel(task.status) }}
              </span>
            </div>
          </div>
          <div class="task-assignee">
            <span class="assignee-avatar">{{ getAssigneeInitial(task.assignee_id) }}</span>
            <span class="assignee-name">{{ getAssigneeName(task.assignee_id) }}</span>
          </div>
          <div class="task-due" :class="getDueDateClass(task.due_date)">
            {{ getDueDateDisplay(task.due_date) }}
          </div>
          <div class="task-actions">
            <button class="btn btn-ghost btn-small" @click="handleEdit(task)">编辑</button>
            <button class="btn btn-ghost btn-small" @click="handleDelete(task)">删除</button>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useTask } from '@/composables/useTask'
import { useMemberStore } from '@/stores/member'
import {
  getPriorityLabel,
  getPriorityColor,
  getPriorityBgColor,
  getStatusLabel,
  getStatusColor,
  getStatusBgColor,
  getDueDateDisplay,
  getDueDateClass
} from '@/utils/task'

const {
  loading,
  filters,
  stats,
  sortedTasks,
  fetchTasks,
  completeTask,
  deleteTask,
  setFilters,
  getAssigneeName,
  getAssigneeInitial
} = useTask()

const memberStore = useMemberStore()
const showCreateDialog = ref(false)

const statusFilters = [
  { label: '全部', value: 'all' },
  { label: '进行中', value: 'in_progress' },
  { label: '待办', value: 'todo' },
  { label: '已完成', value: 'done' },
  { label: '已逾期', value: 'overdue' }
]

const handleTaskComplete = async (task) => {
  if (task.status !== 'done') {
    await completeTask(task.id)
  }
}

const handleEdit = (task) => {
  // TODO: 打开编辑对话框
  console.log('编辑任务:', task)
}

const handleDelete = async (task) => {
  if (confirm('确定要删除这个任务吗？')) {
    await deleteTask(task.id)
  }
}

onMounted(() => {
  fetchTasks()
  memberStore.fetchMembers()
})
</script>

<style scoped>
.task-view {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 头部 */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.header-left p {
  font-size: 14px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
}

.stat-card {
  background: white;
  border-radius: var(--radius-lg);
  padding: 20px;
  border: 1px solid var(--color-border);
  text-align: center;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.stat-label {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

/* 筛选栏 */
.filters {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.filter-btn {
  padding: 8px 16px;
  border-radius: var(--radius-full);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  background: white;
  border: 1px solid var(--color-border);
  color: var(--color-text-secondary);
}

.filter-btn:hover {
  border-color: var(--color-primary);
  color: var(--color-text-primary);
}

.filter-btn.active {
  background: var(--color-primary);
  border-color: var(--color-primary);
  color: white;
}

/* 任务列表容器 */
.task-list-container {
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
  overflow: hidden;
}

.task-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--color-border);
}

.task-list-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.task-list-actions {
  display: flex;
  gap: 12px;
}

/* 任务项 */
.task-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px 24px;
  border-bottom: 1px solid var(--color-border);
  transition: all var(--duration-fast) var(--ease-out);
}

.task-item:last-child {
  border-bottom: none;
}

.task-item:hover {
  background: var(--color-bg-hover);
}

.task-checkbox {
  width: 20px;
  height: 20px;
  border: 2px solid var(--color-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.task-checkbox:hover {
  border-color: var(--color-primary);
}

.task-checkbox.checked {
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.task-checkbox.checked::after {
  content: '✓';
  color: white;
  font-size: 12px;
}

.task-content {
  flex: 1;
}

.task-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.task-title.completed {
  text-decoration: line-through;
  color: var(--color-text-tertiary);
}

.task-meta {
  display: flex;
  gap: 8px;
  align-items: center;
}

.task-tag {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
}

.task-assignee {
  display: flex;
  align-items: center;
  gap: 8px;
}

.assignee-avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: white;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.assignee-name {
  font-size: 13px;
  color: var(--color-text-secondary);
}

.task-due {
  font-size: 13px;
  color: var(--color-text-tertiary);
  white-space: nowrap;
}

.task-due.overdue {
  color: var(--color-danger);
  font-weight: 500;
}

.task-due.today {
  color: var(--color-warning);
  font-weight: 500;
}

.task-actions {
  display: flex;
  gap: 8px;
  opacity: 0;
  transition: opacity var(--duration-fast) var(--ease-out);
}

.task-item:hover .task-actions {
  opacity: 1;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 48px 24px;
  color: var(--color-text-tertiary);
}

.empty-state .icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.empty-state p {
  font-size: 14px;
  margin-bottom: 16px;
}

/* 加载状态 */
.loading {
  padding: 24px;
}

/* 响应式 */
@media (max-width: 1024px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .task-item {
    flex-wrap: wrap;
  }

  .task-actions {
    opacity: 1;
    width: 100%;
    justify-content: flex-end;
  }
}
</style>

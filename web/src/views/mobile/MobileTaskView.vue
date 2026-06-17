<template>
  <div class="mobile-task-view">
    <PageHeader title="任务管理" show-back @back="$router.back()">
      <template #right>
        <button
          type="button"
          class="header-action"
          aria-label="筛选"
          title="筛选"
          @click="showFilter = true"
        >🔍</button>
        <button
          type="button"
          class="header-action primary"
          aria-label="新建"
          title="新建"
          @click="showCreate = true"
        >+</button>
      </template>
    </PageHeader>

    <main
      class="task-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- Tabs -->
      <div class="tab-bar">
        <button
          v-for="t in tabs"
          :key="t.value"
          type="button"
          class="tab-item"
          :class="{ active: activeTab === t.value }"
          @click="switchTab(t.value)"
        >
          {{ t.label }}
        </button>
      </div>

      <!-- 列表 -->
      <CardList
        :items="filteredTasks"
        :field-config="fieldConfig"
        :avatar-field="(t) => t.assignee_id"
        :loading="loading"
        empty-icon="📋"
        empty-title="暂无任务"
        empty-hint="点击右上角 + 创建任务"
        :has-more="hasMore"
        @item-click="viewDetail"
        @load-more="loadMore"
      >
        <template #item-actions="{ item }">
          <div class="task-actions">
            <button type="button" class="action-btn" @click.stop="editTask(item)">✏️</button>
            <button
              type="button"
              class="action-btn danger"
              @click.stop="handleDelete(item)"
            >🗑</button>
          </div>
        </template>
      </CardList>

      <!-- 分页信息 -->
      <div v-if="total > pageSize" class="pagination-info">
        共 {{ total }} 条 · 第 {{ currentPage }} / {{ totalPages }} 页
      </div>
    </main>

    <!-- 筛选 Sheet -->
    <MobileSearchSheet
      v-model="showFilter"
      v-model:keyword="searchKeyword"
      title="筛选任务"
      placeholder="搜索任务标题..."
      :filters="searchFilters"
      v-model:filters="activeFilters"
      @confirm="onSearchConfirm"
      @reset="onSearchReset"
    />

    <!-- 创建/编辑 FormSheet -->
    <MobileTaskCreateForm
      v-model="showCreate"
      :editing-task="editingTask"
      @success="onTaskSaved"
    />
  </div>
</template>

<script setup>
/**
 * MobileTaskView.vue — 移动端任务管理
 *
 * PR #8a: 用 CardList + MobileSearchSheet + MobileTaskCreateForm 组合
 * - 顶部 3 tab（全部 / 进行中 / 已完成）
 * - CardList 卡片化任务（不用 el-table）
 * - 搜索/筛选 Sheet
 * - 创建/编辑 FormSheet
 */

import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'
import { useTask } from '@/composables/useTask'
import { useMemberStore } from '@/stores/member'
import PageHeader from '@/components/mobile/PageHeader.vue'
import CardList from '@/components/mobile/CardList.vue'
import MobileSearchSheet from '@/components/mobile/MobileSearchSheet.vue'
import MobileTaskCreateForm from '@/components/mobile/MobileTaskCreateForm.vue'

const router = useRouter()
const route = useRoute()
const memberStore = useMemberStore()

const {
  tasks, total, currentPage, pageSize, loading,
  filters, fetchTasks, deleteTask,
} = useTask()

const activeTab = ref('all')
const showFilter = ref(false)
const showCreate = ref(false)
const editingTask = ref(null)

const searchKeyword = ref(filters.value.search || '')
const activeFilters = ref({
  priority: filters.value.priority || '',
  assignee_id: filters.value.assignee_id || '',
})

const tabs = [
  { label: '全部', value: 'all' },
  { label: '进行中', value: 'in_progress' },
  { label: '已完成', value: 'done' },
]

const searchFilters = computed(() => [
  {
    key: 'priority',
    label: '优先级',
    options: [
      { value: '', label: '全部' },
      { value: 'high', label: '🔴 高' },
      { value: 'medium', label: '🟡 中' },
      { value: 'low', label: '🟢 低' },
    ],
  },
  {
    key: 'assignee_id',
    label: '负责人',
    options: [
      { value: '', label: '全部' },
      { value: 'unassigned', label: '未分配' },
      ...memberStore.members.map((m) => ({ value: m.id, label: m.name })),
    ],
  },
])

// 过滤后的任务
const filteredTasks = computed(() => {
  let list = tasks.value || []
  if (activeTab.value !== 'all') {
    list = list.filter((t) => t.status === activeTab.value)
  }
  // 处理查询参数 overdue
  if (route.query.overdue === 'true') {
    list = list.filter((t) => {
      if (!t.due_date) return false
      return dayjs(t.due_date).isBefore(dayjs())
    })
  }
  return list
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const hasMore = computed(() => currentPage.value < totalPages.value)

// CardList 配置
const fieldConfig = computed(() => ({
  title: (t) => t.title,
  subtitle: (t) => `${memberStore.getMemberName(t.assignee_id) || '未分配'}${t.due_date ? ` · ${formatDue(t.due_date)}` : ''}`,
  badge: (t) => ({
    label: getPriorityLabel(t.priority),
    type: t.priority === 'high' ? 'danger' : t.priority === 'medium' ? 'warning' : 'info',
  }),
  fields: (t) => [
    { key: 'status', label: '状态', value: getStatusLabel(t.status) },
    { key: 'priority', label: '优先级', value: getPriorityLabel(t.priority) },
  ],
}))

// 切换 tab
function switchTab(tab) {
  activeTab.value = tab
  filters.value.status = tab === 'all' ? '' : tab
  currentPage.value = 1
  fetchTasks()
}

// 搜索确认
function onSearchConfirm({ keyword, filters }) {
  searchKeyword.value = keyword
  Object.assign(activeFilters.value, filters)
  filters.value.search = keyword
  filters.value.priority = filters.priority || ''
  filters.value.assignee_id = filters.assignee_id === 'unassigned' ? '' : (filters.assignee_id || '')
  currentPage.value = 1
  fetchTasks()
}

function onSearchReset() {
  searchKeyword.value = ''
  activeFilters.value = { priority: '', assignee_id: '' }
  filters.value.search = ''
  filters.value.priority = ''
  filters.value.assignee_id = ''
  currentPage.value = 1
  fetchTasks()
}

function loadMore() {
  if (hasMore.value) {
    currentPage.value += 1
    fetchTasks()
  }
}

// 操作
function viewDetail(task) {
  // 简化：点击跳转到编辑表单
  editTask(task)
}

function editTask(task) {
  editingTask.value = task
  showCreate.value = true
}

async function handleDelete(task) {
  try {
    await ElMessageBox.confirm(
      `确定删除任务"${task.title}"？`,
      '删除任务',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch { return }
  try {
    await deleteTask(task.id)
    ElMessage.success('任务已删除')
  } catch {
    ElMessage.error('删除失败')
  }
}

function onTaskSaved() {
  editingTask.value = null
  showCreate.value = false
  fetchTasks()
}

// 工具
function getPriorityLabel(p) {
  return { high: '🔴 高', medium: '🟡 中', low: '🟢 低' }[p] || p || ''
}
function getStatusLabel(s) {
  return { in_progress: '进行中', done: '已完成', cancelled: '已取消' }[s] || s || ''
}
function formatDue(d) {
  if (!d) return ''
  const diff = dayjs(d).diff(dayjs(), 'day')
  if (diff < 0) return `${Math.abs(diff)} 天前到期`
  if (diff === 0) return '今天到期'
  if (diff === 1) return '明天到期'
  if (diff < 7) return `${diff} 天后到期`
  return dayjs(d).format('MM-DD')
}

onMounted(() => {
  // 处理 ?status=xxx & overdue=true 查询参数
  if (route.query.status) {
    activeTab.value = route.query.status
    filters.value.status = route.query.status
  } else if (route.query.overdue === 'true') {
    filters.value.status = 'in_progress'
  }
  fetchTasks()
})
</script>

<style scoped>
.mobile-task-view {
  min-height: 100vh;
  background: var(--color-bg-page);
  display: flex;
  flex-direction: column;
}

.task-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* Tab bar */
.tab-bar {
  display: flex;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 4px;
  margin-bottom: 12px;
}
.tab-item {
  flex: 1;
  padding: 8px;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.tab-item.active {
  background: var(--color-primary);
  color: white;
  font-weight: var(--font-weight-medium, 500);
}

/* 分页信息 */
.pagination-info {
  text-align: center;
  font-size: 11px;
  color: var(--color-text-secondary);
  padding: 12px 0;
}

/* Header action */
.header-action {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--color-text-regular);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  margin-left: 4px;
}
.header-action:active { background: var(--color-primary-bg); }
.header-action.primary {
  background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
  color: white;
  font-weight: 600;
  font-size: 22px;
}

/* 任务操作按钮（CardList slot） */
.task-actions {
  display: flex;
  gap: 6px;
  margin-top: 6px;
}
.action-btn {
  flex: 1;
  padding: 6px;
  border-radius: var(--radius-sm);
  border: none;
  font-size: 14px;
  cursor: pointer;
  background: var(--color-bg-page);
  -webkit-tap-highlight-color: transparent;
}
.action-btn:active { opacity: 0.6; }
.action-btn.danger {
  background: var(--color-danger-bg);
  color: var(--color-danger, #F56C6C);
}
</style>
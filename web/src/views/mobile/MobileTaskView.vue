<template>
  <div
    class="mobile-task-view mg-page"
    :class="{ 'done-mode': activeTab === 'done', 'overdue-mode': route.query.overdue === 'true' }"
  >
    <PageHeader title="任务管理" show-back @back="$router.back()">
      <template #right>
        <button
          type="button"
          class="header-action"
          aria-label="任务回收站"
          title="任务回收站"
          @click="$router.push('/tasks/trash')"
        >🗑</button>
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
      <div class="tab-bar mg-glass">
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

      <!-- 列表：2026-06-26 按负责人分组（一人一头像，下方罗列任务） -->
      <div v-if="loading && groupedTasks.length === 0" class="loading-state mg-glass">
        <div class="empty-icon">⏳</div>
        <div class="empty-hint">加载中...</div>
      </div>

      <div v-else-if="groupedTasks.length === 0" class="empty-state mg-glass">
        <div class="empty-icon">📋</div>
        <div class="empty-title">暂无任务</div>
        <div class="empty-hint">点击右上角 + 创建任务</div>
      </div>

      <div v-else class="task-groups">
        <section
          v-for="(group, gIdx) in groupedTasks"
          :key="group.assignee_id"
          class="task-group fade-slide-up mg-rise"
          :class="'mg-stagger-' + ((gIdx % 5) + 1)"
          :style="{ animationDelay: `${gIdx * 0.05}s` }"
        >
          <!-- 组头：带头像 + 名字 + 任务数 + 折叠箭头 -->
          <header class="task-group-header" @click="toggleGroup(group.assignee_id)">
            <MemberAvatar
              :member-id="group.assignee_id === 'unassigned' ? null : group.assignee_id"
              :member-name="getGroupName(group.assignee_id)"
              :size="36"
              class="group-avatar"
            />
            <span class="group-name">{{ getGroupName(group.assignee_id) }}</span>
            <span class="group-count mg-chip">{{ group.tasks.length }}项</span>
            <span
              class="collapse-icon"
              :class="{ collapsed: collapsedGroups[group.assignee_id] }"
            >›</span>
          </header>

          <!-- 组内任务列表：复用 CardList（不传 avatar-field，避免与组头重复） -->
          <div v-show="!collapsedGroups[group.assignee_id]" class="task-group-list">
            <CardList
              :items="group.tasks"
              :field-config="fieldConfig"
              :avatar-field="null"
              :loading="false"
              :has-more="false"
              :show-end-hint="false"
              empty-icon=""
              empty-title=""
              empty-hint=""
              @item-click="editTask"
            >
              <template #item-actions="{ item }">
                <div class="task-actions">
                  <!-- 2026-06-25: 完成按钮（之前 PR #8a 重构遗漏） -->
                  <button
                    type="button"
                    class="action-btn"
                    :class="item.status === 'done' ? 'success' : 'primary'"
                    @click.stop="toggleTaskStatus(item)"
                  >{{ item.status === 'done' ? '↶ 取消' : '完成' }}</button>
                  <button type="button" class="action-btn" @click.stop="editTask(item)">✏️</button>
                  <button
                    type="button"
                    class="action-btn danger"
                    @click.stop="handleDelete(item)"
                  >🗑</button>
                </div>
              </template>
            </CardList>
          </div>
        </section>
      </div>

      <!-- 分页信息 -->
      <div v-if="total > pageSize" class="pagination-info">
        共 {{ total }} 条 · 第 {{ currentPage }} / {{ totalPages }} 页
      </div>
    </main>

    <MobileFab :actions="fabActions" />

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
import MemberAvatar from '@/components/mobile/MemberAvatar.vue'  // 2026-06-26: 按负责人分组的组头头像
import { groupTasksByAssignee } from '@/utils/taskGroup'  // 2026-06-26: 从 TaskView 抽出共用
import MobileFab from '@/components/mobile/MobileFab.vue'

const router = useRouter()
const route = useRoute()
const memberStore = useMemberStore()

const {
  tasks, total, currentPage, pageSize, loading,
  filters, fetchTasks, deleteTask, updateTask,  // 2026-06-25: 加 updateTask
} = useTask()

const activeTab = ref('in_progress')  // 2026-06-25: 删除"全部" tab，默认显示"进行中"
const showFilter = ref(false)
const showCreate = ref(false)
const editingTask = ref(null)

const searchKeyword = ref(filters.value.search || '')
const activeFilters = ref({
  priority: filters.value.priority || '',
  assignee_id: filters.value.assignee_id || '',
})

// 2026-06-25: 删除"全部" tab，只保留"进行中"和"已完成"两个
const tabs = [
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

const fabActions = [
  { name: 'create', label: 'New task', icon: '＋', handler: () => { editingTask.value = null; showCreate.value = true } },
  { name: 'search', label: 'Filter tasks', icon: '🔍', handler: () => { showFilter.value = true } },
  { name: 'trash', label: 'Task trash', icon: '🗑', handler: () => router.push('/tasks/trash') },
  { name: 'refresh', label: 'Refresh list', icon: '↻', handler: () => fetchTasks() },
]

// 过滤后的任务
const filteredTasks = computed(() => {
  // 2026-06-25: 删除 'all' 分支，直接按状态过滤
  let list = (tasks.value || []).filter((t) => t.status === activeTab.value)
  // 处理查询参数 overdue
  if (route.query.overdue === 'true') {
    list = list.filter((t) => {
      if (!t.due_date) return false
      return dayjs(t.due_date).isBefore(dayjs())
    })
  }
  return list
})

// 2026-06-26: 按负责人分组（一人一头像，下方罗列任务）
const groupedTasks = computed(() => groupTasksByAssignee(filteredTasks.value))

// 2026-06-26: 折叠状态（默认全部展开，reactive 对象跨 tab 共享）
const collapsedGroups = ref({})
function toggleGroup(id) {
  collapsedGroups.value[id] = !collapsedGroups.value[id]
}

// 2026-06-26: 组名（unassigned 走中文，其他走 memberStore）
function getGroupName(id) {
  if (id === 'unassigned') return '未分配'
  return memberStore.getMemberName(id) || '未知成员'
}

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))
const hasMore = computed(() => currentPage.value < totalPages.value)

// CardList 配置
const fieldConfig = computed(() => ({
  title: (t) => t.title,
  // 2026-06-26: 分组后组内都是同一人，不再重复显示负责人名
  subtitle: (t) => {
    const parts = []
    if (t.status) parts.push(getStatusLabel(t.status))
    if (t.due_date) parts.push(formatDue(t.due_date))
    return parts.join(' · ')
  },
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
  // 2026-06-25: 简化（不再有 'all' → '' 转换）
  activeTab.value = tab
  filters.value.status = tab
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

/**
 * 2026-06-25: 切换任务状态（完成 / 取消完成）
 * 与桌面端 TaskView.vue:489-498 一致，复用 useTask().updateTask
 * @param {Object} task - 任务对象
 */
async function toggleTaskStatus(task) {
  const newStatus = task.status === 'done' ? 'in_progress' : 'done'
  try {
    await updateTask(task.id, { status: newStatus })
    ElMessage.success(newStatus === 'done' ? '已完成' : '已恢复进行中')
  } catch (e) {
    const msg = e.response?.data?.error?.message || '状态更新失败'
    ElMessage.error(msg)
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
  // 2026-06-25: 加白名单校验，防止 ?status=todo 等无效值进入 activeTab
  const VALID_TABS = ['in_progress', 'done']
  if (route.query.status && VALID_TABS.includes(route.query.status)) {
    activeTab.value = route.query.status
    filters.value.status = route.query.status
  } else if (route.query.overdue === 'true') {
    filters.value.status = 'in_progress'
  }
  fetchTasks()
})
</script>

<style scoped>
/* 液态毛玻璃 (Liquid Glass) — 2026-08-31 升级
   背景/文字色由全局 .mg-page 提供 (极光渐变 + --mg-text), 本块严禁再设 background/color 根属性覆盖玻璃配方 */
.mobile-task-view {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.task-main {
  flex: 1;
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* PageHeader 玻璃化 (子组件经 :deep 命中; safe-area 顶部由 PageHeader 自身 --sat 处理) */
:deep(.mobile-page-header) {
  background: var(--mg-glass-bg);
  -webkit-backdrop-filter: blur(24px);
  backdrop-filter: blur(24px);
  border-bottom: 1px solid var(--mg-glass-border);
}
:deep(.header-title) {
  color: var(--mg-text-strong);
}
:deep(.header-back) {
  color: var(--mg-text);
}
:deep(.header-back:active) {
  background: var(--mg-gradient-soft);
  color: var(--mg-primary);
}

/* Tab bar — mg-glass 胶囊 (mg-glass 提供底/描边/blur/阴影, 此处仅改圆角为 pill) */
.tab-bar {
  display: flex;
  padding: 4px;
  margin-bottom: 12px;
  border-radius: var(--mg-radius-pill);
  box-shadow: var(--mg-shadow-sm);
}
.tab-item {
  flex: 1;
  min-height: 44px;
  padding: 10px 8px;
  border: none;
  background: transparent;
  border-radius: var(--mg-radius-pill);
  font-size: 13px;
  font-weight: 600;
  color: var(--mg-text-soft);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: transform 150ms ease;
}
.tab-item:active { transform: scale(0.97); }
.tab-item.active {
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
  font-weight: 800;
  box-shadow: var(--mg-primary-shadow);
}

/* 分页信息 */
.pagination-info {
  text-align: center;
  font-size: 11px;
  color: var(--mg-text-faint);
  padding: 12px 0;
}

/* Header action */
.header-action {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: transparent;
  border: none;
  font-size: 18px;
  color: var(--mg-text);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  margin-left: 4px;
}
.header-action:active { background: var(--mg-gradient-soft); }
.header-action.primary {
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
  font-weight: 600;
  font-size: 22px;
  box-shadow: var(--mg-primary-shadow);
}

/* 任务操作按钮（CardList slot） */
.task-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.action-btn {
  flex: 1;
  min-height: 44px;
  padding: 10px 6px;
  border-radius: 14px;
  border: 1.5px solid var(--mg-glass-border);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  background: var(--mg-glass-bg-strong);
  color: var(--mg-text);
  -webkit-tap-highlight-color: transparent;
  transition: transform 150ms ease, opacity 150ms ease;
}
.action-btn:active { transform: scale(0.97); opacity: 0.85; }
.action-btn.danger {
  background: var(--mg-danger-soft);
  color: var(--mg-danger);
  border-color: transparent;
}
/* 完成按钮（primary 状态）+ 取消完成（success 状态） */
.action-btn.primary {
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
  border: none;
}
.action-btn.success {
  background: var(--mg-success-soft);
  color: var(--mg-success);
  border: 1px solid var(--mg-success);
}

/* 按负责人分组（一组一人一头像 + 任务罗列）— 组卡 = 玻璃卡 */
.task-groups {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.task-group {
  background: var(--mg-glass-bg);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(var(--mg-glass-blur));
  backdrop-filter: blur(var(--mg-glass-blur));
  border-radius: var(--mg-radius-lg);
  box-shadow: var(--mg-shadow);
  overflow: hidden;
}
.task-group-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  background: transparent;
}
.task-group-header:active { background: var(--mg-gradient-soft); }
.group-avatar { flex-shrink: 0; }
.group-name {
  flex: 1;
  font-size: 15px;
  font-weight: 800;
  color: var(--mg-text-strong);
}
/* 计数芯片配色由全局 .mg-chip 提供 (模板已加), 此处只保留布局 */
.group-count { flex-shrink: 0; }
.collapse-icon {
  font-size: 18px;
  color: var(--mg-text-faint);
  transition: transform 0.2s;
  display: inline-block;
}
.collapse-icon.collapsed { transform: rotate(-90deg); }
.task-group-list { padding: 0 0 12px; }

/* 组内 CardList 任务行 = mg-glass 列表卡 (radius-md / padding 13px 14px / 行间距 10px) */
.task-group-list :deep(.list-body) {
  padding: 0 12px;
  gap: 10px;
}
.task-group-list :deep(.list-item) {
  background: var(--mg-glass-bg-strong);
  border: 1.5px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-md);
  padding: 13px 14px;
  box-shadow: var(--mg-shadow-sm);
  transition: transform 150ms ease;
}
.task-group-list :deep(.list-item:active) { transform: scale(0.99); }
.task-group-list :deep(.item-title) {
  color: var(--mg-text-strong);
}
.task-group-list :deep(.item-subtitle) {
  color: var(--mg-text-soft);
}
.task-group-list :deep(.field-key) { color: var(--mg-text-soft); }
.task-group-list :deep(.field-value) { color: var(--mg-text); }
.task-group-list :deep(.item-arrow) { color: var(--mg-text-faint); }

/* 优先级/状态芯片: 高=--mg-danger 中=--mg-warning 低=--mg-info
   (CardList badge type 已由 fieldConfig 映射 danger/warning/info) */
:deep(.badge-tag) {
  border-radius: var(--mg-radius-pill);
  padding: 3px 10px;
  font-weight: 600;
  background: var(--mg-info-soft);
  color: var(--mg-info);
}
:deep(.badge--danger) { background: var(--mg-danger-soft); color: var(--mg-danger); }
:deep(.badge--warning) { background: var(--mg-warning-soft); color: var(--mg-warning); }
:deep(.badge--info)    { background: var(--mg-info-soft);    color: var(--mg-info); }
:deep(.badge--success) { background: var(--mg-success-soft); color: var(--mg-success); }
:deep(.badge--primary) { background: var(--mg-gradient-soft); color: var(--mg-primary); }

/* 逾期筛选视图 (route.query.overdue=true, 根节点动态 class): 副标题里日期文字标红 */
.overdue-mode :deep(.item-subtitle) {
  color: var(--mg-danger);
  font-weight: 600;
}

/* 已完成 tab: 整行降透明度 + 标题删除线 (桌面端同款语义) */
.done-mode :deep(.list-item) { opacity: 0.6; }
.done-mode :deep(.item-title) {
  text-decoration: line-through;
  color: var(--mg-text-faint);
}

/* FAB (MobileFab 子组件): 56px 渐变圆 + 玻璃动作条 */
:deep(.mobile-fab-trigger) {
  background: var(--mg-gradient-btn);
  box-shadow: var(--mg-primary-shadow);
}
:deep(.mobile-fab-action) {
  background: var(--mg-glass-bg-strong);
  -webkit-backdrop-filter: blur(16px);
  backdrop-filter: blur(16px);
  border: 1.5px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-pill);
  color: var(--mg-text);
  box-shadow: var(--mg-shadow);
}
:deep(.mobile-fab-action.danger) { color: var(--mg-danger); }
:deep(.mobile-fab-action-icon) { background: var(--mg-gradient-soft); }

/* 加载中态 / 空态 (模板已加 mg-glass, 卡片配方来自全局) */
.loading-state,
.empty-state {
  text-align: center;
  padding: 48px 20px;
  margin-top: 8px;
  border-radius: var(--mg-radius-lg);
  color: var(--mg-text-soft);
}
.loading-state .empty-icon,
.empty-state .empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}
.empty-state .empty-title {
  font-size: 17px;
  font-weight: 800;
  color: var(--mg-text-strong);
  margin-bottom: 8px;
}
.empty-state .empty-hint {
  font-size: 13px;
  color: var(--mg-text-soft);
}
</style>

<!-- v77 P2.6-B + W68 第 14 批 C-2: dark mode 跨组件统一（v60-v67 教训：必须非 scoped）
     2026-08-31 液态毛玻璃升级: --mg-* token 自带 [data-theme="dark"] 变体, 原 task-group / action-btn /
     group-* 的 dark 覆盖已删除 (否则 --color-bg-card 实色会盖掉玻璃配方);
     非 scoped 块里 :deep() 是死选择器 (原 .task-group-list :deep(.list-item) dark 规则从未生效), 一并移除. -->
<style>
/* header 主操作按钮在 dark 保持渐变 */
[data-theme="dark"] .header-action.primary {
  background: var(--mg-gradient-btn);
  color: var(--mg-on-primary);
}
[data-theme="dark"] .header-action.primary:active {
  background: var(--mg-gradient-btn);
  opacity: 0.85;
}
[data-theme="dark"] .header-action {
  color: var(--mg-text);
}

/* 以下为老 class 名遗留的 dark 规则 (status-badge / priority-pill / task-card),
   可能命中其他视图渲染的同名全局 class, 保留不动防回归 */
[data-theme="dark"] .status-badge.status-todo,
[data-theme="dark"] .status-badge.status-in_progress {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}
[data-theme="dark"] .status-badge.status-done {
  background: var(--color-success-bg);
  color: var(--color-success);
}
[data-theme="dark"] .priority-pill.priority-high {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}
[data-theme="dark"] .priority-pill.priority-medium {
  background: var(--color-warning-bg);
  color: var(--color-warning);
}
[data-theme="dark"] .priority-pill.priority-low {
  background: var(--color-success-bg);
  color: var(--color-success);
}
[data-theme="dark"] .task-card:active {
  background: var(--color-bg-hover);
}
</style>
<script setup lang="ts">
/**
 * Desktop Dashboard View (Phase 2-Impl-1)。
 *
 * 数据源 (全部走 window.api.api.request IPC → main api.service → FastAPI):
 *   - GET /api/v1/dashboard/summary     -> 4 张统计卡
 *   - GET /api/v1/dashboard/project-stats -> 工程统计卡
 *   - GET /api/v1/tasks?page=1&page_size=5 -> 最近任务列表
 *
 * 与 web Dashboard.vue 关系: 仅读源 web/src/views/Dashboard.vue 字段口径,
 * desktop 端完全重写 (UI + API 调用路径)。
 */
import { computed, onMounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'
import { useUserStore } from '../stores/user'
import { isAdminRole } from '@shared/auth-types'
import type { TaskSummary } from '@shared/dashboard-types'
import { Card, Loading, EmptyState, ErrorState } from '../components/ui'

const dashboardStore = useDashboardStore()
const userStore = useUserStore()

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '凌晨好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const displayName = computed(() => userStore.profile?.name ?? '用户')
const isAdmin = computed(() => isAdminRole(userStore.profile?.role))

const statsView = computed(() => {
  const s = dashboardStore.summary
  if (!s) return null
  return {
    inProgress: s.in_progress_tasks,
    done: s.done_tasks,
    overdue: s.overdue_tasks,
    total: s.in_progress_tasks + s.done_tasks
  }
})

const projectStats = computed(() => dashboardStore.projectStats)
const recentTasks = computed<TaskSummary[]>(() => dashboardStore.recentTasks)

function statusLabel(status: string | undefined): string {
  switch (status) {
    case 'todo': return '待办'
    case 'in_progress': return '进行中'
    case 'done': return '已完成'
    case 'paused': return '暂停'
    case 'cancelled': return '取消'
    default: return status ?? '未知'
  }
}

function priorityClass(priority: string | undefined): string {
  switch (priority) {
    case 'urgent':
    case 'high':
      return 'high'
    case 'medium':
      return 'medium'
    case 'low':
      return 'low'
    default:
      return 'normal'
  }
}

async function loadData(): Promise<void> {
  await dashboardStore.loadAll()
}

onMounted(loadData)
</script>

<template>
  <div class="dashboard-view">
    <!-- 欢迎区域 -->
    <section class="welcome">
      <div class="welcome__left">
        <h1 class="welcome__greeting">
          {{ greeting }}, {{ displayName }}{{ isAdmin ? ' 👑' : '' }}
        </h1>
        <p class="welcome__sub">
          今天是 {{ new Date().toLocaleDateString('zh-CN') }}，欢迎使用 MicroBubble Desktop。
        </p>
        <p v-if="dashboardStore.lastError" class="welcome__hint warning">
          ⚠️ 数据加载不完整 ({{ dashboardStore.lastError.code }})：
          {{ dashboardStore.lastError.message }}
        </p>
        <p v-else-if="statsView && statsView.overdue > 0" class="welcome__hint danger">
          ⚠️ 团队共有 {{ statsView.overdue }} 项逾期任务
        </p>
        <p v-else-if="statsView && statsView.inProgress > 0" class="welcome__hint success">
          🎯 团队共有 {{ statsView.inProgress }} 项任务进行中
        </p>
        <p v-else-if="statsView" class="welcome__hint">✨ 今日任务清空，继续保持！</p>
      </div>
      <div class="welcome__right">
        <router-link :to="{ name: 'chat' }" class="welcome__btn welcome__btn--primary">
          💬 开始对话
        </router-link>
        <button class="welcome__btn welcome__btn--secondary" disabled>
          ＋ 创建任务
        </button>
      </div>
    </section>

    <!-- 4 张统计卡 -->
    <h3 class="dashboard-section-title">核心指标</h3>
    <div v-if="dashboardStore.loading && !statsView" class="stats-row">
      <Card padding="md" v-for="i in 4" :key="i">
        <Loading variant="skeleton" :rows="2" />
      </Card>
    </div>
    <div v-else class="stats-row">
      <Card title="进行中" padding="md">
        <p class="stat-number text-orange">{{ statsView?.inProgress ?? 0 }}</p>
        <p class="stat-label">in_progress_tasks</p>
      </Card>
      <Card title="已完成" padding="md">
        <p class="stat-number text-green">{{ statsView?.done ?? 0 }}</p>
        <p class="stat-label">done_tasks</p>
      </Card>
      <Card title="已逾期" padding="md">
        <p class="stat-number text-red">{{ statsView?.overdue ?? 0 }}</p>
        <p class="stat-label">overdue_tasks</p>
      </Card>
      <Card title="活跃任务总数" padding="md">
        <p class="stat-number text-blue">{{ statsView?.total ?? 0 }}</p>
        <p class="stat-label">in_progress + done</p>
      </Card>
    </div>

    <!-- 工程统计 -->
    <h3 class="dashboard-section-title">项目工程统计</h3>
    <div class="stats-row">
      <Card title="提交数" padding="md">
        <p class="stat-number text-blue">{{ projectStats?.total_commits ?? '-' }}</p>
        <p class="stat-label">commits</p>
      </Card>
      <Card title="文件数" padding="md">
        <p class="stat-number text-blue">{{ projectStats?.total_files ?? '-' }}</p>
        <p class="stat-label">files</p>
      </Card>
      <Card title="代码行数" padding="md">
        <p class="stat-number text-blue">{{ projectStats?.total_lines ?? '-' }}</p>
        <p class="stat-label">lines</p>
      </Card>
      <Card title="开发天数" padding="md">
        <p class="stat-number text-blue">{{ projectStats?.dev_days ?? '-' }}</p>
        <p class="stat-label">days</p>
      </Card>
    </div>

    <!-- 最近任务 -->
    <h3 class="dashboard-section-title">最近任务</h3>
    <Card padding="md">
      <Loading v-if="dashboardStore.loading && recentTasks.length === 0" variant="spinner" text="加载任务中…" />
      <EmptyState
        v-else-if="recentTasks.length === 0 && !dashboardStore.loading"
        icon="📋"
        title="暂无任务"
        description="团队目前没有任务记录"
      />
      <ul v-else class="task-list">
        <li v-for="task in recentTasks" :key="task.id" class="task-item">
          <div class="task-item__left">
            <span :class="['task-item__priority', `task-item__priority--${priorityClass(task.priority)}`]">
              {{ task.priority === 'urgent' ? '⚠️' : task.priority === 'high' ? '❗' : '·' }}
            </span>
            <span class="task-item__title">{{ task.title }}</span>
          </div>
          <div class="task-item__right">
            <span :class="['task-item__status', `task-item__status--${task.status}`]">
              {{ statusLabel(task.status) }}
            </span>
            <span v-if="task.due_date" class="task-item__due">{{ task.due_date }}</span>
          </div>
        </li>
      </ul>
    </Card>

    <ErrorState
      v-if="dashboardStore.lastError && recentTasks.length === 0"
      title="Dashboard 加载失败"
      :message="dashboardStore.lastError.message"
      @retry="loadData"
    />
  </div>
</template>

<style scoped>
/* Phase 13: 重设计为 research design tokens (与 LoginView / HomeView 一致).
   之前: 暗色 #0f172a/#f97316. 现在: paper + teal + instrument. */

.dashboard-view {
  min-height: 100vh;
  padding: clamp(24px, 4vw, 48px);
  background: var(--research-mist-50, #f5f7fa);
  color: var(--research-text-primary, #0f172a);
  font-family: var(--research-font-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif);
  box-sizing: border-box;
}

.welcome {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 32px;
  margin-bottom: 24px;
  background: linear-gradient(140deg, var(--research-instrument-900, #1a3742) 0%, #173438 100%);
  color: #e7f3ef;
  border-radius: 16px;
  border: 1px solid transparent;
}
.welcome__left { flex: 1; }
.welcome__greeting {
  margin: 0 0 8px;
  font-size: clamp(22px, 2vw, 28px);
  font-weight: 700;
  letter-spacing: -0.025em;
  color: #e7f3ef;
}
.welcome__sub {
  margin: 0 0 12px;
  font-size: 14px;
  color: #c4d4d1;
}
.welcome__hint {
  margin: 6px 0 0;
  font-size: 13px;
  color: #c4d4d1;
}
.welcome__hint.warning { color: var(--research-warning, #fbbf24); }
.welcome__hint.danger { color: var(--research-error, #ef4444); }
.welcome__hint.success { color: var(--research-signal-green, #7ed6ad); }

.welcome__right {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}
.welcome__btn {
  display: inline-flex;
  align-items: center;
  padding: 10px 20px;
  border-radius: 8px;
  text-decoration: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  font-family: inherit;
  transition: background 0.15s, border-color 0.15s, transform 0.05s;
}
.welcome__btn--primary {
  background: var(--research-signal-green, #7ed6ad);
  color: var(--research-instrument-900, #1a3742);
  border-color: var(--research-signal-green, #7ed6ad);
}
.welcome__btn--primary:hover { background: #6bc79e; }
.welcome__btn--primary:active { transform: translateY(1px); }
.welcome__btn--secondary {
  background: transparent;
  border-color: rgb(126 214 173 / 40%);
  color: #e7f3ef;
}
.welcome__btn--secondary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.welcome__btn--secondary:hover:not(:disabled) {
  background: rgb(126 214 173 / 12%);
}

.dashboard-section-title {
  margin: 24px 0 12px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--research-text-secondary, #6b7280);
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.stat-number {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--research-text-primary, #0f172a);
}
.stat-number.text-orange { color: var(--research-warning, #f97316); }
.stat-number.text-green { color: var(--research-signal-green, #1a7a52); }
.stat-number.text-red { color: var(--research-error, #ef4444); }
.stat-number.text-blue { color: var(--research-info, #3b82f6); }
.stat-label {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--research-text-secondary, #6b7280);
}

.task-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.task-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid var(--research-border-light, #f3f4f6);
}
.task-item:last-child { border-bottom: 0; }
.task-item__left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.task-item__priority {
  display: inline-block;
  width: 20px;
  text-align: center;
  font-weight: 600;
}
.task-item__priority--high { color: var(--research-error, #ef4444); }
.task-item__priority--medium { color: var(--research-warning, #f97316); }
.task-item__priority--low { color: var(--research-text-secondary, #9ca3af); }
.task-item__priority--normal { color: var(--research-text-secondary, #cbd5d1); }
.task-item__title {
  font-size: 14px;
  color: var(--research-text-primary, #0f172a);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-item__right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.task-item__status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}
.task-item__status--todo {
  background: var(--research-mist-100, #f3f4f6);
  color: var(--research-text-secondary, #6b7280);
}
.task-item__status--in_progress {
  background: rgb(249 115 22 / 15%);
  color: var(--research-warning, #f97316);
}
.task-item__status--done {
  background: rgb(126 214 173 / 20%);
  color: var(--research-signal-green, #1a7a52);
}
.task-item__status--paused {
  background: rgb(251 191 36 / 15%);
  color: var(--research-warning, #fbbf24);
}
.task-item__due {
  font-size: 12px;
  color: var(--research-text-secondary, #6b7280);
}
</style>

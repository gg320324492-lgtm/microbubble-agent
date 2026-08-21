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
.dashboard-view {
  padding: 1.5rem 2rem;
  max-width: 1200px;
}

.welcome {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1.5rem 2rem;
  margin-bottom: 1.5rem;
  background: linear-gradient(135deg, rgba(249, 115, 22, 0.12) 0%, rgba(251, 191, 36, 0.04) 100%);
  border: 1px solid rgba(249, 115, 22, 0.25);
  border-radius: 8px;
}
.welcome__greeting {
  margin: 0 0 0.4rem;
  font-size: 1.4rem;
  color: #f1f5f9;
}
.welcome__sub {
  margin: 0 0 0.6rem;
  font-size: 0.85rem;
  color: #94a3b8;
}
.welcome__hint {
  margin: 0.3rem 0 0;
  font-size: 0.85rem;
}
.welcome__hint.warning { color: #fbbf24; }
.welcome__hint.danger { color: #ef4444; }
.welcome__hint.success { color: #10b981; }

.welcome__right {
  display: flex;
  gap: 0.6rem;
}
.welcome__btn {
  padding: 0.5rem 1rem;
  border-radius: 4px;
  text-decoration: none;
  font-size: 0.85rem;
  cursor: pointer;
  border: 1px solid transparent;
  font-family: inherit;
}
.welcome__btn--primary {
  background: #f97316;
  color: #fff;
}
.welcome__btn--primary:hover { background: #ea580c; }
.welcome__btn--secondary {
  background: transparent;
  border-color: #475569;
  color: #cbd5e1;
}
.welcome__btn--secondary:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.dashboard-section-title {
  margin: 1.5rem 0 0.6rem;
  font-size: 0.95rem;
  font-weight: 500;
  color: #cbd5e1;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}
.stat-number {
  margin: 0;
  font-size: 1.8rem;
  font-weight: 700;
  line-height: 1.2;
}
.stat-number.text-orange { color: #f97316; }
.stat-number.text-green { color: #10b981; }
.stat-number.text-red { color: #ef4444; }
.stat-number.text-blue { color: #3b82f6; }
.stat-label {
  margin: 0.3rem 0 0;
  font-size: 0.75rem;
  color: #64748b;
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
  padding: 0.6rem 0;
  border-bottom: 1px solid #334155;
}
.task-item:last-child {
  border-bottom: 0;
}
.task-item__left {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex: 1;
  min-width: 0;
}
.task-item__priority {
  display: inline-block;
  width: 1.2rem;
  text-align: center;
}
.task-item__priority--high { color: #ef4444; }
.task-item__priority--medium { color: #f97316; }
.task-item__priority--low { color: #94a3b8; }
.task-item__priority--normal { color: #475569; }
.task-item__title {
  font-size: 0.9rem;
  color: #f1f5f9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.task-item__right {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-shrink: 0;
}
.task-item__status {
  font-size: 0.75rem;
  padding: 0.15rem 0.5rem;
  border-radius: 3px;
}
.task-item__status--todo {
  background: #334155;
  color: #cbd5e1;
}
.task-item__status--in_progress {
  background: rgba(249, 115, 22, 0.15);
  color: #f97316;
}
.task-item__status--done {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}
.task-item__status--paused {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}
.task-item__due {
  font-size: 0.75rem;
  color: #64748b;
}
</style>

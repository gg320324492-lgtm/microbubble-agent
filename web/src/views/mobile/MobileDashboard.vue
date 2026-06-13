<template>
  <div class="mobile-dashboard">
    <PageHeader title="首页" />

    <main
      class="dashboard-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- 欢迎卡片 -->
      <section class="welcome-card">
        <div class="welcome-content">
          <div class="greeting">{{ greeting }}，{{ username }}！</div>
          <div class="date">{{ currentDate }}</div>
        </div>
        <div class="welcome-emoji">💬</div>
      </section>

      <!-- 快捷入口 -->
      <section class="quick-grid">
        <button
          v-for="action in quickActions"
          :key="action.path"
          type="button"
          class="quick-item"
          @click="$router.push(action.path)"
        >
          <div class="quick-icon" :style="{ background: action.bg }">
            {{ action.icon }}
          </div>
          <div class="quick-label">{{ action.label }}</div>
        </button>
      </section>

      <!-- 数据统计 -->
      <section v-if="!loading && summary" class="stats-section">
        <h3 class="section-title">📊 团队动态</h3>
        <div class="stats-grid">
          <button
            type="button"
            class="stat-card stat-warning"
            @click="$router.push('/tasks')"
          >
            <div class="stat-num">{{ summary.in_progress_tasks || 0 }}</div>
            <div class="stat-label">进行中</div>
          </button>
          <button
            type="button"
            class="stat-card stat-success"
            @click="$router.push('/tasks?status=done')"
          >
            <div class="stat-num">{{ summary.done_tasks || 0 }}</div>
            <div class="stat-label">已完成</div>
          </button>
          <button
            type="button"
            class="stat-card stat-danger"
            :class="{ highlight: summary.overdue_tasks > 0 }"
            @click="$router.push('/tasks?overdue=true')"
          >
            <div class="stat-num">{{ summary.overdue_tasks || 0 }}</div>
            <div class="stat-label">已逾期</div>
          </button>
        </div>
      </section>

      <!-- 加载状态 -->
      <section v-else-if="loading" class="loading-section">
        <div v-for="i in 3" :key="i" class="skeleton-card">
          <div class="skeleton-line w-60" />
          <div class="skeleton-line w-90" />
        </div>
      </section>

      <!-- 待办任务（最近 5 条） -->
      <section v-if="recentTasks.length > 0" class="recent-section">
        <div class="section-header">
          <h3 class="section-title">🚀 待办任务</h3>
          <button type="button" class="view-all-btn" @click="$router.push('/tasks')">
            全部 →
          </button>
        </div>

        <div class="recent-list">
          <button
            v-for="task in recentTasks"
            :key="task.id"
            type="button"
            class="task-item"
            @click="$router.push('/tasks')"
          >
            <span class="task-priority" :class="`priority-${task.priority}`" />
            <div class="task-info">
              <div class="task-title">{{ task.title }}</div>
              <div class="task-meta">
                <span>{{ getAssigneeName(task.assignee_id) }}</span>
                <span v-if="task.due_date" class="task-due" :class="{ overdue: isOverdue(task.due_date) }">
                  {{ formatDue(task.due_date) }}
                </span>
              </div>
            </div>
            <span class="task-arrow">›</span>
          </button>
        </div>
      </section>

      <section v-else class="empty-section">
        <div class="empty-icon">🎉</div>
        <div class="empty-title">今日任务已完成！</div>
      </section>
    </main>
  </div>
</template>

<script setup>
/**
 * MobileDashboard.vue — 移动端仪表盘
 *
 * PR #8a: 简化版（不用桌面兔子/云朵装饰）
 * - 欢迎卡片 + 问候语
 * - 5 个快捷入口（聊/任务/会议/知识/我的）
 * - 3 个数据统计卡片
 * - 最近 5 条待办任务
 */

import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import axios from 'axios'
import { useUserStore } from '@/stores/user'
import { useMemberStore } from '@/stores/member'
import PageHeader from '@/components/mobile/PageHeader.vue'

const router = useRouter()
const userStore = useUserStore()
const memberStore = useMemberStore()

const loading = ref(true)
const summary = ref(null)
const recentTasks = ref([])

const username = computed(() => userStore.username || '研究员')

const greeting = computed(() => {
  const hour = dayjs().hour()
  if (hour < 6) return '夜深了'
  if (hour < 12) return '早上好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const currentDate = computed(() => {
  return dayjs().format('YYYY年M月D日 dddd')
})

// 快捷入口
const quickActions = [
  { icon: '💬', label: '智能对话', path: '/chat', bg: 'linear-gradient(135deg, #FF7A5C, #FFB347)' },
  { icon: '✅', label: '我的任务', path: '/tasks', bg: 'linear-gradient(135deg, #67C23A, #95D475)' },
  { icon: '🎤', label: '会议', path: '/meetings', bg: 'linear-gradient(135deg, #E6A23C, #F3D178)' },
  { icon: '📚', label: '知识库', path: '/knowledge', bg: 'linear-gradient(135deg, #409EFF, #79BBFF)' },
  { icon: '👤', label: '我的', path: '/settings', bg: 'linear-gradient(135deg, #909399, #B9BCC1)' },
]

// 加载数据
async function loadDashboard() {
  loading.value = true
  try {
    const [summaryRes, tasksRes] = await Promise.all([
      axios.get('/api/v1/dashboard/summary').catch(() => ({ data: {} })),
      axios.get('/api/v1/tasks', {
        params: { status: 'in_progress', page_size: 5, page: 1 }
      }).catch(() => ({ data: { items: [] } })),
    ])
    summary.value = summaryRes.data
    recentTasks.value = tasksRes.data?.items || []
  } catch (e) {
    console.error('[MobileDashboard] load failed:', e)
  } finally {
    loading.value = false
  }
}

// 工具
function getAssigneeName(id) {
  if (!id) return '未分配'
  return memberStore.getMemberName(id) || '未知'
}

function isOverdue(due) {
  if (!due) return false
  return dayjs(due).isBefore(dayjs())
}

function formatDue(due) {
  if (!due) return ''
  const d = dayjs(due)
  const diff = d.diff(dayjs(), 'day')
  if (diff < 0) return `${Math.abs(diff)} 天前到期`
  if (diff === 0) return '今天到期'
  if (diff === 1) return '明天到期'
  if (diff < 7) return `${diff} 天后到期`
  return d.format('MM-DD')
}

onMounted(() => {
  loadDashboard()
})
</script>

<style scoped>
.mobile-dashboard {
  min-height: 100vh;
  background: var(--color-bg-page);
}

.dashboard-main {
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* 欢迎卡片 */
.welcome-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 16px;
  background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-accent) 100%);
  border-radius: var(--radius-lg);
  color: white;
  margin-bottom: 16px;
  box-shadow: 0 4px 16px rgba(255, 122, 92, 0.2);
}
.welcome-content { flex: 1; }
.greeting {
  font-size: 18px;
  font-weight: var(--font-weight-semibold, 600);
  margin-bottom: 4px;
}
.date {
  font-size: 12px;
  opacity: 0.9;
}
.welcome-emoji {
  font-size: 48px;
  opacity: 0.85;
}

/* 快捷入口 */
.quick-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  margin-bottom: 16px;
  padding: 12px;
  background: var(--color-bg-card);
  border-radius: var(--radius-lg);
}
.quick-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: none;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  padding: 4px;
}
.quick-item:active { opacity: 0.6; }
.quick-icon {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}
.quick-label {
  font-size: 11px;
  color: var(--color-text-primary);
}

/* 数据统计 */
.section-title {
  font-size: 14px;
  font-weight: var(--font-weight-semibold, 600);
  color: var(--color-text-primary);
  margin: 0 0 10px;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.section-header .section-title { margin-bottom: 0; }
.view-all-btn {
  background: transparent;
  border: none;
  font-size: 13px;
  color: var(--color-primary);
  cursor: pointer;
  padding: 4px 8px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 16px;
}
.stat-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 14px 8px;
  text-align: center;
  border: none;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.stat-card:active { opacity: 0.7; }
.stat-card.highlight {
  background: var(--color-danger-bg);
  animation: pulse-bg 1.5s ease infinite;
}
@keyframes pulse-bg {
  0%, 100% { background: var(--color-bg-card); }
  50% { background: var(--color-danger-bg); }
}
.stat-num {
  font-size: 24px;
  font-weight: var(--font-weight-bold, 700);
  font-variant-numeric: tabular-nums;
  color: var(--color-text-primary);
  margin-bottom: 2px;
}
.stat-warning .stat-num { color: var(--color-primary); }
.stat-success .stat-num { color: var(--color-success, #67C23A); }
.stat-danger .stat-num { color: var(--color-danger, #F56C6C); }
.stat-label {
  font-size: 11px;
  color: var(--color-text-secondary);
}

/* 待办任务 */
.recent-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.task-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px;
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  border: none;
  text-align: left;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.task-item:active { background: var(--color-bg-hover); }
.task-priority {
  width: 4px;
  height: 32px;
  border-radius: 2px;
  background: var(--color-primary);
  flex-shrink: 0;
}
.task-priority.priority-high { background: var(--color-danger, #F56C6C); }
.task-priority.priority-medium { background: var(--color-warning, #E6A23C); }
.task-priority.priority-low { background: var(--color-success, #67C23A); }
.task-info {
  flex: 1;
  min-width: 0;
}
.task-title {
  font-size: 14px;
  font-weight: var(--font-weight-medium, 500);
  color: var(--color-text-primary);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--color-text-secondary);
}
.task-due.overdue {
  color: var(--color-danger, #F56C6C);
  font-weight: var(--font-weight-medium, 500);
}
.task-arrow {
  font-size: 20px;
  color: var(--color-text-placeholder);
}

/* 空态 */
.empty-section {
  text-align: center;
  padding: 40px 20px;
}
.empty-icon {
  font-size: 48px;
  margin-bottom: 8px;
}
.empty-title {
  font-size: 14px;
  color: var(--color-text-regular);
}

/* 加载 */
.loading-section {
  margin-bottom: 16px;
}
.skeleton-card {
  background: var(--color-bg-card);
  border-radius: var(--radius-md);
  padding: 16px;
  margin-bottom: 8px;
}
.skeleton-line {
  height: 12px;
  background: var(--color-border);
  border-radius: var(--radius-sm);
  margin-bottom: 8px;
  position: relative;
  overflow: hidden;
}
.skeleton-line::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, var(--color-bg-warm), transparent);
  animation: shimmer 1.5s infinite;
}
.skeleton-line.w-60 { width: 60%; }
.skeleton-line.w-90 { width: 90%; }
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
</style>
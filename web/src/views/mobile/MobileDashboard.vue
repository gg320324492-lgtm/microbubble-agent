<template>
  <div class="mobile-dashboard mg-page">
    <PageHeader title="首页" />

    <main
      class="dashboard-main"
      :style="{ paddingBottom: 'calc(var(--tabbar-height, 56px) + var(--sab, 0px))' }"
    >
      <!-- 欢迎卡片 -->
      <section class="welcome-card mg-rise">
        <div class="welcome-content">
          <div class="greeting">{{ greeting }}，{{ username }}！</div>
          <div class="date">{{ currentDate }}</div>
        </div>
        <div class="welcome-emoji">🫧</div>
      </section>

      <!-- 快捷入口 -->
      <section class="quick-grid mg-rise mg-stagger-1">
        <button
          v-for="action in quickActions"
          :key="action.path"
          type="button"
          class="quick-item"
          @click="$router.push(action.path)"
        >
          <div class="quick-icon" :class="action.colorClass">
            {{ action.icon }}
          </div>
          <div class="quick-label">{{ action.label }}</div>
        </button>
      </section>

      <!-- 数据统计 -->
      <section v-if="!loading && summary" class="stats-section mg-rise mg-stagger-2">
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
      <section v-if="recentTasks.length > 0" class="recent-section mg-rise mg-stagger-3">
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

      <section v-else class="empty-section mg-rise">
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
 * 2026-08-31 液态毛玻璃升级 (风格 D):
 * - 页面根 .mg-page 极光背景
 * - 渐变紫 hero 欢迎卡 + 玻璃快捷盘 + 玻璃统计/任务行
 * - 数据获取/路由逻辑零改动
 *
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
// v77 P2.6-E.1: bg → colorClass（_runtime-style-tokens.scss .quick-icon--*）
const quickActions = [
  { icon: '💬', label: '智能对话', path: '/chat', colorClass: 'quick-icon--chat' },
  { icon: '✅', label: '我的任务', path: '/tasks', colorClass: 'quick-icon--task' },
  { icon: '🎤', label: '会议', path: '/meetings', colorClass: 'quick-icon--meeting' },
  { icon: '📚', label: '知识库', path: '/knowledge', colorClass: 'quick-icon--knowledge' },
  { icon: '👤', label: '我的', path: '/settings', colorClass: 'quick-icon--me' },
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
}

.dashboard-main {
  padding: var(--mobile-padding-y, 12px) var(--mobile-padding-x, 16px);
}

/* 欢迎卡 — 品牌渐变 hero */
.welcome-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 18px;
  background: var(--mg-gradient-btn);
  border-radius: var(--mg-radius-lg);
  color: var(--mg-on-primary);
  margin-bottom: 14px;
  box-shadow: var(--mg-primary-shadow);
}
.welcome-content { flex: 1; }
.greeting {
  font-size: 18px;
  font-weight: 800;
  margin-bottom: 4px;
}
.date {
  font-size: 12px;
  opacity: 0.9;
}
.welcome-emoji {
  font-size: 46px;
  opacity: 0.9;
}

/* 快捷入口 — 玻璃盘 */
.quick-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 6px;
  margin-bottom: 14px;
  padding: 12px 8px;
  background: var(--mg-glass-bg);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(var(--mg-glass-blur));
  backdrop-filter: blur(var(--mg-glass-blur));
  border-radius: var(--mg-radius-lg);
  box-shadow: var(--mg-shadow);
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
  padding: 8px 4px;
  min-height: var(--touch-target-min, 44px);
}
.quick-item:active { transform: scale(0.94); }
.quick-icon {
  width: 46px;
  height: 46px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  background: var(--mg-glass-bg-strong);
  border: 1px solid var(--mg-glass-border);
  box-shadow: var(--mg-shadow-sm);
}
.quick-label {
  font-size: 11px;
  color: var(--mg-text);
  font-weight: 600;
}

/* 统计 */
.section-title {
  font-size: 15px;
  font-weight: 800;
  color: var(--mg-text-strong);
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
  color: var(--mg-primary);
  font-weight: 600;
  cursor: pointer;
  padding: 4px 8px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 16px;
}
.stat-card {
  background: var(--mg-glass-bg);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(var(--mg-glass-blur));
  backdrop-filter: blur(var(--mg-glass-blur));
  border-radius: var(--mg-radius-md);
  padding: 15px 8px;
  text-align: center;
  cursor: pointer;
  box-shadow: var(--mg-shadow-sm);
  -webkit-tap-highlight-color: transparent;
  transition: transform 150ms ease;
}
.stat-card:active { transform: scale(0.97); }

/* v77 P2: PAINT-free pulse-bg - 用 opacity overlay 替代 background: 切换
   background 切换触发 paint (整个元素背景重绘), opacity 仅 composite.
   高亮态用 ::after 叠加危险色背景, opacity 0↔1 脉冲. */
.stat-card.highlight {
  position: relative;
}
.stat-card.highlight::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: var(--mg-radius-md);
  background: var(--mg-danger-soft);
  opacity: 0;
  animation: pulse-bg-opacity 1.5s ease infinite;
  pointer-events: none;
}
@keyframes pulse-bg-opacity {
  0%, 100% { opacity: 0; }
  50% { opacity: 1; }
}
.stat-num {
  font-size: 26px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  color: var(--mg-text-strong);
  margin-bottom: 2px;
}
.stat-warning .stat-num { color: var(--mg-primary); }
.stat-success .stat-num { color: var(--mg-success); }
.stat-danger .stat-num { color: var(--mg-danger); }
.stat-label {
  font-size: 11px;
  color: var(--mg-text-soft);
}

/* 待办任务 — 玻璃行 */
.recent-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.task-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 13px 14px;
  background: var(--mg-glass-bg);
  border: 1.5px solid var(--mg-glass-border);
  -webkit-backdrop-filter: blur(var(--mg-glass-blur));
  backdrop-filter: blur(var(--mg-glass-blur));
  border-radius: var(--mg-radius-md);
  text-align: left;
  cursor: pointer;
  box-shadow: var(--mg-shadow-sm);
  -webkit-tap-highlight-color: transparent;
  transition: transform 150ms ease;
  min-height: var(--touch-target-min, 44px);
}
.task-item:active { transform: scale(0.98); }
.task-priority {
  width: 4px;
  height: 32px;
  border-radius: 2px;
  background: var(--mg-primary);
  flex-shrink: 0;
}
.task-priority.priority-high { background: var(--mg-danger); }
.task-priority.priority-medium { background: var(--mg-warning); }
.task-priority.priority-low { background: var(--mg-success); }
.task-info {
  flex: 1;
  min-width: 0;
}
.task-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--mg-text);
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
  color: var(--mg-text-soft);
}
.task-due.overdue {
  color: var(--mg-danger);
  font-weight: 600;
}
.task-arrow {
  font-size: 20px;
  color: var(--mg-text-faint);
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
  color: var(--mg-text-soft);
}

/* 加载骨架 */
.loading-section {
  margin-bottom: 16px;
}
.skeleton-card {
  background: var(--mg-glass-bg);
  border: 1.5px solid var(--mg-glass-border);
  border-radius: var(--mg-radius-md);
  padding: 16px;
  margin-bottom: 10px;
}
.skeleton-line {
  height: 12px;
  background: var(--mg-track);
  border-radius: var(--mg-radius-pill);
  margin-bottom: 8px;
  position: relative;
  overflow: hidden;
}
.skeleton-line::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.5), transparent);
  animation: shimmer 1.5s infinite;
}
.skeleton-line.w-60 { width: 60%; }
.skeleton-line.w-90 { width: 90%; }
@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
</style>

<!-- dark 跨组件规则保留非 scoped (v60-v67 教训)。
     mg-* token 自带 dark 变体, 这里仅保留: welcome 渐变压暗 +
     全局同名 class (quick-action 被 MobileChatView/MobileMessageList 复用) 兜底 -->
<style>
[data-theme="dark"] .welcome-card {
  /* 渐变 hero 在 dark 压暗一档避免过曝 */
  filter: brightness(0.88) saturate(0.95);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}
[data-theme="dark"] .skeleton-line {
  background: var(--color-border-light);
}
[data-theme="dark"] .skeleton-line::after {
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.06), transparent);
}
[data-theme="dark"] .stat-warning .stat-num { color: var(--color-primary); }
[data-theme="dark"] .stat-success .stat-num { color: var(--color-success); }
[data-theme="dark"] .stat-danger .stat-num { color: var(--color-danger); }
/* 同名 class 全局兜底: 快捷动作 (MobileChatView 等复用 quick-action 命名) */
[data-theme="dark"] .quick-action {
  background: var(--color-bg-card);
  color: var(--color-text-primary);
  border-color: var(--color-border);
}
[data-theme="dark"] .quick-action:active {
  background: var(--color-bg-hover);
}
[data-theme="dark"] .quick-action .action-name {
  color: var(--color-text-primary);
}
[data-theme="dark"] .empty-state,
[data-theme="dark"] .loading-state {
  color: var(--color-text-secondary);
}
[data-theme="dark"] .empty-title {
  color: var(--color-text-primary);
}
</style>

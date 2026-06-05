<template>
  <div class="dashboard">
    <!-- 欢迎区域 -->
    <section class="welcome fade-in">
      <h1>{{ greeting }}，{{ username }}！</h1>
      <p class="subtitle">{{ currentDate }} · 团队共有 {{ stats.in_progress }} 项任务进行中</p>
      <div class="actions">
        <button class="btn btn-primary" @click="$router.push('/chat')">💬 开始对话</button>
        <button class="btn btn-secondary" @click="showCreateTask = true">➕ 创建任务</button>
      </div>
    </section>

    <!-- 统计卡片 -->
    <section class="stats-grid">
      <div class="stat-card fade-in stagger-1">
        <div class="stat-header">
          <div class="stat-icon primary">📋</div>
          <span class="stat-change positive">↑ 12%</span>
        </div>
        <div class="stat-value">{{ stats.in_progress }}</div>
        <div class="stat-label">进行中任务</div>
      </div>
      <div class="stat-card fade-in stagger-2">
        <div class="stat-header">
          <div class="stat-icon success">✅</div>
          <span class="stat-change positive">↑ 8%</span>
        </div>
        <div class="stat-value">{{ stats.done }}</div>
        <div class="stat-label">已完成任务</div>
      </div>
      <div class="stat-card fade-in stagger-3">
        <div class="stat-header">
          <div class="stat-icon warning">📅</div>
          <span class="stat-change negative">↓ 3%</span>
        </div>
        <div class="stat-value">{{ meetingStats.today }}</div>
        <div class="stat-label">今日会议</div>
      </div>
      <div class="stat-card fade-in stagger-4">
        <div class="stat-header">
          <div class="stat-icon danger">⚠️</div>
          <span class="stat-change negative">+2</span>
        </div>
        <div class="stat-value">{{ stats.overdue }}</div>
        <div class="stat-label">逾期任务</div>
      </div>
    </section>

    <!-- 快速操作 -->
    <section class="quick-actions">
      <div class="quick-action fade-in stagger-1" @click="$router.push('/tasks')">
        <div class="icon">📝</div>
        <h4>新建任务</h4>
        <p>创建新的工作任务</p>
      </div>
      <div class="quick-action fade-in stagger-2" @click="$router.push('/meetings')">
        <div class="icon">📅</div>
        <h4>安排会议</h4>
        <p>创建或加入会议</p>
      </div>
      <div class="quick-action fade-in stagger-3" @click="$router.push('/knowledge')">
        <div class="icon">📚</div>
        <h4>知识库</h4>
        <p>查阅文档资料</p>
      </div>
      <div class="quick-action fade-in stagger-4" @click="$router.push('/chat')">
        <div class="icon">🤖</div>
        <h4>AI 助手</h4>
        <p>与 AI 对话</p>
      </div>
    </section>

    <!-- 进行中任务 -->
    <section class="card fade-in">
      <div class="card-header">
        <div class="card-title">
          <span class="icon">🚀</span>
          进行中任务
        </div>
        <div class="card-actions">
          <span class="task-count">共 {{ inProgressTasks.length }} 项</span>
          <button class="btn btn-ghost btn-small" @click="$router.push('/tasks')">查看全部 →</button>
        </div>
      </div>
      <div class="card-body">
        <div v-if="loading" class="loading">
          <div v-for="i in 3" :key="i" class="task-item skeleton">
            <div class="skeleton-circle"></div>
            <div class="skeleton-content">
              <div class="skeleton-text" style="width: 60%"></div>
              <div class="skeleton-text" style="width: 40%"></div>
            </div>
          </div>
        </div>
        <div v-else-if="inProgressTasks.length === 0" class="empty-state">
          <div class="icon">🎉</div>
          <p>暂无进行中任务</p>
        </div>
        <div v-else>
          <div
            v-for="task in inProgressTasks.slice(0, 5)"
            :key="task.id"
            class="task-item"
          >
            <div class="task-checkbox" @click="completeTask(task)"></div>
            <div class="task-content">
              <div class="task-title">{{ task.title }}</div>
              <div class="task-meta">
                <span class="task-tag" :style="{ background: getPriorityBgColor(task.priority), color: getPriorityColor(task.priority) }">
                  {{ getPriorityLabel(task.priority) }}
                </span>
                <span class="task-assignee">
                  <span class="assignee-avatar">{{ getAssigneeInitial(task.assignee_id) }}</span>
                  {{ getAssigneeName(task.assignee_id) }}
                </span>
              </div>
            </div>
            <div class="task-due" :class="getDueDateClass(task.due_date)">
              {{ getDueDateDisplay(task.due_date) }}
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 最近会议 -->
    <section class="card fade-in">
      <div class="card-header">
        <div class="card-title">
          <span class="icon">📅</span>
          最近会议
        </div>
        <div class="card-actions">
          <button class="btn btn-ghost btn-small" @click="$router.push('/meetings')">查看全部 →</button>
        </div>
      </div>
      <div class="card-body">
        <div v-if="todayMeetings.length === 0" class="empty-state">
          <div class="icon">📅</div>
          <p>今日暂无会议</p>
        </div>
        <div v-else>
          <div
            v-for="meeting in todayMeetings.slice(0, 3)"
            :key="meeting.id"
            class="meeting-item"
          >
            <div class="meeting-time">
              <div class="time">{{ formatMeetingTime(meeting.start_time) }}</div>
            </div>
            <div class="meeting-content">
              <div class="meeting-title">{{ meeting.title }}</div>
              <div class="meeting-meta">
                <span class="meeting-tag" :style="{ color: getMeetingStatusColor(meeting) }">
                  {{ getMeetingStatus(meeting) }}
                </span>
                <span class="meeting-location">📍 {{ meeting.location || '线上会议' }}</span>
              </div>
            </div>
            <div class="meeting-participants">
              <div class="participant-avatars">
                <span
                  v-for="p in (meeting.participants || []).slice(0, 3)"
                  :key="p"
                  class="participant-avatar"
                >
                  {{ getParticipantInitial(p) }}
                </span>
              </div>
              <span v-if="(meeting.participants || []).length > 3" class="participant-count">
                +{{ meeting.participants.length - 3 }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { useTask } from '@/composables/useTask'
import { useMeeting } from '@/composables/useMeeting'
import {
  getPriorityLabel,
  getPriorityColor,
  getPriorityBgColor,
  getDueDateDisplay,
  getDueDateClass
} from '@/utils/task'

const userStore = useUserStore()
const { tasks, loading, stats, inProgressTasks, fetchTasks, completeTask, getAssigneeName, getAssigneeInitial } = useTask()
const { todayMeetings, stats: meetingStats, fetchMeetings, getParticipantInitial, formatMeetingTime, getMeetingStatus, getMeetingStatusColor } = useMeeting()

const showCreateTask = ref(false)

const username = computed(() => userStore.username || '用户')

const greeting = computed(() => {
  const hour = new Date().getHours()
  if (hour < 6) return '凌晨好'
  if (hour < 9) return '早上好'
  if (hour < 12) return '上午好'
  if (hour < 14) return '中午好'
  if (hour < 17) return '下午好'
  if (hour < 19) return '傍晚好'
  return '晚上好'
})

const currentDate = computed(() => {
  const now = new Date()
  const weekdays = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六']
  return `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日 ${weekdays[now.getDay()]}`
})

onMounted(() => {
  fetchTasks()
  fetchMeetings()
})
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 欢迎区域 */
.welcome {
  background: white;
  border-radius: var(--radius-lg);
  padding: 40px;
  border: 1px solid var(--color-border);
}

.welcome h1 {
  font-size: 32px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.welcome .subtitle {
  font-size: 16px;
  color: var(--color-text-secondary);
  margin-bottom: 24px;
}

.welcome .actions {
  display: flex;
  gap: 12px;
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
  padding: 24px;
  border: 1px solid var(--color-border);
  transition: all var(--duration-normal) var(--ease-out);
}

.stat-card:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-2px);
}

.stat-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.stat-icon.primary { background: var(--color-bg-active); }
.stat-icon.success { background: var(--color-success-bg); }
.stat-icon.warning { background: var(--color-warning-bg); }
.stat-icon.danger { background: var(--color-danger-bg); }

.stat-change {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: var(--radius-full);
  font-weight: 500;
}

.stat-change.positive {
  background: var(--color-success-bg);
  color: var(--color-success);
}

.stat-change.negative {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}

.stat-value {
  font-size: 36px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 4px;
  letter-spacing: -1px;
}

.stat-label {
  font-size: 13px;
  color: var(--color-text-tertiary);
}

/* 快速操作 */
.quick-actions {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.quick-action {
  background: white;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  padding: 24px;
  text-align: center;
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-out);
}

.quick-action:hover {
  border-color: var(--color-primary);
  transform: translateY(-4px);
  box-shadow: var(--shadow-sm);
}

.quick-action .icon {
  font-size: 32px;
  margin-bottom: 12px;
}

.quick-action h4 {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.quick-action p {
  font-size: 12px;
  color: var(--color-text-tertiary);
  margin-top: 4px;
}

/* 卡片 */
.card {
  background: white;
  border-radius: var(--radius-lg);
  border: 1px solid var(--color-border);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--color-border);
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.task-count {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.card-body {
  padding: 24px;
}

/* 任务列表 */
.task-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
  margin-bottom: 8px;
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

.task-content {
  flex: 1;
}

.task-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 4px;
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
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.assignee-avatar {
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: white;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.task-due {
  font-size: 13px;
  color: var(--color-text-tertiary);
  white-space: nowrap;
}

.task-due.overdue {
  color: var(--color-danger);
}

.task-due.today {
  color: var(--color-warning);
}

/* 会议列表 */
.meeting-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border-radius: var(--radius-md);
  transition: all var(--duration-fast) var(--ease-out);
  margin-bottom: 8px;
}

.meeting-item:hover {
  background: var(--color-bg-hover);
}

.meeting-time {
  width: 60px;
  text-align: center;
  flex-shrink: 0;
}

.meeting-time .time {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.meeting-content {
  flex: 1;
}

.meeting-title {
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-primary);
  margin-bottom: 4px;
}

.meeting-meta {
  display: flex;
  gap: 12px;
  align-items: center;
}

.meeting-tag {
  font-size: 12px;
  font-weight: 500;
}

.meeting-location {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.meeting-participants {
  display: flex;
  align-items: center;
  gap: 8px;
}

.participant-avatars {
  display: flex;
}

.participant-avatar {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  background: var(--color-primary);
  color: white;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: -8px;
  border: 2px solid white;
}

.participant-avatar:first-child {
  margin-left: 0;
}

.participant-count {
  font-size: 12px;
  color: var(--color-text-tertiary);
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
}

/* 加载状态 */
.loading {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skeleton-content {
  flex: 1;
}

/* 响应式 */
@media (max-width: 1024px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .quick-actions {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .quick-actions {
    grid-template-columns: 1fr;
  }

  .welcome {
    padding: 24px;
  }

  .welcome h1 {
    font-size: 24px;
  }
}
</style>

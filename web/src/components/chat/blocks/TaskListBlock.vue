<script setup>
/**
 * TaskListBlock.vue — 任务列表卡
 *
 * 接收 block.data = {tasks: [{id, title, status, priority, assignee_name, due_date, progress, project_name, tags}]}
 */
import { useRouter } from 'vue-router'
const props = defineProps({ block: { type: Object, required: true } })
const router = useRouter()

const tasks = (props.block.data || {}).tasks || []

const formatDate = (d) => {
  if (!d) return ''
  try { return new Date(d).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) }
  catch { return d }
}

const priorityColor = (p) => {
  // v77 P2.5.3: getComputedStyle 读 token 实色值
  const map = { high: '--color-danger', medium: '--color-warning', low: '--color-text-secondary' }
  const token = map[p] || '--color-text-secondary'
  return getComputedStyle(document.documentElement).getPropertyValue(token).trim()
}

const statusLabel = (s) => {
  return {
    in_progress: '进行中', todo: '待办', blocked: '阻塞',
    review: '待审核', done: '已完成', cancelled: '已取消'
  }[s] || s
}

const isOverdue = (d, s) => {
  if (!d || ['done', 'cancelled'].includes(s)) return false
  return new Date(d) < new Date()
}

const goToTask = (id) => { if (id) router.push(`/tasks?task_id=${id}`) }
</script>

<template>
  <div class="task-list rich-card">
    <div class="card-header">
      <span class="icon">📋</span>
      <span class="title">{{ block.title || '任务列表' }} ({{ tasks.length }})</span>
    </div>
    <div v-for="t in tasks" :key="t.id" class="task-item" @click="goToTask(t.id)">
      <div class="task-row1">
        <span class="priority-dot" :style="{ background: priorityColor(t.priority) }" />
        <span class="task-title">{{ t.title }}</span>
        <span class="status" :class="t.status">{{ statusLabel(t.status) }}</span>
      </div>
      <div class="task-row2">
        <span v-if="t.assignee_name" class="meta">👤 {{ t.assignee_name }}</span>
        <span v-if="t.due_date" class="meta" :class="{ overdue: isOverdue(t.due_date, t.status) }">
          📅 {{ formatDate(t.due_date) }}{{ isOverdue(t.due_date, t.status) ? ' (逾期)' : '' }}
        </span>
        <span v-if="t.project_name" class="meta">📊 {{ t.project_name }}</span>
      </div>
      <div v-if="t.progress != null" class="progress-bar">
        <div class="progress-fill" :style="{ width: t.progress + '%' }" />
      </div>
      <div v-if="t.tags && t.tags.length" class="tags">
        <span v-for="tag in t.tags" :key="tag" class="tag">{{ tag }}</span>
      </div>
    </div>
    <div v-if="!tasks.length" class="empty">暂无任务</div>
  </div>
</template>

<style scoped>
.rich-card { background: var(--color-bg-card); border: 1px solid var(--color-border-light); border-radius: 10px; padding: 12px 14px; margin: 8px 0; box-shadow: var(--shadow-xs); }
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 14px; margin-bottom: 10px; color: var(--color-primary); }
.icon { font-size: 18px; }
.task-item { padding: 10px 0; border-top: 1px solid var(--color-border-light); cursor: pointer; transition: background 0.15s; }
.task-item:first-of-type { border-top: none; }
.task-item:hover { background: var(--color-bg-warm); margin: 0 -8px; padding: 10px 8px; border-radius: 6px; }
.task-row1 { display: flex; align-items: center; gap: 8px; }
.priority-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.task-title { flex: 1; font-weight: 500; font-size: 14px; }
.status { font-size: 11px; padding: 1px 8px; border-radius: 10px; background: var(--color-bg-hover); color: var(--color-text-regular); }
.status.done { background: var(--color-success-bg); color: var(--color-success); }
.status.in_progress { background: var(--color-warning-bg); color: var(--color-warning); }
.status.blocked { background: var(--color-danger-bg); color: var(--color-danger); }
.task-row2 { display: flex; gap: 12px; font-size: 12px; color: var(--color-text-secondary); margin-top: 4px; flex-wrap: wrap; }
.meta.overdue { color: var(--color-danger); font-weight: 500; }
.progress-bar { height: 4px; background: var(--color-info-bg); border-radius: 2px; margin-top: 6px; overflow: hidden; }
.progress-fill { height: 100%; background: var(--gradient-welcome-hero); transition: width 0.3s; }
.tags { display: flex; gap: 4px; margin-top: 6px; flex-wrap: wrap; }
.tag { font-size: 11px; background: var(--color-bg-hover); color: var(--color-text-regular); padding: 1px 6px; border-radius: 8px; }
.empty { text-align: center; color: var(--color-text-secondary); padding: 20px 0; font-size: 13px; }

/* v77 P2.5.3: dark mode hover（light 下 .task-item:hover 已用 --color-bg-warm，dark 下 --color-bg-warm 与外层同色，改用 --color-bg-hover） */
[data-theme="dark"] .task-item:hover {
  background: var(--color-bg-hover);
}
</style>

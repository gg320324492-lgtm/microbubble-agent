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
  return { high: '#f56c6c', medium: '#e6a23c', low: '#909399' }[p] || '#909399'
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
.rich-card { background: white; border: 1px solid #e8eaed; border-radius: 10px; padding: 12px 14px; margin: 8px 0; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 14px; margin-bottom: 10px; color: #FF7A5C; }
.icon { font-size: 18px; }
.task-item { padding: 10px 0; border-top: 1px solid #f0f1f3; cursor: pointer; transition: background 0.15s; }
.task-item:first-of-type { border-top: none; }
.task-item:hover { background: #fafbfc; margin: 0 -8px; padding: 10px 8px; border-radius: 6px; }
.task-row1 { display: flex; align-items: center; gap: 8px; }
.priority-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.task-title { flex: 1; font-weight: 500; font-size: 14px; }
.status { font-size: 11px; padding: 1px 8px; border-radius: 10px; background: #f0f4f8; color: #666; }
.status.done { background: #e8f5e9; color: #2e7d32; }
.status.in_progress { background: #fff7e6; color: #d4880f; }
.status.blocked { background: #ffebee; color: #c62828; }
.task-row2 { display: flex; gap: 12px; font-size: 12px; color: #888; margin-top: 4px; flex-wrap: wrap; }
.meta.overdue { color: #f56c6c; font-weight: 500; }
.progress-bar { height: 4px; background: #f0f1f3; border-radius: 2px; margin-top: 6px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, #FF7A5C, #FFB347); transition: width 0.3s; }
.tags { display: flex; gap: 4px; margin-top: 6px; flex-wrap: wrap; }
.tag { font-size: 11px; background: #f0f4f8; color: #666; padding: 1px 6px; border-radius: 8px; }
.empty { text-align: center; color: #999; padding: 20px 0; font-size: 13px; }
</style>

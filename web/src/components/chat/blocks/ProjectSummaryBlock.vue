<script setup>
/**
 * ProjectSummaryBlock.vue — 项目摘要卡
 *
 * 接收 block.data = {projects: [...]} 或 {id, name, task_stats, milestones, recent_tasks}
 */
import { useRouter } from 'vue-router'
import { computed } from 'vue'

const props = defineProps({ block: { type: Object, required: true } })
const router = useRouter()

// 兼容单/列表
const projects = computed(() => {
  const d = props.block.data || {}
  if (Array.isArray(d.projects)) return d.projects
  if (d.id && d.name) return [d]
  return []
})

const formatDate = (d) => {
  if (!d) return ''
  try { return new Date(d).toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }) }
  catch { return d }
}

const goToTask = (id) => { if (id) router.push(`/tasks?task_id=${id}`) }

const taskStatusLabel = (s) => ({
  in_progress: '进行中', todo: '待办', blocked: '阻塞',
  review: '待审核', done: '已完成', cancelled: '已取消'
}[s] || s)
</script>

<template>
  <div class="project-summary rich-card">
    <div class="card-header">
      <span class="icon">📊</span>
      <span class="title">{{ block.title || '项目摘要' }} ({{ projects.length }})</span>
    </div>
    <div v-for="p in projects" :key="p.id || p.name" class="project-item">
      <div class="project-title">{{ p.name }}</div>
      <div v-if="p.description" class="project-desc">{{ p.description.slice(0, 150) }}{{ p.description.length > 150 ? '...' : '' }}</div>

      <!-- 任务统计 -->
      <div v-if="p.task_stats" class="task-stats">
        <div class="stat-line">
          <span class="stat-label">总任务：</span>
          <span class="stat-value">{{ p.task_stats.total || 0 }}</span>
          <span v-if="p.task_stats.in_progress" class="stat-pill in-progress">进行中 {{ p.task_stats.in_progress }}</span>
          <span v-if="p.task_stats.done" class="stat-pill done">已完成 {{ p.task_stats.done }}</span>
          <span v-if="p.task_stats.overdue" class="stat-pill overdue">逾期 {{ p.task_stats.overdue }}</span>
        </div>
        <!-- 进度条 -->
        <div v-if="p.task_stats.total" class="progress-bar">
          <div class="progress-done" :style="{ width: ((p.task_stats.done || 0) / p.task_stats.total * 100) + '%' }" />
          <div class="progress-active" :style="{ width: ((p.task_stats.in_progress || 0) / p.task_stats.total * 100) + '%', left: ((p.task_stats.done || 0) / p.task_stats.total * 100) + '%' }" />
        </div>
      </div>

      <!-- 里程碑 -->
      <div v-if="p.milestones && p.milestones.length" class="milestones">
        <div class="section-label">📅 里程碑</div>
        <div v-for="m in p.milestones" :key="m.id" class="milestone-item">
          <span class="ms-name">{{ m.name }}</span>
          <span v-if="m.due_date" class="ms-date">{{ formatDate(m.due_date) }}</span>
          <span v-if="m.status" class="ms-status" :class="m.status">{{ m.status }}</span>
        </div>
      </div>

      <!-- 最近任务 -->
      <div v-if="p.recent_tasks && p.recent_tasks.length" class="recent-tasks">
        <div class="section-label">📋 最近任务</div>
        <div v-for="t in p.recent_tasks" :key="t.id" class="recent-task" @click="goToTask(t.id)">
          <span class="task-title">{{ t.title }}</span>
          <span v-if="t.assignee_name" class="task-assignee">{{ t.assignee_name }}</span>
          <span class="task-status">{{ taskStatusLabel(t.status) }}</span>
        </div>
      </div>
    </div>
    <div v-if="!projects.length" class="empty">暂无项目</div>
  </div>
</template>

<style scoped>
.rich-card { background: var(--color-bg-card); border: 1px solid var(--color-border-light); border-radius: 10px; padding: 12px 14px; margin: 8px 0; box-shadow: var(--shadow-xs); }
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 14px; margin-bottom: 10px; color: var(--color-primary); }
.icon { font-size: 18px; }
.project-item { padding: 10px 0; border-top: 1px solid var(--color-border-light); }
.project-item:first-of-type { border-top: none; }
.project-title { font-weight: 600; font-size: 15px; color: var(--color-primary); }
.project-desc { font-size: 12px; color: var(--color-text-regular); margin-top: 4px; line-height: 1.5; }
.task-stats { margin-top: 8px; }
.stat-line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; }
.stat-label { color: var(--color-text-secondary); }
.stat-value { font-weight: 600; color: var(--color-text-primary); }
.stat-pill { font-size: 11px; padding: 1px 8px; border-radius: 10px; }
.stat-pill.in-progress { background: var(--color-warning-bg); color: var(--color-warning); }
.stat-pill.done { background: var(--color-success-bg); color: var(--color-success); }
.stat-pill.overdue { background: var(--color-danger-bg); color: var(--color-danger); }
.progress-bar { position: relative; height: 6px; background: var(--color-info-bg); border-radius: 3px; margin-top: 6px; overflow: hidden; }
.progress-done { position: absolute; left: 0; top: 0; height: 100%; background: var(--color-success); }
.progress-active { position: absolute; top: 0; height: 100%; background: var(--color-accent); }
.section-label { font-size: 12px; font-weight: 500; color: var(--color-text-regular); margin-top: 8px; margin-bottom: 4px; }
.milestone-item { display: flex; gap: 8px; padding: 3px 0; font-size: 12px; align-items: center; }
.ms-name { flex: 1; color: var(--color-text-primary); }
.ms-date { color: var(--color-text-secondary); }
.ms-status { font-size: 11px; padding: 1px 6px; border-radius: 8px; background: var(--color-bg-hover); color: var(--color-text-regular); }
.recent-task { display: flex; gap: 8px; padding: 4px 6px; font-size: 12px; border-radius: 4px; cursor: pointer; align-items: center; }
.recent-task:hover { background: var(--color-bg-warm); }
.task-title { flex: 1; color: var(--color-text-primary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-assignee { color: var(--color-text-secondary); font-size: 11px; }
.task-status { font-size: 11px; color: var(--color-text-secondary); }
.empty { text-align: center; color: var(--color-text-secondary); padding: 20px 0; font-size: 13px; }

/* v77 P2.5.3: dark mode hover（recent-task 用 --color-bg-warm，dark 下与外层同色，改 --color-bg-hover） */
[data-theme="dark"] .recent-task:hover {
  background: var(--color-bg-hover);
}
</style>

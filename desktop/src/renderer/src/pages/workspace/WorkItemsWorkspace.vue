<template>
  <div class="work-items-workspace" data-testid="work-items-workspace">
    <header class="work-items-workspace__header">
      <h1>工作项工作区</h1>
      <p class="work-items-workspace__hint">
        本地副本（历史归档）。修改仅保存在桌面端，不会回传到网页。
      </p>
    </header>

    <p v-if="error" class="work-items-workspace__error">{{ error }}</p>

    <ul v-if="tasks.length" data-testid="work-items-list">
      <li v-for="t in tasks" :key="t.id" class="work-items-workspace__row">
        <span class="work-items-workspace__title">{{ t.title }}</span>
        <span v-if="t.assignee_username" class="work-items-workspace__assignee">{{ t.assignee_username }}</span>
        <span class="work-items-workspace__priority" :data-priority="t.priority">{{ t.priority }}</span>
        <button
          data-testid="task-status"
          :data-status="t.status"
          :data-task-id="t.id"
          @click="toggleStatus(t)"
        >
          {{ statusLabel(t.status) }}
        </button>
      </li>
    </ul>
    <p v-else-if="!error" class="work-items-workspace__empty" data-testid="empty">
      Empty — 暂无任务（请先在迁移中心导入一个 .mbrp 包）。
    </p>
  </div>
</template>

<script setup lang="ts">
// [类 20.203] 2026-08-28: WorkItemsWorkspace 真实数据接入.
//   之前用 window.workspace.listTasks() (不存在, 永远空数组 → "暂无任务").
//   改为: 直接读 desktop_tasks 表 (95 行真实任务), 通过 window.api.database.query (preload 已暴露).
import { onMounted, ref } from 'vue'

interface Task {
  id: number
  title: string
  status: string
  priority: string
  assignee_username: string | null
  due_date_epoch: number | null
}

const STATUS_LABELS: Record<string, string> = {
  todo: '待办',
  in_progress: '进行中',
  blocked: '阻塞',
  review: '评审',
  done: '已完成',
  cancelled: '已取消'
}

function statusLabel(s: string): string {
  return STATUS_LABELS[s] ?? s
}

const tasks = ref<Task[]>([])
const error = ref<string>('')

async function loadTasks(): Promise<void> {
  error.value = ''
  const api = (globalThis as unknown as { window?: { api?: { database?: { query: <T>(p: { sql: string; params?: unknown[] }) => Promise<{ rows: T[] }> } } } }).window?.api
  if (!api?.database) {
    error.value = '数据库 API 不可用'
    return
  }
  try {
    const { rows } = await api.database.query<Task>({
      sql: `SELECT id, title, status, priority, assignee_username, due_date_epoch
            FROM desktop_tasks
            ORDER BY (due_date_epoch IS NULL), due_date_epoch ASC
            LIMIT 200`
    })
    tasks.value = rows
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function toggleStatus(t: Task): Promise<void> {
  const next = t.status === 'in_progress' ? 'done' : 'in_progress'
  const api = (globalThis as unknown as { window?: { api?: { database?: { update: (p: { sql: string; params?: unknown[] }) => Promise<{ changes: number }> } } } }).window?.api
  if (!api?.database) return
  try {
    await api.database.update({
      sql: 'UPDATE desktop_tasks SET status = ? WHERE id = ?',
      params: [next, t.id]
    })
    t.status = next
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

onMounted(loadTasks)

defineExpose({ tasks, error, loadTasks, toggleStatus })
</script>

<style scoped>
.work-items-workspace { padding: 1.5rem; max-width: 880px; }
.work-items-workspace__header h1 { margin: 0 0 0.5rem; font-size: 1.5rem; }
.work-items-workspace__hint { color: #555; font-size: 0.9rem; }
.work-items-workspace__error { color: #dc2626; padding: 0.5rem 0; }
.work-items-workspace__assignee { color: #6b7280; font-size: 0.85rem; }
.work-items-workspace__priority { font-size: 0.75rem; padding: 0.1rem 0.4rem; border-radius: 3px; background: #f3f4f6; }
.work-items-workspace__priority[data-priority="high"] { background: #fee2e2; color: #991b1b; }
.work-items-workspace__priority[data-priority="medium"] { background: #fef3c7; color: #92400e; }
.work-items-workspace__priority[data-priority="low"] { background: #dcfce7; color: #166534; }
ul { list-style: none; padding: 0; margin: 1rem 0 0; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; }
.work-items-workspace__row { display: flex; align-items: center; justify-content: space-between; padding: 0.6rem 0.9rem; border-bottom: 1px solid #e5e7eb; gap: 0.5rem; }
.work-items-workspace__row:last-child { border-bottom: 0; }
.work-items-workspace__title { font-weight: 500; flex: 1; }

<style scoped>
.work-items-workspace { padding: 1.5rem; max-width: 880px; }
.work-items-workspace__header h1 { margin: 0 0 0.5rem; font-size: 1.5rem; }
.work-items-workspace__hint { color: #555; font-size: 0.9rem; }
ul { list-style: none; padding: 0; margin: 1rem 0 0; border: 1px solid #e5e7eb; border-radius: 8px; background: #fff; }
.work-items-workspace__row { display: flex; align-items: center; justify-content: space-between; padding: 0.6rem 0.9rem; border-bottom: 1px solid #e5e7eb; }
.work-items-workspace__row:last-child { border-bottom: 0; }
.work-items-workspace__title { font-weight: 500; }
button[data-testid="task-status"] { padding: 0.3rem 0.9rem; border: 0; border-radius: 999px; color: white; font-size: 0.8rem; cursor: pointer; }
button[data-testid="task-status"][data-status="done"] { background: #16a34a; }
button[data-testid="task-status"][data-status="in_progress"] { background: #f59e0b; }
.work-items-workspace__empty { padding: 1rem; color: #6b7280; }
</style>

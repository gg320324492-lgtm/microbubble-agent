<template>
  <div class="work-items-workspace" data-testid="work-items-workspace">
    <header class="work-items-workspace__header">
      <h1>工作项工作区</h1>
      <p class="work-items-workspace__hint">
        本地副本（历史归档）。修改仅保存在桌面端，不会回传到网页。
      </p>
    </header>

    <ul v-if="tasks.length" data-testid="work-items-list">
      <li v-for="t in tasks" :key="t.id" class="work-items-workspace__row">
        <span class="work-items-workspace__title">{{ t.title }}</span>
        <button
          data-testid="task-status"
          :data-status="t.status"
          :data-task-id="t.id"
          @click="toggleStatus(t)"
        >
          {{ t.status }}
        </button>
      </li>
    </ul>
    <p v-else class="work-items-workspace__empty" data-testid="empty">
      Empty — 暂无任务（请先在迁移中心导入一个 .mbrp 包）。
    </p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

interface Task {
  id: string
  title: string
  status: string
}

interface WindowWorkspace {
  listTasks?: () => Promise<Task[]>
  updateTaskStatus?: (taskId: string, status: string) => Promise<{ ok: boolean }>
}

const tasks = ref<Task[]>([])
const error = ref<string>('')

async function loadTasks(): Promise<void> {
  error.value = ''
  const w = (globalThis as unknown as { window?: { workspace?: WindowWorkspace } }).window
  if (!w?.workspace?.listTasks) {
    error.value = '工作区桥接未注入'
    return
  }
  try {
    tasks.value = await w.workspace.listTasks()
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  }
}

async function toggleStatus(t: Task): Promise<void> {
  const next = t.status === 'in_progress' ? 'done' : 'in_progress'
  t.status = next
  const w = (globalThis as unknown as { window?: { workspace?: WindowWorkspace } }).window
  if (!w?.workspace?.updateTaskStatus) return
  await w.workspace.updateTaskStatus(t.id, next)
}

onMounted(loadTasks)

defineExpose({ tasks, error, loadTasks, toggleStatus })
</script>

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

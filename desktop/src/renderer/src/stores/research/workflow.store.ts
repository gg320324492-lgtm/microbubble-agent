// Workflow Store — 全局科研工作流状态管理。
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type TaskStatus = 'idle' | 'pending' | 'running' | 'completed' | 'failed'

export interface WorkflowTask {
  id: string
  type: 'literature' | 'experiment' | 'analysis' | 'manuscript' | 'design'
  label: string
  status: TaskStatus
  startedAt?: number
  completedAt?: number
  result?: string
  error?: string
}

export interface WorkflowEvent {
  id: string
  taskId: string
  type: 'step_start' | 'step_complete' | 'step_fail' | 'info'
  label: string
  detail: string
  timestamp: number
}

export const useWorkflowStore = defineStore('research-workflow', () => {
  const tasks = ref<WorkflowTask[]>([])
  const events = ref<WorkflowEvent[]>([])
  const currentTaskId = ref<string | null>(null)
  const errors = ref<string[]>([])

  const activeTask = computed(() => tasks.value.find(t => t.id === currentTaskId.value))
  const runningTasks = computed(() => tasks.value.filter(t => t.status === 'running'))
  const completedTasks = computed(() => tasks.value.filter(t => t.status === 'completed'))
  const recentEvents = computed(() => [...events.value].sort((a, b) => b.timestamp - a.timestamp).slice(0, 20))

  function addTask(task: WorkflowTask) {
    tasks.value = [...tasks.value, task]
  }

  function updateTaskStatus(id: string, status: TaskStatus, result?: string, error?: string) {
    tasks.value = tasks.value.map(t =>
      t.id === id ? { ...t, status, ...(result ? { result } : {}), ...(error ? { error } : {}), ...(status === 'completed' ? { completedAt: Date.now() } : {}), ...(status === 'running' && !t.startedAt ? { startedAt: Date.now() } : {}) } : t
    )
  }

  function addEvent(event: WorkflowEvent) {
    events.value = [...events.value, event]
  }

  function addError(msg: string) {
    errors.value = [...errors.value, msg]
  }

  function clearErrors() { errors.value = [] }

  function reset() {
    tasks.value = []
    events.value = []
    currentTaskId.value = null
    errors.value = []
  }

  return {
    tasks, events, currentTaskId, errors,
    activeTask, runningTasks, completedTasks, recentEvents,
    addTask, updateTaskStatus, addEvent, addError, clearErrors, reset
  }
})

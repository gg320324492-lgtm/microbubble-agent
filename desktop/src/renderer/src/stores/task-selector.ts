// task-selector Pinia store (Phase 6-C3: Task-aware Chat Header UI).
//
// Phase 6-C3: chat-side state for the task-aware header. Phase 6-C2
// capability-router is the picker (main process); this store mirrors
// the user's UI selection (mode + taskType) and the latest routing
// decision so the chat header can show it.
//
// Phase 6-C3 frozen contract:
//   - mode: 'manual' | 'auto'      (manual = Phase 6-B ModelSelector only)
//   - taskType: ResearchTaskType | null
//   - lastDecision: ModelRouteTaskResult | null
//   - selectTask(taskType)         -> updates taskType
//   - setMode(mode)                -> 'manual' | 'auto'
//   - routeNow()                   -> calls window.api.model.routeTask
//   - reset()                      -> clears state
//
// Phase 6-C3 strict:
//   - Never holds apiKey (lastDecision has no key field)
//   - All capability routing happens in main process
//   - Manual mode is unchanged (Phase 6-B ModelSelector still controls)

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ResearchTaskType } from '@shared/model/research-task'
import { researchTaskLabel } from '@shared/model/research-task'
import type { ModelRouteTaskResult } from '@shared/preload-api'

export type TaskSelectorMode = 'manual' | 'auto'

export const TASK_TYPE_LIST: ResearchTaskType[] = [
  'literature-review',
  'paper-writing',
  'coding',
  'matlab',
  'python-analysis',
  'cfd-analysis',
  'image-analysis',
  'experiment-design',
  'data-analysis'
]

/**
 * Phase 6-C3: required capabilities per taskType (mirror of
 * BUILT_IN_TASK_PROFILES in shared/model/research-task.ts).
 * Renderer-side lookup so the UI can preview what will be sent.
 */
export const TASK_TYPE_CAPABILITIES: Record<ResearchTaskType, string[]> = {
  'literature-review': ['literature'],
  'paper-writing': ['paper-writing'],
  'coding': ['coding'],
  'matlab': ['matlab'],
  'python-analysis': ['python', 'data-analysis'],
  'cfd-analysis': ['cfd'],
  'image-analysis': ['image-analysis'],
  'experiment-design': ['coding'],
  'data-analysis': ['data-analysis']
}

export const useTaskSelectorStore = defineStore('task-selector', () => {
  // ============ State ============
  const mode = ref<TaskSelectorMode>('manual')
  const taskType = ref<ResearchTaskType | null>(null)
  const lastDecision = ref<ModelRouteTaskResult | null>(null)
  const routing = ref(false)
  const lastError = ref<string | null>(null)

  // ============ Getters ============
  const isAuto = computed(() => mode.value === 'auto')
  const isManual = computed(() => mode.value === 'manual')
  const hasDecision = computed(() => lastDecision.value !== null && lastDecision.value.decision !== null)
  const decisionLabel = computed(() => {
    const d = lastDecision.value?.decision
    if (!d) return null
    return `${d.providerId} · ${d.model}`
  })
  const decisionSourceLabel = computed(() => {
    const r = lastDecision.value?.route
    if (r === 'task-routed') return 'Auto-routed'
    if (r === 'active-fallback') return 'Active fallback'
    if (r === 'no-route') return 'No route'
    return null
  })
  const taskLabel = computed(() => (taskType.value ? researchTaskLabel(taskType.value) : null))

  // ============ Actions ============

  /**
   * Phase 6-C3: switch between manual (Phase 6-B ModelSelector)
   * and auto (Phase 6-C2 capability router) modes.
   */
  function setMode(next: TaskSelectorMode): void {
    mode.value = next
    // Phase 6-C3 strict: every setMode clears lastError (defensive — stale
    // errors from the previous mode must not bleed into the new mode).
    lastError.value = null
    if (next === 'manual') {
      // clear auto-specific state when falling back to manual
      lastDecision.value = null
    }
  }

  /**
   * Phase 6-C3: select the active task type.
   * Triggers a routing decision when mode='auto'.
   */
  async function selectTask(next: ResearchTaskType | null): Promise<void> {
    taskType.value = next
    lastError.value = null
    if (mode.value === 'auto' && next) {
      await routeNow()
    } else if (mode.value === 'auto' && !next) {
      lastDecision.value = null
    }
  }

  /**
   * Phase 6-C3: ask main process to route the current task.
   * Result is non-secret (no apiKey field).
   */
  async function routeNow(): Promise<void> {
    if (!taskType.value) {
      lastDecision.value = null
      return
    }
    routing.value = true
    lastError.value = null
    try {
      const profile = {
        taskType: taskType.value,
        requiredCapabilities: TASK_TYPE_CAPABILITIES[taskType.value]
      }
      const result = await window.api.model.routeTask(profile)
      lastDecision.value = result
    } catch (e) {
      lastError.value = e instanceof Error ? e.message : String(e)
    } finally {
      routing.value = false
    }
  }

  function reset(): void {
    mode.value = 'manual'
    taskType.value = null
    lastDecision.value = null
    lastError.value = null
  }

  return {
    // state
    mode,
    taskType,
    lastDecision,
    routing,
    lastError,
    // getters
    isAuto,
    isManual,
    hasDecision,
    decisionLabel,
    decisionSourceLabel,
    taskLabel,
    // actions
    setMode,
    selectTask,
    routeNow,
    reset
  }
})

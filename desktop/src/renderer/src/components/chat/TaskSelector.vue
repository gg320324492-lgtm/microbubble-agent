<script setup lang="ts">
/**
 * TaskSelector.vue (Phase 6-C3: Task-aware Chat Header UI).
 *
 * Chat-header widget exposing the Agent Capability Router to users.
 *
 * - Mode toggle: Manual (Phase 6-B ModelSelector) | Auto (Phase 6-C2 router)
 * - Task picker: 9 task types (literature-review / paper-writing / ...)
 * - Routing decision display: providerId · model + reason
 *
 * Phase 6-C3 strict forbids:
 *   - NEVER display API key plaintext
 *   - NEVER store key in component state
 *   - All routing happens in main process (window.api.model.routeTask)
 */
import { computed } from 'vue'
import {
  useTaskSelectorStore,
  TASK_TYPE_LIST,
  type TaskSelectorMode
} from '../../stores/task-selector'

const store = useTaskSelectorStore()

const showMenu = computed(() => true)
const decision = computed(() => store.lastDecision?.decision ?? null)
const sourceLabel = computed(() => store.decisionSourceLabel)
const decisionLabel = computed(() => store.decisionLabel)

function onSetMode(mode: TaskSelectorMode): void {
  store.setMode(mode)
}

async function onPickTask(taskType: typeof TASK_TYPE_LIST[number]): Promise<void> {
  await store.selectTask(taskType)
}

async function onClearTask(): Promise<void> {
  await store.selectTask(null)
}
</script>

<template>
  <div class="task-selector" data-testid="task-selector">
    <div class="task-selector__mode" role="tablist">
      <button
        :class="['task-selector__mode-btn', { 'is-active': store.isManual }]"
        type="button"
        data-testid="mode-manual"
        @click="onSetMode('manual')"
      >
        Manual
      </button>
      <button
        :class="['task-selector__mode-btn', { 'is-active': store.isAuto }]"
        type="button"
        data-testid="mode-auto"
        @click="onSetMode('auto')"
      >
        Auto
      </button>
    </div>

    <div v-if="store.isAuto" class="task-selector__auto">
      <button class="task-selector__trigger" data-testid="task-trigger" type="button">
        <span class="task-selector__icon">🎯</span>
        <span class="task-selector__label">
          {{ store.taskLabel ?? 'Pick a task...' }}
        </span>
        <span class="task-selector__chevron">▾</span>
      </button>
      <div v-if="showMenu" class="task-selector__menu" data-testid="task-menu">
        <button
          v-for="t in TASK_TYPE_LIST"
          :key="t"
          :class="['task-selector__item', { 'is-active': store.taskType === t }]"
          type="button"
          :data-testid="`task-${t}`"
          @click="onPickTask(t)"
        >
          {{ t }}
        </button>
        <button
          v-if="store.taskType"
          class="task-selector__clear"
          type="button"
          data-testid="task-clear"
          @click="onClearTask"
        >
          Clear task
        </button>
      </div>
      <div v-if="store.routing" class="task-selector__status" data-testid="task-routing">
        Routing…
      </div>
      <div
        v-else-if="decision"
        class="task-selector__decision"
        data-testid="task-decision"
        :title="decision.reason"
      >
        <span class="task-selector__chip">{{ sourceLabel }}</span>
        <span class="task-selector__chip is-model">{{ decisionLabel }}</span>
      </div>
      <div
        v-else-if="store.taskType && !store.routing"
        class="task-selector__status task-selector__status--warn"
        data-testid="task-no-route"
      >
        No provider matches
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-selector {
  display: inline-flex;
  flex-direction: column;
  gap: 0.4rem;
}
.task-selector__mode {
  display: inline-flex;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 2px;
}
.task-selector__mode-btn {
  background: transparent;
  border: 0;
  color: #94a3b8;
  padding: 0.25rem 0.7rem;
  border-radius: 4px;
  font-size: 0.78rem;
  cursor: pointer;
}
.task-selector__mode-btn.is-active {
  background: #f97316;
  color: #fff;
}
.task-selector__auto {
  position: relative;
  display: inline-flex;
  flex-direction: column;
  gap: 0.3rem;
}
.task-selector__trigger {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 6px;
  padding: 0.3rem 0.6rem;
  color: #e2e8f0;
  font-size: 0.8rem;
  cursor: pointer;
}
.task-selector__trigger:hover { border-color: #f97316; }
.task-selector__icon { font-size: 0.9rem; }
.task-selector__label { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.task-selector__chevron { font-size: 0.7rem; color: #94a3b8; }
.task-selector__menu {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  z-index: 50;
  background: #0f172a;
  border: 1px solid #334155;
  border-radius: 6px;
  min-width: 240px;
  padding: 0.3rem;
  display: none;
}
.task-selector:hover .task-selector__menu,
.task-selector:focus-within .task-selector__menu { display: block; }
.task-selector__item {
  display: block;
  width: 100%;
  background: transparent;
  border: 0;
  color: #e2e8f0;
  padding: 0.35rem 0.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
  text-align: left;
}
.task-selector__item:hover { background: rgba(249, 115, 22, 0.1); }
.task-selector__item.is-active { background: rgba(249, 115, 22, 0.18); color: #fde68a; }
.task-selector__clear {
  display: block;
  width: 100%;
  background: transparent;
  border: 1px dashed #475569;
  color: #94a3b8;
  border-radius: 4px;
  padding: 0.3rem 0.5rem;
  font-size: 0.78rem;
  cursor: pointer;
  margin-top: 0.3rem;
}
.task-selector__clear:hover { color: #f1f5f9; border-color: #f97316; }
.task-selector__status {
  font-size: 0.72rem;
  color: #94a3b8;
}
.task-selector__status--warn { color: #fca5a5; }
.task-selector__decision {
  display: inline-flex;
  gap: 0.3rem;
  align-items: center;
}
.task-selector__chip {
  font-size: 0.7rem;
  padding: 0.15rem 0.45rem;
  background: #334155;
  color: #cbd5e1;
  border-radius: 3px;
}
.task-selector__chip.is-model {
  background: rgba(249, 115, 22, 0.2);
  color: #fde68a;
}
</style>

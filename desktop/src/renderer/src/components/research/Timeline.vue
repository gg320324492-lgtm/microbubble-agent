<script setup lang="ts">
/**
 * 时间线组件 — 实验流程 / 研究进度。
 */
import ResearchIcon from '../icons/ResearchIcon.vue'
import type { ResearchIconName } from '../icons/research-icons'

defineProps<{
  steps: Array<{
    label: string
    detail?: string
    time?: string
    status: 'done' | 'current' | 'pending' | 'error'
    statusLabel?: string
  }>
}>()

const ICON: Record<'done' | 'current' | 'pending' | 'error', ResearchIconName> = {
  done: 'check',
  current: 'running',
  pending: 'idle',
  error: 'error'
}

const STATUS_LABEL: Record<'done' | 'current' | 'pending' | 'error', string> = {
  done: '已完成',
  current: '进行中',
  pending: '待开始',
  error: '异常'
}

const DATA_STATUS: Record<'done' | 'current' | 'pending' | 'error', string> = {
  done: 'completed',
  current: 'running',
  pending: 'pending',
  error: 'error'
}
</script>

<template>
  <div class="timeline" role="list">
    <div
      v-for="(step, i) in steps"
      :key="`${i}-${step.label}`"
      class="timeline__step"
      :class="`timeline__step--${step.status}`"
      :data-stage="i"
      :data-status="DATA_STATUS[step.status]"
      :aria-current="step.status === 'current' ? 'step' : undefined"
      role="listitem"
    >
      <div class="timeline__marker"><ResearchIcon :name="ICON[step.status]" :size="14" /></div>
      <div class="timeline__content">
        <div class="timeline__label">{{ step.label }}</div>
        <div v-if="step.detail" class="timeline__detail">{{ step.detail }}</div>
        <span class="timeline__status-label">{{ step.statusLabel ?? STATUS_LABEL[step.status] }}</span>
        <div v-if="step.time" class="timeline__time">{{ step.time }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline { display: flex; flex-direction: column; gap: 0; }
.timeline__step { display: flex; gap: var(--research-space-3); padding: var(--research-space-2) 0; position: relative; }
.timeline__step:not(:last-child)::after { content: ''; position: absolute; left: 10px; top: 30px; bottom: -8px; width: 2px; background: var(--research-border-subtle); }
.timeline__step--done::after { background: var(--research-success-500); }
.timeline__step--current::after { background: linear-gradient(180deg, var(--research-primary-500), var(--research-border-subtle)); }
.timeline__marker { width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; z-index: 1; border-radius: var(--research-radius-pill); background: var(--research-bg-panel); color: var(--research-text-secondary); }
.timeline__step--done .timeline__marker { background: var(--research-success-50); color: var(--research-success-700); }
.timeline__step--current .timeline__marker { background: var(--research-primary-50); color: var(--research-primary-700); }
.timeline__step--error .timeline__marker { background: var(--research-danger-50); color: var(--research-danger-600); }
.timeline__label { font-size: var(--research-text-body); color: var(--research-text-primary); font-weight: var(--research-font-weight-medium); }
.timeline__detail { margin-top: var(--research-space-1); color: var(--research-text-secondary); font-size: var(--research-text-xs); line-height: var(--research-line-height-body); }
.timeline__time { font-size: var(--research-text-xs); color: var(--research-text-secondary); margin-top: var(--research-space-1); font-variant-numeric: tabular-nums; }
.timeline__status-label {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>

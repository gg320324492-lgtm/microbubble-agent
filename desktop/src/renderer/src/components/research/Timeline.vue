<script setup lang="ts">
/**
 * 时间线组件 — 实验流程 / 研究进度。
 */
import ResearchIcon from '../icons/ResearchIcon.vue'
import type { ResearchIconName } from '../icons/research-icons'

defineProps<{
  steps: Array<{ label: string; time?: string; status: 'done' | 'current' | 'pending' }>
}>()

const ICON: Record<'done' | 'current' | 'pending', ResearchIconName> = {
  done: 'check',
  current: 'running',
  pending: 'idle'
}

const STATUS_LABEL: Record<'done' | 'current' | 'pending', string> = {
  done: '已完成',
  current: '进行中',
  pending: '待开始'
}
</script>

<template>
  <div class="timeline">
    <div v-for="(step, i) in steps" :key="i" class="timeline__step" :class="`timeline__step--${step.status}`">
      <div class="timeline__marker"><ResearchIcon :name="ICON[step.status]" :size="14" /></div>
      <div class="timeline__content">
        <div class="timeline__label">{{ step.label }}</div>
        <span class="timeline__status-label">{{ STATUS_LABEL[step.status] }}</span>
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
.timeline__label { font-size: var(--research-text-body); color: var(--research-text-primary); font-weight: var(--research-font-weight-medium); }
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

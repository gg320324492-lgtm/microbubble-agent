<script setup lang="ts">
/**
 * 时间线组件 — 实验流程 / 研究进度。
 */
defineProps<{
  steps: Array<{ label: string; time?: string; status: 'done' | 'current' | 'pending' }>
}>()

const ICON: Record<string, string> = { done: '✅', current: '🔵', pending: '⬜' }
</script>

<template>
  <div class="timeline">
    <div v-for="(step, i) in steps" :key="i" class="timeline__step" :class="`timeline__step--${step.status}`">
      <div class="timeline__marker">{{ ICON[step.status] }}</div>
      <div class="timeline__content">
        <div class="timeline__label">{{ step.label }}</div>
        <div v-if="step.time" class="timeline__time">{{ step.time }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline { display: flex; flex-direction: column; gap: 0; }
.timeline__step { display: flex; gap: 10px; padding: 8px 0; position: relative; }
.timeline__step:not(:last-child)::after { content: ''; position: absolute; left: 10px; top: 28px; bottom: -8px; width: 2px; background: #e2e8f0; }
.timeline__step--done::after { background: #10b981; }
.timeline__step--current::after { background: linear-gradient(180deg, #3b82f6, #e2e8f0); }
.timeline__marker { width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; z-index: 1; }
.timeline__label { font-size: 13px; color: #1e293b; font-weight: 500; }
.timeline__time { font-size: 11px; color: #94a3b8; margin-top: 2px; }
</style>

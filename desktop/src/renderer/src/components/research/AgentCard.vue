<script setup lang="ts">
/**
 * 智能体卡片 — Agent状态展示。
 */
defineProps<{
  icon: string
  name: string
  status: 'running' | 'idle' | 'error'
  task?: string
}>()

const STATUS_LABEL: Record<string, { label: string; color: string }> = {
  running: { label: '运行中', color: '#10B981' },
  idle:    { label: '空闲',   color: '#94A3B8' },
  error:   { label: '异常',   color: '#EF4444' }
}
</script>

<template>
  <div class="agent-card" :class="`agent-card--${status}`">
    <div class="agent-card__icon">{{ icon }}</div>
    <div class="agent-card__name">{{ name }}</div>
    <div class="agent-card__status">
      <span class="agent-card__dot" :style="{ background: STATUS_LABEL[status].color }" />
      {{ STATUS_LABEL[status].label }}
    </div>
    <div v-if="task" class="agent-card__task">{{ task }}</div>
  </div>
</template>

<style scoped>
.agent-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px; text-align: center; transition: box-shadow .15s; }
.agent-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,.05); }
.agent-card--running { border-color: #bbf7d0; }
.agent-card__icon { font-size: 28px; margin-bottom: 8px; }
.agent-card__name { font-size: 13px; font-weight: 600; color: #1e293b; margin-bottom: 4px; }
.agent-card__status { font-size: 12px; color: #64748b; display: flex; align-items: center; justify-content: center; gap: 4px; }
.agent-card__dot { width: 6px; height: 6px; border-radius: 50%; }
.agent-card__task { font-size: 11px; color: #94a3b8; margin-top: 6px; }
</style>

<script setup lang="ts">
/**
 * 科研指标卡片 — 单个数值指标展示。
 */
defineProps<{
  label: string
  value: string
  unit?: string
  trend?: 'up' | 'down' | 'stable'
  trendText?: string
}>()

const TREND_ICON: Record<string, string> = { up: '↑', down: '↓', stable: '→' }
const TREND_COLOR: Record<string, string> = { up: '#10B981', down: '#EF4444', stable: '#94A3B8' }
</script>

<template>
  <div class="metric-card">
    <div class="metric-card__label">{{ label }}</div>
    <div class="metric-card__value">
      {{ value }}<span v-if="unit" class="metric-card__unit">{{ unit }}</span>
    </div>
    <div v-if="trend" class="metric-card__trend" :style="{ color: TREND_COLOR[trend] }">
      {{ TREND_ICON[trend] }} {{ trendText }}
    </div>
  </div>
</template>

<style scoped>
.metric-card { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; padding: 16px; }
.metric-card__label { font-size: 12px; color: #64748b; margin-bottom: 6px; }
.metric-card__value { font-size: 22px; font-weight: 700; color: #1e293b; }
.metric-card__unit { font-size: 13px; font-weight: 400; color: #64748b; margin-left: 4px; }
.metric-card__trend { font-size: 12px; font-weight: 500; margin-top: 4px; }
</style>

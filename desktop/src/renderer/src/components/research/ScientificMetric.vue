<script setup lang="ts">
/**
 * 科研指标卡片 — 单个数值指标展示。
 */
import ResearchIcon from '../icons/ResearchIcon.vue'

defineProps<{
  label: string
  value: string
  unit?: string
  trend?: 'up' | 'down' | 'stable'
  trendText?: string
}>()

</script>

<template>
  <div class="metric-card">
    <div class="metric-card__label">{{ label }}</div>
    <div class="metric-card__value">
      {{ value }}<span v-if="unit" class="metric-card__unit">{{ unit }}</span>
    </div>
    <div v-if="trend" :class="['metric-card__trend', `metric-card__trend--${trend}`]">
      <ResearchIcon
        name="progress"
        :size="13"
        :class="['metric-card__trend-icon', `metric-card__trend-icon--${trend}`]"
      />
      {{ trendText }}
    </div>
  </div>
</template>

<style scoped>
.metric-card { background: var(--research-bg-card); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); padding: var(--research-space-4); box-shadow: var(--research-shadow-soft); }
.metric-card__label { font-size: var(--research-text-sm); color: var(--research-text-secondary); margin-bottom: var(--research-space-2); }
.metric-card__value { font-size: 22px; font-weight: var(--research-font-weight-bold); color: var(--research-text-primary); font-variant-numeric: tabular-nums; }
.metric-card__unit { font-size: var(--research-text-body); font-weight: var(--research-font-weight-regular); color: var(--research-text-secondary); margin-left: var(--research-space-1); }
.metric-card__trend { display: flex; align-items: center; gap: var(--research-space-1); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-medium); margin-top: var(--research-space-1); color: var(--research-text-secondary); }
.metric-card__trend--up { color: var(--research-success-700); }
.metric-card__trend--down { color: var(--research-danger-600); }
.metric-card__trend-icon { flex-shrink: 0; }
.metric-card__trend-icon--up { transform: rotate(-90deg); }
.metric-card__trend-icon--down { transform: rotate(90deg); }
.metric-card__trend-icon--stable { transform: rotate(0deg); }
</style>

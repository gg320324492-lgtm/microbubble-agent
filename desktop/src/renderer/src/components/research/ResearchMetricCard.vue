<script setup lang="ts">
withDefaults(defineProps<{
  label: string
  value: string
  unit?: string
  description?: string
  trend?: 'up' | 'down' | 'stable'
  trendText?: string
}>(), { trend: 'stable' })
</script>

<template>
  <article class="research-metric-card" :aria-label="`${label}：${value}${unit ?? ''}`">
    <p>{{ label }}</p>
    <div class="research-metric-card__value research-scientific-number">{{ value }}<span v-if="unit">{{ unit }}</span></div>
    <div v-if="trendText" :class="['research-metric-card__trend', `is-${trend}`]">{{ trendText }}</div>
    <small v-if="description">{{ description }}</small>
  </article>
</template>

<style scoped>
.research-metric-card { min-width: 0; padding: var(--research-space-4); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-md); background: var(--research-bg-card); box-shadow: var(--research-shadow-surface); }
.research-metric-card p, .research-metric-card small { margin: 0; color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.research-metric-card__value { margin-block: var(--research-space-2); color: var(--research-text-primary); font-size: 24px; font-weight: var(--research-font-weight-semibold); line-height: var(--research-line-height-tight); }
.research-metric-card__value span { margin-inline-start: var(--research-space-1); color: var(--research-text-secondary); font-family: var(--research-font-ui); font-size: var(--research-text-body); font-weight: var(--research-font-weight-regular); }
.research-metric-card__trend { color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.research-metric-card__trend.is-up { color: var(--research-success-700); }
.research-metric-card__trend.is-down { color: var(--research-danger-600); }
</style>

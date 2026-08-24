<script lang="ts">
export type ResearchMetricTrend = 'up' | 'down' | 'stable'
export type ResearchMetricStatus = 'neutral' | 'success' | 'warning' | 'danger'

/** 由科研页面传入的单个指标展示数据。 */
export interface ResearchMetricItem {
  label: string
  value: string | number
  unit?: string
  trend?: ResearchMetricTrend
  status?: 'neutral' | 'success' | 'warning' | 'danger'
}
</script>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  items?: ResearchMetricItem[]
  ariaLabel?: string
}>(), {
  items: () => [],
  ariaLabel: '科研关键指标'
})

const trendLabels: Record<ResearchMetricTrend, string> = {
  up: '上升',
  down: '下降',
  stable: '稳定'
}

const statusLabels: Record<ResearchMetricStatus, string> = {
  neutral: '常规',
  success: '可信',
  warning: '待确认',
  danger: '需关注'
}
</script>

<template>
  <section class="research-metric-panel" :aria-label="props.ariaLabel">
    <header class="research-metric-panel__header">
      <h2 class="research-metric-panel__title">科研关键指标</h2>
    </header>

    <div v-if="props.items.length" class="research-metric-panel__grid" role="list">
      <article
        v-for="item in props.items"
        :key="item.label"
        class="research-metric-panel__item"
        role="listitem"
      >
        <p class="research-metric-panel__label">{{ item.label }}</p>
        <p class="research-metric-panel__value research-scientific-number">
          {{ item.value }}<span v-if="item.unit" class="research-metric-panel__unit">{{ item.unit }}</span>
        </p>
        <div v-if="item.trend || item.status" class="research-metric-panel__meta">
          <span v-if="item.trend" :class="['research-metric-panel__trend', `is-${item.trend}`]">
            {{ trendLabels[item.trend] }}
          </span>
          <span v-if="item.status" :class="['research-metric-panel__status', `is-${item.status}`]" role="status">
            {{ statusLabels[item.status] }}
          </span>
        </div>
      </article>
    </div>

    <p v-else class="research-metric-panel__empty" role="status">暂无科研指标</p>
  </section>
</template>

<style scoped>
.research-metric-panel {
  min-width: 0;
  padding: var(--research-space-5);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-panel);
  background: var(--research-bg-card);
  box-shadow: var(--research-shadow-soft);
}

.research-metric-panel__header { margin-bottom: var(--research-space-4); }

.research-metric-panel__title {
  margin: 0;
  color: var(--research-text-primary);
  font-size: var(--research-text-section-title);
  font-weight: var(--research-font-weight-semibold);
  line-height: var(--research-line-height-tight);
}

.research-metric-panel__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 180px), 1fr));
  gap: var(--research-grid-gap);
}

.research-metric-panel__item {
  min-width: 0;
  padding: var(--research-space-4);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-card);
  background: var(--research-bg-panel);
}

.research-metric-panel__label,
.research-metric-panel__value { margin: 0; }

.research-metric-panel__label {
  color: var(--research-text-secondary);
  font-size: var(--research-text-sm);
  line-height: var(--research-line-height-body);
}

.research-metric-panel__value {
  margin-top: var(--research-space-2);
  color: var(--research-text-primary);
  font-family: var(--research-font-scientific);
  font-size: var(--research-text-section-title);
  font-weight: var(--research-font-weight-semibold);
  font-variant-numeric: tabular-nums;
  line-height: var(--research-line-height-tight);
  overflow-wrap: anywhere;
}

.research-metric-panel__unit {
  margin-inline-start: var(--research-space-1);
  color: var(--research-text-secondary);
  font-family: var(--research-font-ui);
  font-size: var(--research-text-body);
  font-weight: var(--research-font-weight-regular);
}

.research-metric-panel__meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--research-space-2);
  margin-top: var(--research-space-3);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-medium);
}

.research-metric-panel__trend { color: var(--research-text-secondary); }
.research-metric-panel__trend.is-up { color: var(--research-success-700); }
.research-metric-panel__trend.is-down { color: var(--research-danger-600); }
.research-metric-panel__status { color: var(--research-text-secondary); }
.research-metric-panel__status.is-success { color: var(--research-success-700); }
.research-metric-panel__status.is-warning { color: var(--research-warning-600); }
.research-metric-panel__status.is-danger { color: var(--research-danger-600); }

.research-metric-panel__empty {
  margin: 0;
  color: var(--research-text-secondary);
  font-size: var(--research-text-body);
  line-height: var(--research-line-height-body);
}
</style>

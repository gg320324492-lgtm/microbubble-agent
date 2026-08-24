<script setup lang="ts">
import { computed } from 'vue'
import type { RealtimeMetric } from '../../../../shared/control/experiment-control-schema'

const props = withDefaults(defineProps<{
  metrics: RealtimeMetric[]
  metricName: string
  deviceId?: string
  ariaLabel?: string
}>(), {
  ariaLabel: undefined
})

const series = computed(() => [...props.metrics]
  .filter((metric) => metric.metric === props.metricName)
  .filter((metric) => props.deviceId === undefined || metric.deviceId === props.deviceId)
  .sort((left, right) => left.timestamp - right.timestamp))

const min = computed(() => series.value.length ? Math.min(...series.value.map((metric) => metric.value)) : null)
const max = computed(() => series.value.length ? Math.max(...series.value.map((metric) => metric.value)) : null)
const latest = computed(() => series.value.at(-1) ?? null)

const points = computed(() => {
  const lowerBound = min.value
  const upperBound = max.value
  if (!series.value.length || lowerBound === null || upperBound === null) return ''

  const width = 240
  const height = 96
  const range = upperBound - lowerBound
  const step = series.value.length === 1 ? 0 : width / (series.value.length - 1)

  return series.value.map((metric, index) => {
    const x = index * step
    const y = range === 0 ? height / 2 : height - ((metric.value - lowerBound) / range) * height
    return `${x},${y}`
  }).join(' ')
})

const metricLabel = computed(() => props.metricName || '实时指标')
const chartAriaLabel = computed(() => props.ariaLabel?.trim() || `${metricLabel.value}实时趋势`)
const formatValue = (value: number | null): string => value === null
  ? '--'
  : value.toLocaleString('zh-CN', { maximumFractionDigits: 4 })
</script>

<template>
  <section class="scada-chart-panel" :aria-label="chartAriaLabel">
    <header class="scada-chart-panel__header">
      <div>
        <p class="scada-chart-panel__eyebrow">实时指标</p>
        <h2 class="scada-chart-panel__title">{{ metricLabel }}</h2>
      </div>
      <p v-if="latest" class="scada-chart-panel__latest">
        {{ formatValue(latest.value) }}<span class="scada-chart-panel__unit">{{ latest.unit }}</span>
      </p>
    </header>

    <div v-if="series.length" class="scada-chart-panel__chart">
      <svg
        class="scada-chart-panel__svg"
        viewBox="0 0 240 96"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <g class="scada-chart-panel__grid" aria-hidden="true">
          <line x1="0" y1="0" x2="240" y2="0" />
          <line x1="0" y1="24" x2="240" y2="24" />
          <line x1="0" y1="48" x2="240" y2="48" />
          <line x1="0" y1="72" x2="240" y2="72" />
          <line x1="0" y1="96" x2="240" y2="96" />
        </g>
        <polyline class="scada-chart-panel__line" :points="points" fill="none" />
      </svg>
      <dl class="scada-chart-panel__summary">
        <div>
          <dt>最小值</dt>
          <dd>{{ formatValue(min) }}</dd>
        </div>
        <div>
          <dt>最大值</dt>
          <dd>{{ formatValue(max) }}</dd>
        </div>
        <div>
          <dt>最新值</dt>
          <dd>{{ latest ? formatValue(latest.value) : '--' }}</dd>
        </div>
      </dl>
    </div>

    <p v-else class="scada-chart-panel__empty" role="status">暂无实时指标</p>
  </section>
</template>

<style scoped>
.scada-chart-panel {
  min-width: 0;
  padding: var(--research-space-5);
  border: 1px solid var(--research-instrument-line);
  border-radius: var(--research-radius-panel);
  background: var(--research-instrument-900);
  color: var(--research-instrument-text);
  box-shadow: var(--research-shadow-soft);
}

.scada-chart-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--research-space-4);
  min-width: 0;
  margin-bottom: var(--research-space-4);
}

.scada-chart-panel__eyebrow,
.scada-chart-panel__title,
.scada-chart-panel__latest { margin: 0; }

.scada-chart-panel__eyebrow {
  color: var(--research-instrument-muted);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-medium);
  line-height: var(--research-line-height-tight);
}

.scada-chart-panel__title {
  margin-top: var(--research-space-1);
  color: var(--research-instrument-text);
  font-size: var(--research-text-section-title);
  font-weight: var(--research-font-weight-semibold);
  line-height: var(--research-line-height-tight);
  overflow-wrap: anywhere;
}

.scada-chart-panel__latest {
  color: var(--research-signal-green);
  font-family: var(--research-font-scientific);
  font-size: var(--research-text-section-title);
  font-weight: var(--research-font-weight-semibold);
  font-variant-numeric: tabular-nums;
  line-height: var(--research-line-height-tight);
  white-space: nowrap;
}

.scada-chart-panel__unit {
  margin-inline-start: var(--research-space-1);
  color: var(--research-instrument-muted);
  font-family: var(--research-font-ui);
  font-size: var(--research-text-sm);
  font-weight: var(--research-font-weight-regular);
}

.scada-chart-panel__chart { min-width: 0; }

.scada-chart-panel__svg {
  display: block;
  width: 100%;
  min-width: 0;
  height: 144px;
  overflow: visible;
}

.scada-chart-panel__grid line {
  stroke: var(--research-scada-grid);
  stroke-width: 1;
  vector-effect: non-scaling-stroke;
}

.scada-chart-panel__line {
  stroke: var(--research-signal-green);
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
  vector-effect: non-scaling-stroke;
  animation: scada-chart-panel-draw var(--research-duration-slow) var(--research-ease-emphasized) both;
}

.scada-chart-panel__summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--research-space-2);
  margin: var(--research-space-4) 0 0;
}

.scada-chart-panel__summary div {
  min-width: 0;
  padding: var(--research-space-2);
  border: 1px solid var(--research-instrument-line);
  border-radius: var(--research-radius-sm);
  background: var(--research-instrument-850);
}

.scada-chart-panel__summary dt,
.scada-chart-panel__summary dd { margin: 0; }

.scada-chart-panel__summary dt {
  color: var(--research-instrument-muted);
  font-size: var(--research-text-xs);
  line-height: var(--research-line-height-tight);
}

.scada-chart-panel__summary dd {
  margin-top: var(--research-space-1);
  color: var(--research-instrument-text);
  font-family: var(--research-font-scientific);
  font-size: var(--research-text-sm);
  font-variant-numeric: tabular-nums;
  overflow-wrap: anywhere;
}

.scada-chart-panel__empty {
  margin: 0;
  color: var(--research-instrument-muted);
  font-size: var(--research-text-body);
  line-height: var(--research-line-height-body);
}

@keyframes scada-chart-panel-draw {
  from { opacity: 0; }
  to { opacity: 1; }
}

@media (max-width: 480px) {
  .scada-chart-panel__summary { grid-template-columns: 1fr; }
}

@media (prefers-reduced-motion: reduce) {
  .scada-chart-panel__line { animation: none; }
}
</style>

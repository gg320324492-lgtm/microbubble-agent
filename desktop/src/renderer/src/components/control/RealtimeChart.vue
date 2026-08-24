<script setup lang="ts">
import { computed } from 'vue'
import type { RealtimeMetric } from '../../../../shared/control/experiment-control-schema'

const props = withDefaults(defineProps<{ metrics: RealtimeMetric[]; metricName: string }>(), {
  metrics: () => [],
  metricName: ''
})

const series = computed(() => props.metrics.filter((m) => m.metric === props.metricName))
const values = computed(() => series.value.map((m) => m.value))
const min = computed(() => values.value.length === 0 ? 0 : Math.min(...values.value))
const max = computed(() => values.value.length === 0 ? 1 : Math.max(...values.value))
const latest = computed(() => series.value.length === 0 ? null : series.value[series.value.length - 1])
const points = computed(() => {
  if (series.value.length === 0) return ''
  const w = 200, h = 60
  const range = Math.max(max.value - min.value, 1e-9)
  const step = series.value.length === 1 ? 0 : w / (series.value.length - 1)
  return series.value.map((m, i) => {
    const x = i * step
    const y = h - ((m.value - min.value) / range) * h
    return `${x},${y}`
  }).join(' ')
})
const latestLabel = computed(() => latest.value ? latest.value.value.toFixed(2) : '--')
const unit = computed(() => latest.value?.unit ?? '')
</script>

<template>
  <div class="realtime-chart">
    <div class="realtime-chart__head">
      <span class="realtime-chart__name">{{ metricName }}</span>
      <span class="realtime-chart__latest">{{ latestLabel }} {{ unit }}</span>
    </div>
    <svg viewBox="0 0 200 60" preserveAspectRatio="none" class="realtime-chart__svg">
      <polyline :points="points" fill="none" stroke="#FF7A5C" stroke-width="2" />
    </svg>
    <div class="realtime-chart__legend">
      <span>min: {{ min.toFixed(2) }}</span>
      <span>max: {{ max.toFixed(2) }}</span>
      <span>点: {{ series.length }}</span>
    </div>
  </div>
</template>

<style scoped>
.realtime-chart {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
}
.realtime-chart__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
}
.realtime-chart__name {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}
.realtime-chart__latest {
  font-size: 18px;
  font-weight: 700;
  color: #FF7A5C;
}
.realtime-chart__svg {
  width: 100%;
  height: 60px;
  display: block;
}
.realtime-chart__legend {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: #94a3b8;
  margin-top: 6px;
}
</style>
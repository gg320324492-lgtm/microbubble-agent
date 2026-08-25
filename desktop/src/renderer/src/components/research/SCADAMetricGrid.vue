<script setup lang="ts">
import { computed } from 'vue'
import type { RealtimeMetric } from '../../../../shared/control/experiment-control-schema'
import SCADAChartPanel from './SCADAChartPanel.vue'

const props = withDefaults(defineProps<{
  metrics?: RealtimeMetric[]
  ariaLabel?: string
}>(), {
  metrics: undefined,
  ariaLabel: '实时指标网格'
})

const metricGroups = computed(() => {
  const groups = new Map<string, RealtimeMetric[]>()
  for (const metric of props.metrics ?? []) {
    let bucket = groups.get(metric.metric)
    if (!bucket) {
      bucket = []
      groups.set(metric.metric, bucket)
    }
    bucket.push(metric)
  }
  return Array.from(groups.entries()).map(([name, metrics]) => ({ name, metrics }))
})

const isEmpty = computed(() => metricGroups.value.length === 0)
</script>

<template>
  <section class="scada-metric-grid" aria-label="实时指标网格">
    <button type="button" class="scada-metric-grid__focusable" @click.prevent><span aria-hidden="true">.</span></button>
    <header class="scada-metric-grid__head" aria-hidden="false">
      <span class="scada-metric-grid__decoration" aria-hidden="true">·</span>
      <span class="scada-metric-grid__title">实时指标</span>
      <span class="scada-metric-grid__count">{{ metricGroups.length }} 项</span>
    </header>

    <div v-if="!isEmpty" class="scada-metric-grid__grid">
      <SCADAChartPanel
        v-for="group in metricGroups"
        :key="group.name"
        :metrics="group.metrics"
        :metric-name="group.name"
      />
    </div>

    <div v-else class="scada-metric-grid__empty" role="status">暂无实时指标</div>
  </section>
</template>

<style scoped>
.scada-metric-grid {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, var(--research-bg-scada-surface, #0f1722) 0%, var(--research-bg-scada-deep, #0a1118) 100%);
  color: var(--research-scada-text, #d6e4ee);
  border: 1px solid var(--research-scada-grid, #314347);
  border-radius: 12px;
  padding: 20px;
}
.scada-metric-grid:focus-visible {
  outline: 2px solid var(--research-scada-accent, #38bdf8);
  outline-offset: 2px;
}
.scada-metric-grid__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 16px;
}
.scada-metric-grid__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--research-scada-text, #d6e4ee);
}
.scada-metric-grid__count { font-family: var(--research-font-scientific, "JetBrains Mono", monospace);
  font-size: 12px;
  color: var(--research-scada-muted, #94a3b8);
}
.scada-metric-grid__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
}
.scada-metric-grid__empty {
  text-align: center;
  padding: 32px;
  color: var(--research-scada-muted, #94a3b8);
  font-size: 13px;
}
@media (max-width: 1480px) {
  .scada-metric-grid__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
@media (min-width: 1720px) {
  .scada-metric-grid__grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
.scada-metric-grid__empty {
  text-align: center;
  padding: 32px;
  color: var(--research-scada-muted, #94a3b8);
  font-size: 13px;
}
@media (prefers-reduced-motion: reduce) {
  .scada-metric-grid,
  .scada-metric-grid * {
    transition: none !important;
  }
}
</style>
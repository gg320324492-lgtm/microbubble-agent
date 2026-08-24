<script setup lang="ts">
import { computed } from 'vue'
import type { TwinPrediction } from '../../../../shared/digital-twin/digital-twin-schema'

const props = withDefaults(defineProps<{
  predictions: TwinPrediction[]
  variant?: 'research' | 'scada'
}>(), {
  variant: 'research'
})

const latestPrediction = computed(() => [...props.predictions]
  .map((prediction, index) => ({ prediction, index }))
  .sort((left, right) => left.prediction.timestamp - right.prediction.timestamp || left.index - right.index)
  .at(-1)?.prediction ?? null)
const outputEntries = computed(() => latestPrediction.value
  ? Object.entries(latestPrediction.value.output)
  : [])
const confidence = computed(() => latestPrediction.value
  ? Math.round(latestPrediction.value.confidence * 100)
  : null)
const panelClass = computed(() => [
  'prediction-panel',
  `prediction-panel--${props.variant}`
])
const formatValue = (value: number): string => value.toLocaleString('zh-CN', { maximumFractionDigits: 4 })
</script>

<template>
  <section :class="panelClass" aria-label="数字孪生预测">
    <header class="prediction-panel__header">
      <h2 class="prediction-panel__title">数字孪生预测</h2>
      <p v-if="confidence !== null" class="prediction-panel__confidence">
        <span class="prediction-panel__confidence-marker" aria-hidden="true" />
        置信度 {{ confidence }}%
      </p>
    </header>

    <dl v-if="outputEntries.length" class="prediction-panel__outputs">
      <div v-for="[name, value] in outputEntries" :key="name" class="prediction-panel__output">
        <dt>{{ name }}</dt>
        <dd>{{ formatValue(value) }}</dd>
      </div>
    </dl>

    <p v-else-if="latestPrediction" class="prediction-panel__empty" role="status">暂无预测输出</p>
    <p v-else class="prediction-panel__empty" role="status">暂无数字孪生预测</p>
  </section>
</template>

<style scoped>
.prediction-panel {
  min-width: 0;
  padding: var(--research-space-5);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-panel);
  background: var(--research-bg-card);
  box-shadow: var(--research-shadow-soft);
}

.prediction-panel--scada {
  border-color: var(--research-instrument-line);
  background: var(--research-instrument-900);
  color: var(--research-instrument-text);
}

.prediction-panel__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--research-space-3);
  min-width: 0;
  margin-bottom: var(--research-space-4);
}

.prediction-panel__title,
.prediction-panel__confidence { margin: 0; }

.prediction-panel__title {
  color: var(--research-text-primary);
  font-size: var(--research-text-section-title);
  font-weight: var(--research-font-weight-semibold);
  line-height: var(--research-line-height-tight);
}

.prediction-panel--scada .prediction-panel__title { color: var(--research-instrument-text); }

.prediction-panel__confidence {
  display: inline-flex;
  align-items: center;
  gap: var(--research-space-1);
  flex: 0 0 auto;
  color: var(--research-success-700);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-semibold);
  white-space: nowrap;
}

.prediction-panel--scada .prediction-panel__confidence { color: var(--research-signal-green); }

.prediction-panel__confidence-marker {
  width: 6px;
  height: 6px;
  border-radius: var(--research-radius-pill);
  background: currentColor;
  animation: prediction-panel-pulse var(--research-duration-slow) var(--research-ease-standard) infinite;
}

.prediction-panel__outputs {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr));
  gap: var(--research-space-3);
  margin: 0;
}

.prediction-panel__output {
  min-width: 0;
  padding: var(--research-space-3);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-card);
  background: var(--research-bg-panel);
}

.prediction-panel--scada .prediction-panel__output {
  border-color: var(--research-instrument-line);
  background: var(--research-instrument-850);
}

.prediction-panel__output dt,
.prediction-panel__output dd { margin: 0; }

.prediction-panel__output dt {
  color: var(--research-text-secondary);
  font-size: var(--research-text-sm);
  line-height: var(--research-line-height-body);
  overflow-wrap: anywhere;
}

.prediction-panel--scada .prediction-panel__output dt { color: var(--research-instrument-muted); }

.prediction-panel__output dd {
  margin-top: var(--research-space-2);
  color: var(--research-text-primary);
  font-family: var(--research-font-scientific);
  font-size: var(--research-text-card-title);
  font-weight: var(--research-font-weight-semibold);
  font-variant-numeric: tabular-nums;
  line-height: var(--research-line-height-tight);
  overflow-wrap: anywhere;
}

.prediction-panel--scada .prediction-panel__output dd { color: var(--research-instrument-text); }

.prediction-panel__empty {
  margin: 0;
  color: var(--research-text-secondary);
  font-size: var(--research-text-body);
  line-height: var(--research-line-height-body);
}

.prediction-panel--scada .prediction-panel__empty { color: var(--research-instrument-muted); }

@keyframes prediction-panel-pulse {
  50% { opacity: 0.5; }
}

@media (prefers-reduced-motion: reduce) {
  .prediction-panel__confidence-marker { animation: none; }
}
</style>

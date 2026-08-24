<script setup lang="ts">
import { computed } from 'vue'
import type { TwinPrediction } from '../../../../shared/digital-twin/digital-twin-schema'

const props = withDefaults(defineProps<{ predictions: TwinPrediction[] }>(), {
  predictions: () => []
})

const latest = computed(() => props.predictions.length === 0 ? null : props.predictions[props.predictions.length - 1])
const outputEntries = computed(() => latest.value ? Object.entries(latest.value.output) : [])
const confidencePct = computed(() => latest.value ? Math.round(latest.value.confidence * 100) : 0)
const confidenceColor = computed(() => {
  const c = confidencePct.value
  if (c >= 80) return '#10b981'
  if (c >= 60) return '#f59e0b'
  return '#ef4444'
})
</script>

<template>
  <div class="prediction-panel">
    <div class="prediction-panel__head">
      <span class="prediction-panel__title">数字孪生预测</span>
      <span class="prediction-panel__confidence" :style="{ color: confidenceColor }">{{ confidencePct }}% 置信度</span>
    </div>
    <div v-if="latest" class="prediction-panel__body">
      <div v-for="[key, val] in outputEntries" :key="key" class="prediction-panel__row">
        <span class="prediction-panel__key">{{ key }}</span>
        <span class="prediction-panel__val">{{ val.toFixed(4) }}</span>
      </div>
    </div>
    <div v-else class="prediction-panel__empty">暂无预测数据</div>
  </div>
</template>

<style scoped>
.prediction-panel {
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
}
.prediction-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.prediction-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}
.prediction-panel__confidence {
  font-size: 12px;
  font-weight: 700;
}
.prediction-panel__body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.prediction-panel__row {
  display: flex;
  justify-content: space-between;
  padding: 6px 12px;
  background: rgba(255, 122, 92, 0.06);
  border-radius: 6px;
}
.prediction-panel__key {
  font-size: 12px;
  color: #475569;
}
.prediction-panel__val {
  font-size: 14px;
  font-weight: 700;
  color: #FF7A5C;
}
.prediction-panel__empty {
  text-align: center;
  color: #94a3b8;
  padding: 24px;
}
</style>
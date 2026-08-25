<script setup lang="ts">
import { computed } from 'vue'

export interface ModelFit {
  model: string
  rSquared: number
  parameters: Record<string, number>
  residualError: number
}

const props = withDefaults(defineProps<{
  models?: ModelFit[]
  ariaLabel?: string
}>(), {
  models: () => [],
  ariaLabel: '模型拟合面板'
})

const itemList = computed(() => props.models ?? [])
const isEmpty = computed(() => itemList.value.length === 0)
const best = computed(() => {
  if (itemList.value.length === 0) return null
  return [...itemList.value].sort((a, b) => b.rSquared - a.rSquared)[0] ?? null
})
</script>

<template>
  <section class="model-panel" :aria-label="ariaLabel">
    <button type="button" class="modelfit-panel__focusable" @keydown.enter.prevent><span aria-hidden="true">.</span></button>
      <header class="modelfit-panel__head">
      <h2 class="model-panel__title">模型拟合</h2>
      <span v-if="best" class="model-panel__best">最优 R² = {{ best.rSquared.toFixed(4) }}</span>
    </header>

    <ul v-if="!isEmpty" class="model-panel__list">
      <li v-for="(m, idx) in itemList" :key="idx" class="model-panel__item">
        <div class="model-panel__head-row">
          <span class="model-panel__name">{{ m.model }}</span>
          <span class="model-panel__r2" :data-tier="m.rSquared > 0.8 ? 'high' : m.rSquared > 0.5 ? 'mid' : 'low'">
            R² = {{ m.rSquared.toFixed(4) }}
          </span>
        </div>
        <div class="model-panel__params">
          <span v-for="(value, key) in m.parameters" :key="key" class="model-panel__param">
            <span class="model-panel__param-key">{{ key }}</span>
            <span class="model-panel__param-value">{{ value.toFixed(4) }}</span>
          </span>
        </div>
        <p class="model-panel__residual">残差 = {{ m.residualError.toFixed(4) }}</p>
      </li>
    </ul>

    <div v-else class="model-panel__empty" role="status">暂无模型</div>
  </section>
</template>

<style scoped>
.model-panel {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
}
.model-panel:focus-visible {
  outline: 2px solid var(--research-primary-500, #FF7A5C);
  outline-offset: 2px;
}
.model-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.model-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}
.model-panel__best {
  font-size: 12px;
  color: var(--research-primary-500, #FF7A5C);
  font-weight: 600;
}
.model-panel__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.model-panel__item {
  background: white;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 8px;
  padding: 12px;
}
.model-panel__head-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}
.model-panel__name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}
.model-panel__r2 {
  font-size: 12px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.06);
  color: #1e293b;
}
.model-panel__r2[data-tier='high'] {
  background: rgba(16, 185, 129, 0.18);
  color: #10b981;
}
.model-panel__r2[data-tier='mid'] {
  background: rgba(245, 158, 11, 0.18);
  color: #f59e0b;
}
.model-panel__r2[data-tier='low'] {
  background: rgba(239, 68, 68, 0.18);
  color: #ef4444;
}
.model-panel__params {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 4px;
}
.model-panel__param {
  display: flex;
  gap: 4px;
  padding: 2px 6px;
  background: rgba(15, 23, 42, 0.04);
  border-radius: 4px;
  font-size: 11px;
}
.model-panel__param-key {
  color: #94a3b8;
}
.model-panel__param-value {
  color: #1e293b;
  font-weight: 600;
}
.model-panel__residual {
  font-size: 11px;
  color: #94a3b8;
  margin: 0;
}
.model-panel__empty {
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 13px;
}
@media (max-width: 1480px) {
  .model-panel { padding: 12px; }
}
@media (min-width: 1720px) {
  .model-panel { padding: 20px; }
}
@media (prefers-reduced-motion: reduce) {
  .model-panel,
  .model-panel * {
    transition: none !important;
  }
}
</style>
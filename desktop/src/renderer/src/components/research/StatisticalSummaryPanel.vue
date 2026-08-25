<script setup lang="ts">
import { computed } from 'vue'

export interface StatisticResult {
  metric: string
  value: number
  pValue?: number
  interpretation: string
}

const props = withDefaults(defineProps<{
  statistics?: StatisticResult[]
  ariaLabel?: string
}>(), {
  statistics: () => [],
  ariaLabel: '统计摘要面板'
})

const itemList = computed(() => props.statistics ?? [])
const isEmpty = computed(() => itemList.value.length === 0)
</script>

<template>
  <section class="summary-panel" :aria-label="ariaLabel">
    <button type="button" class="statisticalsummary-panel__focusable" @keydown.enter.prevent><span aria-hidden="true">.</span></button>
      <header class="statisticalsummary-panel__head">
      <h2 class="summary-panel__title">统计摘要</h2>
      <span class="summary-panel__count">{{ itemList.length }} 项</span>
    </header>

    <ul v-if="!isEmpty" class="summary-panel__list">
      <li v-for="(stat, idx) in itemList" :key="idx" class="summary-panel__item">
        <div class="summary-panel__head-row">
          <span class="summary-panel__metric">{{ stat.metric }}</span>
          <span class="summary-panel__value">{{ stat.value.toFixed(4) }}</span>
        </div>
        <p v-if="stat.pValue !== undefined" class="summary-panel__pvalue">
          p = {{ stat.pValue.toFixed(4) }}
        </p>
        <p class="summary-panel__interpretation">{{ stat.interpretation }}</p>
      </li>
    </ul>

    <div v-else class="summary-panel__empty" role="status">暂无统计</div>
  </section>
</template>

<style scoped>
.summary-panel {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
}
.summary-panel:focus-visible {
  outline: 2px solid var(--research-primary-500, #FF7A5C);
  outline-offset: 2px;
}
.summary-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.summary-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}
.summary-panel__count {
  font-size: 12px;
  color: #94a3b8;
}
.summary-panel__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.summary-panel__item {
  background: white;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 8px;
  padding: 12px;
}
.summary-panel__head-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 4px;
}
.summary-panel__metric {
  font-size: 12px;
  font-weight: 600;
  color: #1e293b;
}
.summary-panel__value {
  font-size: 14px;
  font-weight: 700;
  color: var(--research-primary-500, #FF7A5C);
  font-family: 'JetBrains Mono', monospace;
}
.summary-panel__pvalue {
  font-size: 11px;
  color: #94a3b8;
  margin: 0 0 4px;
  font-family: 'JetBrains Mono', monospace;
}
.summary-panel__interpretation {
  font-size: 12px;
  color: #475569;
  margin: 0;
  line-height: 1.5;
}
.summary-panel__empty {
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 13px;
}
@media (max-width: 1480px) {
  .summary-panel { padding: 12px; }
}
@media (min-width: 1720px) {
  .summary-panel { padding: 20px; }
}
@media (prefers-reduced-motion: reduce) {
  .summary-panel,
  .summary-panel * {
    transition: none !important;
  }
}
</style>
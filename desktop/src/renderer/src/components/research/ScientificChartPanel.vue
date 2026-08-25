<script setup lang="ts">
import { computed } from 'vue'

export interface FigureItem {
  type: string
  title: string
  xVariable: string
  yVariable: string
  reason?: string
}

const props = withDefaults(defineProps<{
  figures?: FigureItem[]
  ariaLabel?: string
}>(), {
  figures: () => [],
  ariaLabel: '科学图表规划面板'
})

const itemList = computed(() => props.figures ?? [])
const isEmpty = computed(() => itemList.value.length === 0)
</script>

<template>
  <section class="chart-panel" :aria-label="ariaLabel">
    <button type="button" class="scientificchart-panel__focusable" @keydown.enter.prevent><span aria-hidden="true">.</span></button>
      <header class="scientificchart-panel__head">
      <h2 class="chart-panel__title">图表规划</h2>
      <span class="chart-panel__count">{{ itemList.length }} 项</span>
    </header>

    <ul v-if="!isEmpty" class="chart-panel__list">
      <li v-for="(figure, idx) in itemList" :key="idx" class="chart-panel__item">
        <div class="chart-panel__head-row">
          <span class="chart-panel__type" aria-hidden="true">{{ figure.type }}</span>
          <span class="chart-panel__title-text">{{ figure.title }}</span>
        </div>
        <p class="chart-panel__vars">
          <span>{{ figure.xVariable }}</span>
          <span aria-hidden="true">×</span>
          <span>{{ figure.yVariable }}</span>
        </p>
        <p class="chart-panel__reason">{{ figure.reason }}</p>
      </li>
    </ul>

    <div v-else class="chart-panel__empty" role="status">暂无图表</div>
  </section>
</template>

<style scoped>
.chart-panel {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
}
.chart-panel:focus-visible {
  outline: 2px solid var(--research-primary-500, #FF7A5C);
  outline-offset: 2px;
}
.chart-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.chart-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}
.chart-panel__count {
  font-size: 12px;
  color: #94a3b8;
}
.chart-panel__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.chart-panel__item {
  background: white;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 8px;
  padding: 12px;
}
.chart-panel__head-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.chart-panel__type {
  font-size: 11px;
  font-weight: 600;
  color: white;
  background: var(--research-primary-500, #FF7A5C);
  padding: 2px 6px;
  border-radius: 4px;
}
.chart-panel__title-text {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}
.chart-panel__vars {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: #475569;
  margin: 0 0 4px;
}
.chart-panel__reason {
  font-size: 11px;
  color: #94a3b8;
  margin: 0;
  line-height: 1.4;
}
.chart-panel__empty {
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 13px;
}
@media (max-width: 1480px) {
  .chart-panel { padding: 12px; }
}
@media (min-width: 1720px) {
  .chart-panel { padding: 20px; }
}
@media (prefers-reduced-motion: reduce) {
  .chart-panel,
  .chart-panel * {
    transition: none !important;
  }
}
</style>
<script setup lang="ts">
import { computed } from 'vue'

export interface FigureItem {
  figureId: string
  caption: string
  description: string
}

const props = withDefaults(defineProps<{
  figures?: FigureItem[]
  ariaLabel?: string
}>(), {
  figures: () => [],
  ariaLabel: '图表管理面板'
})

const figureItems = computed(() => props.figures ?? [])
</script>

<template>
  <section class="figure-manager-panel" :aria-label="ariaLabel">
    <header class="figure-manager-panel__head">
      <h2 class="figure-manager-panel__title">图表管理</h2>
      <span class="figure-manager-panel__count">{{ figureItems.length }} 张</span>
    </header>

    <ul v-if="figureItems.length > 0" class="figure-manager-panel__list">
      <li
        v-for="figure in figureItems"
        :key="figure.figureId"
        class="figure-manager-panel__item"
      >
        <div class="figure-manager-panel__head-row">
          <span class="figure-manager-panel__id">{{ figure.figureId }}</span>
          <span class="figure-manager-panel__caption">{{ figure.caption }}</span>
        </div>
        <p class="figure-manager-panel__description">{{ figure.description }}</p>
        <!-- [类 20.191] 2026-08-27: 删 '<span>图表占位</span>' literal stub.
             真图表渲染待 ECharts / Canvas 接入 (留 R3 hardening). 改为显示真实描述. -->
      </li>
    </ul>

    <div v-else class="figure-manager-panel__empty" role="status">暂无图表</div>
  </section>
</template>

<style scoped>
.figure-manager-panel {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
}
.figure-manager-panel:focus-visible {
  outline: 2px solid var(--research-primary-500, #FF7A5C);
  outline-offset: 2px;
}
.figure-manager-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.figure-manager-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}
.figure-manager-panel__count {
  font-size: 12px;
  color: #94a3b8;
}
.figure-manager-panel__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.figure-manager-panel__item {
  background: white;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 8px;
  padding: 12px;
}
.figure-manager-panel__head-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}
.figure-manager-panel__id {
  font-size: 11px;
  font-weight: 600;
  color: var(--research-primary-500, #FF7A5C);
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 122, 92, 0.08);
}
.figure-manager-panel__caption {
  font-size: 12px;
  font-weight: 600;
  color: #1e293b;
}
.figure-manager-panel__description {
  font-size: 11px;
  color: #475569;
  margin: 0 0 8px;
  line-height: 1.5;
}
.figure-manager-panel__placeholder {
  background: rgba(15, 23, 42, 0.04);
  border: 1px dashed rgba(15, 23, 42, 0.16);
  border-radius: 6px;
  padding: 16px;
  text-align: center;
  font-size: 11px;
  color: #94a3b8;
}
.figure-manager-panel__empty {
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 13px;
}
@media (max-width: 1480px) {
  .figure-manager-panel {
    padding: 12px;
  }
}
@media (min-width: 1720px) {
  .figure-manager-panel {
    padding: 20px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .figure-manager-panel,
  .figure-manager-panel * {
    transition: none !important;
  }
}
</style>
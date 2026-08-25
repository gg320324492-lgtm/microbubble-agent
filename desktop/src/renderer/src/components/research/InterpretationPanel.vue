<script setup lang="ts">
import { computed } from 'vue'

export interface Interpretation {
  observation: string
  interpretation: string
  confidence: number
}

const props = withDefaults(defineProps<{
  conclusions?: Interpretation[]
  ariaLabel?: string
}>(), {
  conclusions: () => [],
  ariaLabel: 'AI 解释面板'
})

const itemList = computed(() => props.conclusions ?? [])
const isEmpty = computed(() => itemList.value.length === 0)
</script>

<template>
  <section class="interpretation-panel" :aria-label="ariaLabel">
    <button type="button" class="interpretation-panel__focusable" @keydown.enter.prevent><span aria-hidden="true">.</span></button>
      <header class="interpretation-panel__head">
      <h2 class="interpretation-panel__title">科学解释</h2>
      <span class="interpretation-panel__count">{{ itemList.length }} 项</span>
    </header>

    <ul v-if="!isEmpty" class="interpretation-panel__list">
      <li v-for="(item, idx) in itemList" :key="idx" class="interpretation-panel__item">
        <div class="interpretation-panel__head-row">
          <span class="interpretation-panel__observation">{{ item.observation }}</span>
          <span class="interpretation-panel__confidence">
            置信度 {{ Math.round(item.confidence * 100) }}%
          </span>
        </div>
        <p class="interpretation-panel__interpretation">{{ item.interpretation }}</p>
      </li>
    </ul>

    <div v-else class="interpretation-panel__empty" role="status">暂无 AI 解释</div>
  </section>
</template>

<style scoped>
.interpretation-panel {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, #ffffff 0%, #fef3ec 100%);
  border: 1px solid rgba(255, 122, 92, 0.2);
  border-radius: 12px;
  padding: 16px;
}
.interpretation-panel:focus-visible {
  outline: 2px solid var(--research-primary-500, #FF7A5C);
  outline-offset: 2px;
}
.interpretation-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.interpretation-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}
.interpretation-panel__count {
  font-size: 12px;
  color: #94a3b8;
}
.interpretation-panel__list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.interpretation-panel__item {
  background: white;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 8px;
  padding: 12px;
}
.interpretation-panel__head-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 6px;
  gap: 8px;
}
.interpretation-panel__observation {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
  flex: 1;
}
.interpretation-panel__confidence {
  font-size: 11px;
  color: var(--research-primary-500, #FF7A5C);
  font-weight: 600;
  white-space: nowrap;
}
.interpretation-panel__interpretation {
  font-size: 12px;
  color: #475569;
  margin: 0;
  line-height: 1.5;
}
.interpretation-panel__empty {
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 13px;
}
@media (max-width: 1480px) {
  .interpretation-panel { padding: 12px; }
}
@media (min-width: 1720px) {
  .interpretation-panel { padding: 20px; }
}
@media (prefers-reduced-motion: reduce) {
  .interpretation-panel,
  .interpretation-panel * {
    transition: none !important;
  }
}
</style>
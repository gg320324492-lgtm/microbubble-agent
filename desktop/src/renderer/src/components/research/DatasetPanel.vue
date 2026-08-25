<script setup lang="ts">
import { computed } from 'vue'

export interface DatasetInfo {
  name: string
  description?: string
  rows?: number
  columns?: number
  variables?: string[]
}

const props = withDefaults(defineProps<{
  dataset?: DatasetInfo | null
  ariaLabel?: string
}>(), {
  dataset: null,
  ariaLabel: '数据集管理面板'
})

const displayName = computed(() => props.dataset?.name ?? '未选择数据集')
const displayRows = computed(() => props.dataset?.rows ?? 0)
const displayColumns = computed(() => props.dataset?.columns ?? 0)
const variableList = computed(() => props.dataset?.variables ?? [])
const isEmpty = computed(() => !props.dataset)
</script>

<template>
  <section class="dataset-panel" :aria-label="ariaLabel">
    <button type="button" class="dataset-panel__focusable" @keydown.enter.prevent><span aria-hidden="true">.</span></button>
      <header class="dataset-panel__head">
      <h2 class="dataset-panel__title">数据集</h2>
      <span v-if="!isEmpty" class="dataset-panel__count">{{ displayRows }} × {{ displayColumns }}</span>
    </header>

    <div v-if="!isEmpty" class="dataset-panel__body">
      <h3 class="dataset-panel__name">{{ displayName }}</h3>
      <p v-if="props.dataset && props.dataset.description" class="dataset-panel__description">
        {{ props.dataset.description }}
      </p>
      <div v-if="variableList.length > 0" class="dataset-panel__variables">
        <span class="dataset-panel__label">变量</span>
        <ul class="dataset-panel__list">
          <li v-for="(variable, idx) in variableList" :key="idx" class="dataset-panel__variable">
            {{ variable }}
          </li>
        </ul>
      </div>
    </div>

    <div v-else class="dataset-panel__empty" role="status">暂无数据集</div>
  </section>
</template>

<style scoped>
.dataset-panel {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
}
.dataset-panel:focus-visible {
  outline: 2px solid var(--research-primary-500, #FF7A5C);
  outline-offset: 2px;
}
.dataset-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.dataset-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}
.dataset-panel__count {
  font-size: 12px;
  color: #94a3b8;
}
.dataset-panel__name {
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
  margin: 0 0 8px;
}
.dataset-panel__description {
  font-size: 12px;
  color: #475569;
  margin: 0 0 12px;
  line-height: 1.5;
}
.dataset-panel__variables {
  margin-top: 8px;
}
.dataset-panel__label {
  font-size: 11px;
  color: #94a3b8;
  display: block;
  margin-bottom: 4px;
}
.dataset-panel__list {
  list-style: disc;
  padding-left: 20px;
  margin: 0;
}
.dataset-panel__variable {
  font-size: 12px;
  color: #1e293b;
  margin-bottom: 2px;
}
.dataset-panel__empty {
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 13px;
}
@media (max-width: 1480px) {
  .dataset-panel { padding: 12px; }
}
@media (min-width: 1720px) {
  .dataset-panel { padding: 20px; }
}
@media (prefers-reduced-motion: reduce) {
  .dataset-panel,
  .dataset-panel * {
    transition: none !important;
  }
}
</style>
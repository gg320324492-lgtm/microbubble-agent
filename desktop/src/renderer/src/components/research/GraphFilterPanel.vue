<script setup lang="ts">
import { computed } from 'vue'

export interface GraphFilters {
  entityTypes: string[]
  relationTypes: string[]
  searchTerm: string
}

const props = withDefaults(defineProps<{
  filters?: GraphFilters | null
  ariaLabel?: string
}>(), {
  filters: null,
  ariaLabel: '图谱过滤面板'
})

const isEmpty = computed(() => !props.filters)
const filter = computed(() => props.filters)
</script>

<template>
  <section class="graph-filter-panel" :aria-label="ariaLabel">
    <button type="button" class="graph-filter-panel__focusable" @keydown.enter.prevent><span aria-hidden="true">.</span></button>
    <header class="graph-filter-panel__head">
      <h2 class="graph-filter-panel__title">搜索与过滤</h2>
    </header>

    <div v-if="!isEmpty && filter" class="graph-filter-panel__body">
      <label class="graph-filter-panel__field">
        <span class="graph-filter-panel__label">搜索</span>
        <input
          class="graph-filter-panel__input"
          type="text"
          :value="filter.searchTerm"
          :placeholder="'输入节点名称...'"
          readonly
        />
      </label>
      <div class="graph-filter-panel__types">
        <span class="graph-filter-panel__label">实体类型</span>
        <ul class="graph-filter-panel__list">
          <li v-for="t in filter.entityTypes" :key="t" class="graph-filter-panel__tag">{{ t }}</li>
        </ul>
      </div>
      <div class="graph-filter-panel__types">
        <span class="graph-filter-panel__label">关系类型</span>
        <ul class="graph-filter-panel__list">
          <li v-for="t in filter.relationTypes" :key="t" class="graph-filter-panel__tag">{{ t }}</li>
        </ul>
      </div>
    </div>

    <div v-else class="graph-filter-panel__empty" role="status">暂无过滤条件</div>
  </section>
</template>

<style scoped>
.graph-filter-panel { min-width: 0; overflow-x: hidden; background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%); border: 1px solid rgba(15, 23, 42, 0.08); border-radius: 12px; padding: 16px; }
.graph-filter-panel:focus-visible { outline: 2px solid var(--research-primary-500, #FF7A5C); outline-offset: 2px; }
.graph-filter-panel__head { margin-bottom: 12px; }
.graph-filter-panel__title { font-size: 14px; font-weight: 600; color: #1e293b; margin: 0; }
.graph-filter-panel__field { display: block; margin-bottom: 12px; }
.graph-filter-panel__label { display: block; font-size: 12px; color: #475569; margin-bottom: 4px; }
.graph-filter-panel__input { width: 100%; padding: 6px 10px; border: 1px solid rgba(15, 23, 42, 0.12); border-radius: 6px; font-size: 12px; }
.graph-filter-panel__types { margin-bottom: 8px; }
.graph-filter-panel__list { list-style: none; padding: 0; margin: 4px 0 0; display: flex; flex-wrap: wrap; gap: 4px; }
.graph-filter-panel__tag { font-size: 11px; padding: 2px 8px; background: rgba(15, 23, 42, 0.04); border-radius: 4px; }
.graph-filter-panel__empty { text-align: center; padding: 24px; color: #94a3b8; font-size: 13px; }
@media (max-width: 1480px) { .graph-filter-panel { padding: 12px; } }
@media (min-width: 1720px) { .graph-filter-panel { padding: 20px; } }
@media (prefers-reduced-motion: reduce) { .graph-filter-panel, .graph-filter-panel * { transition: none !important; } }
</style>
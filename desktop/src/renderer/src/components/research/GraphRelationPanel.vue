<script setup lang="ts">
import { computed } from 'vue'

export interface GraphRelation {
  id: string
  source: string
  target: string
  type: string
  evidence?: string
}

const props = withDefaults(defineProps<{
  relations?: GraphRelation[]
  ariaLabel?: string
}>(), {
  relations: () => [],
  ariaLabel: '关系列表面板'
})

const relationList = computed(() => props.relations ?? [])
const isEmpty = computed(() => relationList.value.length === 0)
</script>

<template>
  <section class="graph-relation-panel" :aria-label="ariaLabel">
    <button type="button" class="graph-relation-panel__focusable" @keydown.enter.prevent><span aria-hidden="true">.</span></button>
    <header class="graph-relation-panel__head">
      <h2 class="graph-relation-panel__title">关系</h2>
      <span class="graph-relation-panel__count">{{ relationList.length }} 条</span>
    </header>

    <ul v-if="!isEmpty" class="graph-relation-panel__list">
      <li v-for="rel in relationList" :key="rel.id" class="graph-relation-panel__item">
        <div class="graph-relation-panel__row">
          <span class="graph-relation-panel__source">{{ rel.source }}</span>
          <span class="graph-relation-panel__type" aria-hidden="true">→</span>
          <span class="graph-relation-panel__target">{{ rel.target }}</span>
        </div>
        <span class="graph-relation-panel__kind">{{ rel.type }}</span>
        <p v-if="rel.evidence" class="graph-relation-panel__evidence">{{ rel.evidence }}</p>
      </li>
    </ul>

    <div v-else class="graph-relation-panel__empty" role="status">暂无关系</div>
  </section>
</template>

<style scoped>
.graph-relation-panel { min-width: 0; overflow-x: hidden; background: #fff; border: 1px solid rgba(15, 23, 42, 0.08); border-radius: 12px; padding: 16px; }
.graph-relation-panel:focus-visible { outline: 2px solid var(--research-primary-500, #FF7A5C); outline-offset: 2px; }
.graph-relation-panel__head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }
.graph-relation-panel__title { font-size: 14px; font-weight: 600; color: #1e293b; margin: 0; }
.graph-relation-panel__count { font-size: 12px; color: #94a3b8; }
.graph-relation-panel__list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 6px; }
.graph-relation-panel__item { padding: 8px 10px; background: rgba(15, 23, 42, 0.02); border-radius: 6px; }
.graph-relation-panel__row { display: flex; gap: 6px; align-items: center; font-size: 12px; color: #1e293b; margin-bottom: 4px; }
.graph-relation-panel__source, .graph-relation-panel__target { font-weight: 600; }
.graph-relation-panel__type { color: #FF7A5C; font-size: 11px; }
.graph-relation-panel__kind { font-size: 11px; color: #94a3b8; padding: 1px 6px; border-radius: 4px; background: rgba(15, 23, 42, 0.04); }
.graph-relation-panel__evidence { font-size: 11px; color: #475569; margin: 4px 0 0; line-height: 1.4; }
.graph-relation-panel__empty { text-align: center; padding: 24px; color: #94a3b8; font-size: 13px; }
@media (max-width: 1480px) { .graph-relation-panel { padding: 12px; } }
@media (min-width: 1720px) { .graph-relation-panel { padding: 20px; } }
@media (prefers-reduced-motion: reduce) { .graph-relation-panel, .graph-relation-panel * { transition: none !important; } }
</style>
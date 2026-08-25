<script setup lang="ts">
import { computed } from 'vue'

export interface EvidenceItem {
  source: string
  page: number
  citation: string
  excerpt?: string
}

const props = withDefaults(defineProps<{
  evidence?: EvidenceItem[]
  ariaLabel?: string
}>(), {
  evidence: () => [],
  ariaLabel: '证据追踪面板'
})

const evidenceList = computed(() => props.evidence ?? [])
const isEmpty = computed(() => evidenceList.value.length === 0)
</script>

<template>
  <section class="evidence-trace-panel" :aria-label="ariaLabel">
    <button type="button" class="evidence-trace-panel__focusable" @keydown.enter.prevent><span aria-hidden="true">.</span></button>
    <header class="evidence-trace-panel__head">
      <h2 class="evidence-trace-panel__title">证据追踪</h2>
      <span class="evidence-trace-panel__count">{{ evidenceList.length }} 条</span>
    </header>

    <ul v-if="!isEmpty" class="evidence-trace-panel__list">
      <li v-for="(ev, idx) in evidenceList" :key="idx" class="evidence-trace-panel__item">
        <div class="evidence-trace-panel__head-row">
          <span class="evidence-trace-panel__source">{{ ev.source }}</span>
          <span class="evidence-trace-panel__page">第 {{ ev.page }} 页</span>
        </div>
        <p class="evidence-trace-panel__citation">{{ ev.citation }}</p>
        <p v-if="ev.excerpt" class="evidence-trace-panel__excerpt">{{ ev.excerpt }}</p>
      </li>
    </ul>

    <div v-else class="evidence-trace-panel__empty" role="status">暂无证据</div>
  </section>
</template>

<style scoped>
.evidence-trace-panel { min-width: 0; overflow-x: hidden; background: #fff; border: 1px solid rgba(15, 23, 42, 0.08); border-radius: 12px; padding: 16px; }
.evidence-trace-panel:focus-visible { outline: 2px solid var(--research-primary-500, #FF7A5C); outline-offset: 2px; }
.evidence-trace-panel__head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }
.evidence-trace-panel__title { font-size: 14px; font-weight: 600; color: #1e293b; margin: 0; }
.evidence-trace-panel__count { font-size: 12px; color: #94a3b8; }
.evidence-trace-panel__list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.evidence-trace-panel__item { padding: 8px 10px; background: rgba(15, 23, 42, 0.02); border-radius: 6px; }
.evidence-trace-panel__head-row { display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px; }
.evidence-trace-panel__source { color: #1e293b; font-weight: 600; }
.evidence-trace-panel__page { color: #94a3b8; }
.evidence-trace-panel__citation { font-size: 12px; color: #475569; margin: 0 0 4px; line-height: 1.4; }
.evidence-trace-panel__excerpt { font-size: 11px; color: #94a3b8; margin: 0; line-height: 1.4; font-style: italic; }
.evidence-trace-panel__empty { text-align: center; padding: 24px; color: #94a3b8; font-size: 13px; }
@media (max-width: 1480px) { .evidence-trace-panel { padding: 12px; } }
@media (min-width: 1720px) { .evidence-trace-panel { padding: 20px; } }
@media (prefers-reduced-motion: reduce) { .evidence-trace-panel, .evidence-trace-panel * { transition: none !important; } }
</style>
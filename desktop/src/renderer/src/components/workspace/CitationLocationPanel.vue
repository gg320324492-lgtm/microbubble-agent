<script setup lang="ts">
import { computed } from 'vue'

export interface CitationItem {
  refId: string
  authors: string
  title: string
  journal: string
  year: number
  doi?: string
}

const props = withDefaults(defineProps<{
  citations?: CitationItem[]
  ariaLabel?: string
}>(), {
  citations: () => [],
  ariaLabel: '引用定位面板'
})

const citationItems = computed(() => props.citations ?? [])
</script>

<template>
  <section class="citation-location-panel" :aria-label="ariaLabel">
    <header class="citation-location-panel__head">
      <h2 class="citation-location-panel__title">引用定位</h2>
      <span class="citation-location-panel__count">{{ citationItems.length }} 项</span>
    </header>

    <ol v-if="citationItems.length > 0" class="citation-location-panel__list">
      <li
        v-for="citation in citationItems"
        :key="citation.refId"
        class="citation-location-panel__item"
      >
        <div class="citation-location-panel__ref">{{ citation.refId }}</div>
        <div class="citation-location-panel__body">
          <div class="citation-location-panel__authors">{{ citation.authors }}</div>
          <div class="citation-location-panel__title-text">{{ citation.title }}</div>
          <div class="citation-location-panel__meta">
            <span>{{ citation.journal }}</span>
            <span>{{ citation.year }}</span>
            <span v-if="citation.doi">DOI: {{ citation.doi }}</span>
          </div>
        </div>
      </li>
    </ol>

    <div v-else class="citation-location-panel__empty" role="status">暂无引用</div>
  </section>
</template>

<style scoped>
.citation-location-panel {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
}
.citation-location-panel:focus-visible {
  outline: 2px solid var(--research-primary-500, #FF7A5C);
  outline-offset: 2px;
}
.citation-location-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.citation-location-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}
.citation-location-panel__count {
  font-size: 12px;
  color: #94a3b8;
}
.citation-location-panel__list {
  list-style: decimal;
  padding: 0 0 0 24px;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.citation-location-panel__item {
  min-width: 0;
}
.citation-location-panel__ref {
  font-size: 11px;
  font-weight: 600;
  color: var(--research-primary-500, #FF7A5C);
}
.citation-location-panel__body {
  margin-top: 2px;
}
.citation-location-panel__authors {
  font-size: 12px;
  font-weight: 600;
  color: #1e293b;
}
.citation-location-panel__title-text {
  font-size: 12px;
  color: #1e293b;
  line-height: 1.5;
  margin-top: 2px;
}
.citation-location-panel__meta {
  display: flex;
  gap: 8px;
  font-size: 11px;
  color: #94a3b8;
  margin-top: 4px;
  flex-wrap: wrap;
}
.citation-location-panel__empty {
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 13px;
}
@media (max-width: 1480px) {
  .citation-location-panel {
    padding: 12px;
  }
}
@media (min-width: 1720px) {
  .citation-location-panel {
    padding: 20px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .citation-location-panel,
  .citation-location-panel * {
    transition: none !important;
  }
}
</style>
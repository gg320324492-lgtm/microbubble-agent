<script lang="ts">
/** 可由不同研究模块提供的灵活证据展示字段。 */
export interface EvidenceItem {
  id?: string | number
  title?: string
  label?: string
  value?: string | number
  description?: string
  summary?: string
  source?: string
  confidence?: number
  url?: string
}

/** 可由不同研究模块提供的灵活引用展示字段。 */
export interface CitationItem {
  id?: string | number
  title?: string
  authors?: string
  year?: string | number
  source?: string
  doi?: string
  url?: string
}
</script>

<script setup lang="ts">
const props = withDefaults(defineProps<{
  evidence?: EvidenceItem[]
  citations?: CitationItem[]
  ariaLabel?: string
}>(), {
  evidence: () => [],
  citations: () => [],
  ariaLabel: '证据与引用'
})

const evidenceTitle = (item: EvidenceItem): string => item.title ?? item.label ?? '未命名证据'
const evidenceBody = (item: EvidenceItem): string | number | undefined =>
  item.description ?? item.summary ?? item.value
const citationTitle = (item: CitationItem): string => item.title ?? '未命名引用'
const citationMeta = (item: CitationItem): string[] =>
  [item.authors, item.year === undefined ? undefined : String(item.year), item.source, item.doi]
    .filter((value): value is string => Boolean(value))
</script>

<template>
  <section class="evidence-panel" :aria-label="props.ariaLabel">
    <div class="evidence-panel__section">
      <h2 class="evidence-panel__title">证据</h2>
      <div v-if="props.evidence.length" class="evidence-panel__list" role="list">
        <component
          :is="item.url ? 'a' : 'article'"
          v-for="(item, index) in props.evidence"
          :key="item.id ?? item.title ?? item.label ?? index"
          class="evidence-panel__item"
          :href="item.url"
          role="listitem"
        >
          <span class="evidence-panel__marker" aria-hidden="true">证</span>
          <span class="evidence-panel__content">
            <span class="evidence-panel__item-title">{{ evidenceTitle(item) }}</span>
            <span v-if="evidenceBody(item) !== undefined" class="evidence-panel__body">{{ evidenceBody(item) }}</span>
            <span v-if="item.source" class="evidence-panel__source">来源：{{ item.source }}</span>
            <span v-if="item.confidence !== undefined" class="evidence-panel__confidence">
              置信度：{{ Math.round(item.confidence * 100) }}%
            </span>
          </span>
        </component>
      </div>
      <p v-else class="evidence-panel__empty" role="status">暂无证据</p>
    </div>

    <div class="evidence-panel__section evidence-panel__section--citations">
      <h2 class="evidence-panel__title">引用</h2>
      <ol v-if="props.citations.length" class="evidence-panel__citations">
        <li v-for="(item, index) in props.citations" :key="item.id ?? item.title ?? index">
          <component :is="item.url ? 'a' : 'span'" class="evidence-panel__citation" :href="item.url">
            <span class="evidence-panel__citation-title">{{ citationTitle(item) }}</span>
            <span v-if="citationMeta(item).length" class="evidence-panel__citation-meta">
              {{ citationMeta(item).join(' · ') }}
            </span>
          </component>
        </li>
      </ol>
      <p v-else class="evidence-panel__empty" role="status">暂无引用来源</p>
    </div>
  </section>
</template>

<style scoped>
.evidence-panel {
  display: grid;
  min-width: 0;
  gap: var(--research-space-5);
  padding: var(--research-space-5);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-panel);
  background: var(--research-bg-card);
  box-shadow: var(--research-shadow-soft);
}

.evidence-panel__section { min-width: 0; }
.evidence-panel__section--citations { padding-top: var(--research-space-5); border-top: 1px solid var(--research-divider); }

.evidence-panel__title {
  margin: 0 0 var(--research-space-3);
  color: var(--research-text-primary);
  font-size: var(--research-text-section-title);
  font-weight: var(--research-font-weight-semibold);
  line-height: var(--research-line-height-tight);
}

.evidence-panel__list { display: grid; gap: var(--research-space-3); }

.evidence-panel__item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--research-space-3);
  min-width: 0;
  padding: var(--research-space-3);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-card);
  background: var(--research-bg-panel);
  color: inherit;
  text-decoration: none;
}

a.evidence-panel__item:focus-visible,
a.evidence-panel__citation:focus-visible {
  border-radius: var(--research-radius-sm);
  outline: none;
  box-shadow: var(--research-shadow-focus-primary);
}

.evidence-panel__marker {
  display: grid;
  width: var(--research-space-5);
  height: var(--research-space-5);
  place-items: center;
  border-radius: var(--research-radius-pill);
  background: var(--research-primary-50);
  color: var(--research-primary-700);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-semibold);
}

.evidence-panel__content { display: grid; min-width: 0; gap: var(--research-space-1); }

.evidence-panel__item-title,
.evidence-panel__citation-title {
  color: var(--research-text-primary);
  font-size: var(--research-text-body);
  font-weight: var(--research-font-weight-medium);
  line-height: var(--research-line-height-body);
  overflow-wrap: anywhere;
}

.evidence-panel__body,
.evidence-panel__source,
.evidence-panel__confidence,
.evidence-panel__citation-meta {
  color: var(--research-text-secondary);
  font-size: var(--research-text-sm);
  line-height: var(--research-line-height-body);
  overflow-wrap: anywhere;
}

.evidence-panel__citations {
  display: grid;
  gap: var(--research-space-2);
  margin: 0;
  padding-inline-start: var(--research-space-5);
}

.evidence-panel__citation { color: inherit; text-decoration: none; }
.evidence-panel__citation-meta { margin-inline-start: var(--research-space-2); }

.evidence-panel__empty {
  margin: 0;
  color: var(--research-text-secondary);
  font-size: var(--research-text-body);
  line-height: var(--research-line-height-body);
}
</style>

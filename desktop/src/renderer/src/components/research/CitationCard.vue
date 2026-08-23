<script setup lang="ts">
/**
 * 引用卡片 — 论文引用信息展示。
 */
import ResearchIcon from '../icons/ResearchIcon.vue'

const props = withDefaults(defineProps<{
  index: number
  authors: string
  title: string
  journal: string
  year: number
  tags?: string[]
  citedBy?: number
  relevance?: number
  evidenceLevel?: number
  location?: string
  documentId?: string
  active?: boolean
  selectable?: boolean
}>(), {
  selectable: false
})

const emit = defineEmits<{
  select: [documentId?: string]
  openLocation: [documentId?: string]
}>()

function selectCard() {
  if (!props.selectable) return
  emit('select', props.documentId)
}

function onSelectKeydown(event: KeyboardEvent) {
  if (event.key !== 'Enter' && event.key !== ' ') return
  event.preventDefault()
  event.stopPropagation()
  selectCard()
}

function openLocation() {
  emit('openLocation', props.documentId)
}
</script>

<template>
  <article
    :class="['citation-card', { 'citation-card--active': active, 'citation-card--selectable': selectable }]"
    :data-document-id="documentId"
    role="listitem"
    :aria-label="`文献：${title}`"
  >
    <component
      :is="selectable ? 'button' : 'div'"
      class="citation-card__select"
      :type="selectable ? 'button' : undefined"
      :aria-label="selectable ? `选择文献：${title}` : undefined"
      :aria-pressed="selectable ? (active ? 'true' : 'false') : undefined"
      @click="selectCard"
      @keydown="onSelectKeydown"
    >
      <div class="citation-card__num"><ResearchIcon name="citation" :size="13" /><span>{{ index }}</span></div>
      <div class="citation-card__body">
        <div class="citation-card__title">{{ title }}</div>
        <div class="citation-card__secondary">
          <div class="citation-card__meta">{{ authors }} · {{ journal }}, {{ year }}</div>
          <div v-if="relevance !== undefined || evidenceLevel !== undefined" class="citation-card__evidence">
            <span v-if="relevance !== undefined">相关度 {{ Math.round(Math.max(0, Math.min(1, relevance)) * 100) }}%</span>
            <span v-if="evidenceLevel !== undefined">证据等级 {{ evidenceLevel }}/5</span>
          </div>
          <div v-if="tags?.length" class="citation-card__tags">
            <span v-for="t in tags" :key="t" class="citation-card__tag">{{ t }}</span>
          </div>
          <div v-if="citedBy !== undefined" class="citation-card__cited">被引 {{ citedBy }}</div>
        </div>
      </div>
    </component>
    <button
      v-if="location"
      class="citation-card__location"
      type="button"
      :data-testid="`citation-location-${documentId ?? index}`"
      :aria-label="`查看《${title}》的引用位置`"
      @click.stop="openLocation"
      @keydown.enter.stop.prevent="openLocation"
      @keydown.space.stop.prevent="openLocation"
    >
      <ResearchIcon name="progress" :size="13" />
      引用位置 {{ location }}
    </button>
  </article>
</template>

<style scoped>
.citation-card { display: flex; flex-wrap: wrap; gap: 0; padding: var(--research-space-3) var(--research-space-4); background: var(--research-bg-card); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); transition: border-color var(--research-duration-fast) var(--research-ease-standard), box-shadow var(--research-duration-fast) var(--research-ease-standard), transform var(--research-duration-fast) var(--research-ease-standard); }
.citation-card:hover { border-color: var(--research-primary-200); box-shadow: var(--research-shadow-soft); transform: translateY(-1px); }
.citation-card:focus-within { border-color: var(--research-primary-500); box-shadow: var(--research-shadow-focus-primary); }
.citation-card--active { border-color: var(--research-primary-400); background: var(--research-primary-50); box-shadow: var(--research-shadow-soft); }
.citation-card__select { display: flex; width: 100%; min-width: 0; gap: var(--research-space-3); padding: 0; border: 0; background: transparent; color: inherit; font: inherit; text-align: left; }
button.citation-card__select { cursor: pointer; }
.citation-card__select:focus-visible { outline: none; }
.citation-card__num { min-width: 42px; height: 28px; padding-inline: var(--research-space-2); border-radius: var(--research-radius-pill); background: var(--research-primary-50); color: var(--research-primary-600); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-bold); display: flex; gap: var(--research-space-1); align-items: center; justify-content: center; flex-shrink: 0; }
.citation-card__body { flex: 1; min-width: 0; }
.citation-card__title { font-size: var(--research-text-body); font-weight: var(--research-font-weight-medium); color: var(--research-text-primary); margin-bottom: var(--research-space-1); line-height: var(--research-line-height-body); }
.citation-card__secondary { max-height: 0; overflow: hidden; opacity: 0; transition: max-height var(--research-duration-normal) var(--research-ease-standard), opacity var(--research-duration-fast) var(--research-ease-standard); }
.citation-card:hover .citation-card__secondary { max-height: 260px; opacity: 1; }
.citation-card:focus-within .citation-card__secondary { max-height: 260px; opacity: 1; }
.citation-card__meta { font-size: var(--research-text-sm); color: var(--research-text-secondary); }
.citation-card__evidence { display: flex; flex-wrap: wrap; gap: var(--research-space-2); margin-top: var(--research-space-2); color: var(--research-success-700); font-size: var(--research-text-xs); font-variant-numeric: tabular-nums; }
.citation-card__tags { display: flex; gap: var(--research-space-1); margin-top: var(--research-space-2); flex-wrap: wrap; }
.citation-card__tag { font-size: var(--research-text-xs); padding: var(--research-space-1) var(--research-space-2); background: var(--research-primary-50); color: var(--research-primary-700); border-radius: var(--research-radius-pill); }
.citation-card__cited { margin-top: var(--research-space-2); font-size: var(--research-text-sm); color: var(--research-text-secondary); white-space: nowrap; font-variant-numeric: tabular-nums; }
.citation-card__location { display: inline-flex; max-height: 0; align-items: center; gap: var(--research-space-1); margin: 0 0 0 54px; padding: 0; overflow: hidden; border: 0; opacity: 0; background: transparent; color: var(--research-primary-700); font: inherit; font-size: var(--research-text-xs); cursor: pointer; transition: max-height var(--research-duration-normal) var(--research-ease-standard), margin-top var(--research-duration-normal) var(--research-ease-standard), opacity var(--research-duration-fast) var(--research-ease-standard); }
.citation-card:hover .citation-card__location,
.citation-card:focus-within .citation-card__location { max-height: 28px; margin-top: var(--research-space-2); opacity: 1; }
.citation-card__location:focus-visible { outline: none; border-radius: var(--research-radius-input); box-shadow: var(--research-shadow-focus-primary); }

@media (prefers-reduced-motion: reduce) {
  .citation-card, .citation-card__secondary, .citation-card__location { transition: none; }
  .citation-card:hover { transform: none; }
}
</style>

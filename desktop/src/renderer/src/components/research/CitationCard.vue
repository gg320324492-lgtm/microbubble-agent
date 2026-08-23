<script setup lang="ts">
/**
 * 引用卡片 — 论文引用信息展示。
 */
import ResearchIcon from '../icons/ResearchIcon.vue'

defineProps<{
  index: number
  authors: string
  title: string
  journal: string
  year: number
  tags?: string[]
  citedBy?: number
}>()

</script>

<template>
  <div class="citation-card">
    <div class="citation-card__num"><ResearchIcon name="citation" :size="13" /><span>{{ index }}</span></div>
    <div class="citation-card__body">
      <div class="citation-card__title">{{ title }}</div>
      <div class="citation-card__meta">{{ authors }} · {{ journal }}, {{ year }}</div>
      <div v-if="tags?.length" class="citation-card__tags">
        <span v-for="t in tags" :key="t" class="citation-card__tag">{{ t }}</span>
      </div>
    </div>
    <div v-if="citedBy !== undefined" class="citation-card__cited">被引 {{ citedBy }}</div>
  </div>
</template>

<style scoped>
.citation-card { display: flex; gap: var(--research-space-3); padding: var(--research-space-3) var(--research-space-4); background: var(--research-bg-card); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); }
.citation-card__num { min-width: 42px; height: 28px; padding-inline: var(--research-space-2); border-radius: var(--research-radius-pill); background: var(--research-primary-50); color: var(--research-primary-600); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-bold); display: flex; gap: var(--research-space-1); align-items: center; justify-content: center; flex-shrink: 0; }
.citation-card__body { flex: 1; min-width: 0; }
.citation-card__title { font-size: var(--research-text-body); font-weight: var(--research-font-weight-medium); color: var(--research-text-primary); margin-bottom: var(--research-space-1); line-height: var(--research-line-height-body); }
.citation-card__meta { font-size: var(--research-text-sm); color: var(--research-text-secondary); }
.citation-card__tags { display: flex; gap: var(--research-space-1); margin-top: var(--research-space-2); flex-wrap: wrap; }
.citation-card__tag { font-size: var(--research-text-xs); padding: var(--research-space-1) var(--research-space-2); background: var(--research-primary-50); color: var(--research-primary-700); border-radius: var(--research-radius-pill); }
.citation-card__cited { font-size: var(--research-text-sm); color: var(--research-text-secondary); white-space: nowrap; font-variant-numeric: tabular-nums; }
</style>

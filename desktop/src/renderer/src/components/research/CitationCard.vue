<script setup lang="ts">
/**
 * 引用卡片 — 论文引用信息展示。
 */
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
    <div class="citation-card__num">{{ index }}</div>
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
.citation-card { display: flex; gap: 12px; padding: 12px 14px; background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; }
.citation-card__num { width: 28px; height: 28px; border-radius: 50%; background: #eff6ff; color: #3b82f6; font-size: 12px; font-weight: 700; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.citation-card__body { flex: 1; min-width: 0; }
.citation-card__title { font-size: 13px; font-weight: 500; color: #1e293b; margin-bottom: 2px; }
.citation-card__meta { font-size: 12px; color: #64748b; }
.citation-card__tags { display: flex; gap: 4px; margin-top: 6px; flex-wrap: wrap; }
.citation-card__tag { font-size: 11px; padding: 2px 8px; background: #f0f9ff; color: #2563eb; border-radius: 4px; }
.citation-card__cited { font-size: 12px; color: #64748b; white-space: nowrap; }
</style>

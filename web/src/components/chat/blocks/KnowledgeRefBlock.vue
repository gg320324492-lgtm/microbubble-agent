<script setup>
/**
 * KnowledgeRefBlock.vue — 知识库引用卡
 *
 * 接收 block.data = {results: [{id, title, content, score, category, tags, source}]}
 */
import { useRouter } from 'vue-router'
const props = defineProps({ block: { type: Object, required: true } })
const router = useRouter()

const results = (props.block.data || {}).results || []

const stripHtml = (html) => {
  if (!html) return ''
  return html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
}

const goToKnowledge = (id) => { if (id) router.push(`/knowledge/${id}`) }
</script>

<template>
  <div class="kb-ref rich-card">
    <div class="card-header">
      <span class="icon">📚</span>
      <span class="title">{{ block.title || '知识引用' }} ({{ results.length }})</span>
    </div>
    <div v-for="r in results" :key="r.id" class="ref-item" @click="goToKnowledge(r.id)">
      <div class="ref-title">{{ r.title }}</div>
      <div class="ref-content">{{ stripHtml(r.content).slice(0, 200) }}{{ stripHtml(r.content).length > 200 ? '...' : '' }}</div>
      <div class="ref-meta">
        <span v-if="r.category" class="meta">📁 {{ r.category }}</span>
        <span v-if="r.source" class="meta">📎 {{ r.source }}</span>
        <span v-if="r.score != null" class="meta score">⭐ {{ (r.score * 100).toFixed(0) }}%</span>
        <span v-for="tag in (r.tags || []).slice(0, 3)" :key="tag" class="tag">{{ tag }}</span>
      </div>
    </div>
    <div v-if="!results.length" class="empty">暂无知识</div>
  </div>
</template>

<style scoped>
.rich-card { background: white; border: 1px solid #e8eaed; border-radius: 10px; padding: 12px 14px; margin: 8px 0; box-shadow: var(--shadow-xs); }
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 14px; margin-bottom: 10px; color: var(--color-primary); }
.icon { font-size: 18px; }
.ref-item { padding: 10px 0; border-top: 1px solid #f0f1f3; cursor: pointer; transition: background 0.15s; }
.ref-item:first-of-type { border-top: none; }
.ref-item:hover { background: var(--color-bg-warm); margin: 0 -8px; padding: 10px 8px; border-radius: 6px; }
.ref-title { font-weight: 500; font-size: 14px; color: var(--color-primary); }
.ref-content { font-size: 13px; color: var(--color-text-regular); margin-top: 4px; line-height: 1.5; }
.ref-meta { display: flex; gap: 8px; margin-top: 6px; flex-wrap: wrap; }
.meta { font-size: 11px; color: #888; }
.meta.score { color: var(--color-warning); font-weight: 500; }
.tag { font-size: 11px; background: var(--color-bg-hover); color: var(--color-text-regular); padding: 1px 6px; border-radius: 8px; }
.empty { text-align: center; color: var(--color-text-secondary); padding: 20px 0; font-size: 13px; }
</style>

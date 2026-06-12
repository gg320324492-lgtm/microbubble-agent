<script setup>
/**
 * FallbackBlock.vue — 兜底 block，未识别 type 渲染为 markdown
 */
import { marked } from 'marked'
import { computed } from 'vue'
const props = defineProps({ block: { type: Object, required: true } })
marked.setOptions({ breaks: true, gfm: true })

const html = computed(() => {
  const data = props.block?.data || {}
  // 优先 data.content 字段，其次整个 JSON
  const text = data.content || data.text || JSON.stringify(data, null, 2)
  return marked.parse(text)
})
</script>

<template>
  <div class="fallback-block">
    <div v-if="block.title" class="fb-title">{{ block.title }}</div>
    <div class="fb-content" v-html="html" />
  </div>
</template>

<style scoped>
.fallback-block {
  background: #fafbfc;
  border-left: 3px solid #FF7A5C;
  padding: 8px 12px;
  margin: 8px 0;
  border-radius: 4px;
  font-size: 13px;
}
.fb-title { font-weight: 600; margin-bottom: 4px; }
.fb-content :deep(pre) { background: white; padding: 6px; border-radius: 4px; overflow-x: auto; font-size: 12px; }
</style>

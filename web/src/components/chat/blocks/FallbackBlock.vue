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
  background: var(--color-bg-warm);
  border-left: 3px solid var(--color-primary);
  padding: 8px 12px;
  margin: 8px 0;
  border-radius: 4px;
  font-size: 13px;
}
.fb-title { font-weight: 600; margin-bottom: 4px; }
.fb-content :deep(pre) { background: var(--color-bg-card); padding: 6px; border-radius: 4px; overflow-x: auto; font-size: 12px; }
</style>

<!-- v77 P2.6-B: dark mode 适配（v60-v67 教训：必须非 scoped） -->
<style>
[data-theme="dark"] .fallback-block {
  background: var(--color-bg-warm);
  color: var(--color-text-regular);
}
[data-theme="dark"] .fb-title {
  color: var(--color-text-primary);
}
[data-theme="dark"] .fb-content {
  color: var(--color-text-regular);
}
[data-theme="dark"] .fb-content :deep(pre) {
  background: var(--color-bg-page);
  color: var(--color-text-primary);
  border: 1px solid var(--color-border-light);
}
[data-theme="dark"] .fb-content :deep(code) {
  color: var(--color-text-primary);
  background: var(--color-bg-page);
}
[data-theme="dark"] .fb-content :deep(a) {
  color: var(--color-primary);
}
</style>

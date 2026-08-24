<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  description?: string
}>(), {
  title: 'AI 正在分析...',
  description: '正在整理科研数据与证据，请稍候。'
})
</script>

<template>
  <section class="research-loading-state" role="status" aria-live="polite" aria-busy="true">
    <span class="research-loading-state__indicator" aria-hidden="true" />
    <h2>{{ title }}</h2>
    <p>{{ description }}</p>
  </section>
</template>

<style scoped>
.research-loading-state { display: grid; min-height: 208px; place-items: center; align-content: center; padding: var(--research-space-8); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-lg); background: var(--research-bg-panel); color: var(--research-text-secondary); text-align: center; }
.research-loading-state__indicator { width: 28px; height: 28px; margin-block-end: var(--research-space-3); border: 3px solid var(--research-ai-100); border-top-color: var(--research-ai-500); border-radius: 50%; animation: research-loading-spin var(--research-duration-slow) var(--research-ease-linear) infinite; }
.research-loading-state h2, .research-loading-state p { margin: 0; }
.research-loading-state h2 { color: var(--research-text-primary); font-size: var(--research-text-card-title); }
.research-loading-state p { margin-block-start: var(--research-space-2); font-size: var(--research-text-sm); }
@keyframes research-loading-spin { to { transform: rotate(1turn); } }
@media (prefers-reduced-motion: reduce) { .research-loading-state__indicator { animation: none; } }
</style>

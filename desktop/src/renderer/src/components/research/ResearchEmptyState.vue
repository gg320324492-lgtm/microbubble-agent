<script setup lang="ts">
withDefaults(defineProps<{
  title?: string
  description?: string
}>(), {
  title: '暂无科研数据',
  description: '导入资料或创建研究任务后，这里会显示结果。'
})
</script>

<template>
  <section class="research-empty-state" role="status" aria-live="polite">
    <div class="research-empty-state__mark" aria-hidden="true">—</div>
    <h2>{{ title }}</h2>
    <p>{{ description }}</p>
    <div v-if="$slots.actions" class="research-empty-state__actions"><slot name="actions" /></div>
  </section>
</template>

<style scoped>
.research-empty-state { display: grid; min-height: 208px; place-items: center; align-content: center; padding: var(--research-space-8); border: 1px dashed var(--research-border-strong); border-radius: var(--research-radius-lg); background: var(--research-bg-panel); color: var(--research-text-secondary); text-align: center; }
.research-empty-state__mark { display: grid; width: 42px; height: 42px; margin-block-end: var(--research-space-3); place-items: center; border-radius: var(--research-radius-md); background: var(--research-coral-50); color: var(--research-coral-500); }
.research-empty-state h2, .research-empty-state p { margin: 0; }
.research-empty-state h2 { color: var(--research-text-primary); font-size: var(--research-text-card-title); }
.research-empty-state p { max-width: 420px; margin-block-start: var(--research-space-2); font-size: var(--research-text-sm); }
.research-empty-state__actions { display: flex; gap: var(--research-space-2); margin-block-start: var(--research-space-4); }
</style>

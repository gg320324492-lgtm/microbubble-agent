<script setup lang="ts">
defineProps<{
  title: string
  description?: string
  eyebrow?: string
  status?: string
}>()
</script>

<template>
  <header class="research-page-header">
    <div class="research-page-header__copy">
      <p v-if="eyebrow" class="research-page-header__eyebrow">{{ eyebrow }}</p>
      <div class="research-page-header__title-row">
        <h1>{{ title }}</h1>
        <span v-if="status" class="research-page-header__status">{{ status }}</span>
      </div>
      <p v-if="description" class="research-page-header__description">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="research-page-header__actions"><slot name="actions" /></div>
  </header>
</template>

<style scoped>
.research-page-header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--research-space-6); margin-block-end: var(--research-space-6); }
.research-page-header__copy { min-width: 0; }
.research-page-header__eyebrow { margin: 0 0 var(--research-space-2); color: var(--research-coral-500); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); letter-spacing: .08em; }
.research-page-header__title-row { display: flex; align-items: center; gap: var(--research-space-3); flex-wrap: wrap; }
.research-page-header h1 { margin: 0; color: var(--research-text-primary); font-size: var(--research-text-page-title); font-weight: var(--research-font-weight-bold); letter-spacing: var(--research-letter-spacing-title); line-height: var(--research-line-height-tight); }
.research-page-header__status { padding: var(--research-space-1) var(--research-space-3); border-radius: var(--research-radius-pill); background: var(--research-coral-50); color: var(--research-coral-500); font-size: var(--research-text-sm); }
.research-page-header__description { max-width: 760px; margin: var(--research-space-2) 0 0; color: var(--research-text-secondary); }
.research-page-header__actions { display: flex; flex: 0 0 auto; align-items: center; gap: var(--research-space-2); }
@media (max-width: 900px) { .research-page-header { flex-direction: column; } .research-page-header__actions { width: 100%; } }
</style>

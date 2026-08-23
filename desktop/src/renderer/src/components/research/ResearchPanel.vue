<script setup lang="ts">
withDefaults(defineProps<{
  title: string
  subtitle?: string
  tone?: 'default' | 'primary' | 'ai' | 'success' | 'warning' | 'danger'
}>(), {
  tone: 'default'
})
</script>

<template>
  <section :class="['research-panel', `research-panel--${tone}`]">
    <header class="research-panel__header">
      <div class="research-panel__heading">
        <h2 class="research-panel__title">{{ title }}</h2>
        <p v-if="subtitle" class="research-panel__subtitle">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.actions" class="research-panel__actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="research-panel__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.research-panel {
  --research-panel-accent: var(--research-border-strong);
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--research-border-subtle);
  border-block-start: 2px solid var(--research-panel-accent);
  border-radius: var(--research-radius-panel);
  background: var(--research-bg-card);
  box-shadow: var(--research-shadow-soft);
}
.research-panel--primary { --research-panel-accent: var(--research-primary-500); }
.research-panel--ai { --research-panel-accent: var(--research-ai-500); }
.research-panel--success { --research-panel-accent: var(--research-success-500); }
.research-panel--warning { --research-panel-accent: var(--research-warning-500); }
.research-panel--danger { --research-panel-accent: var(--research-danger-500); }
.research-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--research-space-4);
  padding: var(--research-space-4) var(--research-space-5);
  border-block-end: 1px solid var(--research-divider);
}
.research-panel__heading { min-width: 0; }
.research-panel__title {
  margin: 0;
  color: var(--research-text-primary);
  font-size: var(--research-text-card-title);
  font-weight: var(--research-font-weight-semibold);
  line-height: var(--research-line-height-tight);
}
.research-panel__subtitle {
  margin: var(--research-space-1) 0 0;
  color: var(--research-text-secondary);
  font-size: var(--research-text-sm);
  line-height: var(--research-line-height-body);
}
.research-panel__actions { display: flex; align-items: center; gap: var(--research-space-2); flex: 0 0 auto; }
.research-panel__body { min-width: 0; padding: var(--research-space-5); }
</style>

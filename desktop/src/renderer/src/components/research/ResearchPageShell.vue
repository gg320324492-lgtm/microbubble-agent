<script setup lang="ts">
defineProps<{
  eyebrow?: string
  title: string
  description?: string
  status?: string
}>()
</script>

<template>
  <section class="research-page-shell">
    <header class="research-page-shell__header">
      <div class="research-page-shell__heading">
        <p v-if="eyebrow" class="research-page-shell__eyebrow">{{ eyebrow }}</p>
        <div class="research-page-shell__title-row">
          <h1 class="research-page-shell__title">{{ title }}</h1>
          <span v-if="status" class="research-page-shell__status">{{ status }}</span>
        </div>
        <p v-if="description" class="research-page-shell__description">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="research-page-shell__actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="research-page-shell__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.research-page-shell {
  width: 100%;
  min-width: 0;
  max-width: var(--research-content-max-width);
  margin-inline: auto;
  padding: var(--research-page-gutter);
}

.research-page-shell__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--research-space-6);
  margin-block-end: var(--research-space-6);
}

.research-page-shell__heading { min-width: 0; }
.research-page-shell__eyebrow {
  margin: 0 0 var(--research-space-2);
  color: var(--research-primary-600);
  font-size: var(--research-text-xs);
  font-weight: var(--research-font-weight-semibold);
  letter-spacing: .08em;
}
.research-page-shell__title-row { display: flex; align-items: center; gap: var(--research-space-3); flex-wrap: wrap; }
.research-page-shell__title {
  margin: 0;
  color: var(--research-text-primary);
  font-size: var(--research-text-page-title);
  font-weight: var(--research-font-weight-bold);
  letter-spacing: var(--research-letter-spacing-title);
  line-height: var(--research-line-height-tight);
}
.research-page-shell__status {
  padding: var(--research-space-1) var(--research-space-3);
  border: 1px solid var(--research-ai-200);
  border-radius: var(--research-radius-pill);
  background: var(--research-ai-50);
  color: var(--research-ai-700);
  font-size: var(--research-text-sm);
  font-weight: var(--research-font-weight-medium);
}
.research-page-shell__description {
  max-width: 760px;
  margin: var(--research-space-2) 0 0;
  color: var(--research-text-secondary);
  font-size: var(--research-text-body);
  line-height: var(--research-line-height-body);
}
.research-page-shell__actions { display: flex; align-items: center; gap: var(--research-space-2); flex: 0 0 auto; }
.research-page-shell__body { min-width: 0; }

@media (max-width: 900px) {
  .research-page-shell__header { flex-direction: column; }
  .research-page-shell__actions { width: 100%; }
}
</style>

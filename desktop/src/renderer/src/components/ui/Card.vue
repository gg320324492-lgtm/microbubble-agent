<script setup lang="ts">
/**
 * 基础 Card 容器。
 * 严禁引 Element Plus / v-card 等 UI 框架同名组件。
 */
interface Props {
  title?: string
  subtitle?: string
  padding?: 'sm' | 'md' | 'lg'
}
withDefaults(defineProps<Props>(), { padding: 'md' })
</script>

<template>
  <section :class="['ui-card', `ui-card--${padding}`]">
    <header v-if="title || subtitle || $slots.header" class="ui-card__header">
      <slot name="header">
        <h3 v-if="title" class="ui-card__title">{{ title }}</h3>
        <p v-if="subtitle" class="ui-card__subtitle">{{ subtitle }}</p>
      </slot>
    </header>
    <div class="ui-card__body">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="ui-card__footer">
      <slot name="footer" />
    </footer>
  </section>
</template>

<style scoped>
.ui-card {
  background: var(--research-bg-card);
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-card);
  display: flex;
  flex-direction: column;
  box-shadow: var(--research-shadow-soft);
}
.ui-card--sm { padding: var(--research-space-3) var(--research-space-4); }
.ui-card--md { padding: var(--research-space-4) var(--research-space-5); }
.ui-card--lg { padding: var(--research-space-6) var(--research-space-7); }

.ui-card__header {
  margin-bottom: var(--research-space-3);
  padding-bottom: var(--research-space-3);
  border-bottom: 1px solid var(--research-divider);
}
.ui-card__title {
  margin: 0;
  font-size: var(--research-text-card-title);
  font-weight: var(--research-font-weight-semibold);
  color: var(--research-text-primary);
}
.ui-card__subtitle {
  margin: var(--research-space-1) 0 0;
  font-size: var(--research-text-sm);
  color: var(--research-text-secondary);
  line-height: var(--research-line-height-body);
}
.ui-card__body {
  flex: 1;
}
.ui-card__footer {
  margin-top: var(--research-space-3);
  padding-top: var(--research-space-3);
  border-top: 1px solid var(--research-divider);
}
</style>

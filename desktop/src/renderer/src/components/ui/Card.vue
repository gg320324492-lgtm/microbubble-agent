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
  background: #1e293b;
  border: 1px solid #334155;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
}
.ui-card--sm { padding: 0.75rem 1rem; }
.ui-card--md { padding: 1rem 1.25rem; }
.ui-card--lg { padding: 1.5rem 1.75rem; }

.ui-card__header {
  margin-bottom: 0.75rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #334155;
}
.ui-card__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #f1f5f9;
}
.ui-card__subtitle {
  margin: 0.3rem 0 0;
  font-size: 0.8rem;
  color: #94a3b8;
}
.ui-card__body {
  flex: 1;
}
.ui-card__footer {
  margin-top: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid #334155;
}
</style>

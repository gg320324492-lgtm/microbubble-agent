<script setup lang="ts">
import ResearchIcon from '../icons/ResearchIcon.vue'

withDefaults(defineProps<{
  title: string
  type: 'line' | 'bar' | 'scatter' | 'heatmap' | 'surface'
  description?: string
}>(), {
  description: ''
})
</script>

<template>
  <section class="chart-panel" :aria-label="`${title}图表面板`">
    <div class="chart-panel__header">
      <span class="chart-panel__icon" aria-hidden="true"><ResearchIcon name="data" :size="18" /></span>
      <div class="chart-panel__heading">
        <h3 class="chart-panel__title">{{ title }}</h3>
        <p v-if="description" class="chart-panel__description">{{ description }}</p>
      </div>
      <span class="chart-panel__type">{{ type === 'line' ? '曲线' : type === 'scatter' ? '散点' : '科学图形' }}</span>
    </div>
    <div class="chart-panel__body">
      <slot>
        <div class="chart-panel__placeholder">{{ title }} 暂无可绘制数据</div>
      </slot>
    </div>
  </section>
</template>

<style scoped>
.chart-panel {
  min-width: 0;
  overflow: hidden;
  border: 1px solid var(--research-border-subtle);
  border-radius: var(--research-radius-card);
  background: var(--research-bg-card);
  box-shadow: var(--research-shadow-soft);
}
.chart-panel__header {
  display: flex;
  align-items: center;
  gap: var(--research-space-3);
  padding: var(--research-space-4) var(--research-space-5);
  border-block-end: 1px solid var(--research-divider);
}
.chart-panel__icon {
  display: grid;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  place-items: center;
  border-radius: var(--research-radius-input);
  background: var(--research-primary-50);
  color: var(--research-primary-600);
}
.chart-panel__heading { min-width: 0; flex: 1; }
.chart-panel__title {
  margin: 0;
  color: var(--research-text-primary);
  font-size: var(--research-text-card-title);
  font-weight: var(--research-font-weight-semibold);
}
.chart-panel__description {
  margin: var(--research-space-1) 0 0;
  color: var(--research-text-secondary);
  font-size: var(--research-text-sm);
  line-height: var(--research-line-height-body);
}
.chart-panel__type {
  padding: var(--research-space-1) var(--research-space-2);
  border-radius: var(--research-radius-pill);
  background: var(--research-bg-panel);
  color: var(--research-text-secondary);
  font-size: var(--research-text-xs);
}
.chart-panel__body { min-width: 0; padding: var(--research-space-4); }
.chart-panel__placeholder {
  display: grid;
  min-height: 180px;
  place-items: center;
  color: var(--research-text-secondary);
  font-size: var(--research-text-sm);
  text-align: center;
}
</style>

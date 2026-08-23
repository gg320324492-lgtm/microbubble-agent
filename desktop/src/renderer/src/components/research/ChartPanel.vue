<script setup lang="ts">
/**
 * 图表面板 — 数据可视化占位。
 */
defineProps<{
  title: string
  type: 'line' | 'bar' | 'scatter' | 'heatmap' | 'surface'
}>()

const ICON: Record<string, string> = { line: '📈', bar: '📊', scatter: '⚬', heatmap: '🗺️', surface: '🌊' }
</script>

<template>
  <div class="chart-panel">
    <div class="chart-panel__header">
      <span>{{ ICON[type] }}</span>
      <span class="chart-panel__title">{{ title }}</span>
    </div>
    <div class="chart-panel__body">
      <slot>
        <div class="chart-panel__placeholder">{{ title }} 图表</div>
      </slot>
    </div>
  </div>
</template>

<style scoped>
.chart-panel { background: #fff; border: 1px solid #e5e7eb; border-radius: 10px; overflow: hidden; }
.chart-panel__header { padding: 12px 16px; border-bottom: 1px solid #f1f5f9; display: flex; align-items: center; gap: 8px; }
.chart-panel__title { font-size: 13px; font-weight: 600; color: #1e293b; }
.chart-panel__body { padding: 16px; min-height: 120px; display: flex; align-items: center; justify-content: center; }
.chart-panel__placeholder { font-size: 13px; color: #94a3b8; }
</style>

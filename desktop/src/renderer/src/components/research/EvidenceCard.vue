<script setup lang="ts">
/**
 * 证据卡片 — 显示证据条目及来源。
 */
defineProps<{
  label: string
  value: string
  source?: string
  confidence?: number
}>()
</script>

<template>
  <div class="evidence-card">
    <div class="evidence-card__label">{{ label }}</div>
    <div class="evidence-card__value">{{ value }}</div>
    <div v-if="source" class="evidence-card__source">来源: {{ source }}</div>
    <div v-if="confidence !== undefined" class="evidence-card__bar">
      <div class="evidence-card__fill" :style="{ width: Math.round(confidence * 100) + '%', background: confidence > 0.7 ? '#10B981' : confidence > 0.4 ? '#F59E0B' : '#EF4444' }" />
      <span class="evidence-card__pct">{{ Math.round(confidence * 100) }}%</span>
    </div>
  </div>
</template>

<style scoped>
.evidence-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 14px; }
.evidence-card__label { font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: .03em; margin-bottom: 4px; }
.evidence-card__value { font-size: 14px; font-weight: 500; color: #1e293b; }
.evidence-card__source { font-size: 11px; color: #64748b; margin-top: 6px; }
.evidence-card__bar { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.evidence-card__bar > div:first-child { flex: 1; height: 4px; background: #e2e8f0; border-radius: 2px; overflow: hidden; }
.evidence-card__bar > div:first-child > div { height: 100%; border-radius: 2px; }
.evidence-card__pct { font-size: 11px; font-weight: 600; color: #64748b; min-width: 28px; }
</style>

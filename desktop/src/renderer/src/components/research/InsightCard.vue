<script setup lang="ts">
/**
 * AI洞察卡片 — AI发现/建议展示。
 */
defineProps<{
  finding: string
  suggestion: string
  severity?: 'info' | 'warning' | 'critical'
}>()

const SEVERITY: Record<string, { bg: string; border: string; icon: string }> = {
  info:     { bg: '#eff6ff', border: '#bfdbfe', icon: '💡' },
  warning:  { bg: '#fffbeb', border: '#fde68a', icon: '⚠️' },
  critical: { bg: '#fef2f2', border: '#fecaca', icon: '🔴' }
}
</script>

<template>
  <div class="insight-card" :style="{ background: SEVERITY[severity ?? 'info'].bg, borderColor: SEVERITY[severity ?? 'info'].border }">
    <div class="insight-card__icon">{{ SEVERITY[severity ?? 'info'].icon }}</div>
    <div class="insight-card__body">
      <div class="insight-card__finding">{{ finding }}</div>
      <div class="insight-card__suggestion">{{ suggestion }}</div>
    </div>
  </div>
</template>

<style scoped>
.insight-card {
  border: 1px solid;
  border-radius: 10px;
  padding: 14px 16px;
  display: flex;
  gap: 12px;
}
.insight-card__icon { font-size: 18px; flex-shrink: 0; margin-top: 1px; }
.insight-card__finding { font-size: 13px; font-weight: 500; color: #1e293b; margin-bottom: 4px; }
.insight-card__suggestion { font-size: 12px; color: #64748b; line-height: 1.5; }
</style>

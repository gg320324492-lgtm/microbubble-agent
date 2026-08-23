<script setup lang="ts">
/**
 * AI洞察卡片 — AI发现/建议展示。
 */
import ResearchIcon from '../icons/ResearchIcon.vue'
import type { ResearchIconName } from '../icons/research-icons'

const props = defineProps<{
  finding: string
  suggestion: string
  severity?: 'info' | 'warning' | 'critical'
}>()

const ICON: Record<NonNullable<typeof props.severity>, ResearchIconName> = {
  info: 'sparkles',
  warning: 'warning',
  critical: 'error'
}
</script>

<template>
  <div :class="['insight-card', `insight-card--${severity ?? 'info'}`]">
    <div class="insight-card__icon"><ResearchIcon :name="ICON[severity ?? 'info']" :size="18" /></div>
    <div class="insight-card__body">
      <div class="insight-card__finding">{{ finding }}</div>
      <div class="insight-card__suggestion">{{ suggestion }}</div>
    </div>
  </div>
</template>

<style scoped>
.insight-card {
  border: 1px solid var(--research-primary-100);
  border-radius: var(--research-radius-card);
  padding: var(--research-space-3) var(--research-space-4);
  display: flex;
  gap: var(--research-space-3);
  background: var(--research-primary-50);
}
.insight-card--warning { border-color: var(--research-warning-100); background: var(--research-warning-50); }
.insight-card--critical { border-color: var(--research-danger-100); background: var(--research-danger-50); }
.insight-card__icon { color: var(--research-primary-600); flex-shrink: 0; margin-top: var(--research-space-1); }
.insight-card--warning .insight-card__icon { color: var(--research-warning-600); }
.insight-card--critical .insight-card__icon { color: var(--research-danger-600); }
.insight-card__finding { font-size: var(--research-text-body); font-weight: var(--research-font-weight-medium); color: var(--research-text-primary); margin-bottom: var(--research-space-1); }
.insight-card__suggestion { font-size: var(--research-text-sm); color: var(--research-text-secondary); line-height: var(--research-line-height-body); }
</style>

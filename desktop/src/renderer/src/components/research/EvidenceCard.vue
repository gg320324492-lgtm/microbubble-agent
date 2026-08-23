<script setup lang="ts">
/**
 * 证据卡片 — 显示证据条目及来源。
 */
import { computed } from 'vue'
import ResearchIcon from '../icons/ResearchIcon.vue'

const props = defineProps<{
  label: string
  value: string
  source?: string
  confidence?: number
}>()
const confidencePercent = computed(() => Math.round(Math.min(1, Math.max(0, props.confidence ?? 0)) * 100))
const confidenceTone = computed(() => confidencePercent.value > 70 ? 'high' : confidencePercent.value > 40 ? 'medium' : 'low')
</script>

<template>
  <article class="evidence-card" :aria-label="`${label}证据`">
    <div class="evidence-card__label"><ResearchIcon name="evidence" :size="13" />{{ label }}</div>
    <div class="evidence-card__value">{{ value }}</div>
    <div v-if="source" class="evidence-card__source">来源：{{ source }}</div>
    <div v-if="confidence !== undefined" class="evidence-card__bar">
      <div
        class="evidence-card__track"
        role="progressbar"
        :aria-label="`${label}置信度`"
        aria-valuemin="0"
        aria-valuemax="100"
        :aria-valuenow="confidencePercent"
      >
        <div :class="['evidence-card__fill', `evidence-card__fill--${confidenceTone}`]" :style="{ width: confidencePercent + '%' }" />
      </div>
      <span class="evidence-card__pct">{{ confidencePercent }}%</span>
    </div>
  </article>
</template>

<style scoped>
.evidence-card { background: var(--research-bg-panel); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); padding: var(--research-space-3) var(--research-space-4); }
.evidence-card__label { display: flex; align-items: center; gap: var(--research-space-1); font-size: var(--research-text-xs); color: var(--research-text-secondary); letter-spacing: .03em; margin-bottom: var(--research-space-1); }
.evidence-card__value { font-size: var(--research-text-body); font-weight: var(--research-font-weight-medium); color: var(--research-text-primary); line-height: var(--research-line-height-body); }
.evidence-card__source { font-size: var(--research-text-xs); color: var(--research-text-secondary); margin-top: var(--research-space-2); }
.evidence-card__bar { display: flex; align-items: center; gap: var(--research-space-2); margin-top: var(--research-space-2); }
.evidence-card__track { flex: 1; height: 5px; background: var(--research-border-subtle); border-radius: var(--research-radius-pill); overflow: hidden; }
.evidence-card__fill { height: 100%; border-radius: var(--research-radius-pill); }
.evidence-card__fill--high { background: var(--research-success-500); }
.evidence-card__fill--medium { background: var(--research-warning-500); }
.evidence-card__fill--low { background: var(--research-danger-500); }
.evidence-card__pct { font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); color: var(--research-text-secondary); min-width: 30px; font-variant-numeric: tabular-nums; }
</style>

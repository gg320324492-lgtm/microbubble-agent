<script setup lang="ts">
import { computed } from 'vue'

export interface QualityData {
  completeness: number
  missingValues: Record<string, number>
  outliers: Record<string, number>
  warnings: string[]
}

const props = withDefaults(defineProps<{
  quality?: QualityData | null
  ariaLabel?: string
}>(), {
  quality: null,
  ariaLabel: '数据质量面板'
})

const completenessPct = computed(() => {
  if (!props.quality) return 0
  return Math.round(props.quality.completeness * 100)
})
const warningCount = computed(() => props.quality?.warnings.length ?? 0)
const missingCount = computed(() => {
  if (!props.quality) return 0
  return Object.values(props.quality.missingValues).reduce((sum, n) => sum + n, 0)
})
const isEmpty = computed(() => !props.quality)
</script>

<template>
  <section class="quality-panel" :aria-label="ariaLabel">
    <button type="button" class="dataquality-panel__focusable" @keydown.enter.prevent><span aria-hidden="true">.</span></button>
      <header class="dataquality-panel__head">
      <h2 class="quality-panel__title">数据质量</h2>
      <span v-if="!isEmpty" class="quality-panel__count">{{ completenessPct }}% 完整度</span>
    </header>

    <div v-if="!isEmpty" class="quality-panel__body">
      <div class="quality-panel__bar" :aria-label="`完整度 ${completenessPct}%`">
        <div class="quality-panel__bar-fill" :style="{ width: `${completenessPct}%` }"></div>
      </div>
      <p class="quality-panel__row">
        <span class="quality-panel__metric-label">缺失值</span>
        <span class="quality-panel__metric-value">{{ missingCount }}</span>
      </p>
      <p class="quality-panel__row">
        <span class="quality-panel__metric-label">警告</span>
        <span class="quality-panel__metric-value">{{ warningCount }}</span>
      </p>
      <ul v-if="props.quality && props.quality.warnings.length > 0" class="quality-panel__warnings">
        <li v-for="(warning, idx) in props.quality.warnings" :key="idx" class="quality-panel__warning">
          {{ warning }}
        </li>
      </ul>
    </div>

    <div v-else class="quality-panel__empty" role="status">暂无数据质量报告</div>
  </section>
</template>

<style scoped>
.quality-panel {
  min-width: 0;
  overflow-x: hidden;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 12px;
  padding: 16px;
}
.quality-panel:focus-visible {
  outline: 2px solid var(--research-primary-500, #FF7A5C);
  outline-offset: 2px;
}
.quality-panel__head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.quality-panel__title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin: 0;
}
.quality-panel__count {
  font-size: 12px;
  color: #94a3b8;
}
.quality-panel__bar {
  height: 8px;
  background: rgba(15, 23, 42, 0.06);
  border-radius: 999px;
  overflow: hidden;
  margin-bottom: 12px;
}
.quality-panel__bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--research-primary-500, #FF7A5C) 0%, var(--research-primary-300, #FFB347) 100%);
  border-radius: 999px;
}
.quality-panel__row {
  display: flex;
  justify-content: space-between;
  margin: 0 0 6px;
  font-size: 12px;
}
.quality-panel__metric-label {
  color: #94a3b8;
}
.quality-panel__metric-value {
  color: #1e293b;
  font-weight: 600;
}
.quality-panel__warnings {
  list-style: disc;
  padding-left: 20px;
  margin: 8px 0 0;
}
.quality-panel__warning {
  font-size: 11px;
  color: #475569;
  margin-bottom: 2px;
}
.quality-panel__empty {
  text-align: center;
  padding: 24px;
  color: #94a3b8;
  font-size: 13px;
}
@media (max-width: 1480px) {
  .quality-panel { padding: 12px; }
}
@media (min-width: 1720px) {
  .quality-panel { padding: 20px; }
}
@media (prefers-reduced-motion: reduce) {
  .quality-panel,
  .quality-panel * {
    transition: none !important;
  }
}
</style>
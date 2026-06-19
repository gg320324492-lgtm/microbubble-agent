<template>
  <div class="formula-block" :class="{ 'formula-block-compact': compact }">
    <div class="formula-header">
      <span class="formula-icon">📐</span>
      <span v-if="formula.formula_no" class="formula-no">{{ formula.formula_no }}</span>
      <span v-if="formula.page" class="formula-page">P{{ formula.page }}</span>
      <span v-if="formula.confidence" class="formula-confidence">
        置信度 {{ Math.round(formula.confidence * 100) }}%
      </span>
    </div>
    <pre v-if="formula.data?.latex || formula.contentText" class="formula-content"><code>{{ formula.data?.latex || formula.contentText }}</code></pre>
    <div v-if="formula.data?.caption" class="formula-caption">
      {{ formula.data.caption }}
    </div>
  </div>
</template>

<script setup>
defineProps({
  formula: { type: Object, required: true },
  compact: { type: Boolean, default: false },
})
</script>

<style scoped>
.formula-block {
  background: #fff;
  border: 1px solid var(--color-border-light);
  border-left: 3px solid var(--color-primary);
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 12px;
  transition: box-shadow 0.2s;
}

.formula-block:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.formula-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #6B7280;
}

.formula-icon {
  font-size: 14px;
}

.formula-no {
  font-weight: 600;
  color: var(--color-primary);
}

.formula-page {
  background: #F3F4F6;
  color: #6B7280;
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 11px;
}

.formula-confidence {
  color: #9CA3AF;
  font-size: 11px;
}

.formula-content {
  margin: 0;
  padding: 12px 16px;
  background: #F9FAFB;
  border-radius: 6px;
  font-family: 'KaTeX_Main', 'Latin Modern Math', 'Times New Roman', serif;
  font-size: 14px;
  line-height: 1.6;
  color: #1F2937;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-x: auto;
}

.formula-caption {
  margin-top: 8px;
  font-size: 13px;
  color: #6B7280;
  font-style: italic;
  line-height: 1.6;
}

.formula-block-compact {
  padding: 8px 12px;
  margin-bottom: 8px;
}

.formula-block-compact .formula-content {
  padding: 8px 12px;
  font-size: 13px;
}
</style>

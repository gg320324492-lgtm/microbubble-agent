<template>
  <div class="table-card" :class="{ 'table-card-compact': compact }">
    <div class="table-header">
      <span class="table-icon">📊</span>
      <span v-if="table.table_no" class="table-no">{{ table.table_no }}</span>
      <span v-if="table.page" class="table-page">P{{ table.page }}</span>
      <span v-if="table.confidence" class="table-confidence">
        置信度 {{ Math.round(table.confidence * 100) }}%
      </span>
    </div>

    <!-- caption -->
    <div v-if="table.data?.caption" class="table-caption">
      {{ table.data.caption }}
    </div>

    <!-- 渲染好的表格（来自 extractions panel 的 data.headers/rows） -->
    <div v-if="renderedTable" class="table-wrapper" v-html="renderedTable"></div>
    <div v-else-if="table.contentText" class="table-fallback">
      <pre>{{ table.contentText }}</pre>
    </div>
    <div v-else class="table-empty">无表格内容</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  table: { type: Object, required: true },
  compact: { type: Boolean, default: false },
})

function escapeHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

const renderedTable = computed(() => {
  if (!props.table.data) return null
  const headers = props.table.data.headers || []
  const rows = props.table.data.rows || []
  if (headers.length === 0 && rows.length === 0) return null
  const thead = headers.length
    ? '<thead><tr>' + headers.map((h) => `<th>${escapeHtml(h)}</th>`).join('') + '</tr></thead>'
    : ''
  const tbody = '<tbody>' + rows.map((r) =>
    '<tr>' + r.map((c) => `<td>${escapeHtml(c)}</td>`).join('') + '</tr>'
  ).join('') + '</tbody>'
  return `<table class="paper-table">${thead}${tbody}</table>`
})
</script>

<style scoped>
.table-card {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-left: 3px solid var(--color-success);
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 14px;
  transition: box-shadow 0.2s;
}

.table-card:hover {
  box-shadow: var(--shadow-sm);
}

.table-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--color-text-secondary);
}

.table-icon {
  font-size: 14px;
}

.table-no {
  font-weight: 600;
  color: var(--color-success);
}

.table-page {
  background: var(--color-border-light);
  color: var(--color-text-secondary);
  padding: 1px 6px;
  border-radius: 6px;
  font-size: 11px;
}

.table-confidence {
  color: var(--color-text-placeholder);
  font-size: 11px;
}

.table-caption {
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--color-text-regular);
  font-weight: 500;
  font-style: italic;
  line-height: 1.6;
}

.table-wrapper {
  overflow-x: auto;
  border-radius: 6px;
  border: 1px solid var(--color-border-light);
}

.table-wrapper :deep(.paper-table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  min-width: 400px;
}

.table-wrapper :deep(.paper-table th) {
  background: var(--color-border-light);
  font-weight: 600;
  text-align: left;
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text-primary);
  white-space: nowrap;
}

.table-wrapper :deep(.paper-table td) {
  padding: 8px 12px;
  border-bottom: 1px solid var(--color-border-light);
  color: var(--color-text-secondary);
  vertical-align: top;
}

.table-wrapper :deep(.paper-table tr:hover td) {
  background: var(--color-bg-page);
}

.table-fallback {
  background: var(--color-bg-card);
  border-radius: 6px;
  padding: 10px 12px;
}

.table-fallback pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'SF Mono', Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  max-height: 280px;
  overflow: auto;
}

.table-empty {
  font-size: 12px;
  color: var(--color-text-placeholder);
  font-style: italic;
  text-align: center;
  padding: 12px;
}
</style>

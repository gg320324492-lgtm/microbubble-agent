<template>
  <div class="rich-block table-block">
    <div v-if="block.title" class="block-title">📋 {{ block.title }}</div>
    <div v-if="rows.length" class="table-wrap">
      <table class="data-table">
        <thead v-if="columns.length">
          <tr>
            <th
              v-for="col in columns"
              :key="col.key"
              class="th"
            >{{ col.label || col.key }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, idx) in rows"
            :key="idx"
          >
            <td
              v-for="col in columns"
              :key="col.key"
              class="td"
            >{{ formatCell(row[col.key]) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else class="empty-state">暂无表格数据</div>
  </div>
</template>

<script setup>
/**
 * TableBlock.vue — Rich Block 表格类型（PR #3 新增）
 *
 * 注册到 registry.ts 后，对话中流式 rich_block.type === 'table' 时会渲染此组件。
 *
 * 数据格式（与后端 app/agent/protocol.py 对齐）：
 *   block.data = {
 *     columns: [{ key: 'id', label: 'ID' }, ...],
 *     rows: [{ id: '...', name: '...' }, ...],
 *     title?: string
 *   }
 */

import { computed } from 'vue'

const props = defineProps({
  block: { type: Object, required: true },
  compact: { type: Boolean, default: false },
})

const columns = computed(() => props.block?.data?.columns || [])
const rows = computed(() => props.block?.data?.rows || [])

function formatCell(v) {
  if (v == null) return ''
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}
</script>

<style scoped>
.rich-block {
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 12px;
  margin: 8px 0;
  font-size: 13px;
}

[data-theme="dark"] .rich-block {
  background: var(--color-bg-card);
  border-color: var(--color-border-base);
}

.block-title {
  font-weight: var(--font-weight-semibold, 600);
  font-size: 13px;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.th,
.td {
  padding: 6px 8px;
  border-bottom: 1px solid var(--color-border-light);
  text-align: left;
  white-space: nowrap;
}

[data-theme="dark"] .th,
[data-theme="dark"] .td {
  border-bottom-color: var(--color-border-base);
}

.th {
  background: var(--color-bg-page);
  font-weight: var(--font-weight-medium, 500);
  color: var(--color-text-regular);
}

.td {
  color: var(--color-text-primary);
}

.empty-state {
  text-align: center;
  color: var(--color-text-secondary);
  padding: 12px;
}
</style>
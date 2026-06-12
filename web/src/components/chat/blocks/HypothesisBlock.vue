<script setup>
/**
 * HypothesisBlock.vue — 研究假设卡
 *
 * 接收 block.data = {items: [{id, statement, rationale, status, priority, confidence, validation_note}]}
 */
const props = defineProps({ block: { type: Object, required: true } })
const items = (props.block.data || {}).items || []

const statusColor = (s) => ({
  proposed: '#909399', validated: '#67c23a', rejected: '#f56c6c',
}[s] || '#909399')
const statusLabel = (s) => ({
  proposed: '提议中', validated: '已验证', rejected: '已否定',
}[s] || s)
const priorityColor = (p) => ({ high: '#f56c6c', medium: '#e6a23c', low: '#909399' }[p] || '#909399')
</script>

<template>
  <div class="hypothesis-block rich-card">
    <div class="card-header">
      <span class="icon">💡</span>
      <span class="title">{{ block.title || '研究假设' }} ({{ items.length }})</span>
    </div>
    <div v-for="h in items" :key="h.id" class="hyp-item">
      <div class="hyp-row1">
        <span class="status" :style="{ background: statusColor(h.status) }">{{ statusLabel(h.status) }}</span>
        <span v-if="h.priority" class="priority" :style="{ color: priorityColor(h.priority) }">
          {{ h.priority === 'high' ? '高优' : h.priority === 'medium' ? '中优' : '低优' }}
        </span>
        <span v-if="h.confidence != null" class="confidence">置信度 {{ (h.confidence * 100).toFixed(0) }}%</span>
      </div>
      <div class="statement">{{ h.statement }}</div>
      <div v-if="h.rationale" class="rationale">💭 {{ h.rationale }}</div>
      <div v-if="h.validation_note" class="validation">
        ✅ 验证记录：{{ h.validation_note }}
      </div>
    </div>
    <div v-if="!items.length" class="empty">暂无假设</div>
  </div>
</template>

<style scoped>
.rich-card { background: white; border: 1px solid #e8eaed; border-radius: 10px; padding: 12px 14px; margin: 8px 0; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }
.card-header { display: flex; align-items: center; gap: 8px; font-weight: 600; font-size: 14px; margin-bottom: 10px; color: #FF7A5C; }
.icon { font-size: 18px; }
.hyp-item { padding: 10px 0; border-top: 1px solid #f0f1f3; }
.hyp-item:first-of-type { border-top: none; }
.hyp-row1 { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 6px; }
.status { font-size: 11px; padding: 2px 8px; border-radius: 10px; color: white; }
.priority { font-size: 12px; font-weight: 500; }
.confidence { font-size: 11px; color: #999; }
.statement { font-size: 14px; color: #333; line-height: 1.6; font-weight: 500; }
.rationale { font-size: 12px; color: #666; margin-top: 4px; line-height: 1.5; }
.validation { font-size: 12px; color: #67c23a; margin-top: 4px; padding: 6px 8px; background: #f0f9eb; border-radius: 4px; }
.empty { text-align: center; color: #999; padding: 20px 0; font-size: 13px; }
</style>

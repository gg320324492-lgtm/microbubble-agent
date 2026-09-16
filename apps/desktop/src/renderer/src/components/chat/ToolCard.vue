<script setup lang="ts">
// 工具卡片 — 内嵌助手消息流：工具名 + 输入摘要 + 状态（运行中/成功/失败）+ 可展开结果详情
import { computed, ref } from 'vue'
import type { ToolCallRecord } from '@shared/types'

const props = defineProps<{ call: ToolCallRecord }>()

const expanded = ref(false)

const inputSummary = computed<string>(() => {
  let text: string
  try {
    text = JSON.stringify(props.call.input) ?? ''
  } catch {
    text = String(props.call.input)
  }
  return text.length > 80 ? `${text.slice(0, 80)}…` : text
})

const statusLabel = computed(() => (props.call.status === 'running' ? '运行中' : props.call.status === 'ok' ? '成功' : '失败'))

const dataText = computed<string>(() => {
  if (props.call.data === undefined) return ''
  try {
    return JSON.stringify(props.call.data, null, 2)
  } catch {
    return String(props.call.data)
  }
})
</script>

<template>
  <div class="tool-card" :class="`is-${call.status}`" data-testid="tool-card">
    <button class="tool-head" :aria-expanded="expanded" @click="expanded = !expanded">
      <span class="tool-status" data-testid="tool-status">
        <span v-if="call.status === 'running'" class="spin" aria-hidden="true">⟳</span>
        <span v-else-if="call.status === 'ok'" class="ok" aria-hidden="true">✓</span>
        <span v-else class="fail" aria-hidden="true">✗</span>
        {{ statusLabel }}
      </span>
      <span class="tool-name">{{ call.name }}</span>
      <span class="tool-input">{{ inputSummary }}</span>
      <span class="tool-chevron" aria-hidden="true">{{ expanded ? '▾' : '▸' }}</span>
    </button>
    <div v-if="expanded" class="tool-detail" data-testid="tool-detail">
      <div class="detail-line"><span class="detail-key">结果</span><span>{{ call.summary }}</span></div>
      <pre v-if="dataText" class="detail-data">{{ dataText }}</pre>
    </div>
  </div>
</template>

<style scoped>
.tool-card {
  margin: var(--space-2) 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-bg-secondary);
  overflow: hidden;
  font-size: var(--font-size-xs);
}
.tool-card.is-running {
  border-color: rgba(var(--color-primary-rgb), 0.55);
}
.tool-card.is-error {
  border-color: rgba(214, 69, 69, 0.45);
}
.tool-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
}
.tool-status {
  flex-shrink: 0;
  min-width: 52px;
  color: var(--color-text-secondary);
}
.tool-status .spin {
  display: inline-block;
  animation: toolSpin 1s linear infinite;
  color: var(--color-primary);
}
.tool-status .ok {
  color: var(--color-success, #22a06b);
}
.tool-status .fail {
  color: var(--color-danger, #d64545);
}
@keyframes toolSpin {
  to {
    transform: rotate(360deg);
  }
}
.tool-name {
  flex-shrink: 0;
  font-family: var(--font-family-mono);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-regular);
}
.tool-input {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--font-family-mono);
  color: var(--color-text-secondary);
}
.tool-chevron {
  flex-shrink: 0;
  color: var(--color-text-placeholder);
}
.tool-detail {
  padding: var(--space-2) var(--space-3) var(--space-3);
  border-top: 1px dashed var(--color-border-light);
}
.detail-line {
  display: flex;
  gap: var(--space-2);
  color: var(--color-text-regular);
  line-height: 1.6;
}
.detail-key {
  flex-shrink: 0;
  color: var(--color-text-secondary);
}
.detail-data {
  margin: var(--space-2) 0 0;
  max-height: 220px;
  overflow: auto;
  padding: var(--space-2);
  border-radius: var(--radius-sm);
  background: var(--wb-panel-950, #10241d);
  color: var(--wb-panel-text, #d7e7df);
  font-family: var(--font-family-mono);
  font-size: 11px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>

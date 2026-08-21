<script setup lang="ts">
/**
 * ToolResultCard (Phase 5-A: Agent Tool Renderer Foundation).
 *
 * 单条 tool_result 的展示卡片.
 * - 严禁 v-html (output JSON 走 JSON.stringify + 文本插值)
 * - 显示: tool name + status + duration + output payload + error
 *
 * Phase 5-A 提示: ToolCallCard 已覆盖 tool_use; 本组件针对 tool_result.
 * 两者合用: ToolCallCard 显示 "调用 + 状态 pill", ToolResultCard 显示 "输出".
 */
import { computed } from 'vue'
import type { ToolCallSnapshot } from '@shared/chat-types'

interface Props {
  tool: ToolCallSnapshot
}
const props = defineProps<Props>()

const outputJson = computed(() => {
  if (!props.tool.output) return null
  try {
    return JSON.stringify(props.tool.output, null, 2)
  } catch (_e) {
    return String(props.tool.output)
  }
})

const errorText = computed(() => props.tool.error ?? '')
</script>

<template>
  <div :class="['tool-result', `tool-result--${tool.status}`]">
    <div class="tool-result__head">
      <span class="tool-result__icon">{{ tool.status === 'error' ? '❌' : '✅' }}</span>
      <span class="tool-result__name">{{ tool.name }} 结果</span>
      <span v-if="tool.duration_ms != null" class="tool-result__duration">
        {{ tool.duration_ms }}ms
      </span>
    </div>
    <pre v-if="errorText" class="tool-result__error">{{ errorText }}</pre>
    <details v-else-if="outputJson" class="tool-result__output">
      <summary>输出</summary>
      <pre>{{ outputJson }}</pre>
    </details>
    <p v-else class="tool-result__empty">（无输出）</p>
  </div>
</template>

<style scoped>
.tool-result {
  margin: 0.4rem 0;
  background: rgba(148, 163, 184, 0.04);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-left: 3px solid #475569;
  border-radius: 4px;
  padding: 0.4rem 0.75rem;
  font-size: 0.82rem;
}
.tool-result--success {
  border-left-color: #10b981;
}
.tool-result--error {
  border-left-color: #ef4444;
  background: rgba(239, 68, 68, 0.06);
}
.tool-result__head {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.82rem;
}
.tool-result__icon { font-size: 0.95rem; }
.tool-result__name {
  font-weight: 600;
  color: #f1f5f9;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}
.tool-result__duration {
  margin-left: auto;
  font-size: 0.7rem;
  color: #64748b;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}
.tool-result__error {
  margin: 0.4rem 0 0;
  padding: 0.4rem 0.6rem;
  background: #0b1220;
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 3px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.75rem;
  color: #fca5a5;
  white-space: pre-wrap;
  word-break: break-word;
}
.tool-result__output {
  margin-top: 0.4rem;
  font-size: 0.75rem;
  color: #94a3b8;
}
.tool-result__output summary {
  cursor: pointer;
  user-select: none;
  color: #94a3b8;
}
.tool-result__output pre {
  margin: 0.4rem 0 0;
  padding: 0.4rem 0.6rem;
  background: #0b1220;
  border: 1px solid #1e293b;
  border-radius: 3px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.72rem;
  color: #cbd5e1;
  max-height: 200px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
.tool-result__empty {
  margin: 0.4rem 0 0;
  color: #64748b;
  font-size: 0.75rem;
}
</style>

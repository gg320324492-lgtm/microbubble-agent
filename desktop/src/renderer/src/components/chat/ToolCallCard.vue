<script setup lang="ts">
/**
 * ToolCallCard (Phase 5-A: Agent Tool Renderer Foundation).
 *
 * 单条 tool_use 调用的展示卡片.
 * - 严禁 v-html (input JSON 走 JSON.stringify + 文本插值)
 * - 状态: call_only / success / error (派生于 tool_result)
 * - 显示: tool_name + status pill + duration (有则) + input JSON
 *
 * Phase 5-A 不执行工具, 仅渲染. 后续 Agent 执行 / Replay 留 Phase 5+.
 */
import { computed } from 'vue'
import type { ToolCallSnapshot } from '@shared/chat-types'

interface Props {
  tool: ToolCallSnapshot
}
const props = defineProps<Props>()

const statusLabel = computed(() => {
  switch (props.tool.status) {
    case 'call_only': return '调用中'
    case 'success': return '已完成'
    case 'error': return '失败'
    default: return '未知'
  }
})

const statusVariant = computed(() => props.tool.status)

const inputJson = computed(() => {
  try {
    return JSON.stringify(props.tool.input, null, 2)
  } catch (_e) {
    return String(props.tool.input)
  }
})

const inputDisplay = computed(() => {
  // 截断: > 8 行滚动显示
  return inputJson.value
})
</script>

<template>
  <div :class="['tool-card', `tool-card--${statusVariant}`]">
    <div class="tool-card__head">
      <span class="tool-card__icon">🔧</span>
      <span class="tool-card__name">{{ tool.name }}</span>
      <span :class="['tool-card__status', `tool-card__status--${statusVariant}`]">
        {{ statusLabel }}
      </span>
      <span v-if="tool.duration_ms != null" class="tool-card__duration">
        {{ tool.duration_ms }}ms
      </span>
    </div>
    <details v-if="inputDisplay" class="tool-card__input">
      <summary>输入参数</summary>
      <pre>{{ inputDisplay }}</pre>
    </details>
  </div>
</template>

<style scoped>
.tool-card {
  margin: 0.5rem 0;
  background: rgba(99, 102, 241, 0.06);
  border: 1px solid rgba(99, 102, 241, 0.22);
  border-radius: 6px;
  padding: 0.5rem 0.75rem;
  font-size: 0.85rem;
}
.tool-card--success {
  background: rgba(16, 185, 129, 0.06);
  border-color: rgba(16, 185, 129, 0.22);
}
.tool-card--error {
  background: rgba(239, 68, 68, 0.06);
  border-color: rgba(239, 68, 68, 0.3);
}
.tool-card__head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}
.tool-card__icon { font-size: 0.95rem; }
.tool-card__name {
  font-weight: 600;
  color: #f1f5f9;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  word-break: break-all;
}
.tool-card__status {
  font-size: 0.7rem;
  padding: 0.1rem 0.4rem;
  border-radius: 3px;
  flex-shrink: 0;
}
.tool-card__status--call_only {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}
.tool-card__status--success {
  background: rgba(16, 185, 129, 0.2);
  color: #10b981;
}
.tool-card__status--error {
  background: rgba(239, 68, 68, 0.2);
  color: #ef4444;
}
.tool-card__duration {
  margin-left: auto;
  font-size: 0.7rem;
  color: #64748b;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}
.tool-card__input {
  margin-top: 0.4rem;
  font-size: 0.75rem;
  color: #94a3b8;
}
.tool-card__input summary {
  cursor: pointer;
  user-select: none;
  color: #94a3b8;
  font-size: 0.75rem;
}
.tool-card__input pre {
  margin: 0.4rem 0 0;
  padding: 0.4rem 0.6rem;
  background: #0b1220;
  border: 1px solid #1e293b;
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.72rem;
  color: #cbd5e1;
  max-height: 200px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>

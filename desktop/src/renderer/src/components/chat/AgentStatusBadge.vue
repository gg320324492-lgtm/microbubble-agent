<script setup lang="ts">
/**
 * AgentStatusBadge (Phase 5-C: Agent State Model UI; Phase 6-B: Active Model).
 *
 * 流中显示当前 Agent 状态 (thinking / tool_running / waiting_user / planning).
 * 普通消息 (idle / completed) 不显示.
 *
 * 严格 spec §5: 仅做状态指示, 不接 tool execution / Agent backend / RAG.
 *
 * Phase 6-B: 当传 currentModel 时, 显示当前活动模型 — 例: "🧠 Qwen-Max 思考中"
 *            currentModel 来自 model-selector store, 非密 metadata.
 */
import { computed } from 'vue'
import type { AgentStateHint } from '../../utils/agent-state'

interface Props {
  hint: AgentStateHint
  /**
   * Phase 6-B: optional current model display name (provider displayName + model).
   * NEVER contains apiKey.
   */
  currentModel?: string | null
}
const props = defineProps<Props>()

const visible = computed(() => props.hint.visible)
const variant = computed(() => {
  switch (props.hint.state) {
    case 'thinking': return 'thinking'
    case 'tool_running': return 'executing'
    case 'planning': return 'planning'
    case 'waiting_user': return 'waiting'
    case 'failed': return 'failed'
    default: return 'idle'
  }
})

const isAnimating = computed(() => {
  const s = props.hint.state
  return s === 'thinking' || s === 'tool_running' || s === 'planning'
})

const displayLabel = computed(() => {
  if (!props.currentModel) return props.hint.label
  return `${props.currentModel} · ${props.hint.label}`
})
</script>

<template>
  <span v-if="visible" :class="['agent-status', `agent-status--${variant}`, { 'is-animating': isAnimating }]">
    <span class="agent-status__icon">{{ hint.icon }}</span>
    <span class="agent-status__label">{{ displayLabel }}</span>
  </span>
</template>

<style scoped>
.agent-status {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.1rem 0.5rem;
  border-radius: 3px;
  font-size: 0.7rem;
  font-weight: 500;
  flex-shrink: 0;
}
.agent-status--thinking {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}
.agent-status--executing {
  background: rgba(99, 102, 241, 0.18);
  color: #c7d2fe;
}
.agent-status--planning {
  background: rgba(168, 85, 247, 0.15);
  color: #d8b4fe;
}
.agent-status--waiting {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}
.agent-status--failed {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}
.agent-status--idle {
  background: rgba(148, 163, 184, 0.08);
  color: #94a3b8;
}
.agent-status__icon {
  font-size: 0.78rem;
}
.agent-status__label {
  letter-spacing: 0.02em;
}
.agent-status.is-animating {
  animation: agent-pulse 1.6s ease-in-out infinite;
}
@keyframes agent-pulse {
  0%, 100% { opacity: 0.82; }
  50% { opacity: 1; }
}
</style>

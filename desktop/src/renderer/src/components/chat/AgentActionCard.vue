<script setup lang="ts">
/**
 * AgentActionCard (Phase 5-E2: User Action Foundation).
 * 5 variants: suggestion / retry / confirm / cancel / sync.
 * 0 v-html, 安全文本渲染, disabled 防重入.
 */
import { computed } from 'vue'
import type { UserAction, UserActionType } from '../../utils/agent-interaction'

interface Props {
  action: UserAction
}
const props = defineProps<Props>()

const emit = defineEmits<{
  action: [payload: { action: UserAction; type: UserActionType }]
  retry: [action: UserAction]
  cancel: [action: UserAction]
  sync: [action: UserAction]
}>()

const variant = computed(() => props.action.type)
const label = computed(() => props.action.label || '操作')
const icon = computed(() => {
  switch (props.action.type) {
    case 'suggestion': return '💬'
    case 'retry': return '🔁'
    case 'confirm': return '✔'
    case 'cancel': return '✖'
    case 'sync': return '⟳'
  }
})

function onClick(): void {
  if (props.action.disabled) return
  switch (props.action.type) {
    case 'retry':
      emit('retry', props.action)
      return
    case 'cancel':
      emit('cancel', props.action)
      return
    case 'sync':
      emit('sync', props.action)
      return
    case 'suggestion':
    case 'confirm':
    default:
      emit('action', { action: props.action, type: props.action.type })
      return
  }
}
</script>

<template>
  <button
    type="button"
    :class="['agent-action', `agent-action--${variant}`, { 'is-disabled': action.disabled }]"
    :disabled="action.disabled"
    @click="onClick"
  >
    <span class="agent-action__icon">{{ icon }}</span>
    <span class="agent-action__label">{{ label }}</span>
  </button>
</template>

<style scoped>
.agent-action {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.3rem 0.7rem;
  border-radius: 4px;
  font-size: 0.78rem;
  font-weight: 500;
  cursor: pointer;
  font-family: inherit;
  transition: background 0.12s, border-color 0.12s;
  border: 1px solid transparent;
}
.agent-action:disabled,
.agent-action.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.agent-action--suggestion {
  background: rgba(168, 85, 247, 0.1);
  color: #d8b4fe;
  border-color: rgba(168, 85, 247, 0.3);
}
.agent-action--suggestion:hover:not(:disabled) { background: rgba(168, 85, 247, 0.2); }
.agent-action--retry {
  background: rgba(99, 102, 241, 0.12);
  color: #c7d2fe;
  border-color: rgba(99, 102, 241, 0.3);
}
.agent-action--retry:hover:not(:disabled) { background: rgba(99, 102, 241, 0.22); }
.agent-action--confirm {
  background: rgba(16, 185, 129, 0.15);
  color: #5eead4;
  border-color: rgba(16, 185, 129, 0.4);
}
.agent-action--confirm:hover:not(:disabled) { background: rgba(16, 185, 129, 0.25); }
.agent-action--cancel {
  background: rgba(239, 68, 68, 0.08);
  color: #fca5a5;
  border-color: rgba(239, 68, 68, 0.3);
}
.agent-action--cancel:hover:not(:disabled) { background: rgba(239, 68, 68, 0.18); }
.agent-action--sync {
  background: rgba(245, 158, 11, 0.1);
  color: #fcd34d;
  border-color: rgba(245, 158, 11, 0.3);
}
.agent-action--sync:hover:not(:disabled) { background: rgba(245, 158, 11, 0.2); }
.agent-action__icon { font-size: 0.85rem; }
.agent-action__label { letter-spacing: 0.02em; }
</style>

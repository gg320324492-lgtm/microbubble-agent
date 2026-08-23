<script setup lang="ts">
/**
 * 基础 Button 组件。
 *
 * 主题：Scientific Research OS 语义令牌。
 * 严禁引 Element Plus。
 *
 * variant:
 *   - primary  (默认): 科学蓝填充，用于主要操作
 *   - secondary: 透明边框, 用于次要操作
 *   - danger   : 风险色，用于破坏性操作
 *   - ghost    : 无边框无背景, hover 浅边框
 *
 * size: small / medium / large
 *
 * 状态: disabled / loading
 */
import { computed } from 'vue'
import ResearchIcon from '../icons/ResearchIcon.vue'

interface Props {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'small' | 'medium' | 'large'
  loading?: boolean
  disabled?: boolean
  type?: 'button' | 'submit'
}
const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'medium',
  loading: false,
  disabled: false,
  type: 'button'
})
const emit = defineEmits<{ click: [event: MouseEvent] }>()

const classes = computed(() => [
  'ui-btn',
  `ui-btn--${props.variant}`,
  `ui-btn--${props.size}`,
  { 'is-loading': props.loading, 'is-disabled': props.disabled }
])

function onClick(e: MouseEvent): void {
  if (props.disabled || props.loading) {
    e.preventDefault()
    return
  }
  emit('click', e)
}
</script>

<template>
  <button
    :class="classes"
    :type="type"
    :disabled="disabled || loading"
    :aria-busy="loading ? 'true' : undefined"
    @click="onClick"
  >
    <ResearchIcon v-if="loading" class="ui-btn__spinner" name="running" :size="14" />
    <slot />
  </button>
</template>

<style scoped>
.ui-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--research-space-2);
  border: 1px solid transparent;
  border-radius: var(--research-radius-button);
  font-size: var(--research-text-body);
  font-weight: var(--research-font-weight-medium);
  cursor: pointer;
  transition:
    background var(--research-duration-fast) var(--research-ease-standard),
    color var(--research-duration-fast) var(--research-ease-standard),
    border-color var(--research-duration-fast) var(--research-ease-standard),
    box-shadow var(--research-duration-fast) var(--research-ease-standard);
  font-family: inherit;
}
.ui-btn--small { min-height: 30px; padding: var(--research-space-1) var(--research-space-3); font-size: var(--research-text-sm); }
.ui-btn--medium { min-height: 38px; padding: var(--research-space-2) var(--research-space-4); }
.ui-btn--large { min-height: 44px; padding: var(--research-space-3) var(--research-space-5); font-size: var(--research-text-card-title); }

.ui-btn--primary {
  background: var(--research-primary-600);
  color: var(--research-text-inverse);
}
.ui-btn--primary:hover:not(:disabled) { background: var(--research-primary-700); }

.ui-btn--secondary {
  background: transparent;
  border-color: var(--research-border-strong);
  color: var(--research-text-primary);
}
.ui-btn--secondary:hover:not(:disabled) {
  border-color: var(--research-primary-400);
  color: var(--research-primary-700);
}

.ui-btn--danger {
  background: transparent;
  border-color: var(--research-danger-500);
  color: var(--research-danger-600);
}
.ui-btn--danger:hover:not(:disabled) {
  background: var(--research-danger-500);
  color: var(--research-text-inverse);
}

.ui-btn--ghost {
  background: transparent;
  color: var(--research-text-secondary);
}
.ui-btn--ghost:hover:not(:disabled) {
  background: var(--research-bg-hover);
  color: var(--research-primary-700);
}

.ui-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ui-btn:focus-visible {
  outline: none;
  box-shadow: var(--research-shadow-focus-primary);
}

.ui-btn__spinner {
  animation: ui-btn-spin var(--research-duration-slow) var(--research-ease-linear) infinite;
}
@keyframes ui-btn-spin {
  to { transform: rotate(360deg); }
}
</style>

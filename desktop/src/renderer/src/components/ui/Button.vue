<script setup lang="ts">
/**
 * 基础 Button 组件。
 *
 * 主题: 珊瑚橙 (与 web 端 design token 同色: --color-primary)。
 * 严禁引 Element Plus。
 *
 * variant:
 *   - primary  (默认): 橘色填充, 用于主要操作
 *   - secondary: 透明边框, 用于次要操作
 *   - danger   : 红色, 用于 destructive 操作
 *   - ghost    : 无边框无背景, hover 浅边框
 *
 * size: small / medium / large
 *
 * 状态: disabled / loading
 */
import { computed } from 'vue'

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
  <button :class="classes" :type="type" :disabled="disabled || loading" @click="onClick">
    <span v-if="loading" class="ui-btn__spinner" />
    <slot />
  </button>
</template>

<style scoped>
.ui-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  border: 1px solid transparent;
  border-radius: 4px;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
  font-family: inherit;
}
.ui-btn--small { padding: 0.3rem 0.7rem; font-size: 0.8rem; }
.ui-btn--medium { padding: 0.5rem 1rem; font-size: 0.9rem; }
.ui-btn--large { padding: 0.6rem 1.4rem; font-size: 1rem; }

.ui-btn--primary {
  background: #f97316;
  color: #fff;
}
.ui-btn--primary:hover:not(:disabled) { background: #ea580c; }

.ui-btn--secondary {
  background: transparent;
  border-color: #475569;
  color: #e2e8f0;
}
.ui-btn--secondary:hover:not(:disabled) {
  border-color: #f97316;
  color: #f97316;
}

.ui-btn--danger {
  background: transparent;
  border-color: #ef4444;
  color: #ef4444;
}
.ui-btn--danger:hover:not(:disabled) {
  background: #ef4444;
  color: #fff;
}

.ui-btn--ghost {
  background: transparent;
  color: #94a3b8;
}
.ui-btn--ghost:hover:not(:disabled) {
  background: rgba(148, 163, 184, 0.1);
  color: #f1f5f9;
}

.ui-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ui-btn__spinner {
  width: 12px;
  height: 12px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: ui-btn-spin 0.6s linear infinite;
}
@keyframes ui-btn-spin {
  to { transform: rotate(360deg); }
}
</style>

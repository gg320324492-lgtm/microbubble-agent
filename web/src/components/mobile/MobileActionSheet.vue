<template>
  <Teleport to="body">
    <Transition name="action-sheet">
      <div v-if="modelValue" class="sheet-overlay" @click.self="close">
        <div class="sheet-panel" :style="{ paddingBottom: panelPaddingBottom }">
          <div class="sheet-handle" />

          <div v-if="title" class="sheet-title">{{ title }}</div>

          <div class="sheet-actions">
            <button
              v-for="(action, idx) in actions"
              :key="idx"
              type="button"
              class="action-item"
              :class="{
                danger: action.danger,
                disabled: action.disabled,
              }"
              :disabled="action.disabled"
              @click="onActionClick(action)"
            >
              <span v-if="action.icon" class="action-icon" :style="iconStyle(action)">
                {{ action.icon }}
              </span>
              <span class="action-label">{{ action.label || action.name }}</span>
              <span v-if="action.description" class="action-desc">
                {{ action.description }}
              </span>
            </button>
          </div>

          <button
            type="button"
            class="cancel-btn"
            @click="close"
          >取消</button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
/**
 * MobileActionSheet.vue — 通用移动端 ActionSheet 组件
 *
 * PR #6: 替代桌面 el-popover / el-dropdown 操作菜单
 * - Teleport to body 底部弹出
 * - 支持 actions[] 配置（name/icon/description/danger/disabled）
 * - 点击外部或取消按钮关闭
 * - 错误边界友好（无 actions 时不显示）
 *
 * 用法：
 *   <MobileActionSheet
 *     v-model:show="show"
 *     title="操作"
 *     :actions="[
 *       { name: '编辑', icon: '✏️', callback: () => ... },
 *       { name: '删除', icon: '🗑', danger: true, callback: () => ... },
 *     ]"
 *   />
 */

import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  actions: { type: Array, default: () => [] },
  /** 自定义主题色（用于图标背景） */
  primaryColor: { type: String, default: 'var(--color-primary)' },
  /** 点击 action 后是否自动关闭 */
  autoClose: { type: Boolean, default: true },
})

const emit = defineEmits(['update:modelValue', 'select'])

const panelPaddingBottom = computed(() => {
  return `calc(16px + var(--sab, 0px) + var(--tabbar-height, 56px))`
})

function iconStyle(action) {
  return {
    background: action.color || props.primaryColor,
  }
}

function close() {
  emit('update:modelValue', false)
}

function onActionClick(action) {
  if (action.disabled) return
  if (props.autoClose) close()
  emit('select', action)
  if (typeof action.callback === 'function') {
    try {
      action.callback()
    } catch (e) {
      console.error('[MobileActionSheet] action callback error:', e)
    }
  }
}
</script>

<style scoped>
.sheet-overlay {
  position: fixed;
  inset: 0;
  z-index: 4500;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}
.sheet-panel {
  width: 100%;
  background: var(--color-bg-card);
  border-radius: var(--sheet-radius, 16px) var(--sheet-radius, 16px) 0 0;
  padding: 8px 16px;
  max-height: 80vh;
  overflow-y: auto;
}
[data-theme="dark"] .sheet-panel {
  background: var(--color-bg-card);
}

/* 把手 */
.sheet-handle {
  width: var(--sheet-handle-w, 36px);
  height: var(--sheet-handle-h, 4px);
  background: var(--color-border);
  border-radius: 2px;
  margin: 0 auto 12px;
}

/* 标题 */
.sheet-title {
  text-align: center;
  font-size: 13px;
  color: var(--color-text-secondary);
  margin-bottom: 12px;
  font-weight: var(--font-weight-medium, 500);
}

/* 行动列表 */
.sheet-actions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 8px;
}
.action-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 14px;
  background: var(--color-bg-page);
  border: none;
  border-radius: var(--radius-md);
  font-size: 15px;
  color: var(--color-text-primary);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  text-align: left;
  position: relative;
}
.action-item:active { background: var(--color-bg-hover); }
.action-item.danger {
  background: var(--color-danger-bg, #fef0f0);
  color: var(--color-danger, #F56C6C);
}
.action-item.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.action-icon {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  /* stylelint-disable-next-line color-named */
  color: white;
  font-weight: 600;
  flex-shrink: 0;
}
.action-label {
  flex: 1;
  font-weight: var(--font-weight-medium, 500);
}
.action-desc {
  font-size: 12px;
  color: var(--color-text-secondary);
  font-weight: var(--font-weight-normal, 400);
  margin-left: 8px;
}
.action-item.danger .action-desc {
  color: var(--color-danger, #F56C6C);
  opacity: 0.7;
}

/* 取消按钮 */
.cancel-btn {
  width: 100%;
  padding: 14px;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  font-size: 15px;
  font-weight: var(--font-weight-medium, 500);
  color: var(--color-text-primary);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  margin-top: 4px;
}
.cancel-btn:active {
  background: var(--color-bg-hover);
}

/* 进出动画 */
.action-sheet-enter-active, .action-sheet-leave-active {
  transition: opacity 0.25s ease;
}
.action-sheet-enter-active .sheet-panel,
.action-sheet-leave-active .sheet-panel {
  transition: transform 0.3s var(--ease-sheet);
}
.action-sheet-enter-from, .action-sheet-leave-to { opacity: 0; }
.action-sheet-enter-from .sheet-panel,
.action-sheet-leave-to .sheet-panel {
  transform: translateY(100%);
}
</style>
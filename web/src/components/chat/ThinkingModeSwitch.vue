<script setup>
/**
 * ThinkingModeSwitch.vue — v78 UI-redesign 思考模式分段控件
 *
 * 替代 顶栏 2 个 🧠/⚡ toggle button（视觉冲突）
 * 设计: 2 选 1 segmented control，input bar 上方
 * - 快速回答: 跳过 Self-RAG Phase 0.5 gate（useDeepThinking=false）
 * - 深度思考: 走 Self-RAG judge + 潜在重检索（useDeepThinking=true）
 *
 * a11y 4-attr 全部就绪
 * dark mode 走非 scoped 块（v60-v67 教训）
 */
import { Lightning, Cpu } from '@element-plus/icons-vue'
import { useUiStore } from '@/stores/useUiStore'

const uiStore = useUiStore()

const onChange = (val) => {
  if (val !== uiStore.useDeepThinking) {
    uiStore.setUseDeepThinking(val)
  }
}
</script>

<template>
  <div
    class="thinking-mode-switch"
    role="radiogroup"
    aria-label="思考模式"
    id="thinking-mode-switch"
    name="thinking-mode-switch"
  >
    <button
      id="thinking-mode-quick"
      name="thinking-mode-quick"
      type="button"
      role="radio"
      :aria-checked="!uiStore.useDeepThinking"
      :aria-label="'快速回答'"
      :title="'快速回答（跳过 judge 评估）'"
      class="mode-option"
      :class="{ active: !uiStore.useDeepThinking }"
      @click="onChange(false)"
    >
      <el-icon :size="14"><Lightning /></el-icon>
      <span>快速</span>
    </button>
    <button
      id="thinking-mode-deep"
      name="thinking-mode-deep"
      type="button"
      role="radio"
      :aria-checked="uiStore.useDeepThinking"
      :aria-label="'深度思考'"
      :title="'深度思考（带 Self-RAG 重检索 + judge）'"
      class="mode-option"
      :class="{ active: uiStore.useDeepThinking }"
      @click="onChange(true)"
    >
      <el-icon :size="14"><Cpu /></el-icon>
      <span>深度</span>
    </button>
  </div>
</template>

<style scoped>
.thinking-mode-switch {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 2px;
  border-radius: var(--radius-full);
  background: var(--color-bg-warm, #f5f7fa);
  border: 1px solid var(--color-border-light);
  transition: var(--transition-all-fast, all 0.15s ease);
}

.mode-option {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  background: transparent;
  border: none;
  border-radius: var(--radius-full);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  color: var(--color-text-secondary);
  transition: var(--transition-all-fast, all 0.15s ease);
  -webkit-tap-highlight-color: transparent;
}
.mode-option:hover { color: var(--color-text-primary); }
.mode-option:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 1px; }

.mode-option.active {
  background: var(--color-bg-card);
  color: var(--color-primary);
  box-shadow: var(--shadow-xs, 0 1px 2px rgba(0, 0, 0, 0.06));
}
</style>

<!-- v78 + v77 教训 (v60-v67): dark mode 必须非 scoped 块 -->
<style>
[data-theme="dark"] .thinking-mode-switch {
  background: var(--color-bg-warm, #2a2d35);
  border-color: var(--color-border-light);
}
[data-theme="dark"] .mode-option { color: var(--color-text-secondary); }
[data-theme="dark"] .mode-option:hover { color: var(--color-text-primary); }
[data-theme="dark"] .mode-option.active {
  background: var(--color-bg-card);
  color: var(--color-primary);
}
</style>

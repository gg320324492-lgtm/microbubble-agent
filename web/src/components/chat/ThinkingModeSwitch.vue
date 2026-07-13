<script setup>
/**
 * ThinkingModeSwitch.vue — v78 + 2026-07-13 #P1 三档推理模式 segmented control
 *
 * 替代 顶栏 2 个 🧠/⚡ toggle button（视觉冲突）
 * 设计: 3 选 1 segmented control，input bar 上方
 * - ⚡快速 (fast):     本地 Qwen3-8B + 关 Self-RAG + 小 budget
 * - 🖥平衡 (balanced): 本地 Qwen3-8B + 默认 Self-RAG judge (默认)
 * - ✨深度 (deep):     DeepSeek-R1-Distill-Qwen-7B + thinking + 重检索 2 次
 *
 * a11y 4-attr 全部就绪
 * dark mode 走非 scoped 块（v60-v67 教训）
 */
import { Lightning, Cpu, MagicStick } from '@element-plus/icons-vue'
import { useUiStore } from '@/stores/useUiStore'

const uiStore = useUiStore()

const MODES = [
  { value: 'fast', icon: Lightning, label: '快速', title: '快速回答 (Qwen3-8B · 跳过深度推理)' },
  { value: 'balanced', icon: Cpu, label: '平衡', title: '平衡模式 (Qwen3-8B · 默认 Self-RAG)' },
  { value: 'deep', icon: MagicStick, label: '深度', title: '深度模式 (DeepSeek-R1 + thinking + 重检索)' },
]

function onChange(value) {
  if (value !== uiStore.thinkingMode) {
    uiStore.setThinkingMode(value)
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
      v-for="m in MODES"
      :key="m.value"
      :id="`thinking-mode-${m.value}`"
      :name="`thinking-mode-${m.value}`"
      type="button"
      role="radio"
      :aria-checked="uiStore.thinkingMode === m.value"
      :aria-label="m.label"
      :title="m.title"
      class="mode-option"
      :class="[
        { active: uiStore.thinkingMode === m.value },
        `mode-${m.value}`,
      ]"
      @click="onChange(m.value)"
    >
      <el-icon :size="14"><component :is="m.icon" /></el-icon>
      <span>{{ m.label }}</span>
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

/* 2026-07-13 #P1: 深度模式专属紫色调 (明显区别于快速/平衡) */
.mode-option.active.mode-deep {
  background: linear-gradient(135deg, var(--color-primary-700, #5b21b6), var(--color-primary, #FF7A5C));
  color: #fff;
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
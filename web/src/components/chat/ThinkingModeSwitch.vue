<!--
ThinkingModeSwitch.vue — W72 B-2 子 plan ③ 起步 (派工 v6 段 5 反馈 #3 实战: type hint 必含)

设计要点:
- fast / balanced / deep 3 模式 segmented control
- 派工 v6 段 5 反馈 #3 实战: useUiStore v-model type hint 必含 (ThinkingMode enum export)
- 自 v78 / 2026-07-13 #P1 起即存在, W72 B-2 添加 lang="ts" + JSDoc 类型注释
- a11y 4-attr 全部就绪
- dark mode 走非 scoped 块 (v60-v67 教训)

[CHAT-P1-E E4] 移动端折叠面板:
- 桌面 (≥769px): 直接显示 segmented control (原样)
- 移动 (<769px): 默认收起, 仅显示当前模式 + ⚙️ 图标按钮
  点击 ⚙️ 展开三档 segmented control
- 复用同一 store 状态
-->
<script setup lang="ts">
/**
 * ThinkingModeSwitch.vue — v78 + 2026-07-13 #P1 三档推理模式 segmented control
 *
 * 替代 顶栏 2 个 🧠/⚡ toggle button（视觉冲突）
 * 设计: 3 选 1 segmented control，input bar 上方
 * - ⚡快速 (fast):     本地 Qwen3-8B + 小 budget + 跳过完整 agent 流程
 * - 🖥平衡 (balanced): 本地 Qwen3-8B + 默认 budget + 完整 agent 流程
 * - ✨深度 (deep):     DeepSeek-R1-Distill-Qwen-7B + thinking + 完整质量控制
 *
 * W72 B-2 改造 (派工 v6 段 5 反馈 #3 实战): useUiStore v-model type hint 必含
 *
 * [CHAT-P1-E E4] 移动端折叠面板 — 桌面显示完整, 移动默认收起
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { Lightning, Cpu, MagicStick, Setting } from '@element-plus/icons-vue'
import { useUiStore } from '@/stores/useUiStore'
import type { ThinkingMode } from '@/stores/useUiStore'

interface ModeOption {
  value: ThinkingMode
  icon: typeof Lightning
  label: string
  title: string
}

const uiStore = useUiStore()

const MODES: ModeOption[] = [
  { value: 'fast', icon: Lightning, label: '快速', title: '快速回答 (Qwen3-8B · 跳过深度推理)' },
  { value: 'balanced', icon: Cpu, label: '平衡', title: '平衡模式 (Qwen3-8B · 完整 Agent 流程)' },
  { value: 'deep', icon: MagicStick, label: '深度', title: '深度模式 (DeepSeek-R1 + thinking + 完整质量控制)' },
]

function onChange(value: ThinkingMode): void {
  if (value !== uiStore.thinkingMode) {
    uiStore.setThinkingMode(value)
  }
  // [CHAT-P1-E E4] 移动端选择后自动折叠
  if (isMobile.value) {
    mobileExpanded.value = false
  }
}

// [CHAT-P1-E E4] 移动端折叠状态
const isMobile = ref(false)
const mobileExpanded = ref(false)

let resizeListener: (() => void) | null = null

function checkMobile() {
  if (typeof window === 'undefined') return
  isMobile.value = window.innerWidth < 769
}

onMounted(() => {
  checkMobile()
  resizeListener = checkMobile
  window.addEventListener('resize', resizeListener)
})

onBeforeUnmount(() => {
  if (resizeListener) {
    window.removeEventListener('resize', resizeListener)
    resizeListener = null
  }
})

function toggleMobilePanel() {
  mobileExpanded.value = !mobileExpanded.value
}

const currentModeLabel = () => {
  const m = MODES.find(x => x.value === uiStore.thinkingMode)
  return m ? m.label : ''
}
</script>

<template>
  <!-- [CHAT-P1-E E4] 移动端折叠面板: 默认显示 ⚙️ + 当前模式, 展开后显示三档 -->
  <div
    v-if="isMobile"
    class="thinking-mode-switch-mobile"
    role="radiogroup"
    aria-label="思考模式"
    id="thinking-mode-switch"
    name="thinking-mode-switch"
  >
    <button
      type="button"
      class="mobile-toggle"
      :aria-expanded="mobileExpanded"
      :aria-label="`思考模式: ${currentModeLabel()}, 点击展开`"
      :title="`当前: ${currentModeLabel()}`"
      @click="toggleMobilePanel"
    >
      <el-icon :size="14"><Setting /></el-icon>
      <span class="mobile-mode-label">{{ currentModeLabel() }}</span>
    </button>
    <Transition name="mobile-expand">
      <div v-if="mobileExpanded" class="mobile-panel">
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
    </Transition>
  </div>

  <!-- 桌面端: 原 segmented control (不变) -->
  <div
    v-else
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
  /* #P5: 切换动效 — 弹性 scale + 颜色 + 阴影 */
  transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  -webkit-tap-highlight-color: transparent;
  position: relative;
  z-index: 1;
}
.mode-option:not(.active):hover {
  color: var(--color-text-primary);
  transform: scale(1.06);
}
.mode-option:active {
  transform: scale(0.94);
}
.mode-option:hover { color: var(--color-text-primary); }
.mode-option:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 1px; }

.mode-option.active {
  /* #P5: 统一所有模式选中态为深色实心背景 (主色珊瑚橙) + 白字 */
  background: linear-gradient(135deg, #FF5722 0%, #FF7A5C 100%);
  color: #ffffff;
  box-shadow: 0 2px 6px rgba(255, 87, 34, 0.35);
  /* #P5: 选中态弹跳 + 阴影增强 */
  transform: scale(1.08);
  animation: mode-pulse 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.mode-option.active:hover {
  transform: scale(1.1);
}
@keyframes mode-pulse {
  0% { transform: scale(0.85); }
  60% { transform: scale(1.12); }
  100% { transform: scale(1.08); }
}

/* 2026-07-13 #P1: 深度模式专属紫色调 (与快速/平衡区分 — 用紫色实心) */
.mode-option.active.mode-deep {
  background: linear-gradient(135deg, var(--color-primary-700, #5b21b6), #7c3aed);
  color: var(--el-color-white);
  box-shadow: 0 2px 6px rgba(91, 33, 182, 0.35);
  transform: scale(1.08);
  animation: mode-pulse 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

/* [CHAT-P1-E E4] 移动端折叠面板 */
.thinking-mode-switch-mobile {
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  position: relative;
}
.mobile-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--color-bg-warm, #f5f7fa);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-full);
  cursor: pointer;
  font-size: 12px;
  color: var(--color-text-primary);
  -webkit-tap-highlight-color: transparent;
}
.mobile-mode-label { font-weight: 500; }
.mobile-panel {
  display: flex;
  flex-direction: column;
  gap: 2px;
  position: absolute;
  bottom: calc(100% + 4px);
  left: 0;
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-md);
  padding: 4px;
  box-shadow: var(--shadow-md);
  z-index: 100;
  min-width: 120px;
}
.mobile-panel .mode-option {
  width: 100%;
  justify-content: flex-start;
  border-radius: var(--radius-sm);
  padding: 6px 10px;
}

/* 渐显动画 */
.mobile-expand-enter-active,
.mobile-expand-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.mobile-expand-enter-from,
.mobile-expand-leave-to {
  opacity: 0;
  transform: translateY(4px);
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
  /* v92 X-2 a11y: dark mode 主色文字 token (var(--color-primary-text) 在 dark 段亦定义) */
  color: var(--color-primary-text);
}

/* [CHAT-P1-E E4] 移动端 dark */
[data-theme="dark"] .thinking-mode-switch-mobile .mobile-toggle {
  background: var(--color-bg-warm, #2a2d35);
  border-color: var(--color-border-light);
  color: var(--color-text-primary);
}
[data-theme="dark"] .mobile-panel {
  background: var(--color-bg-card);
  border-color: var(--color-border-light);
}
</style>

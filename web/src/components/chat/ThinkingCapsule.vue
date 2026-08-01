<!--
  ThinkingCapsule.vue — 统一 Thinking Capsule (W99 +14)

  取代 ChatViewSSE.vue:547 三个 6px 跳动圆点。
  取代 RetrievalStatus.vue 在 assistant 气泡内的所有挂载。
  设计文档：C:\Users\pc\.claude\plans\rag-quirky-otter.md §5.3

  行为：
  - visible ref 控制终态延迟淡出（exitDelay 默认 400ms）
  - elapsed 200ms interval，终态即停 + onBeforeUnmount 清
  - 文案 <Transition> out-in 模式跨 stage 切换淡入淡出
  - a11y：role=status + aria-live=polite + 完整 aria-label

  数据源：assistantMsg.phase 推导式字段（useChatStream 接线）
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  isTerminalPhase,
  phaseLabel,
  type AssistantPhase,
} from '@/composables/chat/assistantPhase'

const props = withDefaults(
  defineProps<{
    phase?: AssistantPhase
    startedAt?: number
    foundCount?: number
    retryCount?: number
    compact?: boolean
    exitDelay?: number
  }>(),
  { phase: 'queued', exitDelay: 400 },
)

/** 终态后延迟淡出，让"已完成"有一帧被看见 */
const visible = ref(true)
let exitTimer: ReturnType<typeof setTimeout> | null = null
watch(
  () => props.phase,
  (p) => {
    if (isTerminalPhase(p)) {
      if (exitTimer) clearTimeout(exitTimer)
      exitTimer = setTimeout(() => {
        visible.value = false
      }, props.exitDelay)
    } else {
      if (exitTimer) {
        clearTimeout(exitTimer)
        exitTimer = null
      }
      visible.value = true
    }
  },
  { immediate: true },
)

/** elapsed：单个 200ms interval，终态即停 */
const elapsedMs = ref(0)
let ticker: ReturnType<typeof setInterval> | null = null
const stopTicker = () => {
  if (ticker) {
    clearInterval(ticker)
    ticker = null
  }
}
function startTicker() {
  stopTicker()
  if (!props.startedAt) return
  const tick = () => {
    elapsedMs.value = Date.now() - (props.startedAt as number)
  }
  tick()
  ticker = setInterval(tick, 200)
}
watch(
  () => [props.startedAt, props.phase] as const,
  ([sa, p]) => {
    if (!sa || isTerminalPhase(p as AssistantPhase)) stopTicker()
    else if (!ticker) startTicker()
  },
  { immediate: true },
)
onBeforeUnmount(() => {
  stopTicker()
  if (exitTimer) clearTimeout(exitTimer)
})

const elapsedText = computed(() => {
  if (!props.startedAt || elapsedMs.value <= 0) return ''
  const s = elapsedMs.value / 1000
  if (s < 60) return `${s.toFixed(1)}s`
  return `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`
})

const label = computed(() =>
  phaseLabel(props.phase, {
    foundCount: props.foundCount,
    retryCount: props.retryCount,
  }),
)

const ICONS: Partial<Record<AssistantPhase, string>> = {
  found: '📚',
  done: '✓',
  aborted: '⏹',
  error: '⚠',
}
const staticIcon = computed(() => ICONS[props.phase] ?? '')
const isSpinner = computed(
  () => props.phase === 'retrieving' || props.phase === 'refining',
)
const isDots = computed(() => !staticIcon.value && !isSpinner.value)
</script>

<template>
  <Transition name="capsule">
    <div
      v-if="visible"
      class="thinking-capsule"
      :class="{ compact }"
      :data-phase="phase"
      data-testid="thinking-capsule"
      role="status"
      aria-live="polite"
      :aria-label="`${label}${elapsedText ? '，已用时 ' + elapsedText : ''}`"
    >
      <span class="capsule-icon" aria-hidden="true">
        <span v-if="isSpinner" class="spinner" />
        <span v-else-if="isDots" class="dots"><i /><i /><i /></span>
        <span v-else class="glyph">{{ staticIcon }}</span>
      </span>
      <Transition name="capsule-label" mode="out-in">
        <span
          :key="label"
          class="capsule-label"
          data-testid="capsule-label"
          >{{ label }}</span
        >
      </Transition>
      <span
        v-if="elapsedText"
        class="capsule-elapsed"
        data-testid="capsule-elapsed"
        >{{ elapsedText }}</span
      >
    </div>
  </Transition>
</template>

<style scoped>
.thinking-capsule {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  margin: 2px 0 8px;
  border-radius: var(--radius-full);
  font-size: 13px;
  line-height: 1.4;
  color: var(--color-text-regular);
  background: var(--color-primary-bg);
  border: 1px solid transparent;
  animation: var(--animation-capsule-breathe);
}
.thinking-capsule.compact {
  gap: 6px;
  padding: 4px 9px;
  font-size: 11.5px;
  margin: 0 0 6px;
}

.thinking-capsule[data-phase='found'],
.thinking-capsule[data-phase='done'],
.thinking-capsule[data-phase='aborted'],
.thinking-capsule[data-phase='error'] {
  animation: none;
}
.thinking-capsule[data-phase='done'] {
  background: var(--color-success-bg);
  color: var(--color-success);
}
.thinking-capsule[data-phase='error'] {
  background: var(--color-danger-bg);
  color: var(--color-danger);
}
.thinking-capsule[data-phase='aborted'] {
  background: var(--color-bg-warm);
  color: var(--color-text-secondary);
}

.capsule-icon {
  display: inline-flex;
  align-items: center;
  min-width: 16px;
}
.glyph {
  font-size: 13px;
}
.compact .glyph {
  font-size: 11px;
}
.spinner {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  border: 2px solid var(--color-primary-bg);
  border-top-color: var(--color-primary);
  animation: var(--animation-spin);
}
.dots {
  display: inline-flex;
  gap: 3px;
}
.dots i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: pulse-dot 1.4s var(--ease-in-out) infinite;
}
.dots i:nth-child(2) {
  animation-delay: 0.18s;
}
.dots i:nth-child(3) {
  animation-delay: 0.36s;
}

.capsule-label {
  position: relative;
  font-weight: 500;
}
.thinking-capsule:not([data-phase='found']):not([data-phase='done']):not(
    [data-phase='aborted']
  ):not([data-phase='error']) .capsule-label::after {
  content: '';
  position: absolute;
  inset: 0;
  opacity: 0.45;
  pointer-events: none;
  background: linear-gradient(
    90deg,
    transparent 0%,
    var(--color-bg-card) 50%,
    transparent 100%
  );
  animation: var(--animation-shimmer);
}

.capsule-elapsed {
  font-size: 11px;
  color: var(--color-text-secondary);
  font-variant-numeric: tabular-nums;
}
.compact .capsule-elapsed {
  font-size: 10px;
}

.capsule-enter-active {
  animation: var(--animation-fadeSlideUp);
}
.capsule-leave-active {
  transition: opacity var(--duration-normal) var(--ease-in),
    transform var(--duration-normal) var(--ease-in);
}
.capsule-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
.capsule-label-enter-active,
.capsule-label-leave-active {
  transition: opacity var(--duration-fast) var(--ease-out);
}
.capsule-label-enter-from,
.capsule-label-leave-to {
  opacity: 0;
}

@media (prefers-reduced-motion: reduce) {
  .thinking-capsule,
  .thinking-capsule .spinner,
  .thinking-capsule .dots i,
  .capsule-enter-active {
    animation: none;
  }
  .thinking-capsule .capsule-label::after {
    display: none;
  }
}
</style>

<!-- dark mode 走非 scoped 块（v60-v67 教训） -->
<style>
[data-theme='dark'] .thinking-capsule {
  background: var(--color-bg-hover);
  color: var(--color-text-regular);
}
[data-theme='dark'] .thinking-capsule .capsule-label::after {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.08) 50%,
    transparent 100%
  );
}
</style>
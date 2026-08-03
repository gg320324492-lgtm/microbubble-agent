<!--
  PlanSteps.vue — W100 +22 plan_step 折叠展开
  W100 +49c RICHTEXT-UNFOLD 沿用: 默认 (collapsedByDefault=false) 直接渲染全部 step,
  无 toggle 按钮; LLM 显式 collapsedByDefault=true 时保留 ▼ ▸ 折叠切换 UI (协议兼容).
  W100 +52 升级: 默认模式下，全部 step done 后自动折叠成单行摘要 (类 20.124 风格保留).
  默认模式: 初次显示全部 step (expanded=true) → 全部 done 后 auto-collapse → 折叠态显示单行
  "✓ 计划完成: N 个步骤" + 一个展开 icon (点击可重新展开 step 列表).
  折叠模式 (collapsedByDefault=true): 用户主动 toggle 控制, auto-collapse 不干预.

  设计约束（用户视角 P0 #2）：
  - 默认折叠态：📋 计划中: N 个步骤 (折叠模式初始) / ✓ 计划完成: N 个步骤 (auto-collapse 后默认模式)
  - 默认展开态：列出 step / tool / status (01/02/03 编号 + status 圆点)
  - 全部 done 后自动折叠（独立于 collapsedByDefault，类 20.124 风格不可破）
    - 默认模式：all-done → 折叠成单行摘要 + 展开 icon (W100 +52 升级)
    - LLM-controlled 折叠模式：保留原有 watch + auto-collapse 行为
  - 与 ThinkingCapsule 风格统一：3px 左蓝边 + fadeSlideUp + stagger
  - a11y: role=button + aria-expanded + keyboard Enter/Space
  - 移动端 compact 模式：36px tap target
  - dark mode: 走非 scoped 块（v60-v67 教训）

  数据结构 contract（来自 useChatStream.ts:126）：
  Array<{ step: string; tool?: string; status: 'pending' | 'running' | 'done' }>
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

interface PlanStep {
  step: string
  tool?: string
  status: 'pending' | 'running' | 'done'
}

const props = withDefaults(
  defineProps<{
    steps: PlanStep[]
    compact?: boolean
    /**
     * LLM 显式要求折叠时才保留折叠 UI。
     * 默认 false 与 RICHTEXT-UNFOLD 协议一致：默认展开，真实 step 数据直接可见。
     */
    collapsedByDefault?: boolean
  }>(),
  { compact: false, collapsedByDefault: false },
)

/**
 * 初始 expanded 沿用 W100 +49c 行为 (true 默认模式 / false 折叠模式)。
 * W100 +52 升级：auto-collapse watcher 在默认模式 + all-done 时把 expanded 翻为 false，
 * 折叠模式跳过此逻辑 (用户控制)。
 */
const expanded = ref(!props.collapsedByDefault)

const doneCount = computed(() => props.steps.filter((s) => s.status === 'done').length)
const runningIndex = computed(() => props.steps.findIndex((s) => s.status === 'running'))
const total = computed(() => props.steps.length)

/** 摘要文案 — 不同状态下显示不同进度感 */
const summary = computed(() => {
  const t = total.value
  const d = doneCount.value
  if (d === 0) return `计划中: ${t} 个步骤`
  if (d === t) return `计划完成: ${t} 个步骤`
  return `计划中: ${d}/${t} 步骤`
})

/**
 * 全部 done 后自动折叠（一次性 watch, W100 +52 升级：默认模式生效, 折叠模式跳过）。
 * 默认模式: 从"进行中" (oldVal > 0) 变为"全部 done" → 折叠成单行摘要 (新行为).
 * 折叠模式: 用户手动 toggle 控制展开/折叠, auto-collapse 不干预 (LLM 显式要求保留折叠 UI).
 * 边界: 必须 `oldVal > 0` 守卫 — 初次加载如果所有 step 已 done 状态 (oldVal=0) 不应折叠.
 * 类 20.124 风格: 保留 watch 行为不变 (flush: 'sync'), 仅门控副作用.
 */
watch(
  doneCount,
  (newVal, oldVal) => {
    if (props.collapsedByDefault) return  // 折叠模式跳过自动折叠
    if (oldVal > 0 && newVal === total.value && total.value > 0) {
      expanded.value = false
    }
  },
  { flush: 'sync' },
)

/** 当前是否展开：默认模式受 expanded 控制 (含 auto-collapse); 折叠模式同 */
const isShown = computed(() => expanded.value)

function toggle() {
  expanded.value = !expanded.value
}

function pad(n: number): string {
  return String(n + 1).padStart(2, '0')
}

function statusGlyph(s: PlanStep['status']): string {
  if (s === 'done') return '✓'
  if (s === 'running') return ''
  return ''
}
</script>

<template>
  <div
    v-if="steps && steps.length"
    class="plan-steps"
    :class="{ compact, 'auto-collapsed': !collapsedByDefault && !expanded }"
    data-testid="plan-steps"
    :data-collapsed-by-default="collapsedByDefault ? 'true' : 'false'"
  >
    <div
      v-if="collapsedByDefault"
      class="plan-steps-header"
      role="button"
      tabindex="0"
      :aria-expanded="expanded ? 'true' : 'false'"
      :aria-controls="`plan-steps-detail`"
      :aria-label="`${expanded ? '收起' : '展开'}计划步骤: ${summary}`"
      data-testid="plan-steps-toggle-header"
      @click="toggle"
      @keydown.enter.prevent="toggle"
      @keydown.space.prevent="toggle"
    >
      <span class="plan-steps-icon" aria-hidden="true">📋</span>
      <span class="plan-steps-summary" data-testid="plan-steps-summary">{{ summary }}</span>
      <span v-if="runningIndex >= 0 && !expanded" class="plan-steps-running-dot" aria-hidden="true" />
      <span class="plan-steps-toggle" aria-hidden="true">{{ expanded ? '▾' : '▸' }}</span>
    </div>

    <!-- 默认模式 (W100 +52): 全部 done 后 auto-collapse 成单行摘要 + 展开 icon -->
    <div
      v-else-if="!expanded"
      class="plan-steps-header plan-steps-header-auto"
      role="button"
      tabindex="0"
      :aria-expanded="'false'"
      :aria-controls="`plan-steps-detail`"
      :aria-label="`展开计划步骤: ${summary}`"
      data-testid="plan-steps-toggle-header"
      @click="toggle"
      @keydown.enter.prevent="toggle"
      @keydown.space.prevent="toggle"
    >
      <span class="plan-steps-icon plan-steps-tick" aria-hidden="true">✓</span>
      <span class="plan-steps-summary" data-testid="plan-steps-summary">{{ summary }}</span>
      <span class="plan-steps-toggle" aria-hidden="true">▸</span>
    </div>

    <!-- 默认模式：展开态直接渲染列表，无折叠过渡 -->
    <ul
      v-else
      id="plan-steps-detail"
      class="plan-steps-list plan-steps-list-unfolded"
      data-testid="plan-steps-list"
      role="list"
    >
      <li
        v-for="(s, i) in steps"
        :key="i"
        class="plan-step"
        :class="[`plan-step-${s.status}`, `stagger-${Math.min(i + 1, 6)}`]"
        :data-testid="`plan-step-${i}`"
        :data-status="s.status"
        :aria-label="`步骤 ${i + 1}: ${s.step}${s.tool ? ', 使用工具 ' + s.tool : ''}, ${s.status === 'done' ? '已完成' : s.status === 'running' ? '进行中' : '待执行'}`"
      >
        <span class="plan-step-num" aria-hidden="true">{{ pad(i) }}</span>
        <span class="plan-step-name" :data-testid="`plan-step-${i}-name`">{{ s.step }}</span>
        <span
          v-if="s.tool"
          class="plan-step-tool"
          :data-testid="`plan-step-${i}-tool`"
          >{{ s.tool }}</span
        >
        <span
          class="plan-step-status"
          :class="`plan-step-status-${s.status}`"
          :data-testid="`plan-step-${i}-status`"
          :aria-label="s.status === 'done' ? '已完成' : s.status === 'running' ? '进行中' : '待执行'"
        >
          <span v-if="s.status === 'running'" class="plan-step-spinner" aria-hidden="true" />
          <span v-else-if="s.status === 'done'" class="plan-step-tick" aria-hidden="true">✓</span>
          <span v-else class="plan-step-pending" aria-hidden="true" />
        </span>
      </li>
    </ul>
    <Transition v-if="collapsedByDefault" name="plan-steps-detail">
      <ul
        v-if="isShown"
        id="plan-steps-detail"
        class="plan-steps-list"
        data-testid="plan-steps-list"
        role="list"
      >
        <li
          v-for="(s, i) in steps"
          :key="i"
          class="plan-step"
          :class="[`plan-step-${s.status}`, `stagger-${Math.min(i + 1, 6)}`]"
          :data-testid="`plan-step-${i}`"
          :data-status="s.status"
          :aria-label="`步骤 ${i + 1}: ${s.step}${s.tool ? ', 使用工具 ' + s.tool : ''}, ${s.status === 'done' ? '已完成' : s.status === 'running' ? '进行中' : '待执行'}`"
        >
          <span class="plan-step-num" aria-hidden="true">{{ pad(i) }}</span>
          <span class="plan-step-name" :data-testid="`plan-step-${i}-name`">{{ s.step }}</span>
          <span
            v-if="s.tool"
            class="plan-step-tool"
            :data-testid="`plan-step-${i}-tool`"
            >{{ s.tool }}</span
          >
          <span
            class="plan-step-status"
            :class="`plan-step-status-${s.status}`"
            :data-testid="`plan-step-${i}-status`"
            :aria-label="s.status === 'done' ? '已完成' : s.status === 'running' ? '进行中' : '待执行'"
          >
            <span v-if="s.status === 'running'" class="plan-step-spinner" aria-hidden="true" />
            <span v-else-if="s.status === 'done'" class="plan-step-tick" aria-hidden="true">✓</span>
            <span v-else class="plan-step-pending" aria-hidden="true" />
          </span>
        </li>
      </ul>
    </Transition>

    <!-- 默认模式 a11y 隐藏 summary (展开态时)，仅屏幕阅读器可见 -->
    <div
      v-if="!collapsedByDefault && expanded"
      class="plan-steps-summary plan-steps-summary-static"
      data-testid="plan-steps-summary-static"
      role="status"
      aria-live="polite"
    >
      {{ summary }}
    </div>
  </div>
</template>

<style scoped>
.plan-steps {
  display: block;
  border-radius: var(--radius-md, 8px);
  font-size: 13px;
  line-height: 1.4;
  color: var(--color-text-regular);
  background: var(--color-bg-card);
  border-left: 3px solid var(--color-primary);
  padding: 4px 0;
  margin: 4px 0 8px;
  max-width: 100%;
  overflow: hidden;
}
.plan-steps.compact {
  font-size: 11.5px;
  padding: 2px 0;
  margin: 2px 0 6px;
}

.plan-steps-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  min-height: 44px;
  cursor: pointer;
  user-select: none;
  outline: none;
  transition: background 150ms ease;
}
.plan-steps.compact .plan-steps-header {
  min-height: 36px;
  padding: 4px 9px;
  gap: 6px;
}
.plan-steps-header:hover { background: var(--color-primary-bg); }
.plan-steps-header:focus-visible {
  box-shadow: 0 0 0 2px var(--color-primary);
}

/* W100 +52: 默认模式 auto-collapse 后的单行 header，绿色 tick 视觉提示完成 */
.plan-steps-header-auto {
  background: var(--color-success-bg, #f0f9eb);
  border-left-color: var(--color-success, #67c23a);
}
.plan-steps-header-auto:hover { background: var(--color-success-bg-hover, #e1f3d8); }
.plan-steps-header-auto .plan-steps-tick {
  color: var(--color-success, #67c23a);
  font-weight: 700;
}

.plan-steps-icon {
  font-size: 13px;
}
.plan-steps.compact .plan-steps-icon {
  font-size: 11px;
}

.plan-steps-summary {
  font-weight: 500;
  flex: 1;
}

.plan-steps-running-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: var(--animation-pulse-dot, pulse-dot 1.4s ease-in-out infinite);
}

.plan-steps-toggle {
  color: var(--color-text-secondary);
  font-size: 11px;
  min-width: 12px;
  text-align: right;
}

.plan-steps-list {
  list-style: none;
  margin: 0;
  padding: 4px 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.plan-steps.compact .plan-steps-list {
  padding: 2px 9px 6px;
}
/* 默认模式（always unfolded）：列表无 padding-top，与 header 拆开 */
.plan-steps-list-unfolded {
  padding: 8px 12px 10px;
}
.plan-steps.compact .plan-steps-list-unfolded {
  padding: 6px 9px 8px;
}

/* 默认模式 a11y 隐藏 summary，仅屏幕阅读器可见 */
.plan-steps-summary-static {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.plan-step {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 6px;
  border-radius: var(--radius-sm, 4px);
  font-size: 12.5px;
}
.plan-steps.compact .plan-step {
  padding: 3px 4px;
  font-size: 11px;
  gap: 6px;
}

/* pending 步骤半透明 */
.plan-step-pending {
  opacity: 0.55;
}
/* running 高亮 — 背景浅珊瑚 */
.plan-step-running {
  background: var(--color-primary-bg);
  opacity: 1;
}
/* done 实色 */
.plan-step-done {
  opacity: 1;
}

.plan-step-num {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 11px;
  color: var(--color-text-secondary);
  min-width: 18px;
  font-variant-numeric: tabular-nums;
}

.plan-step-name {
  flex: 1;
  color: var(--color-text-regular);
}

.plan-step-tool {
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 11px;
  color: var(--color-text-secondary);
  background: var(--color-bg-secondary, #F0F2F5);
  padding: 1px 6px;
  border-radius: var(--radius-sm, 4px);
}
.plan-steps.compact .plan-step-tool {
  font-size: 10px;
  padding: 0 4px;
}

.plan-step-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  min-height: 18px;
}

.plan-step-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--color-primary-bg);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: var(--animation-spin, spin 0.8s linear infinite);
}

.plan-step-tick {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--color-success-bg);
  color: var(--color-success);
  font-size: 11px;
  font-weight: 700;
}

.plan-step-pending {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-text-placeholder, #C0C4CC);
}

/* stagger 入场 — 与 ToolTraceItem 保持一致 */
.plan-step.stagger-1 { animation: var(--animation-fadeSlideUp, fadeSlideUp) 0.2s ease-out 0.0s both; }
.plan-step.stagger-2 { animation: var(--animation-fadeSlideUp, fadeSlideUp) 0.2s ease-out 0.05s both; }
.plan-step.stagger-3 { animation: var(--animation-fadeSlideUp, fadeSlideUp) 0.2s ease-out 0.10s both; }
.plan-step.stagger-4 { animation: var(--animation-fadeSlideUp, fadeSlideUp) 0.2s ease-out 0.15s both; }
.plan-step.stagger-5 { animation: var(--animation-fadeSlideUp, fadeSlideUp) 0.2s ease-out 0.20s both; }
.plan-step.stagger-6 { animation: var(--animation-fadeSlideUp, fadeSlideUp) 0.2s ease-out 0.25s both; }

/* 展开收起过渡 */
.plan-steps-detail-enter-active {
  transition: opacity var(--duration-fast, 150ms) ease, transform var(--duration-fast, 150ms) ease;
}
.plan-steps-detail-leave-active {
  transition: opacity var(--duration-fast, 150ms) ease, transform var(--duration-fast, 150ms) ease;
}
.plan-steps-detail-enter-from { opacity: 0; transform: translateY(-4px); }
.plan-steps-detail-leave-to { opacity: 0; transform: translateY(-4px); }

/* 脉冲呼吸 — 给 running dot 用 */
@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.4; transform: scale(0.8); }
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .plan-step,
  .plan-steps-running-dot,
  .plan-step-spinner,
  .plan-steps-detail-enter-active,
  .plan-steps-detail-leave-active {
    animation: none !important;
    transition: none !important;
  }
}
</style>

<!-- dark mode 走非 scoped 块（v60-v67 教训） -->
<style>
[data-theme='dark'] .plan-steps {
  background: var(--color-bg-card);
  border-left-color: var(--color-primary);
}
[data-theme='dark'] .plan-steps-header:hover { background: var(--color-bg-hover); }
[data-theme='dark'] .plan-step-tool {
  background: var(--color-bg-secondary);
  color: var(--color-text-secondary);
}
[data-theme='dark'] .plan-step-running {
  background: rgba(var(--color-primary-rgb), 0.1);
}
/* W100 +52: dark mode 下 auto-collapse header 用深绿底 */
[data-theme='dark'] .plan-steps-header-auto {
  background: rgba(103, 194, 58, 0.15);
}
[data-theme='dark'] .plan-steps-header-auto:hover {
  background: rgba(103, 194, 58, 0.25);
}
</style>
<!--
  EventBadges.vue — W100 +26 SSE 事件徽章渲染

  设计目标（P1-C 后端事件已发未渲染）:
  - 后端 SSE 已发 7 个事件 (synthesis_start / retry / critique / tool_compressed / intent_detected / plan_step / brief+detail)
  - 前端仅 toolTrace 文字流做了 4 件 (intent / plan / synthesis-thinking / retry-thinking) → 0 状态徽章
  - 本组件: 把"事件级状态"提升为彩色 tag 徽章, 让用户看到 LLM 正在做什么

  数据 contract（来自 useChatStream.ts ChatMessage, W100 +21..+25 沉淀）:
  - intent?: { category, confidence, ... }              → intent_detected
  - plan?: PlanStep[]                                   → plan_step (已被 PlanSteps 组件吞)
  - critique?: { score, suggestion, ... }               → critique 完成
  - retryCount?: number                                 → retry 累计次数
  - toolTrace?: Array<{ type, label?, name?, compression?: { original_count, selected_count, summary } }>
      - synthesis_start 事件 push { type: 'thinking', label: '✨ 综合分析中...' }
      - tool_compressed 事件 push { type: 'thinking', label: '🗜️ 压缩：...' } + 写到 lastTool.compression

  4 状态显示逻辑（按 phase / 字段）:
  - synthesis_start: 短暂闪动 (3s 后消失), 蓝色 tag
  - retry: 持续直到 done, 橙色 tag, 显示当前第 N 次
  - critique 完成: 全 message 期间显示, 绿色 tag
  - tool_compressed: 灰底 tag, 一次, 显示 "N → M 条"

  位置: msg-content 之后 / ChatMessageActions 之前
  a11y: role="status" + 语义化 aria-label + 视觉 disabled 状态
  移动端: compact prop
  dark mode: 走非 scoped 块（v60-v67 教训）
-->
<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'

interface SynthesisEvent {
  type: 'thinking'
  label: string
}
interface ToolWithCompression {
  type: 'tool' | 'thinking'
  label?: string
  name?: string
  compression?: {
    original_count: number
    selected_count: number
    summary: string
  }
}

interface ChatMessageLike {
  role?: 'user' | 'assistant'
  intent?: { category: string; confidence: number } | null
  critique?: { score: number; suggestion?: string } | null
  retryCount?: number
  toolTrace?: Array<SynthesisEvent | ToolWithCompression>
  state?: 'streaming' | 'idle' | 'aborted'
}

const props = withDefaults(
  defineProps<{
    msg: ChatMessageLike
    compact?: boolean
  }>(),
  { compact: false },
)

// ---------------------------------------------------------------------------
// synthesis_start 短暂闪动 (3s 后消失)
// ---------------------------------------------------------------------------
const SYNTHESIS_BURST_MS = 3000

/** 是否有 synthesis_start thinking 块 (label 包含 "✨ 综合" 或 "synthesis") */
const hasSynthesisEvent = computed(() => {
  const trace = props.msg.toolTrace
  if (!Array.isArray(trace)) return false
  return trace.some((t) => {
    if (t.type !== 'thinking' || !t.label) return false
    return /综合|synthesis/i.test(t.label)
  })
})

/** synthesis burst 是否在显示中 (3s 窗口) */
const synthesisVisible = ref(false)
let synthesisTimer: ReturnType<typeof setTimeout> | null = null

watch(
  hasSynthesisEvent,
  (now, before) => {
    if (now && !before) {
      // 新触发 synthesis_start → 显示 burst
      synthesisVisible.value = true
      if (synthesisTimer) clearTimeout(synthesisTimer)
      synthesisTimer = setTimeout(() => {
        synthesisVisible.value = false
      }, SYNTHESIS_BURST_MS)
    } else if (!now && before) {
      // 没了 (异常情况: toolTrace 被清空) → 立即收
      synthesisVisible.value = false
      if (synthesisTimer) {
        clearTimeout(synthesisTimer)
        synthesisTimer = null
      }
    }
  },
  { immediate: true },
)

onBeforeUnmount(() => {
  if (synthesisTimer) clearTimeout(synthesisTimer)
})

// ---------------------------------------------------------------------------
// retry badge — 持续直到 done
// ---------------------------------------------------------------------------
const retryCount = computed(() => props.msg.retryCount || 0)
const retryActive = computed(() => {
  // streaming 中且 retryCount > 0 → 持续显示
  return props.msg.state === 'streaming' && retryCount.value > 0
})
const retryLabel = computed(() => `正在重新优化（第 ${retryCount.value} 次）`)

// ---------------------------------------------------------------------------
// critique 完成 — 全 message 期间显示
// ---------------------------------------------------------------------------
const critiqueScore = computed(() => props.msg.critique?.score ?? null)
const critiqueLabel = computed(() =>
  critiqueScore.value == null
    ? '自我评估完成'
    : `自我评估 score=${critiqueScore.value}/10`,
)

// ---------------------------------------------------------------------------
// tool_compressed — 找最近一个带 compression 的 tool 项, 一次性显示
// ---------------------------------------------------------------------------
const compressedInfo = computed(() => {
  const trace = props.msg.toolTrace
  if (!Array.isArray(trace)) return null
  // 反向找最近一个带 compression 的 tool 项
  for (let i = trace.length - 1; i >= 0; i--) {
    const t = trace[i] as ToolWithCompression
    if (t.compression) {
      return {
        original_count: t.compression.original_count,
        selected_count: t.compression.selected_count,
        summary: t.compression.summary,
        name: t.name,
      }
    }
  }
  return null
})

const compressedLabel = computed(() => {
  if (!compressedInfo.value) return ''
  const { original_count, selected_count } = compressedInfo.value
  return `上下文压缩 (${original_count} → ${selected_count} 条)`
})

// ---------------------------------------------------------------------------
// 总开关 — 4 个状态同时为 false 时组件返回 null
// ---------------------------------------------------------------------------
const showSynthesis = computed(
  () => hasSynthesisEvent.value && synthesisVisible.value,
)
const showRetry = computed(() => retryActive.value)
const showCritique = computed(() => critiqueScore.value != null)
const showCompressed = computed(() => compressedInfo.value != null)

const anyVisible = computed(
  () =>
    showSynthesis.value ||
    showRetry.value ||
    showCritique.value ||
    showCompressed.value,
)
</script>

<template>
  <div
    v-if="anyVisible"
    class="event-badges"
    :class="{ compact }"
    role="status"
    aria-live="polite"
    data-testid="event-badges"
  >
    <!-- synthesis_start: 短暂闪动 (3s) -->
    <span
      v-if="showSynthesis"
      class="event-badge event-badge-synthesis"
      data-testid="event-badge-synthesis"
      :class="{ compact }"
      :aria-label="'正在组织回答'"
    >
      <span class="event-badge-icon" aria-hidden="true">📝</span>
      <span class="event-badge-text">正在组织回答</span>
    </span>

    <!-- retry: 持续直到 done -->
    <span
      v-if="showRetry"
      class="event-badge event-badge-retry"
      data-testid="event-badge-retry"
      :class="{ compact }"
      :aria-label="retryLabel"
    >
      <span class="event-badge-icon" aria-hidden="true">🔄</span>
      <span class="event-badge-text" data-testid="event-badge-retry-text">{{ retryLabel }}</span>
    </span>

    <!-- critique: 全 message 期间显示 -->
    <span
      v-if="showCritique"
      class="event-badge event-badge-critique"
      data-testid="event-badge-critique"
      :class="{ compact }"
      :aria-label="critiqueLabel"
    >
      <span class="event-badge-icon" aria-hidden="true">✓</span>
      <span class="event-badge-text" data-testid="event-badge-critique-text">{{ critiqueLabel }}</span>
    </span>

    <!-- tool_compressed: 一次性, 显示 N → M 条 -->
    <span
      v-if="showCompressed"
      class="event-badge event-badge-compressed"
      data-testid="event-badge-compressed"
      :class="{ compact }"
      :aria-label="compressedLabel"
    >
      <span class="event-badge-icon" aria-hidden="true">📦</span>
      <span class="event-badge-text" data-testid="event-badge-compressed-text">{{ compressedLabel }}</span>
    </span>
  </div>
</template>

<style scoped>
.event-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 6px 0 0;
  padding: 0;
  font-size: 12px;
  line-height: 1.2;
  max-width: 100%;
}
.event-badges.compact {
  gap: 4px;
  margin: 4px 0 0;
  font-size: 11px;
}

.event-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 999px;
  font-weight: 500;
  white-space: nowrap;
  user-select: none;
  border: 1px solid transparent;
  transition: background var(--duration-fast, 150ms) ease;
}
.event-badge.compact {
  padding: 2px 6px;
  gap: 3px;
}

.event-badge-icon {
  font-size: 11px;
  line-height: 1;
}
.event-badge.compact .event-badge-icon {
  font-size: 10px;
}

.event-badge-text {
  font-size: inherit;
}

/* synthesis — 蓝 */
.event-badge-synthesis {
  background: rgba(64, 158, 255, 0.1);
  color: #1890ff;
  border-color: rgba(64, 158, 255, 0.3);
  animation: event-badge-pulse 1s ease-in-out 3;
}

/* retry — 橙 (用 --color-accent 金橙) */
.event-badge-retry {
  background: rgba(255, 179, 71, 0.16);
  color: #d97706;
  border-color: rgba(255, 179, 71, 0.4);
}
.event-badge-retry .event-badge-icon {
  animation: event-badge-spin 1.6s linear infinite;
  display: inline-block;
}

/* critique — 绿 */
.event-badge-critique {
  background: rgba(103, 194, 58, 0.12);
  color: #16a34a;
  border-color: rgba(103, 194, 58, 0.35);
}

/* tool_compressed — 灰 */
.event-badge-compressed {
  background: rgba(144, 147, 153, 0.12);
  color: #606266;
  border-color: rgba(144, 147, 153, 0.3);
}

@keyframes event-badge-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(0.96); }
}
@keyframes event-badge-spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .event-badge-synthesis,
  .event-badge-retry .event-badge-icon {
    animation: none !important;
  }
}
</style>

<!-- dark mode 走非 scoped 块（v60-v67 教训） -->
<style>
[data-theme='dark'] .event-badge-synthesis {
  background: rgba(64, 158, 255, 0.18);
  color: #69b1ff;
  border-color: rgba(64, 158, 255, 0.4);
}
[data-theme='dark'] .event-badge-retry {
  background: rgba(255, 179, 71, 0.22);
  color: #fcd34d;
  border-color: rgba(255, 179, 71, 0.5);
}
[data-theme='dark'] .event-badge-critique {
  background: rgba(103, 194, 58, 0.2);
  color: #6ee7b7;
  border-color: rgba(103, 194, 58, 0.45);
}
[data-theme='dark'] .event-badge-compressed {
  background: rgba(180, 180, 180, 0.15);
  color: #c0c4cc;
  border-color: rgba(180, 180, 180, 0.3);
}
</style>

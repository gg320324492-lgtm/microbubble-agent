<!--
FollowUpChips.vue — CHAT-P1-E E2 追问 chips 组件
监听 SSE `suggestions` 事件, 显示 2-3 个追问建议 chip
点击 chip → 复用 sendSSE (同 session 触发新 SSE 请求)

设计要点:
- 监听 `useChatStream` 的 suggestions 事件流 (经由 emit 透传)
- 桌面: 横排 chip + hover 高亮
- 移动: 横排 chip + 大点击区
- 加载态: 渐显动画
-->
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps<{
  /** 当前 session id (用于绑定事件源) */
  sessionId: string
  /** 点击 chip 后的回调, 透传到 sendSSE */
  onClick?: (suggestion: string) => void
}>()

const suggestions = ref<string[]>([])
const isVisible = ref(false)
/* ===== W99 +16 FollowUpChips skeleton 等待态 =====
   用户发新消息 → 用 isWaiting 占位 5s skeleton, suggestions 到达或超时后切换 */
const isWaiting = ref(false)
let waitTimer: ReturnType<typeof setTimeout> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

const stopWait = () => {
  if (waitTimer) {
    clearTimeout(waitTimer)
    waitTimer = null
  }
}

/**
 * 监听 suggestions 事件:
 * - 通过全局 window 事件总线接收 (useChatStream 在 yield 时 dispatch)
 * - 或通过 prop 传入的 onClick 触发
 *
 * 实现策略: 注册 window 'chat:suggestions' 事件
 * (useChatStream 收到 suggestions 事件时 emit)
 */
const handleSuggestions = (e: Event) => {
  const detail = (e as CustomEvent).detail
  if (!detail || detail.sessionId !== props.sessionId) return
  const items = Array.isArray(detail.suggestions) ? detail.suggestions : []
  stopWait()
  isWaiting.value = false
  if (items.length === 0) {
    isVisible.value = false
    return
  }
  suggestions.value = items.slice(0, 3)
  isVisible.value = true
}

const handleSendStart = () => {
  // 用户发新消息 → 隐藏旧 suggestions + 进入等待态
  isVisible.value = false
  suggestions.value = []
  isWaiting.value = true
  stopWait()
  // 5s 超时兜底（避免 suggestions 永远不到时永远转）
  waitTimer = setTimeout(() => {
    isWaiting.value = false
  }, 5000)
}

onMounted(() => {
  window.addEventListener('chat:suggestions', handleSuggestions as EventListener)
  window.addEventListener('chat:send-start', handleSendStart)
})

onBeforeUnmount(() => {
  window.removeEventListener('chat:suggestions', handleSuggestions as EventListener)
  window.removeEventListener('chat:send-start', handleSendStart)
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  stopWait()
})

function clickChip(s: string) {
  if (props.onClick) {
    props.onClick(s)
  }
  // 点击后立即隐藏 (用户已经选择)
  isVisible.value = false
}
</script>

<template>
  <Transition name="chip-fade">
    <!-- ===== W99 +16 skeleton 等待态 ===== -->
    <div v-if="isWaiting" class="followup-chips followup-skeleton" aria-label="正在生成追问建议">
      <span class="hint-text">💡 追问:</span>
      <span class="skeleton skeleton-chip" style="width: 88px" />
      <span class="skeleton skeleton-chip" style="width: 120px" />
      <span class="skeleton skeleton-chip" style="width: 96px" />
    </div>
    <div v-if="isVisible && suggestions.length" class="followup-chips">
      <span class="hint-text">💡 追问:</span>
      <button
        v-for="(s, i) in suggestions"
        :key="`${s}-${i}`"
        type="button"
        class="chip"
        :aria-label="`追问: ${s}`"
        :title="s"
        @click="clickChip(s)"
      >
        {{ s }}
      </button>
    </div>
  </Transition>
</template>

<style scoped>
.followup-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  padding: 8px 0;
  margin-top: 4px;
}
.hint-text {
  font-size: 12px;
  color: var(--color-text-secondary);
  margin-right: 4px;
}
.chip {
  display: inline-block;
  padding: 5px 12px;
  font-size: 13px;
  background: var(--color-bg-warm);
  color: var(--color-primary);
  border: 1px solid var(--color-primary);
  border-radius: 16px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
  -webkit-tap-highlight-color: transparent;
}
.chip:hover {
  background: var(--color-primary);
  color: white;
}
.chip:active {
  transform: scale(0.96);
}

/* ===== W99 +16 skeleton 等待态（复用全局 .skeleton 阴影效果） ===== */
.followup-skeleton {
  /* 与正常 chips 同行布局，仅内部 skeleton 元素 shimmer */
}
.skeleton-chip {
  display: inline-block;
  height: 18px;
  border-radius: 16px;
  background: var(--color-bg-warm);
  opacity: 0.6;
  position: relative;
  overflow: hidden;
}
.skeleton-chip::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    var(--color-bg-card) 50%,
    transparent 100%
  );
  animation: var(--animation-shimmer);
}

@media (prefers-reduced-motion: reduce) {
  .skeleton-chip::after { animation: none; }
}

/* 渐显动画 */
.chip-fade-enter-active,
.chip-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.chip-fade-enter-from,
.chip-fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>

<!-- 移动端适配 (走非 scoped 块) -->
<style>
@media (max-width: 768px) {
  .followup-chips {
    padding: 6px 0;
  }
  .followup-chips .chip {
    padding: 8px 14px;
    font-size: 14px;
    min-height: 36px;
  }
}
</style>
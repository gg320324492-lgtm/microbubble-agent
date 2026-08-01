<!--
RetrievalStatus.vue — CHAT-P1-E E5 检索过程可视化组件
监听 SSE `chat:retrieval-status` 事件, 显示三段状态行:
1. searching — 正在检索 (tool_use 触发)
2. found — 找到 N 条相关内容 (tool_result 触发)
3. generating — 生成中 (首个 text_delta 触发)

设计要点:
- 默认可见, 不依赖 showThinking 开关
- 三段行级显示, 紧凑布局
- dark mode 走非 scoped 块 (v60-v67 教训)
- 桌面 + 移动共用 (父组件传 compact 模式)
-->
<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps<{
  /** 当前 session id (过滤事件) */
  sessionId: string
  /** 紧凑模式 (移动端) */
  compact?: boolean
}>()

interface RetrievalStatus {
  stage: 'searching' | 'found' | 'generating'
  toolName?: string
  count?: number
  messageId?: string
  ts: number
}

const status = ref<RetrievalStatus | null>(null)

function handleEvent(e: Event) {
  const detail = (e as CustomEvent).detail
  if (!detail || detail.sessionId !== props.sessionId) return
  status.value = {
    stage: detail.stage,
    toolName: detail.toolName,
    count: detail.count,
    messageId: detail.messageId,
    ts: Date.now(),
  }
  // found 阶段后 1.5s 自动隐藏 (让位给 generating)
  if (detail.stage === 'found') {
    setTimeout(() => {
      if (status.value && status.value.stage === 'found') {
        status.value = null
      }
    }, 1500)
  }
  // generating 不自动隐藏 (持续到流结束)
}

onMounted(() => {
  window.addEventListener('chat:retrieval-status', handleEvent as EventListener)
})
onBeforeUnmount(() => {
  window.removeEventListener('chat:retrieval-status', handleEvent as EventListener)
})

function getLabel(): string {
  if (!status.value) return ''
  switch (status.value.stage) {
    case 'searching':
      return '🔍 正在检索...'
    case 'found':
      return `📚 找到 ${status.value.count ?? 0} 条相关内容`
    case 'generating':
      return '✨ 生成中...'
    default:
      return ''
  }
}
</script>

<template>
  <Transition name="retrieval-fade">
    <div
      v-if="status"
      class="retrieval-status"
      :class="{ compact }"
      :data-stage="status.stage"
    >
      <span class="dot" />
      <span class="label">{{ getLabel() }}</span>
    </div>
  </Transition>
</template>

<style scoped>
.retrieval-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 12px;
  color: var(--color-text-secondary);
  background: var(--color-bg-warm);
  border-radius: 12px;
  margin: 4px 0;
}
.retrieval-status.compact {
  padding: 3px 8px;
  font-size: 11px;
}
.dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-primary);
  animation: retrieval-pulse 1.4s infinite ease-in-out;
}
.retrieval-status[data-stage="found"] .dot {
  background: var(--el-color-success);
  animation: none;
}
.retrieval-status[data-stage="generating"] .dot {
  background: var(--color-primary);
  animation: retrieval-pulse 0.8s infinite ease-in-out;
}

@keyframes retrieval-pulse {
  0%, 100% { opacity: 0.3; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1); }
}

/* 渐显动画 */
.retrieval-fade-enter-active,
.retrieval-fade-leave-active {
  transition: opacity 0.3s ease;
}
.retrieval-fade-enter-from,
.retrieval-fade-leave-to {
  opacity: 0;
}
</style>

<!-- v60-v67 教训: dark mode 走非 scoped 块 -->
<style>
[data-theme="dark"] .retrieval-status {
  background: var(--color-bg-hover);
  color: var(--color-text-secondary);
}
</style>
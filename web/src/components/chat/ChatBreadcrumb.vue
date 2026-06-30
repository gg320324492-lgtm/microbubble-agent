<script setup>
/**
 * ChatBreadcrumb.vue — v78 UI-redesign 中央标题组件
 *
 * 替代 ChatViewSSE 顶部"小气/在线/.../"标题块
 * 显示当前会话标题 + 在线状态
 *
 * a11y 4-attr 全部就绪
 */
import { computed } from 'vue'
import { ChatDotRound } from '@element-plus/icons-vue'
import { useChatSessionsStore } from '@/stores/chatSessions'

const props = defineProps({
  status: { type: String, default: 'idle' }, // 'idle' | 'thinking' | 'generating'
})

const store = useChatSessionsStore()

const currentSessionTitle = computed(() => {
  const s = store.sessions.find((x) => x.id === store.currentId)
  return s?.title || '新对话'
})

const statusText = computed(() => {
  if (props.status === 'thinking') return '思考中…'
  if (props.status === 'generating') return '生成中…'
  return '在线'
})

const statusClass = computed(() => `status-${props.status}`)
</script>

<template>
  <header class="chat-breadcrumb" role="banner">
    <el-icon :size="20" class="brand-icon"><ChatDotRound /></el-icon>
    <div class="breadcrumb-info">
      <div class="breadcrumb-title" :title="currentSessionTitle">
        {{ currentSessionTitle }}
      </div>
      <div class="breadcrumb-status" :class="statusClass">
        <span class="status-dot" aria-hidden="true" />
        {{ statusText }}
      </div>
    </div>
  </header>
</template>

<style scoped>
.chat-breadcrumb {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.brand-icon {
  color: var(--color-primary);
  flex-shrink: 0;
}

.breadcrumb-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.breadcrumb-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 320px;
}

.breadcrumb-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--color-text-secondary);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-success);
}
.status-thinking .status-dot, .status-generating .status-dot {
  background: var(--color-warning);
  animation: mb-pulse 1.2s ease-in-out infinite;
}
@keyframes mb-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>

<!-- v78 + v77 教训 (v60-v67): dark mode 必须非 scoped 块 -->
<style>
[data-theme="dark"] .breadcrumb-title { color: var(--color-text-primary); }
[data-theme="dark"] .breadcrumb-status { color: var(--color-text-secondary); }
</style>

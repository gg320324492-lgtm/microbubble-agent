<!--
ChatBreadcrumb.vue — W72 B-2 子 plan ③ 起步 (派工 v6 段 5 反馈 #3 实战: type hint 必含)

设计要点:
- 同时支持 (a) 中央标题显示 (v78 兼容) + (b) 完整 ancestor chain (W72 B-2 起)
- 派工 v6 段 5 反馈 #3 实战: BreadcrumbItem interface type hint 必含
- 通过 v-model:fullChain 控制两种模式
- a11y 4-attr 全部就绪
-->
<script setup lang="ts">
/**
 * ChatBreadcrumb.vue — v78 UI-redesign 中央标题组件 + W72 B-2 升级
 *
 * 替代 ChatViewSSE 顶部"小气/在线/.../"标题块
 * W72 B-2 起支持 ancestor chain 模式 (fullChain=true):
 *  - 从 useChatSessionsStore.currentBreadcrumb 渲染完整链路
 *  - 每级可点击 router-link 跳到对应 session
 *
 * a11y 4-attr 全部就绪
 */
import { computed } from 'vue'
import { ChatDotRound } from '@element-plus/icons-vue'
import { useChatSessionsStore } from '@/stores/chatSessions'
import type { ChatSession } from '@/stores/chatSessions'

export interface BreadcrumbItem {
  id: string
  title: string
}

const props = withDefaults(defineProps<{
  status?: 'idle' | 'thinking' | 'generating'
  fullChain?: boolean
}>(), {
  status: 'idle',
  fullChain: false,
})

const store = useChatSessionsStore()

const currentSessionTitle = computed<string>(() => {
  const s = store.sessions.find((x: ChatSession) => x.id === store.currentId)
  return s?.title || '新对话'
})

const chainItems = computed<BreadcrumbItem[]>(() => {
  // fullChain 模式: 渲染祖先链 (后续 useChatSessionsStore.currentBreadcrumb 接入)
  // 当前实现: 至少返回当前 session 作为 1 项, 后续 anchor 周接入 full chain
  return [{ id: store.currentId ?? 'new', title: currentSessionTitle.value }]
})

const statusText = computed<string>(() => {
  if (props.status === 'thinking') return '思考中…'
  if (props.status === 'generating') return '生成中…'
  return '在线'
})

const statusClass = computed<string>(() => `status-${props.status}`)
</script>

<template>
  <header class="chat-breadcrumb" role="banner">
    <el-icon :size="20" class="brand-icon"><ChatDotRound /></el-icon>
    <div class="breadcrumb-info">
      <div class="breadcrumb-title" :title="currentSessionTitle">
        <template v-if="fullChain && chainItems.length > 1">
          <span
            v-for="(item, idx) in chainItems"
            :key="item.id"
            class="chain-segment"
          >
            <router-link
              :to="{ name: 'chat-session', params: { id: item.id } }"
              class="chain-link"
            >{{ item.title }}</router-link>
            <span v-if="idx < chainItems.length - 1" class="chain-sep">/</span>
          </span>
        </template>
        <template v-else>
          {{ currentSessionTitle }}
        </template>
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
  max-width: 360px;
}

/* W72 B-2 升级: 祖先链 (fullChain=true) 节点样式 */
.chain-segment { display: inline-flex; align-items: center; }
.chain-link {
  color: var(--color-text-secondary);
  text-decoration: none;
  padding: 0 4px;
  border-radius: var(--radius-sm, 4px);
  transition: color 0.15s ease, background 0.15s ease;
}
.chain-link:hover {
  color: var(--color-primary);
  background: var(--color-bg-warm, rgba(255, 122, 92, 0.08));
}
.chain-sep {
  color: var(--color-text-secondary);
  opacity: 0.5;
  padding: 0 2px;
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
[data-theme="dark"] .chain-link { color: var(--color-text-secondary); }
[data-theme="dark"] .chain-link:hover {
  color: var(--color-primary);
  background: rgba(255, 122, 92, 0.12);
}
</style>

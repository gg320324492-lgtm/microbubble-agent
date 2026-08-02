<script setup lang="ts">
/**
 * ContextPanel.vue - W100 +29 上下文可见性面板
 *
 * 让用户看到当前会话的上下文：
 * - 💬 对话历史：最近 N 轮 user+assistant 摘要（每条 1 行）
 * - 📚 知识引用：所有 rich_blocks 中 knowledge_ref 的汇总（title + score）
 * - 🔧 工具调用：所有 toolTrace 汇总（name + state + duration）
 *
 * 纯展示组件，由父组件控制可见性（el-drawer / inline panel）。
 * 不依赖后端 API，仅消费 messages prop。
 */
import { ref, computed } from 'vue'

interface ToolTraceItem {
  type: 'thinking' | 'tool'
  label?: string
  name?: string
  state?: 'running' | 'done'
  duration_ms?: number
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  richBlocks: any[]
  toolTrace?: ToolTraceItem[]
  timestamp: string
  intent?: { category: string; confidence: number }
}

const props = defineProps<{
  messages: ChatMessage[]
}>()

// ============================================================================
// 活跃 tab
// ============================================================================
const activeTab = ref<'history' | 'knowledge' | 'tools'>('history')

// ============================================================================
// 对话历史：user+assistant 消息对，最近 20 轮
// ============================================================================
const MAX_ROUNDS = 20

const chatHistory = computed(() => {
  const msgs = props.messages.filter(m => m.content && m.content.trim())
  // 取最近 MAX_ROUNDS * 2 条（每轮 = 1 user + 1 assistant）
  const sliced = msgs.slice(-MAX_ROUNDS * 2)
  return sliced.map(m => ({
    id: m.id,
    role: m.role,
    content: m.content.length > 80 ? m.content.slice(0, 80) + '…' : m.content,
    timestamp: m.timestamp,
  }))
})

// ============================================================================
// 知识引用：扫描所有 messages 的 richBlocks，提取 knowledge_ref
// ============================================================================
const knowledgeRefs = computed(() => {
  const refs: Array<{ title: string; score?: number; msgId: string }> = []
  for (const msg of props.messages) {
    if (!msg.richBlocks) continue
    for (const block of msg.richBlocks) {
      if (block?.type !== 'knowledge_ref') continue
      const results = block?.data?.results || []
      for (const r of results) {
        refs.push({
          title: r.title || '(无标题)',
          score: r.score,
          msgId: msg.id,
        })
      }
    }
  }
  return refs
})

// ============================================================================
// 工具调用：扫描所有 messages 的 toolTrace，提取 type='tool'
// ============================================================================
const toolCalls = computed(() => {
  const calls: Array<{
    name: string
    state: string
    duration_ms?: number
    msgId: string
  }> = []
  for (const msg of props.messages) {
    if (!msg.toolTrace) continue
    for (const trace of msg.toolTrace) {
      if (trace.type !== 'tool') continue
      calls.push({
        name: trace.name || '(未知工具)',
        state: trace.state || 'done',
        duration_ms: trace.duration_ms,
        msgId: msg.id,
      })
    }
  }
  return calls
})

// ============================================================================
// 上下文摘要统计
// ============================================================================
const summary = computed(() => ({
  rounds: Math.floor(chatHistory.value.length / 2),
  knowledgeCount: knowledgeRefs.value.length,
  toolCount: toolCalls.value.length,
}))

// ============================================================================
// 格式化工具耗时
// ============================================================================
function formatDuration(ms?: number): string {
  if (ms == null) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}
</script>

<template>
  <div class="context-panel" data-testid="context-panel">
    <!-- 顶部摘要 -->
    <div class="cp-summary" data-testid="cp-summary">
      <span class="cp-summary-icon">📊</span>
      <span class="cp-summary-text">
        上下文摘要：{{ summary.rounds }} 轮对话 / {{ summary.knowledgeCount }} 条知识 / {{ summary.toolCount }} 次工具调用
      </span>
    </div>

    <!-- Tab 切换 -->
    <div class="cp-tabs" role="tablist" aria-label="上下文分类">
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'history'"
        :class="['cp-tab', { active: activeTab === 'history' }]"
        data-testid="cp-tab-history"
        @click="activeTab = 'history'"
      >
        💬 对话历史
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'knowledge'"
        :class="['cp-tab', { active: activeTab === 'knowledge' }]"
        data-testid="cp-tab-knowledge"
        @click="activeTab = 'knowledge'"
      >
        📚 知识引用
      </button>
      <button
        type="button"
        role="tab"
        :aria-selected="activeTab === 'tools'"
        :class="['cp-tab', { active: activeTab === 'tools' }]"
        data-testid="cp-tab-tools"
        @click="activeTab = 'tools'"
      >
        🔧 工具调用
      </button>
    </div>

    <!-- Tab 内容 -->
    <div class="cp-content">
      <!-- 对话历史 -->
      <div
        v-if="activeTab === 'history'"
        class="cp-tab-pane"
        data-testid="cp-pane-history"
        role="tabpanel"
      >
        <div v-if="chatHistory.length === 0" class="cp-empty">
          暂无对话记录
        </div>
        <ul v-else class="cp-list">
          <li
            v-for="msg in chatHistory"
            :key="msg.id"
            class="cp-history-item"
            :class="`cp-role-${msg.role}`"
            :data-testid="`cp-history-${msg.id}`"
          >
            <span class="cp-role-badge">{{ msg.role === 'user' ? '我' : 'AI' }}</span>
            <span class="cp-history-text">{{ msg.content }}</span>
          </li>
        </ul>
      </div>

      <!-- 知识引用 -->
      <div
        v-if="activeTab === 'knowledge'"
        class="cp-tab-pane"
        data-testid="cp-pane-knowledge"
        role="tabpanel"
      >
        <div v-if="knowledgeRefs.length === 0" class="cp-empty">
          暂无知识引用
        </div>
        <ul v-else class="cp-list">
          <li
            v-for="(ref, idx) in knowledgeRefs"
            :key="`${ref.msgId}-${idx}`"
            class="cp-knowledge-item"
            :data-testid="`cp-knowledge-${idx}`"
          >
            <span class="cp-knowledge-title">{{ ref.title }}</span>
            <span v-if="ref.score != null" class="cp-knowledge-score">
              {{ (ref.score * 100).toFixed(0) }}%
            </span>
          </li>
        </ul>
      </div>

      <!-- 工具调用 -->
      <div
        v-if="activeTab === 'tools'"
        class="cp-tab-pane"
        data-testid="cp-pane-tools"
        role="tabpanel"
      >
        <div v-if="toolCalls.length === 0" class="cp-empty">
          暂无工具调用
        </div>
        <ul v-else class="cp-list">
          <li
            v-for="(call, idx) in toolCalls"
            :key="`${call.msgId}-${idx}`"
            class="cp-tool-item"
            :data-testid="`cp-tool-${idx}`"
          >
            <span class="cp-tool-name">🔧 {{ call.name }}</span>
            <span class="cp-tool-state" :class="`cp-state-${call.state}`">
              {{ call.state === 'running' ? '⏳' : '✓' }}
            </span>
            <span class="cp-tool-duration">{{ formatDuration(call.duration_ms) }}</span>
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>

<style scoped>
.context-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* 顶部摘要 */
.cp-summary {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--color-primary-bg, #fff5f0);
  border-bottom: 1px solid var(--color-border-light, #ebeef5);
  font-size: 13px;
  color: var(--color-text-regular, #606266);
  font-weight: 500;
}
.cp-summary-icon { font-size: 16px; }

/* Tab 切换 */
.cp-tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--color-border-light, #ebeef5);
  padding: 0 8px;
}
.cp-tab {
  flex: 1;
  padding: 10px 8px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary, #909399);
  font-size: 13px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s;
  white-space: nowrap;
}
.cp-tab:hover {
  color: var(--color-primary, #FF7A5C);
}
.cp-tab.active {
  color: var(--color-primary, #FF7A5C);
  border-bottom-color: var(--color-primary, #FF7A5C);
  font-weight: 600;
}

/* Tab 内容 */
.cp-content {
  flex: 1;
  overflow-y: auto;
}
.cp-tab-pane {
  padding: 8px 0;
}
.cp-empty {
  padding: 40px 16px;
  text-align: center;
  color: var(--color-text-placeholder, #c0c4cc);
  font-size: 14px;
}
.cp-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

/* 对话历史项 */
.cp-history-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--color-border-lighter, #f2f6fc);
}
.cp-role-badge {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 600;
}
.cp-role-user .cp-role-badge {
  background: var(--color-primary, #FF7A5C);
  color: #fff;
}
.cp-role-assistant .cp-role-badge {
  background: var(--color-success, #67C23A);
  color: #fff;
}
.cp-history-text {
  flex: 1;
  font-size: 13px;
  color: var(--color-text-regular, #606266);
  line-height: 1.5;
  word-break: break-word;
}

/* 知识引用项 */
.cp-knowledge-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-border-lighter, #f2f6fc);
}
.cp-knowledge-title {
  flex: 1;
  font-size: 13px;
  color: var(--color-text-regular, #606266);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cp-knowledge-score {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-primary, #FF7A5C);
  font-weight: 600;
}

/* 工具调用项 */
.cp-tool-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-border-lighter, #f2f6fc);
}
.cp-tool-name {
  flex: 1;
  font-size: 13px;
  color: var(--color-text-regular, #606266);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cp-tool-state { font-size: 14px; }
.cp-state-running { color: var(--color-warning, #E6A23C); }
.cp-state-done { color: var(--color-success, #67C23A); }
.cp-tool-duration {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-text-secondary, #909399);
}
</style>

<!-- dark mode (非 scoped, v60-v67 教训) -->
<style>
[data-theme="dark"] .cp-summary {
  background: rgba(255, 122, 92, 0.08);
  border-bottom-color: var(--color-border-base, #4c4d4f);
  color: var(--color-text-regular, #a3a6ad);
}
[data-theme="dark"] .cp-tab {
  color: var(--color-text-secondary, #909399);
  border-bottom-color: transparent;
}
[data-theme="dark"] .cp-tab.active {
  color: var(--color-primary, #FF7A5C);
  border-bottom-color: var(--color-primary, #FF7A5C);
}
[data-theme="dark"] .cp-history-item,
[data-theme="dark"] .cp-knowledge-item,
[data-theme="dark"] .cp-tool-item {
  border-bottom-color: var(--color-border-base, #4c4d4f);
}
[data-theme="dark"] .cp-history-text,
[data-theme="dark"] .cp-knowledge-title,
[data-theme="dark"] .cp-tool-name {
  color: var(--color-text-regular, #a3a6ad);
}
[data-theme="dark"] .cp-empty {
  color: var(--color-text-placeholder, #606266);
}
</style>

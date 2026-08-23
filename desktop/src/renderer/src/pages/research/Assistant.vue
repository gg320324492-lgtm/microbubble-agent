<script setup lang="ts">
/**
 * AI科研助手 — 三栏工作台 (Pinia store 驱动)。
 */
import { onMounted } from 'vue'
import { useAgentStore } from '../../stores/research/agent.store'
import CitationCard from '../../components/research/CitationCard.vue'
import EvidenceCard from '../../components/research/EvidenceCard.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'

const agentStore = useAgentStore()
onMounted(() => agentStore.loadSessions())

const inputText = ref('')
import { ref } from 'vue'

function sendMessage() {
  if (!inputText.value.trim()) return
  agentStore.sendMessage(inputText.value.trim())
  inputText.value = ''
}

function selectSession(id: string) { agentStore.selectSession(id) }
function formatTime(ts: number) { return new Date(ts).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' }) }
</script>

<template>
  <div class="assistant">
    <!-- 左栏：会话列表 -->
    <aside class="assistant__left">
      <h3 class="assistant__section-title">研究会话</h3>
      <div v-if="agentStore.isLoading" class="assistant__loading">加载中...</div>
      <div v-for="s in agentStore.sessions" :key="s.id"
           class="assistant__session"
           :class="{ 'assistant__session--active': agentStore.activeSessionId === s.id }"
           @click="selectSession(s.id)">
        <StatusBadge :status="s.status === 'active' ? 'info' : s.status === 'completed' ? 'success' : 'neutral'"
                     :label="s.status === 'active' ? '当前' : s.status === 'completed' ? '完成' : '暂停'" />
        <span>{{ s.name }}</span>
      </div>
    </aside>

    <!-- 中栏：消息流 -->
    <main class="assistant__center">
      <!-- Agent 时间线 -->
      <div class="assistant__timeline" v-if="agentStore.events.length > 0">
        <div class="assistant__timeline-header">研究轨迹 / Trace</div>
        <div v-for="evt in agentStore.events" :key="evt.timestamp" class="assistant__event">
          <StatusBadge :status="evt.status === 'completed' ? 'success' : evt.status === 'error' ? 'error' : 'info'"
                       :label="evt.status === 'completed' ? '✓' : evt.status === 'error' ? '✗' : '●'" />
          <div class="assistant__event-body">
            <div class="assistant__event-label">{{ evt.label }}</div>
            <div class="assistant__event-detail">{{ evt.detail }}</div>
          </div>
          <span class="assistant__event-time">{{ formatTime(evt.timestamp) }}</span>
        </div>
      </div>

      <!-- 消息列表 -->
      <div class="assistant__messages">
        <div v-for="msg in agentStore.messages" :key="msg.id"
             :class="['assistant__msg', `assistant__msg--${msg.role}`]">
          <div class="assistant__msg-role">
            {{ msg.role === 'user' ? '你' : 'MB-Researcher Pro' }}
            <span class="assistant__msg-time">{{ formatTime(msg.timestamp) }}</span>
          </div>
          <div class="assistant__msg-content" style="white-space: pre-line">{{ msg.content }}</div>
          <div v-if="msg.toolCalls?.length" class="assistant__tool-calls">
            <div v-for="(tc, i) in msg.toolCalls" :key="i" class="assistant__tool">
              <StatusBadge :status="tc.status === 'completed' ? 'success' : tc.status === 'error' ? 'error' : 'info'"
                           :label="tc.status === 'completed' ? '✓' : tc.status === 'error' ? '✗' : '●'" />
              <span>{{ tc.name }}</span>
              <span v-if="tc.result" class="assistant__tool-result">{{ tc.result }}</span>
            </div>
          </div>
        </div>
        <div v-if="agentStore.isSending" class="assistant__sending">正在思考...</div>
      </div>

      <!-- 输入框 -->
      <div class="assistant__input">
        <input v-model="inputText" type="text" placeholder="输入你的问题，支持 @引用 / 数据 / 知识库 …"
               @keyup.enter="sendMessage" />
        <button class="assistant__send" @click="sendMessage" :disabled="agentStore.isSending">运行</button>
      </div>
    </main>

    <!-- 右栏：引用与证据 -->
    <aside class="assistant__right">
      <h3 class="assistant__section-title">引用文献 ({{ agentStore.citations.length }})</h3>
      <CitationCard v-for="c in agentStore.citations" :key="c.id" v-bind="c" style="margin-bottom: 8px;" />
      <h3 class="assistant__section-title" style="margin-top: 16px;">证据</h3>
      <EvidenceCard v-for="e in agentStore.evidence" :key="e.label" v-bind="e" style="margin-bottom: 8px;" />
    </aside>
  </div>
</template>

<style scoped>
.assistant { display: flex; height: 100%; }
.assistant__left { width: 220px; border-right: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fafbfc; }
.assistant__center { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.assistant__right { width: 280px; border-left: 1px solid #e5e7eb; padding: 16px; overflow-y: auto; background: #fafbfc; }
.assistant__section-title { margin: 0 0 10px; font-size: 13px; font-weight: 600; color: #0f172a; }
.assistant__loading { font-size: 12px; color: #94a3b8; padding: 8px; }
.assistant__session { padding: 8px 10px; border-radius: 6px; font-size: 13px; color: #475569; cursor: pointer; display: flex; align-items: center; gap: 6px; margin-bottom: 2px; }
.assistant__session--active { background: #eff6ff; color: #2563eb; font-weight: 500; }
.assistant__timeline { padding: 12px 20px; border-bottom: 1px solid #e5e7eb; background: #f8fafc; }
.assistant__timeline-header { font-size: 13px; font-weight: 600; color: #0f172a; margin-bottom: 8px; }
.assistant__event { display: flex; align-items: center; gap: 8px; padding: 4px 0; font-size: 12px; }
.assistant__event-body { flex: 1; }
.assistant__event-label { font-weight: 500; color: #1e293b; }
.assistant__event-detail { color: #64748b; font-size: 11px; }
.assistant__event-time { color: #94a3b8; font-size: 11px; }
.assistant__messages { flex: 1; overflow-y: auto; padding: 20px 24px; }
.assistant__msg { margin-bottom: 16px; }
.assistant__msg--user .assistant__msg-content { background: #f1f5f9; border-radius: 10px; padding: 12px 16px; font-size: 13px; line-height: 1.6; color: #1e293b; }
.assistant__msg--assistant .assistant__msg-content { font-size: 13px; line-height: 1.7; color: #334155; }
.assistant__msg-role { font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 4px; }
.assistant__msg-time { font-weight: 400; color: #94a3b8; }
.assistant__tool-calls { margin-top: 8px; display: flex; flex-direction: column; gap: 4px; }
.assistant__tool { display: inline-flex; align-items: center; gap: 6px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 4px 10px; font-size: 12px; color: #166534; }
.assistant__tool-result { color: #64748b; font-size: 11px; }
.assistant__sending { font-size: 12px; color: #94a3b8; padding: 12px 24px; font-style: italic; }
.assistant__input { padding: 12px 24px 16px; border-top: 1px solid #e5e7eb; display: flex; gap: 10px; }
.assistant__input input { flex: 1; border: 1px solid #d1d5db; border-radius: 8px; padding: 10px 14px; font-size: 13px; outline: none; }
.assistant__input input:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,.15); }
.assistant__send { background: #2563eb; color: #fff; border: none; border-radius: 8px; padding: 10px 20px; font-size: 13px; font-weight: 500; cursor: pointer; }
.assistant__send:hover { background: #1d4ed8; }
.assistant__send:disabled { opacity: .5; cursor: not-allowed; }
</style>

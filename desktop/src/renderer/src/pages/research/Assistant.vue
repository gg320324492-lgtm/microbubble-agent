<script setup lang="ts">
import { onMounted, ref } from 'vue'
import CitationCard from '../../components/research/CitationCard.vue'
import EvidenceCard from '../../components/research/EvidenceCard.vue'
import ResearchIcon from '../../components/icons/ResearchIcon.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import StatusBadge from '../../components/research/StatusBadge.vue'
import type { AgentEvent, ToolCallResult } from '../../services/research/research-agent.service'
import { useAgentStore } from '../../stores/research/agent.store'

const agentStore = useAgentStore()
const inputText = ref('')
const sendError = ref(false)
const failedMessage = ref('')
const sessionLoading = ref(false)
const sessionError = ref('')
const failedSessionId = ref<string | null>(null)

const EVENT_STATUS = {
  pending: { tone: 'neutral', label: '等待中', icon: 'idle' },
  running: { tone: 'info', label: '运行中', icon: 'running' },
  completed: { tone: 'success', label: '已完成', icon: 'check' },
  error: { tone: 'error', label: '错误', icon: 'error' }
} as const satisfies Record<AgentEvent['status'], { tone: 'neutral' | 'info' | 'success' | 'error'; label: string; icon: 'idle' | 'running' | 'check' | 'error' }>

const TOOL_STATUS = {
  running: { tone: 'info', label: '运行中' },
  completed: { tone: 'success', label: '已完成' },
  error: { tone: 'error', label: '错误' }
} as const satisfies Record<ToolCallResult['status'], { tone: 'info' | 'success' | 'error'; label: string }>

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function messageRole(role: 'user' | 'assistant' | 'system'): string {
  if (role === 'user') return '研究者'
  if (role === 'assistant') return '科研助手'
  return '系统'
}

async function submitMessage(content: string): Promise<void> {
  if (!content || !agentStore.activeSessionId || agentStore.isSending) return
  sendError.value = false
  failedMessage.value = content
  try {
    await agentStore.sendMessage(content)
    sendError.value = false
    failedMessage.value = ''
    if (inputText.value.trim() === content) inputText.value = ''
  } catch {
    if (inputText.value.trim() === content) {
      sendError.value = true
      failedMessage.value = content
    } else {
      sendError.value = false
      failedMessage.value = ''
    }
  }
}

async function sendMessage(): Promise<void> {
  await submitMessage(inputText.value.trim())
}

async function retryMessage(): Promise<void> {
  await submitMessage(failedMessage.value.trim())
}

function handleInputChange(event: Event): void {
  const nextValue = (event.target as HTMLInputElement).value.trim()
  if (sendError.value && nextValue !== failedMessage.value) {
    sendError.value = false
    failedMessage.value = ''
  }
}

async function loadSessionsSafely(): Promise<void> {
  if (sessionLoading.value) return
  sessionLoading.value = true
  sessionError.value = ''
  failedSessionId.value = null
  try {
    await agentStore.loadSessions()
  } catch {
    sessionError.value = '研究会话加载失败，请重试'
  } finally {
    sessionLoading.value = false
  }
}

async function selectSession(id: string): Promise<void> {
  if (sessionLoading.value) return
  sessionLoading.value = true
  sessionError.value = ''
  failedSessionId.value = id
  try {
    await agentStore.selectSession(id)
    failedSessionId.value = null
  } catch {
    sessionError.value = '研究会话加载失败，请重试'
  } finally {
    sessionLoading.value = false
  }
}

async function retrySession(): Promise<void> {
  if (sessionLoading.value) return
  const sessionId = failedSessionId.value
  if (sessionId) await selectSession(sessionId)
  else await loadSessionsSafely()
}

onMounted(() => { void loadSessionsSafely() })
</script>

<template>
  <div class="assistant" aria-label="科研助手工作台">
    <aside data-testid="assistant-sessions" class="assistant__sessions" aria-label="研究会话">
      <header class="assistant__aside-header">
        <div>
          <span class="assistant__eyebrow">科研上下文</span>
          <h1>研究会话</h1>
        </div>
        <ResearchIcon name="assistant" :size="20" />
      </header>

      <div v-if="sessionLoading" class="assistant__session-loading" role="status" aria-live="polite">
        <ResearchIcon name="running" :size="15" />
        AI 正在分析...
      </div>
      <p v-if="!sessionLoading && agentStore.sessions.length === 0" class="assistant__session-empty">暂无研究会话</p>
      <nav v-if="agentStore.sessions.length" class="assistant__session-list" aria-label="研究会话列表">
        <button
          v-for="session in agentStore.sessions"
          :key="session.id"
          :data-session-id="session.id"
          :class="['assistant__session', { 'assistant__session--active': agentStore.activeSessionId === session.id }]"
          type="button"
          :disabled="sessionLoading"
          :aria-current="agentStore.activeSessionId === session.id ? 'page' : undefined"
          @click="selectSession(session.id)"
        >
          <span class="assistant__session-name">{{ session.name }}</span>
          <StatusBadge
            :status="session.status === 'active' ? 'info' : session.status === 'completed' ? 'success' : 'neutral'"
            :label="session.status === 'active' ? '当前' : session.status === 'completed' ? '完成' : '暂停'"
          />
        </button>
      </nav>
    </aside>

    <section data-testid="assistant-workbench" class="assistant__workbench" aria-label="科研助手对话工作区">
      <header class="assistant__workbench-header">
        <div>
          <span class="assistant__eyebrow">AI 科研协作</span>
          <h2>{{ agentStore.activeSession?.name ?? '科研助手' }}</h2>
        </div>
        <span class="assistant__online"><span aria-hidden="true" />AI 在线</span>
      </header>

      <div class="assistant__session-content">
        <ResearchState
          v-if="sessionLoading"
          data-testid="assistant-session-state"
          class="assistant__empty"
          state="loading"
          title="AI 正在分析..."
          description="正在加载研究会话、执行轨迹与证据。"
        />

        <ResearchState
          v-else-if="sessionError"
          data-testid="assistant-session-state"
          class="assistant__empty"
          state="error"
          :title="sessionError"
          description="旧会话内容已隐藏，可以安全重试本次加载。"
          @retry="retrySession"
        />

        <ResearchState
          v-else-if="!agentStore.activeSessionId"
          class="assistant__empty"
          state="empty"
          title="暂无科研数据"
          description="请从左侧选择研究会话，再继续分析问题与证据。"
        />

        <div v-else class="assistant__active-session">
        <section v-if="agentStore.events.length" class="assistant__trace" aria-labelledby="assistant-trace-title">
          <header>
            <h3 id="assistant-trace-title">研究轨迹</h3>
            <span>{{ agentStore.events.length }} 个真实节点</span>
          </header>
          <ol>
            <li v-for="event in agentStore.events" :key="`${event.timestamp}-${event.type}`">
              <span :class="['assistant__trace-icon', `assistant__trace-icon--${event.status}`]">
                <ResearchIcon :name="EVENT_STATUS[event.status].icon" :size="14" />
              </span>
              <div>
                <strong>{{ event.label }}</strong>
                <p>{{ event.detail }}</p>
              </div>
              <div class="assistant__trace-meta">
                <StatusBadge :status="EVENT_STATUS[event.status].tone" :label="EVENT_STATUS[event.status].label" />
                <time :datetime="new Date(event.timestamp).toISOString()">{{ formatTime(event.timestamp) }}</time>
              </div>
            </li>
          </ol>
        </section>

        <section class="assistant__messages" aria-label="科研对话消息" aria-live="polite">
          <ResearchState
            v-if="sendError"
            data-testid="assistant-send-error"
            class="assistant__send-error"
            state="error"
            title="分析失败，请重试"
            description="问题内容已保留，可以重新发送本次科研请求。"
            @retry="retryMessage"
          />
          <ResearchState
            v-if="agentStore.messages.length === 0 && !agentStore.isSending && !sendError"
            state="empty"
            title="暂无科研数据"
            description="输入科研问题后，消息、工具结果与证据会显示在这里。"
          />
          <article v-for="message in agentStore.messages" :key="message.id" :class="['assistant__message', `assistant__message--${message.role}`]">
            <header>
              <span>{{ messageRole(message.role) }}</span>
              <time :datetime="new Date(message.timestamp).toISOString()">{{ formatTime(message.timestamp) }}</time>
            </header>
            <p class="assistant__message-content">{{ message.content }}</p>
            <div v-if="message.toolCalls?.length" class="assistant__tools" aria-label="工具执行结果">
              <article v-for="(tool, index) in message.toolCalls" :key="`${index}-${tool.name}`">
                <div class="assistant__tool-name">
                  <ResearchIcon name="tool" :size="15" />
                  <strong>{{ tool.name }}</strong>
                  <StatusBadge :status="TOOL_STATUS[tool.status].tone" :label="TOOL_STATUS[tool.status].label" />
                </div>
                <p>{{ tool.result ?? tool.error ?? '暂无工具输出' }}</p>
              </article>
            </div>
          </article>
          <div v-if="agentStore.isSending" data-testid="assistant-analyzing" class="assistant__analyzing assistant__sending" role="status" aria-live="polite">
            <ResearchIcon name="running" :size="16" />
            AI 正在分析...
          </div>
        </section>

        <form class="assistant__composer" aria-label="发送科研问题" @submit.prevent="sendMessage">
          <label class="assistant__composer-label" for="assistant-input">继续科研对话</label>
          <div>
            <input
              id="assistant-input"
              v-model="inputText"
              data-testid="assistant-input"
              type="text"
              placeholder="输入科研问题，可结合引用、数据或知识库"
              autocomplete="off"
              :disabled="agentStore.isSending"
              @input="handleInputChange"
              @keydown.enter.prevent="sendMessage"
            />
            <button
              data-testid="assistant-send"
              type="submit"
              :disabled="agentStore.isSending || !inputText.trim()"
              :aria-busy="agentStore.isSending"
            >
              <ResearchIcon :name="agentStore.isSending ? 'running' : 'progress'" :size="16" />
              {{ agentStore.isSending ? '分析中' : '发送' }}
            </button>
          </div>
        </form>
        </div>
      </div>
    </section>

    <aside data-testid="assistant-evidence" class="assistant__evidence" aria-label="引用与证据">
      <header class="assistant__aside-header">
        <div>
          <span class="assistant__eyebrow">证据工作区</span>
          <h2>引用与证据</h2>
        </div>
        <ResearchIcon name="evidence" :size="20" />
      </header>

      <p v-if="sessionLoading || sessionError" class="assistant__evidence-empty">当前会话证据已暂时隐藏</p>
      <template v-else>
        <section class="assistant__evidence-section" aria-labelledby="assistant-citations-title">
          <header><h3 id="assistant-citations-title">引用文献</h3><span>{{ agentStore.citations.length }}</span></header>
          <p v-if="agentStore.citations.length === 0" class="assistant__evidence-empty">暂无引用文献</p>
          <CitationCard
            v-for="citation in agentStore.citations"
            :key="citation.id"
            :index="citation.id"
            :authors="citation.authors"
            :title="citation.title"
            :journal="citation.journal"
            :year="citation.year"
            :tags="citation.tags"
            :cited-by="citation.citedBy"
          />
        </section>

        <section class="assistant__evidence-section" aria-labelledby="assistant-evidence-title">
          <header><h3 id="assistant-evidence-title">研究证据</h3><span>{{ agentStore.evidence.length }}</span></header>
          <p v-if="agentStore.evidence.length === 0" class="assistant__evidence-empty">暂无研究证据</p>
          <EvidenceCard
            v-for="evidence in agentStore.evidence"
            :key="`${evidence.label}-${evidence.source}`"
            :label="evidence.label"
            :value="evidence.value"
            :source="evidence.source"
            :confidence="evidence.confidence"
          />
        </section>
      </template>
    </aside>
  </div>
</template>

<style scoped>
.assistant { display: grid; width: 100%; height: 100%; min-width: 0; grid-template-columns: minmax(210px, 236px) minmax(440px, 1fr) minmax(260px, 320px); overflow: hidden; background: var(--research-bg-main); color: var(--research-text-primary); }
.assistant__sessions, .assistant__evidence { min-width: 0; overflow-y: auto; padding: var(--research-space-5); background: var(--research-bg-panel); }
.assistant__sessions { border-right: 1px solid var(--research-divider); }
.assistant__evidence { border-left: 1px solid var(--research-divider); }
.assistant__aside-header, .assistant__workbench-header, .assistant__evidence-section > header { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--research-space-3); }
.assistant__aside-header { margin-bottom: var(--research-space-5); }
.assistant__aside-header svg { color: var(--research-primary-600); }
.assistant__eyebrow { display: block; margin-bottom: var(--research-space-1); color: var(--research-primary-600); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); letter-spacing: .06em; }
.assistant h1, .assistant h2, .assistant h3, .assistant p { margin: 0; }
.assistant__aside-header h1, .assistant__aside-header h2 { font-size: var(--research-text-section-title); }
.assistant__session-loading { display: flex; align-items: center; gap: var(--research-space-2); color: var(--research-ai-700); font-size: var(--research-text-sm); }
.assistant__session-empty, .assistant__evidence-empty { color: var(--research-text-secondary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }
.assistant__session-list { display: flex; flex-direction: column; gap: var(--research-space-2); }
.assistant__session { display: flex; width: 100%; min-width: 0; align-items: center; justify-content: space-between; gap: var(--research-space-2); padding: var(--research-space-3); border: 1px solid transparent; border-radius: var(--research-radius-button); background: transparent; color: var(--research-text-secondary); font: inherit; text-align: left; cursor: pointer; }
.assistant__session:hover { background: var(--research-bg-hover); color: var(--research-text-primary); }
.assistant__session:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.assistant__session:disabled { cursor: wait; background: var(--research-bg-hover); color: var(--research-text-secondary); }
.assistant__session--active { border-color: var(--research-primary-200); background: var(--research-primary-50); color: var(--research-primary-700); }
.assistant__session-name { min-width: 0; overflow: hidden; font-size: var(--research-text-sm); font-weight: var(--research-font-weight-medium); text-overflow: ellipsis; white-space: nowrap; }
.assistant__workbench { display: flex; min-width: 0; min-height: 0; flex-direction: column; overflow: hidden; background: var(--research-bg-card); }
.assistant__workbench-header { flex: 0 0 auto; align-items: center; padding: var(--research-space-4) var(--research-space-6); border-bottom: 1px solid var(--research-divider); }
.assistant__workbench-header h2 { font-size: var(--research-text-section-title); }
.assistant__session-content, .assistant__active-session { display: flex; min-height: 0; flex: 1; flex-direction: column; overflow: hidden; }
.assistant__online { display: inline-flex; align-items: center; gap: var(--research-space-2); color: var(--research-success-700); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); }
.assistant__online > span { width: 7px; height: 7px; border-radius: var(--research-radius-pill); background: var(--research-success-500); }
.assistant__empty { margin: auto var(--research-space-6); }
.assistant__trace { flex: 0 0 auto; max-height: 220px; overflow-y: auto; padding: var(--research-space-4) var(--research-space-6); border-bottom: 1px solid var(--research-divider); background: var(--research-bg-panel); }
.assistant__trace > header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--research-space-3); }
.assistant__trace h3 { font-size: var(--research-text-card-title); }
.assistant__trace > header span { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.assistant__trace ol { display: flex; flex-direction: column; gap: var(--research-space-2); padding: 0; margin: 0; list-style: none; }
.assistant__trace li { display: grid; min-width: 0; grid-template-columns: 24px minmax(0, 1fr) auto; align-items: start; gap: var(--research-space-2); }
.assistant__trace-icon { display: grid; width: 22px; height: 22px; place-items: center; border-radius: var(--research-radius-pill); background: var(--research-bg-hover); color: var(--research-text-secondary); }
.assistant__trace-icon--completed { background: var(--research-success-50); color: var(--research-success-700); }
.assistant__trace-icon--running { background: var(--research-ai-50); color: var(--research-ai-700); }
.assistant__trace-icon--error { background: var(--research-danger-50); color: var(--research-danger-600); }
.assistant__trace strong { display: block; font-size: var(--research-text-sm); }
.assistant__trace p { margin-top: var(--research-space-1); color: var(--research-text-secondary); font-size: var(--research-text-xs); line-height: var(--research-line-height-body); }
.assistant__trace-meta { display: flex; align-items: center; gap: var(--research-space-2); }
.assistant__trace-meta time { color: var(--research-text-secondary); font-size: var(--research-text-xs); font-variant-numeric: tabular-nums; }
.assistant__messages { flex: 1; min-height: 0; overflow-y: auto; padding: var(--research-space-6); }
.assistant__send-error { min-height: 160px; margin-bottom: var(--research-space-5); }
.assistant__message { max-width: 88%; margin-bottom: var(--research-space-5); }
.assistant__message--user { margin-left: auto; }
.assistant__message > header { display: flex; align-items: center; gap: var(--research-space-2); margin-bottom: var(--research-space-2); color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.assistant__message > header span { color: var(--research-text-primary); font-weight: var(--research-font-weight-semibold); }
.assistant__message-content { padding: var(--research-space-4); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-panel); white-space: pre-line; font-size: var(--research-text-body); line-height: var(--research-line-height-reading); }
.assistant__message--assistant .assistant__message-content { border-left: 2px solid var(--research-ai-500); background: var(--research-bg-card); }
.assistant__message--user .assistant__message-content { border-color: var(--research-primary-100); background: var(--research-primary-50); }
.assistant__tools { display: grid; gap: var(--research-space-2); margin-top: var(--research-space-3); }
.assistant__tools article { padding: var(--research-space-3); border: 1px solid var(--research-success-100); border-radius: var(--research-radius-button); background: var(--research-success-50); }
.assistant__tool-name { display: flex; align-items: center; gap: var(--research-space-2); color: var(--research-success-700); font-size: var(--research-text-sm); }
.assistant__tool-name .status-badge { margin-left: auto; }
.assistant__tools p { margin-top: var(--research-space-2); color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.assistant__analyzing { display: flex; align-items: center; gap: var(--research-space-2); color: var(--research-ai-700); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-medium); }
.assistant__composer { flex: 0 0 auto; padding: var(--research-space-4) var(--research-space-6); border-top: 1px solid var(--research-divider); background: var(--research-bg-card); }
.assistant__composer-label { display: block; margin-bottom: var(--research-space-2); color: var(--research-text-secondary); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-medium); }
.assistant__composer > div { display: flex; min-width: 0; gap: var(--research-space-3); }
.assistant__composer input { flex: 1; min-width: 0; min-height: 42px; padding: 0 var(--research-space-4); border: 1px solid var(--research-border-strong); border-radius: var(--research-radius-input); background: var(--research-bg-card); color: var(--research-text-primary); font: inherit; }
.assistant__composer input:focus-visible { outline: none; border-color: var(--research-primary-500); box-shadow: var(--research-shadow-focus-primary); }
.assistant__composer input:disabled { cursor: not-allowed; background: var(--research-bg-panel); color: var(--research-text-secondary); }
.assistant__composer button { display: inline-flex; min-width: 92px; align-items: center; justify-content: center; gap: var(--research-space-2); border: 1px solid var(--research-primary-600); border-radius: var(--research-radius-button); background: var(--research-primary-600); color: var(--research-text-inverse); font: inherit; font-weight: var(--research-font-weight-semibold); cursor: pointer; }
.assistant__composer button:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.assistant__composer button:disabled { cursor: not-allowed; border-color: var(--research-border-strong); background: var(--research-bg-hover); color: var(--research-text-secondary); }
.assistant__evidence-section + .assistant__evidence-section { margin-top: var(--research-space-6); }
.assistant__evidence-section > header { align-items: center; margin-bottom: var(--research-space-3); }
.assistant__evidence-section h3 { font-size: var(--research-text-card-title); }
.assistant__evidence-section > header span { min-width: 24px; padding: var(--research-space-1) var(--research-space-2); border-radius: var(--research-radius-pill); background: var(--research-bg-hover); color: var(--research-text-secondary); font-size: var(--research-text-xs); text-align: center; }
.assistant__evidence-section :deep(.citation-card), .assistant__evidence-section :deep(.evidence-card) { margin-bottom: var(--research-space-3); }
@media (max-width: 1260px) { .assistant { grid-template-columns: 210px minmax(400px, 1fr) 270px; } .assistant__sessions, .assistant__evidence { padding: var(--research-space-4); } .assistant__workbench-header, .assistant__messages, .assistant__composer, .assistant__trace { padding-left: var(--research-space-4); padding-right: var(--research-space-4); } }
</style>

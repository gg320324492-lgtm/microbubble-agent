<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AgentStatusPanel from '../../components/research/AgentStatusPanel.vue'
import EvidencePanel from '../../components/research/EvidencePanel.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import ResearchTimeline from '../../components/research/ResearchTimeline.vue'
import ToolExecutionPanel from '../../components/research/ToolExecutionPanel.vue'
import { useAgentStore } from '../../stores/research/agent.store'

const agentStore = useAgentStore()
const inputText = ref('')
const sendError = ref(false)
const failedMessage = ref('')
const sessionLoading = ref(false)
const sessionError = ref('')
const failedSessionId = ref<string | null>(null)

const evidence = computed(() => agentStore.evidence)
const citations = computed(() => agentStore.citations)
const events = computed(() => agentStore.events.map((event, index) => ({
  id: `${event.timestamp}-${index}`,
  title: event.label,
  description: event.detail,
  timestamp: new Date(event.timestamp).toISOString(),
  status: event.status,
  actor: undefined
})))
const nextActions = computed(() => agentStore.events
  .filter(event => event.status === 'pending' || event.status === 'running')
  .map((event, index) => ({
    id: `${event.timestamp}-next-${index}`,
    title: event.label,
    description: event.detail
  })))
const toolExecutions = computed(() => agentStore.messages.flatMap(message =>
  (message.toolCalls ?? []).map((tool, index) => ({
    id: `${message.id}-${tool.name}-${index}`,
    tool: tool.name,
    status: tool.status,
    output: tool.result ?? tool.error
  }))
))
const FIXED_AGENT_ROLES = ['文献智能体', '实验智能体', '分析智能体', '写作智能体', '审稿智能体'] as const
const agentActivities = computed(() => FIXED_AGENT_ROLES.map(name => {
  const event = [...agentStore.events].reverse().find(item => item.label.includes(name) || item.detail.includes(name))
  const message = [...agentStore.messages].reverse().find(message => message.content.includes(name))
  if (!event && !message) return null
  return {
    name,
    role: name,
    status: event?.status,
    action: event?.detail || message?.content
  }
}).filter((item): item is NonNullable<typeof item> => item !== null))

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function messageAuthor(role: string): string {
  return role === 'assistant' ? '科研助手' : role === 'user' ? '研究者' : '系统'
}

async function submitMessage(content: string): Promise<void> {
  if (!content || !agentStore.activeSessionId || agentStore.isSending) return
  sendError.value = false
  failedMessage.value = content
  try {
    await agentStore.sendMessage(content)
    failedMessage.value = ''
    if (inputText.value.trim() === content) inputText.value = ''
  } catch {
    if (inputText.value.trim() === content) sendError.value = true
  }
}

async function sendMessage(): Promise<void> {
  await submitMessage(inputText.value.trim())
}

async function retryMessage(): Promise<void> {
  await submitMessage(failedMessage.value.trim())
}

function handleInputChange(event: Event): void {
  if ((event.target as HTMLInputElement).value.trim() !== failedMessage.value) {
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
  if (failedSessionId.value) await selectSession(failedSessionId.value)
  else await loadSessionsSafely()
}

onMounted(() => { void loadSessionsSafely() })
</script>

<template>
  <main class="assistant" aria-label="科研助手工作台">
    <aside class="assistant__sessions" aria-label="研究会话">
      <header class="assistant__panel-header">
        <p>科研对话</p>
        <h1>研究会话</h1>
      </header>
      <p v-if="sessionLoading" class="assistant__notice" role="status" aria-live="polite">正在加载研究会话</p>
      <p v-if="!sessionLoading && agentStore.sessions.length === 0" class="assistant__muted">暂无研究会话</p>
      <nav v-else class="assistant__session-list" aria-label="研究会话列表">
        <button
          v-for="session in agentStore.sessions"
          :key="session.id"
          :class="['assistant__session', { 'is-active': agentStore.activeSessionId === session.id }]"
          type="button"
          :aria-current="agentStore.activeSessionId === session.id ? 'page' : undefined"
          :disabled="sessionLoading"
          @click="selectSession(session.id)"
        >
          <span>{{ session.name }}</span>
          <small>{{ session.status }}</small>
        </button>
      </nav>
    </aside>

    <section class="assistant__conversation" aria-label="科研对话工作区">
      <header class="assistant__conversation-header">
        <div>
          <p>Scientific AI Conversation Hub</p>
          <h2>{{ agentStore.activeSession?.name ?? '科研助手' }}</h2>
        </div>
        <span class="assistant__live" role="status" aria-live="polite">
          {{ agentStore.isSending || agentStore.isLoading ? 'AI 正在分析' : 'AI 状态：待命' }}
        </span>
      </header>

      <section class="assistant__context-bar" aria-label="研究上下文">
        <dl class="assistant__context-summary">
          <div><dt>当前项目</dt><dd>待接入数据</dd></div>
          <div><dt>研究模式</dt><dd>{{ agentStore.activeSession?.status ?? '待接入数据' }}</dd></div>
          <div><dt>AI 状态</dt><dd>{{ agentStore.isSending || agentStore.isLoading ? '正在分析' : '待命' }}</dd></div>
        </dl>
      </section>

      <ResearchState
        v-if="sessionLoading"
        class="assistant__state"
        state="loading"
        title="AI 正在分析..."
        description="正在加载研究会话、执行轨迹与证据。"
      />
      <ResearchState
        v-else-if="sessionError"
        class="assistant__state"
        state="error"
        :title="sessionError"
        description="会话数据暂时不可用，可以安全重试。"
        @retry="retrySession"
      />
      <ResearchState
        v-else-if="!agentStore.activeSessionId"
        class="assistant__state"
        state="empty"
        title="暂无科研数据"
        description="请从左侧选择研究会话，再继续科研分析。"
      />

      <section v-else class="assistant__active-session">
        <section class="assistant__messages" aria-label="科研对话消息" aria-live="polite">
          <ResearchState
            v-if="sendError"
            state="error"
            title="分析失败，请重试"
            description="问题内容已保留，可以重新发送本次科研请求。"
            @retry="retryMessage"
          />
          <ResearchState
            v-else-if="agentStore.messages.length === 0 && !agentStore.isSending"
            state="empty"
            title="暂无科研数据"
            description="输入科研问题后，结论、证据与引用会显示在这里。"
          />
          <article
            v-for="message in agentStore.messages"
            :key="message.id"
            :class="['assistant__message', `assistant__message--${message.role}`]"
          >
            <header>
              <strong>{{ messageAuthor(message.role) }}</strong>
              <time :datetime="new Date(message.timestamp).toISOString()">{{ formatTime(message.timestamp) }}</time>
            </header>
            <p v-if="message.role !== 'assistant'" class="assistant__message-body">{{ message.content }}</p>
            <div v-else class="assistant__response-sections">
              <details open>
                <summary>结论</summary>
                <p>{{ message.content }}</p>
              </details>
              <details>
                <summary>证据</summary>
                <p class="assistant__section-source">当前会话证据</p>
                <ul v-if="evidence.length" class="assistant__section-list">
                  <li v-for="item in evidence" :key="`${item.label}-${item.source}`">
                    <strong>{{ item.label }}</strong><span>{{ item.value }}</span><small>来源：{{ item.source }}</small>
                  </li>
                </ul>
                <p v-else>暂无证据</p>
              </details>
              <details>
                <summary>推理摘要</summary>
                <p class="assistant__section-source">当前会话推理摘要</p>
                <ol v-if="events.length" class="assistant__section-list">
                  <li v-for="event in events" :key="event.id"><strong>{{ event.title }}</strong><span>{{ event.description }}</span></li>
                </ol>
                <p v-else>暂无推理摘要</p>
              </details>
              <details>
                <summary>引用</summary>
                <p class="assistant__section-source">当前会话引用</p>
                <ol v-if="citations.length" class="assistant__section-list">
                  <li v-for="citation in citations" :key="citation.id"><strong>{{ citation.title }}</strong><span>{{ citation.authors }} · {{ citation.year }}</span></li>
                </ol>
                <p v-else>暂无引用来源</p>
              </details>
              <details>
                <summary>下一步行动</summary>
                <p class="assistant__section-source">当前会话下一步行动</p>
                <ul v-if="nextActions.length" class="assistant__section-list">
                  <li v-for="action in nextActions" :key="action.id"><strong>{{ action.title }}</strong><span>{{ action.description }}</span></li>
                </ul>
                <p v-else>暂无下一步行动</p>
              </details>
            </div>
          </article>
          <p v-if="agentStore.isSending" class="assistant__notice" role="status" aria-live="polite">AI 正在分析...</p>
        </section>

        <form class="assistant__composer" aria-label="发送科研问题" @submit.prevent="sendMessage">
          <label for="assistant-input">继续科研对话</label>
          <div>
            <input
              id="assistant-input"
              v-model="inputText"
              type="text"
              placeholder="输入科研问题，可结合引用、数据或知识库"
              autocomplete="off"
              :disabled="agentStore.isSending"
              @input="handleInputChange"
            >
            <button type="submit" :disabled="agentStore.isSending || !inputText.trim()" :aria-busy="agentStore.isSending">
              {{ agentStore.isSending ? '分析中' : '发送' }}
            </button>
          </div>
        </form>
      </section>
    </section>

    <aside class="assistant__context" aria-label="证据与引用">
      <header class="assistant__panel-header">
        <p>证据与引用</p>
        <h2>证据与可观测性</h2>
      </header>
      <div class="assistant__context-stack">
        <EvidencePanel :evidence="evidence" :citations="citations" />
        <ResearchTimeline :items="events" />
        <AgentStatusPanel :agents="agentActivities" />
        <ToolExecutionPanel :executions="toolExecutions" />
      </div>
    </aside>
  </main>
</template>

<style scoped>
.assistant { display: grid; width: 100%; height: 100%; min-width: 0; grid-template-columns: minmax(210px, 250px) minmax(0, 1fr) minmax(300px, 360px); overflow-x: clip; background: var(--research-bg-main); color: var(--research-text-primary); }
.assistant__sessions, .assistant__context { min-width: 0; overflow-y: auto; padding: var(--research-space-5); background: var(--research-bg-panel); }
.assistant__sessions { border-right: 1px solid var(--research-divider); }
.assistant__context { border-left: 1px solid var(--research-divider); }
.assistant__panel-header { margin-bottom: var(--research-space-5); }
.assistant__panel-header p, .assistant__conversation-header p { margin: 0 0 var(--research-space-1); color: var(--research-primary-600); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); letter-spacing: .05em; }
.assistant h1, .assistant h2, .assistant p { margin-top: 0; }
.assistant h1, .assistant h2 { margin-bottom: 0; font-size: var(--research-text-section-title); }
.assistant__session-list, .assistant__context-stack { display: grid; min-width: 0; gap: var(--research-space-3); }
.assistant__session { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: var(--research-space-2); padding: var(--research-space-3); border: 1px solid transparent; border-radius: var(--research-radius-button); background: transparent; color: var(--research-text-secondary); font: inherit; text-align: left; cursor: pointer; overflow-wrap: anywhere; }
.assistant__session:hover, .assistant__session.is-active { border-color: var(--research-primary-200); background: var(--research-primary-50); color: var(--research-primary-700); }
.assistant__session:focus-visible, .assistant__composer input:focus-visible, .assistant__composer button:focus-visible, .assistant details > summary:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.assistant__session:disabled { cursor: wait; }
.assistant__session small { flex: 0 0 auto; color: var(--research-text-secondary); }
.assistant__muted, .assistant__notice { margin: 0; color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.assistant__conversation { display: flex; min-width: 0; min-height: 0; flex-direction: column; overflow: hidden; background: var(--research-bg-card); }
.assistant__conversation-header { display: flex; align-items: center; justify-content: space-between; gap: var(--research-space-3); padding: var(--research-space-4) var(--research-space-6); border-bottom: 1px solid var(--research-divider); }
.assistant__live { flex: 0 0 auto; color: var(--research-ai-700); font-size: var(--research-text-sm); }
.assistant__state { margin: auto var(--research-space-6); }
.assistant__active-session { display: flex; min-width: 0; min-height: 0; flex: 1; flex-direction: column; }
.assistant__messages { min-width: 0; flex: 1; overflow-y: auto; padding: var(--research-space-6); }
.assistant__message { max-width: 92%; min-width: 0; margin-bottom: var(--research-space-5); }
.assistant__message--user { margin-left: auto; }
.assistant__message > header { display: flex; flex-wrap: wrap; gap: var(--research-space-2); margin-bottom: var(--research-space-2); color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.assistant__message-body, .assistant__response-sections { min-width: 0; padding: var(--research-space-4); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-panel); overflow-wrap: anywhere; line-height: var(--research-line-height-reading); }
.assistant__message-body { margin: 0; }
.assistant__response-sections { display: grid; gap: var(--research-space-2); border-left: 2px solid var(--research-ai-500); background: var(--research-bg-card); }
.assistant details { min-width: 0; border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-button); background: var(--research-bg-panel); }
.assistant details > summary { padding: var(--research-space-3); color: var(--research-text-primary); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-semibold); cursor: pointer; }
.assistant details > p { margin: 0; padding: 0 var(--research-space-3) var(--research-space-3); color: var(--research-text-secondary); overflow-wrap: anywhere; }
.assistant__section-source { padding-bottom: var(--research-space-1); color: var(--research-text-tertiary); font-size: var(--research-text-xs); }
.assistant__section-list { display: grid; gap: var(--research-space-2); margin: 0; padding: 0 var(--research-space-3) var(--research-space-3) var(--research-space-5); color: var(--research-text-secondary); font-size: var(--research-text-sm); }
.assistant__section-list li { display: grid; min-width: 0; gap: var(--research-space-1); overflow-wrap: anywhere; }
.assistant__section-list strong { color: var(--research-text-primary); font-weight: var(--research-font-weight-medium); }
.assistant__section-list small { color: var(--research-text-secondary); }
.assistant__composer { padding: var(--research-space-4) var(--research-space-6); border-top: 1px solid var(--research-divider); }
.assistant__composer label { display: block; margin-bottom: var(--research-space-2); color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.assistant__composer > div { display: flex; min-width: 0; gap: var(--research-space-3); }
.assistant__composer input { min-width: 0; flex: 1; padding: var(--research-space-3) var(--research-space-4); border: 1px solid var(--research-border-strong); border-radius: var(--research-radius-input); background: var(--research-bg-card); color: var(--research-text-primary); font: inherit; }
.assistant__composer button { padding: var(--research-space-3) var(--research-space-4); border: 1px solid var(--research-primary-600); border-radius: var(--research-radius-button); background: var(--research-primary-600); color: var(--research-text-inverse); font: inherit; cursor: pointer; }
.assistant__composer button:disabled { cursor: not-allowed; border-color: var(--research-border-strong); background: var(--research-bg-hover); color: var(--research-text-secondary); }
.assistant__context-bar { flex: 0 0 auto; min-width: 0; padding: var(--research-space-3) var(--research-space-6); border-bottom: 1px solid var(--research-divider); background: var(--research-bg-panel); }
.assistant__context-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--research-space-2); margin: 0; }
.assistant__context-summary div { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--research-space-3); min-width: 0; padding: var(--research-space-3); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-button); }
.assistant__context-summary dt { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.assistant__context-summary dd { min-width: 0; margin: 0; color: var(--research-text-primary); font-size: var(--research-text-sm); overflow-wrap: anywhere; }
@media (min-width: 1720px) { .assistant { grid-template-columns: minmax(230px, 280px) minmax(0, 1fr) minmax(330px, 390px); } .assistant__messages { padding-inline: var(--research-space-8); } }
@media (max-width: 1480px) { .assistant { grid-template-columns: minmax(180px, 210px) minmax(0, 1fr) minmax(250px, 290px); } .assistant__sessions, .assistant__context { padding: var(--research-space-4); } .assistant__conversation-header, .assistant__context-bar, .assistant__messages, .assistant__composer { padding-inline: var(--research-space-4); } }
@media (max-width: 1080px) { .assistant { height: auto; min-height: 100%; grid-template-columns: 1fr; overflow-x: hidden; } .assistant__sessions, .assistant__context { border: 0; border-bottom: 1px solid var(--research-divider); } .assistant__conversation { min-height: 640px; } .assistant__context-stack { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) { .assistant__conversation-header, .assistant__context-bar, .assistant__messages, .assistant__composer { padding-inline: var(--research-space-4); } .assistant__context-summary { grid-template-columns: minmax(0, 1fr); } .assistant__context-stack { grid-template-columns: minmax(0, 1fr); } .assistant__message { max-width: 100%; } }
@media (prefers-reduced-motion: reduce) { .assistant *, .assistant *::before, .assistant *::after { scroll-behavior: auto; transition-property: none; animation: none; } }
</style>

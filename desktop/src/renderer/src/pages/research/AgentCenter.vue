<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AgentWorkspaceCard from '../../components/research/AgentWorkspaceCard.vue'
import EvidencePanel from '../../components/research/EvidencePanel.vue'
import ResearchMetricPanel from '../../components/research/ResearchMetricPanel.vue'
import ResearchPageShell from '../../components/research/ResearchPageShell.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import ResearchTimeline from '../../components/research/ResearchTimeline.vue'
import ToolExecutionPanel from '../../components/research/ToolExecutionPanel.vue'
import { useAgentStore } from '../../stores/research/agent.store'

const agentStore = useAgentStore()
const researchInput = ref('')
const sessionLoadError = ref('')
const researchError = ref('')

const FIXED_AGENT_ROLES = [
  { name: '文献智能体', role: '文献智能体' },
  { name: '实验智能体', role: '实验智能体' },
  { name: '分析智能体', role: '分析智能体' },
  { name: '写作智能体', role: '写作智能体' },
  { name: '审稿智能体', role: '审稿智能体' }
] as const

const metrics = computed(() => [
  { label: '研究会话', value: agentStore.sessions.length },
  { label: '对话消息', value: agentStore.messages.length },
  { label: '协作事件', value: agentStore.events.length },
  { label: '引用来源', value: agentStore.citations.length },
  { label: '研究证据', value: agentStore.evidence.length }
])
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
const toolExecutions = computed(() => agentStore.messages.flatMap(message =>
  (message.toolCalls ?? []).map((tool, index) => ({
    id: `${message.id}-${tool.name}-${index}`,
    tool: tool.name,
    status: tool.status,
    output: tool.result ?? tool.error
  }))
))
const agentCards = computed(() => FIXED_AGENT_ROLES.map(definition => {
  const role = FIXED_AGENT_ROLES.find(role => role.name === definition.name)
  const event = role
    ? [...agentStore.events].reverse().find(item => item.label.includes(role.name) || item.detail.includes(role.name))
    : undefined
  const message = role
    ? [...agentStore.messages].reverse().find(item => item.content.includes(role.name))
    : undefined
  return {
    name: definition.name,
    role: definition.role,
    status: event?.status,
    currentTask: event?.detail || message?.content || undefined,
    queue: undefined,
    dataAvailable: Boolean(event || message)
  }
}))

async function runResearch(): Promise<void> {
  const problem = researchInput.value.trim()
  if (!problem || agentStore.isLoading) return
  researchError.value = ''
  try {
    await agentStore.runResearch(problem)
  } catch {
    researchError.value = '科研任务执行失败，请重试。'
  }
}

async function retryResearch(): Promise<void> {
  await runResearch()
}

async function loadSessionsSafely(): Promise<void> {
  if (agentStore.isLoading) return
  try {
    await agentStore.loadSessions()
    sessionLoadError.value = ''
  } catch {
    sessionLoadError.value = '科研会话加载失败，请重试'
  }
}

onMounted(() => { void loadSessionsSafely() })
</script>

<template>
  <ResearchPageShell
    eyebrow="科研智能体"
    title="Agent 中心"
    description="观察真实科研会话中的协作事件、证据与工具调用。"
    :status="agentStore.isLoading ? 'AI 正在分析...' : '可观察执行'"
  >
    <main class="agent-center" aria-label="Agent 中心">
      <form class="agent-center__task" aria-label="科研任务输入" @submit.prevent="runResearch">
        <label for="research-task-input">科研任务</label>
        <div class="agent-center__task-row">
          <input
            id="research-task-input"
            v-model="researchInput"
            data-testid="research-task-input"
            type="text"
            placeholder="请输入需要分析的科研问题"
            autocomplete="off"
            :disabled="agentStore.isLoading"
          >
          <button
            data-testid="run-research"
            type="submit"
            :disabled="agentStore.isLoading || !researchInput.trim()"
            :aria-busy="agentStore.isLoading"
          >
            {{ agentStore.isLoading ? 'AI 正在分析...' : '开始研究' }}
          </button>
        </div>
      </form>

      <section v-if="sessionLoadError" class="agent-center__error" role="alert" aria-live="assertive">
        <strong>{{ sessionLoadError }}</strong>
        <button data-testid="retry-session-load" type="button" :disabled="agentStore.isLoading" @click="loadSessionsSafely">重新加载</button>
      </section>
      <section v-if="researchError" class="agent-center__error" role="alert" aria-live="assertive">
        <ResearchState state="error" :title="researchError" description="请在保留的科研任务输入基础上重新分析。" @retry="retryResearch" />
        <button data-testid="retry-research" type="button" :disabled="agentStore.isLoading" @click="retryResearch">重新分析</button>
      </section>

      <ResearchState
        v-if="agentStore.isLoading"
        class="agent-center__state"
        state="loading"
        title="AI 正在分析..."
        description="正在等待当前科研任务的真实协作事件。"
      />
      <ResearchState
        v-else-if="agentStore.sessions.length === 0"
        class="agent-center__state"
        state="empty"
        title="暂无科研数据"
        description="创建或选择研究会话后，可观察 AI 研究团队协作。"
      />

      <section class="agent-center__metrics" aria-label="Agent 中心指标">
        <ResearchMetricPanel :items="metrics" />
      </section>

      <section class="agent-center__roles" aria-label="AI 研究团队">
        <header class="agent-center__section-header">
          <div><p>Observable AI Research Team</p><h2>AI 研究团队</h2></div>
          <span role="status" aria-live="polite">未知运行数据将显示待接入数据</span>
        </header>
        <div class="agent-center__role-grid">
          <AgentWorkspaceCard
            v-for="agent in agentCards"
            :key="agent.name"
            :name="agent.name"
            :role="agent.role"
            :status="agent.status"
            :currentTask="agent.currentTask"
            :queue="agent.queue"
            :dataAvailable="agent.dataAvailable"
          />
        </div>
      </section>

      <section class="agent-center__observability" aria-label="协作时间线与证据">
        <ResearchTimeline :items="events" />
        <EvidencePanel :evidence="evidence" :citations="citations" />
      </section>

      <section class="agent-center__tools" aria-label="工具执行">
        <ToolExecutionPanel :executions="toolExecutions" />
      </section>

      <section class="agent-center__design" aria-label="研究设计结果">
        <ResearchState
          v-if="!agentStore.designResult"
          state="empty"
          title="暂无科研数据"
          description="提交科研任务后，这里将展示真实研究设计结果。"
        />
        <div v-else data-testid="design-result" class="agent-center__design-result">
          <h2>研究设计结果</h2>
          <section>
            <h3>核心科研问题</h3>
            <p>{{ agentStore.designResult.problemAnalysis.keyScientificQuestion }}</p>
          </section>
          <section>
            <h3>研究假设</h3>
            <ul><li v-for="hypothesis in agentStore.designResult.hypotheses" :key="hypothesis.statement">{{ hypothesis.statement }}</li></ul>
          </section>
          <section>
            <h3>模型选择</h3>
            <p>{{ agentStore.designResult.modelSelection.model }}</p>
          </section>
        </div>
      </section>
    </main>
  </ResearchPageShell>
</template>

<style scoped>
.agent-center { display: grid; min-width: 0; gap: var(--research-grid-gap); overflow-x: hidden; color: var(--research-text-primary); }
.agent-center__task, .agent-center__roles, .agent-center__design { min-width: 0; padding: var(--research-space-5); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-panel); background: var(--research-bg-card); box-shadow: var(--research-shadow-soft); }
.agent-center__task > label { display: block; margin-bottom: var(--research-space-3); font-size: var(--research-text-card-title); font-weight: var(--research-font-weight-semibold); }
.agent-center__task-row { display: flex; min-width: 0; gap: var(--research-space-3); }
.agent-center__task-row input { min-width: 0; flex: 1; padding: var(--research-space-3) var(--research-space-4); border: 1px solid var(--research-border-strong); border-radius: var(--research-radius-input); background: var(--research-bg-card); color: var(--research-text-primary); font: inherit; }
.agent-center__task-row button, .agent-center__error button { padding: var(--research-space-3) var(--research-space-4); border: 1px solid var(--research-primary-600); border-radius: var(--research-radius-button); background: var(--research-primary-600); color: var(--research-text-inverse); font: inherit; cursor: pointer; }
.agent-center__task-row input:focus-visible, .agent-center__task-row button:focus-visible, .agent-center__error button:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.agent-center__task-row button:disabled, .agent-center__error button:disabled { cursor: not-allowed; opacity: .62; }
.agent-center__error { display: flex; align-items: center; justify-content: space-between; gap: var(--research-space-3); padding: var(--research-space-4); border: 1px solid var(--research-danger-100); border-radius: var(--research-radius-card); background: var(--research-danger-50); color: var(--research-danger-600); }
.agent-center__error button { border-color: var(--research-danger-500); background: var(--research-bg-card); color: var(--research-danger-600); }
.agent-center__state { min-height: 160px; }
.agent-center__section-header { display: flex; flex-wrap: wrap; align-items: start; justify-content: space-between; gap: var(--research-space-3); margin-bottom: var(--research-space-4); }
.agent-center__section-header p, .agent-center__section-header h2 { margin: 0; }
.agent-center__section-header p { color: var(--research-primary-600); font-size: var(--research-text-xs); font-weight: var(--research-font-weight-semibold); letter-spacing: .05em; }
.agent-center__section-header h2 { margin-top: var(--research-space-1); font-size: var(--research-text-section-title); }
.agent-center__section-header > span { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.agent-center__role-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: var(--research-space-3); min-width: 0; }
.agent-center__observability { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--research-grid-gap); min-width: 0; }
.agent-center__tools { min-width: 0; }
.agent-center__design-result { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--research-space-4); }
.agent-center__design-result > h2 { grid-column: 1 / -1; margin: 0; font-size: var(--research-text-section-title); }
.agent-center__design-result section { min-width: 0; padding: var(--research-space-4); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-panel); }
.agent-center__design-result h3, .agent-center__design-result p, .agent-center__design-result ul { margin: 0; }
.agent-center__design-result h3 { font-size: var(--research-text-card-title); }
.agent-center__design-result p, .agent-center__design-result li { margin-top: var(--research-space-2); color: var(--research-text-secondary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); overflow-wrap: anywhere; }
.agent-center__design-result ul { padding-inline-start: var(--research-space-5); }
@media (min-width: 1720px) { .agent-center__role-grid { gap: var(--research-space-4); } .agent-center__observability { grid-template-columns: minmax(0, .9fr) minmax(0, 1.1fr); } }
@media (max-width: 1480px) { .agent-center__role-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } .agent-center__design-result { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 1050px) { .agent-center__observability, .agent-center__design-result { grid-template-columns: minmax(0, 1fr); } .agent-center__task-row { flex-direction: column; } }
@media (prefers-reduced-motion: reduce) { .agent-center *, .agent-center *::before, .agent-center *::after { transition-property: none; animation: none; } }
</style>

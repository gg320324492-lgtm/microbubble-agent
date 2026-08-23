<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AgentCard from '../../components/research/AgentCard.vue'
import ResearchPageShell from '../../components/research/ResearchPageShell.vue'
import ResearchPanel from '../../components/research/ResearchPanel.vue'
import ResearchState from '../../components/research/ResearchState.vue'
import Timeline from '../../components/research/Timeline.vue'
import ResearchIcon from '../../components/icons/ResearchIcon.vue'
import type { ResearchIconName } from '../../components/icons/research-icons'
import type { AgentEvent, ToolCallResult } from '../../services/research/research-agent.service'
import { useAgentStore } from '../../stores/research/agent.store'
import { useWorkflowStore, type TaskStatus, type WorkflowTask } from '../../stores/research/workflow.store'

type TimelineStatus = 'done' | 'current' | 'pending' | 'error'
type AgentStatus = 'running' | 'completed' | 'idle' | 'error'

interface ThinkingStage {
  label: string
  eventType: AgentEvent['type']
}

interface AgentDefinition {
  type: WorkflowTask['type']
  name: string
  icon: ResearchIconName
}

const agentStore = useAgentStore()
const workflowStore = useWorkflowStore()
const researchInput = ref('')
const sessionLoadError = ref('')

const THINKING_STAGES: ThinkingStage[] = [
  { label: '理解科研问题', eventType: 'planner' },
  { label: '检索知识与证据', eventType: 'retrieval' },
  { label: '分析降解机制', eventType: 'analysis' },
  { label: '设计实验参数', eventType: 'tool_call' },
  { label: '生成科研报告', eventType: 'response' }
]

const AGENT_DEFINITIONS: AgentDefinition[] = [
  { type: 'design', name: '规划智能体', icon: 'agent' },
  { type: 'literature', name: '知识智能体', icon: 'literature' },
  { type: 'experiment', name: '实验智能体', icon: 'experiment' },
  { type: 'analysis', name: '分析智能体', icon: 'data' },
  { type: 'manuscript', name: '写作智能体', icon: 'manuscript' }
]

const TIMELINE_STATUS: Record<AgentEvent['status'], TimelineStatus> = {
  pending: 'pending',
  running: 'current',
  completed: 'done',
  error: 'error'
}

const TIMELINE_STATUS_LABEL: Record<AgentEvent['status'], string> = {
  pending: '等待中',
  running: '运行中',
  completed: '已完成',
  error: '错误'
}

const TASK_STATUS: Record<TaskStatus, AgentStatus> = {
  idle: 'idle',
  pending: 'idle',
  running: 'running',
  completed: 'completed',
  failed: 'error'
}

const TOOL_STATUS_LABEL: Record<ToolCallResult['status'], string> = {
  running: '运行中',
  completed: '已完成',
  error: '错误'
}

const TOOL_STATUS_ICON: Record<ToolCallResult['status'], ResearchIconName> = {
  running: 'running',
  completed: 'check',
  error: 'error'
}

const thoughtSteps = computed(() => THINKING_STAGES.map(stage => {
  const event = [...agentStore.events].reverse().find(item => item.type === stage.eventType)
  return {
    label: stage.label,
    detail: event?.detail,
    time: event ? formatTime(event.timestamp) : undefined,
    status: event ? TIMELINE_STATUS[event.status] : 'pending' as const,
    statusLabel: event ? TIMELINE_STATUS_LABEL[event.status] : '等待中'
  }
}))

const agentCards = computed(() => AGENT_DEFINITIONS.map(definition => {
  const task = [...workflowStore.tasks].reverse().find(item => item.type === definition.type)
  const loadingExperiment = definition.type === 'experiment'
    && agentStore.isLoading
    && (!task || ['idle', 'pending', 'running'].includes(task.status))
  return {
    ...definition,
    status: loadingExperiment ? 'running' as const : task ? TASK_STATUS[task.status] : 'idle' as const,
    task: task?.label ?? '等待任务',
    result: task?.error ?? task?.result,
    duration: formatDuration(task)
  }
}))

const latestToolCalls = computed<ToolCallResult[]>(() => {
  const message = [...agentStore.messages].reverse().find(item => item.toolCalls?.length)
  return message?.toolCalls ?? []
})

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function formatDuration(task?: WorkflowTask): string {
  if (
    !task
    || typeof task.startedAt !== 'number'
    || typeof task.completedAt !== 'number'
    || task.completedAt < task.startedAt
  ) return '—'
  return `${((task.completedAt - task.startedAt) / 1000).toFixed(1)} 秒`
}

function variableTypeLabel(type: string): string {
  return ({ independent: '自变量', dependent: '因变量', control: '控制变量' } as Record<string, string>)[type] ?? type
}

async function runResearch(): Promise<void> {
  const problem = researchInput.value.trim()
  if (!problem || agentStore.isLoading) return
  workflowStore.clearErrors()
  try {
    await agentStore.runResearch(problem)
  } catch {
    workflowStore.addError('科研任务执行失败，请重试。')
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
    description="观察科研任务的思考阶段、智能体协作与工具执行证据。"
    :status="agentStore.isLoading ? 'AI 正在分析...' : '可观察执行'"
  >
    <form class="agent-center__task" aria-label="科研任务输入" @submit.prevent="runResearch">
      <label class="agent-center__task-label" for="research-task-input">
        <ResearchIcon name="sparkles" :size="18" />
        科研任务
      </label>
      <div class="agent-center__task-row">
        <input
          id="research-task-input"
          v-model="researchInput"
          data-testid="research-task-input"
          type="text"
          placeholder="请输入需要分析的科研问题"
          autocomplete="off"
          :disabled="agentStore.isLoading"
          @keydown.enter.prevent="runResearch"
        />
        <button
          class="agent-center__run"
          data-testid="run-research"
          type="submit"
          :disabled="agentStore.isLoading || !researchInput.trim()"
          :aria-busy="agentStore.isLoading"
        >
          <ResearchIcon :name="agentStore.isLoading ? 'running' : 'sparkles'" :size="16" />
          {{ agentStore.isLoading ? 'AI 正在分析...' : '开始研究' }}
        </button>
      </div>
    </form>

    <section
      v-if="sessionLoadError"
      data-testid="agent-session-load-error"
      class="agent-center__errors"
      role="alert"
      aria-live="assertive"
    >
      <div><strong>{{ sessionLoadError }}</strong></div>
      <button
        data-testid="retry-session-load"
        type="button"
        :disabled="agentStore.isLoading"
        @click="loadSessionsSafely"
      >
        <ResearchIcon name="running" :size="15" />
        重新加载
      </button>
    </section>

    <section v-if="workflowStore.errors.length" class="agent-center__errors" role="alert" aria-live="assertive">
      <div>
        <strong>分析失败，请重试</strong>
        <p v-for="(error, index) in workflowStore.errors" :key="`${index}-${error}`">{{ error }}</p>
      </div>
      <button data-testid="retry-research" type="button" @click="retryResearch">
        <ResearchIcon name="running" :size="15" />
        重新分析
      </button>
    </section>

    <div class="agent-center__observability">
      <ResearchPanel class="agent-center__timeline-panel" title="AI 思考时间线" subtitle="五阶段科研推理轨迹" tone="ai">
        <Timeline data-testid="thinking-timeline" :steps="thoughtSteps" />
      </ResearchPanel>

      <ResearchPanel class="agent-center__matrix-panel" title="智能体协作矩阵" subtitle="状态与任务均来自当前工作流" tone="primary">
        <div class="agent-center__matrix">
          <AgentCard
            v-for="agent in agentCards"
            :key="agent.type"
            :data-agent-kind="agent.type"
            :icon="agent.icon"
            :name="agent.name"
            :status="agent.status"
            :task="agent.task"
            :result="agent.result"
            :duration="agent.duration"
          />
        </div>
      </ResearchPanel>
    </div>

    <ResearchPanel data-testid="tool-execution" class="agent-center__tools" title="工具执行可视化" subtitle="只显示最近一条真实消息携带的工具结果" tone="success">
      <ResearchState v-if="latestToolCalls.length === 0" state="empty" title="暂无工具执行记录" description="科研智能体调用工具后，这里将展示真实执行轨迹。" />
      <div v-else class="agent-center__tool-list">
        <article v-for="(tool, index) in latestToolCalls" :key="`${index}-${tool.name}`" class="agent-center__tool">
          <header class="agent-center__tool-header">
            <span class="agent-center__tool-icon"><ResearchIcon name="tool" :size="18" /></span>
            <div><h3>{{ tool.name }}</h3><p>工具执行 {{ index + 1 }}</p></div>
            <span :class="['agent-center__tool-status', `agent-center__tool-status--${tool.status}`]">
              <ResearchIcon :name="TOOL_STATUS_ICON[tool.status]" :size="14" />
              {{ TOOL_STATUS_LABEL[tool.status] }}
            </span>
          </header>
          <dl class="agent-center__tool-details">
            <div><dt>输入：</dt><dd>—</dd></div>
            <div><dt>输出：</dt><dd>{{ tool.result ?? tool.error ?? '—' }}</dd></div>
            <div><dt>结果：</dt><dd>{{ TOOL_STATUS_LABEL[tool.status] }}</dd></div>
            <div><dt>来源：</dt><dd>—</dd></div>
            <div><dt>耗时：</dt><dd>—</dd></div>
          </dl>
        </article>
      </div>
    </ResearchPanel>

    <ResearchPanel class="agent-center__design" title="研究设计结果" subtitle="科研问题、机制、假设、变量与模型" tone="ai">
      <ResearchState v-if="!agentStore.designResult" state="empty" title="暂无科研数据" description="提交科研任务后，这里将展示真实研究设计结果。" />
      <div v-else data-testid="design-result" class="agent-center__design-grid">
        <section>
          <h3>核心科研问题</h3>
          <p>{{ agentStore.designResult.problemAnalysis.keyScientificQuestion }}</p>
          <h4>可能机制</h4>
          <ul><li v-for="mechanism in agentStore.designResult.problemAnalysis.possibleMechanisms" :key="mechanism">{{ mechanism }}</li></ul>
        </section>
        <section>
          <h3>研究假设</h3>
          <ul>
            <li v-for="hypothesis in agentStore.designResult.hypotheses" :key="hypothesis.statement">
              {{ hypothesis.statement }}<span>置信度 {{ Math.round(hypothesis.confidence * 100) }}%</span>
            </li>
          </ul>
        </section>
        <section>
          <h3>实验变量</h3>
          <dl>
            <div v-for="variable in agentStore.designResult.experimentPlan.variables" :key="variable.name">
              <dt>{{ variable.name }}</dt><dd>{{ variable.range }} · {{ variableTypeLabel(variable.type) }}</dd>
            </div>
          </dl>
        </section>
        <section>
          <h3>模型选择</h3>
          <p>{{ agentStore.designResult.modelSelection.model }}</p>
          <span>置信度 {{ Math.round(agentStore.designResult.modelSelection.confidence * 100) }}%</span>
        </section>
      </div>
    </ResearchPanel>
  </ResearchPageShell>
</template>

<style scoped>
.agent-center__task { padding: var(--research-space-5); margin-bottom: var(--research-space-5); border: 1px solid var(--research-ai-200); border-radius: var(--research-radius-panel); background: var(--research-bg-card); box-shadow: var(--research-shadow-soft); }
.agent-center__task-label { display: flex; align-items: center; gap: var(--research-space-2); margin-bottom: var(--research-space-3); color: var(--research-text-primary); font-size: var(--research-text-card-title); font-weight: var(--research-font-weight-semibold); }
.agent-center__task-label svg { color: var(--research-ai-600); }
.agent-center__task-row { display: flex; gap: var(--research-space-3); min-width: 0; }
.agent-center__task-row input { flex: 1; min-width: 0; min-height: 42px; padding: 0 var(--research-space-4); border: 1px solid var(--research-border-strong); border-radius: var(--research-radius-input); background: var(--research-bg-card); color: var(--research-text-primary); font: inherit; }
.agent-center__task-row input:focus-visible { outline: none; border-color: var(--research-primary-500); box-shadow: var(--research-shadow-focus-primary); }
.agent-center__task-row input:disabled { cursor: not-allowed; background: var(--research-bg-panel); color: var(--research-text-secondary); }
.agent-center__run, .agent-center__errors button { display: inline-flex; min-height: 42px; align-items: center; justify-content: center; gap: var(--research-space-2); padding: 0 var(--research-space-5); border: 1px solid var(--research-primary-600); border-radius: var(--research-radius-button); background: var(--research-primary-600); color: var(--research-text-inverse); font: inherit; font-weight: var(--research-font-weight-semibold); cursor: pointer; }
.agent-center__run:focus-visible, .agent-center__errors button:focus-visible { outline: none; box-shadow: var(--research-shadow-focus-primary); }
.agent-center__run:disabled { cursor: not-allowed; border-color: var(--research-border-strong); background: var(--research-bg-hover); color: var(--research-text-secondary); }
.agent-center__errors { display: flex; align-items: center; justify-content: space-between; gap: var(--research-space-4); margin-bottom: var(--research-space-5); padding: var(--research-space-4) var(--research-space-5); border: 1px solid var(--research-danger-100); border-radius: var(--research-radius-card); background: var(--research-danger-50); color: var(--research-danger-600); }
.agent-center__errors strong { color: var(--research-text-primary); }
.agent-center__errors p { margin: var(--research-space-1) 0 0; font-size: var(--research-text-sm); }
.agent-center__errors button { min-height: 36px; border-color: var(--research-danger-500); background: var(--research-bg-card); color: var(--research-danger-600); }
.agent-center__observability { display: grid; grid-template-columns: minmax(280px, .78fr) minmax(0, 1.55fr); gap: var(--research-grid-gap); align-items: start; }
.agent-center__matrix { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: var(--research-space-3); }
.agent-center__tools, .agent-center__design { margin-top: var(--research-grid-gap); }
.agent-center__tool-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--research-space-4); }
.agent-center__tool { min-width: 0; padding: var(--research-space-4); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-panel); }
.agent-center__tool-header { display: flex; align-items: center; gap: var(--research-space-3); }
.agent-center__tool-icon { display: grid; width: 36px; height: 36px; place-items: center; border-radius: var(--research-radius-button); background: var(--research-success-50); color: var(--research-success-700); }
.agent-center__tool-header h3, .agent-center__tool-header p { margin: 0; }
.agent-center__tool-header h3 { color: var(--research-text-primary); font-size: var(--research-text-body); }
.agent-center__tool-header p { margin-top: var(--research-space-1); color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.agent-center__tool-status { display: inline-flex; align-items: center; gap: var(--research-space-1); margin-left: auto; color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.agent-center__tool-status--completed { color: var(--research-success-700); }
.agent-center__tool-status--error { color: var(--research-danger-600); }
.agent-center__tool-details { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--research-space-3); margin: var(--research-space-4) 0 0; }
.agent-center__tool-details div { min-width: 0; }
.agent-center__tool-details dt { color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.agent-center__tool-details dd { margin: var(--research-space-1) 0 0; overflow-wrap: anywhere; color: var(--research-text-primary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }
.agent-center__design-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--research-space-4); }
.agent-center__design-grid section { min-width: 0; padding: var(--research-space-4); border: 1px solid var(--research-border-subtle); border-radius: var(--research-radius-card); background: var(--research-bg-panel); }
.agent-center__design-grid h3, .agent-center__design-grid h4, .agent-center__design-grid p, .agent-center__design-grid ul, .agent-center__design-grid dl { margin: 0; }
.agent-center__design-grid h3 { color: var(--research-text-primary); font-size: var(--research-text-card-title); }
.agent-center__design-grid h4 { margin-top: var(--research-space-4); color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.agent-center__design-grid p, .agent-center__design-grid li, .agent-center__design-grid dd { margin-top: var(--research-space-2); color: var(--research-text-primary); font-size: var(--research-text-sm); line-height: var(--research-line-height-body); }
.agent-center__design-grid ul { padding-left: var(--research-space-5); }
.agent-center__design-grid li span, .agent-center__design-grid section > span { display: block; margin-top: var(--research-space-1); color: var(--research-text-secondary); font-size: var(--research-text-xs); }
.agent-center__design-grid dl div { padding: var(--research-space-2) 0; border-bottom: 1px solid var(--research-divider); }
.agent-center__design-grid dt { color: var(--research-text-primary); font-size: var(--research-text-sm); font-weight: var(--research-font-weight-medium); }
.agent-center__design-grid dd { margin-top: var(--research-space-1); color: var(--research-text-secondary); }
@media (max-width: 1480px) { .agent-center__matrix { grid-template-columns: repeat(3, minmax(0, 1fr)); } .agent-center__design-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 1050px) { .agent-center__observability { grid-template-columns: minmax(0, 1fr); } .agent-center__tool-list { grid-template-columns: minmax(0, 1fr); } }
</style>

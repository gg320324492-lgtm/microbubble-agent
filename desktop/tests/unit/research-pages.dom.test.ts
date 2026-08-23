// @vitest-environment happy-dom
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import type { Component } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('echarts/core', () => ({
  use: vi.fn(),
  init: vi.fn(() => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }))
}))
vi.mock('echarts/charts', () => ({ LineChart: { name: 'LineChart' } }))
vi.mock('echarts/components', () => ({
  GridComponent: { name: 'GridComponent' },
  LegendComponent: { name: 'LegendComponent' },
  TooltipComponent: { name: 'TooltipComponent' },
  AriaComponent: { name: 'AriaComponent' }
}))
vi.mock('echarts/renderers', () => ({ CanvasRenderer: { name: 'CanvasRenderer' } }))

import AgentCard from '@/components/research/AgentCard.vue'
import CitationCard from '@/components/research/CitationCard.vue'
import AgentCenter from '@/pages/research/AgentCenter.vue'
import Assistant from '@/pages/research/Assistant.vue'
import DataAnalysis from '@/pages/research/DataAnalysis.vue'
import Experiment from '@/pages/research/Experiment.vue'
import Literature from '@/pages/research/Literature.vue'
import { useAgentStore } from '@/stores/research/agent.store'
import { useDatasetStore } from '@/stores/research/dataset.store'
import { useExperimentStore } from '@/stores/research/experiment.store'
import { useKnowledgeStore } from '@/stores/research/knowledge.store'
import { useWorkflowStore } from '@/stores/research/workflow.store'
import {
  dataAnalysisService,
  type AnalysisReport,
  type DataAnalysisAdapter,
  type VariableImportance
} from '@/services/research/data-analysis.service'
import {
  experimentService,
  type ExperimentAdapter,
  type ExperimentDesign
} from '@/services/research/experiment.service'
import {
  knowledgeService,
  type DocumentItem,
  type KnowledgeAdapter,
  type KnowledgeFolder
} from '@/services/research/knowledge.service'
import {
  literatureService,
  type LiteratureAdapter,
  type PaperAssessment
} from '@/services/research/literature.service'
import type {
  AgentEvent,
  AgentMessage,
  CitationItem,
  EvidenceItem,
  ResearchDesignResult,
  ResearchSession
} from '@/services/research/research-agent.service'

type AgentStore = ReturnType<typeof useAgentStore>
type WorkflowStore = ReturnType<typeof useWorkflowStore>

interface MountedResearchPage {
  wrapper: VueWrapper
  pinia: Pinia
  agentStore: AgentStore
  workflowStore: WorkflowStore
}

const TIMESTAMP = new Date('2026-08-24T09:30:00+08:00').getTime()
const mountedPageWrappers: VueWrapper[] = []

const literatureDocuments: DocumentItem[] = [
  {
    id: 'd1',
    title: '臭氧微纳米气泡降解四环素的动力学研究',
    authors: '李小红、张伟',
    journal: '环境科学学报',
    year: 2024,
    type: 'paper',
    tags: ['臭氧', '动力学'],
    credibility: 0.83,
    citations: 18,
    relevance: 0.94
  },
  {
    id: 'd2',
    title: '纳米气泡传质机制综述',
    authors: '王宇',
    journal: '化工进展',
    year: 2023,
    type: 'paper',
    tags: ['传质'],
    credibility: 0.72,
    citations: 9,
    relevance: 0.81
  }
]

const literatureFolders: KnowledgeFolder[] = [
  { id: 'folder-1', name: '四环素降解', count: 2 }
]

const literatureAssessments: PaperAssessment[] = [
  {
    documentId: 'd1',
    reliabilityScore: 0.82,
    evidenceScore: 0.78,
    methodologyScore: 0.65,
    limitations: ['样本量仍需扩大'],
    concerns: ['缺少长期稳定性验证']
  }
]

const experimentDesign: ExperimentDesign = {
  id: 'exp-real',
  title: '臭氧微纳米气泡参数优化',
  question: '如何提高四环素降解过程的臭氧利用率？',
  hypotheses: [{ statement: '减小气泡粒径可提高气液传质效率', confidence: 0.82 }],
  variables: [
    { name: '气泡粒径', type: 'independent', range: '80–300', unit: 'nm' },
    { name: '四环素去除率', type: 'dependent', range: '0–100', unit: '%' }
  ],
  groups: [
    { name: '对照组', condition: '常规曝气', purpose: '建立基线' },
    { name: '实验组', condition: '微纳米气泡曝气', purpose: '检验传质增益' }
  ],
  metrics: ['去除率', '动力学常数'],
  model: { name: '伪一级动力学', confidence: 0.88 },
  status: 'designing'
}

const analysisReport: AnalysisReport = {
  quality: {
    completeness: 0.96,
    missingValues: { pH: 2, temperature: 1 },
    outliers: { ozone: 3 },
    warnings: ['pH 存在两个缺失值', '臭氧浓度存在离群点']
  },
  statistics: [
    { metric: '平均臭氧浓度', value: 4.75, interpretation: '反映总体氧化剂水平' },
    { metric: '浓度标准差', value: 2.31, interpretation: '反映实验批次波动' },
    { metric: '降解相关系数', value: -0.987, interpretation: '时间与归一化浓度强负相关' }
  ],
  models: [
    { model: 'first-order', parameters: { k: 0.0243 }, rSquared: 0.9887, residualError: 0.0211 },
    { model: 'zero-order', parameters: { k: 0.158 }, rSquared: 0.892, residualError: -0.085 },
    { model: 'r2-negative', parameters: { k: 0.1 }, rSquared: -0.1, residualError: 0.02 },
    { model: 'r2-overflow', parameters: { k: 0.1 }, rSquared: 1.2, residualError: 0.02 },
    { model: 'r2-nan', parameters: { k: 0.1 }, rSquared: Number.NaN, residualError: 0.02 },
    { model: 'r2-infinite', parameters: { k: 0.1 }, rSquared: Number.POSITIVE_INFINITY, residualError: 0.02 }
  ],
  figures: [
    { type: 'line', title: '臭氧浓度时间曲线', xVariable: '时间', yVariable: '浓度' },
    { type: 'scatter+fit', title: '一级动力学拟合图', xVariable: '时间', yVariable: 'C/C₀' }
  ],
  conclusions: [
    { observation: '降解过程符合一级动力学特征', interpretation: '拟合结果支持浓度依赖机制', confidence: 0.9 },
    { observation: '可信度负值', interpretation: '非法边界样本', confidence: -0.1 },
    { observation: '可信度溢出', interpretation: '非法边界样本', confidence: 1.2 },
    { observation: '可信度非数值', interpretation: '非法边界样本', confidence: Number.NaN },
    { observation: '可信度无穷', interpretation: '非法边界样本', confidence: Number.POSITIVE_INFINITY }
  ]
}

const analysisImportance: VariableImportance[] = [
  { variable: '真实曝气量', importance: 0.42, contribution: '强正效应', confidence: 0.85 },
  { variable: '真实初始 pH', importance: 0.21, contribution: '负相关', confidence: 0.72 },
  { variable: '真实气泡粒径', importance: 0.11, contribution: '弱负效应', confidence: 0.55 }
]

let knowledgeAdapter: KnowledgeAdapter
let literatureAdapter: LiteratureAdapter
let experimentAdapter: ExperimentAdapter
let dataAnalysisAdapter: DataAnalysisAdapter

function installResearchAdapters(options: {
  documents?: DocumentItem[]
  assessments?: PaperAssessment[]
  design?: ExperimentDesign | null
  report?: AnalysisReport | null
  importance?: VariableImportance[]
} = {}) {
  const documents = options.documents ?? literatureDocuments
  const assessments = options.assessments ?? literatureAssessments
  const design = options.design === undefined ? experimentDesign : options.design
  knowledgeAdapter = {
    getDocuments: vi.fn().mockResolvedValue(documents),
    getDocument: vi.fn(async id => documents.find(document => document.id === id)),
    searchDocuments: vi.fn().mockResolvedValue([]),
    getFolders: vi.fn().mockResolvedValue(literatureFolders),
    getDocumentCount: vi.fn().mockResolvedValue(documents.length),
    importDocument: vi.fn().mockResolvedValue(null)
  }
  literatureAdapter = {
    assessPaper: vi.fn(async id => assessments.find(item => item.documentId === id) ?? null),
    extractEvidence: vi.fn().mockResolvedValue([]),
    getDocumentAssessments: vi.fn().mockResolvedValue(assessments),
    summarizePaper: vi.fn().mockResolvedValue('AI 摘要：实验结果支持传质强化机制。')
  }
  experimentAdapter = {
    getDesign: vi.fn().mockResolvedValue(design as ExperimentDesign),
    getDesignStatus: vi.fn().mockResolvedValue(design?.status ?? 'designing'),
    generateHypotheses: vi.fn().mockResolvedValue([
      { statement: '提高气液界面积可增强臭氧利用率', confidence: 0.76 }
    ]),
    updateDesign: vi.fn().mockResolvedValue(undefined)
  }
  const report = options.report === undefined ? analysisReport : options.report
  const importance = options.importance ?? analysisImportance
  dataAnalysisAdapter = {
    getAnalysisReport: vi.fn().mockResolvedValue(report as AnalysisReport),
    getVariableImportance: vi.fn().mockResolvedValue(importance),
    fitModels: vi.fn().mockResolvedValue(report?.models ?? []),
    interpretResults: vi.fn().mockResolvedValue(report?.conclusions ?? [])
  }
  knowledgeService.setAdapter(knowledgeAdapter)
  literatureService.setAdapter(literatureAdapter)
  experimentService.setAdapter(experimentAdapter)
  dataAnalysisService.setAdapter(dataAnalysisAdapter)
}

const completedPlannerEvent: AgentEvent = {
  type: 'planner',
  label: '研究问题解析',
  detail: '已识别目标污染物与反应体系',
  timestamp: TIMESTAMP,
  status: 'completed'
}

const designResult: ResearchDesignResult = {
  problemAnalysis: {
    keyScientificQuestion: '微纳米气泡如何改变臭氧传质效率？',
    possibleMechanisms: ['扩大气液界面', '延长臭氧停留时间']
  },
  hypotheses: [{ statement: '更小气泡可提高体积传质系数', confidence: 0.82 }],
  experimentPlan: {
    variables: [{ name: '气泡粒径', type: 'independent', range: '80–300 nm' }]
  },
  modelSelection: { model: '伪一级动力学', confidence: 0.91 }
}

function mountPage(
  component: Component,
  configure?: (agentStore: AgentStore, workflowStore: WorkflowStore) => void
): MountedResearchPage {
  const pinia = createPinia()
  setActivePinia(pinia)
  const agentStore = useAgentStore()
  const workflowStore = useWorkflowStore()
  vi.spyOn(agentStore, 'loadSessions').mockResolvedValue(undefined)
  configure?.(agentStore, workflowStore)
  const wrapper = mount(component, { attachTo: document.body, global: { plugins: [pinia] } })
  mountedPageWrappers.push(wrapper)
  return { wrapper, pinia, agentStore, workflowStore }
}

beforeEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  installResearchAdapters()
})

afterEach(() => {
  for (const wrapper of mountedPageWrappers.splice(0)) wrapper.unmount()
})

describe('Agent 中心思考阶段（5）', () => {
  it.each([
    [0, '理解科研问题'],
    [1, '检索知识与证据'],
    [2, '分析降解机制'],
    [3, '设计实验参数'],
    [4, '生成科研报告']
  ] as const)('阶段 %i 使用真实标签并以真实等待态初始化', (index, label) => {
    const { wrapper } = mountPage(AgentCenter)
    const stage = wrapper.get(`[data-stage="${index}"]`)
    expect(stage.text()).toContain(label)
    expect(stage.text()).toContain('等待中')
    expect(stage.attributes('data-status')).toBe('pending')
  })
})

describe('Agent 中心智能体矩阵（5）', () => {
  it.each([
    ['design', '规划智能体'],
    ['literature', '知识智能体'],
    ['experiment', '实验智能体'],
    ['analysis', '分析智能体'],
    ['manuscript', '写作智能体']
  ] as const)('%s 使用中文名称且空任务不伪造结果', (kind, label) => {
    const { wrapper } = mountPage(AgentCenter)
    const agent = wrapper.get(`[data-agent-kind="${kind}"]`)
    expect(agent.text()).toContain(label)
    expect(agent.text()).toContain('等待任务')
    expect(agent.text()).toContain('—')
  })
})

describe('AgentCard 四态展示隔离（4）', () => {
  it.each([
    ['running', '运行中', 'running'],
    ['completed', '已完成', 'check'],
    ['idle', '等待中', 'idle'],
    ['error', '异常', 'error']
  ] as const)('%s 不依赖 Store 即可呈现“%s”', (status, label, icon) => {
    const wrapper = mount(AgentCard, {
      props: { icon: 'agent', name: '验证智能体', status, task: '验证真实状态', duration: '—' }
    })
    expect(wrapper.text()).toContain(label)
    expect(wrapper.get('.agent-card__status').attributes('role')).toBe('status')
    expect(wrapper.get('.agent-card__status svg').classes()).toContain(`research-icon--${icon}`)
    expect(wrapper.text()).toContain('验证真实状态')
    expect(wrapper.text()).toContain('—')
  })
})

describe('Agent 中心真实状态与交互（9）', () => {
  it('无事件时五阶段均等待，且会话加载失败可独立重试', async () => {
    const { wrapper, agentStore, workflowStore } = mountPage(AgentCenter, agent => {
      vi.mocked(agent.loadSessions)
        .mockRejectedValueOnce(new Error('RAW_AGENT_LOAD_FAILURE'))
        .mockResolvedValueOnce(undefined)
    })
    await flushPromises()
    expect(wrapper.get('[data-testid="thinking-timeline"]').findAll('[data-stage]')).toHaveLength(5)
    expect(wrapper.findAll('[data-stage][data-status="pending"]')).toHaveLength(5)
    expect(wrapper.get('[data-testid="thinking-timeline"]').text()).not.toMatch(/\d+(?:\.\d+)?\s*(?:秒|分钟)/)
    expect(wrapper.get('[data-testid="agent-session-load-error"]').text()).toContain('科研会话加载失败，请重试')
    expect(workflowStore.errors).toEqual([])
    expect(wrapper.text()).not.toContain('RAW_AGENT_LOAD_FAILURE')
    const retry = wrapper.get('[data-testid="retry-session-load"]')
    agentStore.isLoading = true
    await wrapper.vm.$nextTick()
    expect(retry.attributes('disabled')).toBeDefined()
    await retry.trigger('click')
    await retry.trigger('click')
    await flushPromises()
    expect(agentStore.loadSessions).toHaveBeenCalledOnce()
    agentStore.isLoading = false
    await wrapper.vm.$nextTick()
    await retry.trigger('click')
    await flushPromises()
    expect(agentStore.loadSessions).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="agent-session-load-error"]').exists()).toBe(false)
  })

  it('把真实完成与错误事件映射到对应阶段并保留详情', () => {
    const retrievalError: AgentEvent = {
      type: 'retrieval',
      label: '知识检索异常',
      detail: '本地索引暂不可用',
      timestamp: TIMESTAMP + 1000,
      status: 'error'
    }
    const { wrapper } = mountPage(AgentCenter, agent => {
      agent.events = [completedPlannerEvent, retrievalError]
    })
    const completed = wrapper.get('[data-stage="0"]')
    const failed = wrapper.get('[data-stage="1"]')
    expect(completed.attributes('data-status')).toBe('completed')
    expect(completed.text()).toContain('已识别目标污染物与反应体系')
    expect(failed.attributes('data-status')).toBe('error')
    expect(failed.text()).toContain('本地索引暂不可用')
  })

  it('从工作流任务映射智能体任务、四态与据实耗时', () => {
    const { wrapper } = mountPage(AgentCenter, (_agent, workflow) => {
      workflow.tasks = [
        {
          id: 'plan-1', type: 'design', label: '拆解研究问题', status: 'completed',
          startedAt: TIMESTAMP, completedAt: TIMESTAMP + 2500, result: '形成研究计划'
        },
        { id: 'lit-1', type: 'literature', label: '检索知识库', status: 'pending' },
        { id: 'exp-1', type: 'experiment', label: '生成实验变量', status: 'running', startedAt: TIMESTAMP },
        { id: 'ana-1', type: 'analysis', label: '拟合动力学', status: 'failed', error: '数据列缺失' }
      ]
    })
    expect(wrapper.get('[data-agent-kind="design"]').text()).toContain('2.5 秒')
    expect(wrapper.get('[data-agent-kind="design"]').text()).toContain('形成研究计划')
    expect(wrapper.get('[data-agent-kind="literature"]').text()).toContain('—')
    expect(wrapper.get('[data-agent-kind="experiment"]').text()).toContain('运行中')
    expect(wrapper.get('[data-agent-kind="analysis"]').text()).toContain('数据列缺失')
  })

  it('最近工具调用同时展示真实输入占位、输出和执行结果', () => {
    const messages: AgentMessage[] = [{
      id: 'tool-message', role: 'assistant', content: '完成分析', timestamp: TIMESTAMP,
      toolCalls: [{ name: '动力学拟合', status: 'completed', result: 'R² = 0.943' }]
    }]
    const { wrapper } = mountPage(AgentCenter, agent => { agent.messages = messages })
    const tool = wrapper.get('[data-testid="tool-execution"]')
    expect(tool.text()).toContain('动力学拟合')
    expect(tool.text()).toContain('输入：—')
    expect(tool.text()).toContain('输出：R² = 0.943')
    expect(tool.text()).toContain('结果：已完成')
    expect(tool.text()).toContain('来源：—')
    expect(tool.text()).toContain('耗时：—')
  })

  it('研究设计只展示 Store 中的真实问题、假设、变量、机制与模型', () => {
    const { wrapper } = mountPage(AgentCenter, agent => { agent.designResult = designResult })
    const result = wrapper.get('[data-testid="design-result"]')
    for (const text of [
      '微纳米气泡如何改变臭氧传质效率？', '扩大气液界面', '更小气泡可提高体积传质系数',
      '气泡粒径', '80–300 nm', '自变量', '伪一级动力学'
    ]) expect(result.text()).toContain(text)
    expect(result.text()).not.toContain('independent')
  })

  it('点击提交按钮只以裁剪后的输入调用现有 runResearch', async () => {
    const { wrapper, agentStore, workflowStore } = mountPage(AgentCenter, (_agent, workflow) => {
      workflow.errors = ['上一次分析错误']
    })
    const clear = vi.spyOn(workflowStore, 'clearErrors')
    const run = vi.spyOn(agentStore, 'runResearch').mockResolvedValue(undefined)
    await wrapper.get('[data-testid="research-task-input"]').setValue('  分析 TC 降解动力学  ')
    await wrapper.get('[data-testid="run-research"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('form').attributes('aria-label')).toBe('科研任务输入')
    expect(run).toHaveBeenCalledOnce()
    expect(run).toHaveBeenCalledWith('分析 TC 降解动力学')
    expect(clear).toHaveBeenCalledOnce()
    expect(workflowStore.errors).toEqual([])
  })

  it('回车提交只调用一次现有 runResearch', async () => {
    const { wrapper, agentStore } = mountPage(AgentCenter)
    const run = vi.spyOn(agentStore, 'runResearch').mockResolvedValue(undefined)
    const input = wrapper.get('[data-testid="research-task-input"]')
    await input.setValue('设计正交实验')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(run).toHaveBeenCalledOnce()
    expect(run).toHaveBeenCalledWith('设计正交实验')
  })

  it('运行中输入与按钮禁用且不会重复提交', async () => {
    const { wrapper, agentStore } = mountPage(AgentCenter, agent => { agent.isLoading = true })
    const run = vi.spyOn(agentStore, 'runResearch').mockResolvedValue(undefined)
    const input = wrapper.get('[data-testid="research-task-input"]')
    const button = wrapper.get('[data-testid="run-research"]')
    expect(input.attributes('disabled')).toBeDefined()
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.attributes('aria-busy')).toBe('true')
    await button.trigger('click')
    expect(run).not.toHaveBeenCalled()
  })

  it('错误重试清除错误但保留完成事件、任务输入并重新运行', async () => {
    const { wrapper, agentStore, workflowStore } = mountPage(AgentCenter, (agent, workflow) => {
      agent.events = [completedPlannerEvent]
      workflow.errors = ['模型服务暂不可用']
    })
    const clear = vi.spyOn(workflowStore, 'clearErrors')
    const run = vi.spyOn(agentStore, 'runResearch').mockResolvedValue(undefined)
    const input = wrapper.get('[data-testid="research-task-input"]')
    await input.setValue('  保留的科研问题  ')
    expect(wrapper.get('[role="alert"]').text()).toContain('模型服务暂不可用')
    await wrapper.get('[data-testid="retry-research"]').trigger('click')
    await flushPromises()
    expect(clear).toHaveBeenCalledOnce()
    expect(workflowStore.errors).toEqual([])
    expect(agentStore.events).toEqual([completedPlannerEvent])
    expect((input.element as HTMLInputElement).value).toBe('  保留的科研问题  ')
    expect(run).toHaveBeenCalledWith('保留的科研问题')
  })
})

describe('科研助手真实三栏与交互（3）', () => {
  it('无选中会话保留三栏，初始会话加载失败显示可重试中文错误', async () => {
    const { wrapper } = mountPage(Assistant)
    await flushPromises()
    expect(wrapper.get('[data-testid="assistant-sessions"]').text()).toContain('研究会话')
    expect(wrapper.get('[data-testid="assistant-workbench"]').text()).toContain('暂无科研数据')
    expect(wrapper.get('[data-testid="assistant-evidence"]').text()).toContain('引用与证据')
    expect(wrapper.get('[data-testid="assistant-workbench"]').attributes('aria-label')).toBe('科研助手对话工作区')
    expect(wrapper.get('[data-testid="assistant-workbench"]').element.tagName).toBe('SECTION')

    const failed = mountPage(Assistant, agent => {
      vi.mocked(agent.loadSessions)
        .mockRejectedValueOnce(new Error('RAW_SESSION_LOAD_FAILURE'))
        .mockResolvedValueOnce(undefined)
    })
    await flushPromises()
    const state = failed.wrapper.get('[data-testid="assistant-session-state"]')
    expect(state.text()).toContain('研究会话加载失败，请重试')
    expect(failed.wrapper.text()).not.toContain('RAW_SESSION_LOAD_FAILURE')
    await state.get('.research-state__retry').trigger('click')
    await flushPromises()
    expect(failed.agentStore.loadSessions).toHaveBeenCalledTimes(2)
    expect(failed.wrapper.find('[data-testid="assistant-session-state"]').exists()).toBe(false)
  })

  it('会话切换期间隐藏旧数据并阻止竞态，失败后可重试当前会话', async () => {
    const session: ResearchSession = {
      id: 'session-real', name: '真实降解研究', createdAt: TIMESTAMP, status: 'active', messages: [], events: []
    }
    const message: AgentMessage = {
      id: 'message-real', role: 'assistant', content: '真实模型结论', timestamp: TIMESTAMP,
      toolCalls: [{ name: '真实文献检索', status: 'completed', result: '获得 3 条证据' }]
    }
    const citation: CitationItem = {
      id: 7, authors: '研究团队', title: '微纳米气泡传质研究', journal: '环境科学学报',
      year: 2026, tags: ['传质'], citedBy: 12, confidence: 0.89
    }
    const evidence: EvidenceItem = {
      label: '体积传质系数', value: '0.45 min⁻¹', source: '实验批次 A', confidence: 0.93
    }
    const { wrapper, agentStore } = mountPage(Assistant, agent => {
      agent.sessions = [session]
      agent.activeSessionId = session.id
      agent.messages = [message]
      agent.events = [completedPlannerEvent]
      agent.citations = [citation]
      agent.evidence = [evidence]
    })
    await flushPromises()
    for (const text of [
      '真实降解研究', '真实模型结论', '已识别目标污染物与反应体系', '真实文献检索',
      '获得 3 条证据', '微纳米气泡传质研究', '体积传质系数', '实验批次 A'
    ]) expect(wrapper.text()).toContain(text)

    let rejectSelection!: (reason?: unknown) => void
    let resolveRetry!: () => void
    const pendingSelection = new Promise<void>((_resolve, reject) => { rejectSelection = reject })
    const pendingRetry = new Promise<void>(resolve => { resolveRetry = resolve })
    const select = vi.spyOn(agentStore, 'selectSession')
      .mockImplementationOnce(() => pendingSelection)
      .mockImplementationOnce(() => pendingRetry)
    await wrapper.get('[data-session-id="session-real"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect(select).toHaveBeenCalledWith('session-real')
    expect(wrapper.get('[data-testid="assistant-session-state"]').text()).toContain('AI 正在分析...')
    expect(wrapper.get('[data-session-id="session-real"]').attributes('disabled')).toBeDefined()
    for (const text of ['真实模型结论', '真实文献检索', '获得 3 条证据', '微纳米气泡传质研究', '体积传质系数']) {
      expect(wrapper.text()).not.toContain(text)
    }
    await wrapper.get('[data-session-id="session-real"]').trigger('click')
    expect(select).toHaveBeenCalledOnce()

    rejectSelection(new Error('RAW_SESSION_SWITCH_FAILURE'))
    await flushPromises()
    const errorState = wrapper.get('[data-testid="assistant-session-state"]')
    expect(errorState.text()).toContain('研究会话加载失败，请重试')
    expect(wrapper.text()).not.toContain('RAW_SESSION_SWITCH_FAILURE')
    expect(wrapper.text()).not.toContain('真实模型结论')
    await errorState.get('.research-state__retry').trigger('click')
    await wrapper.vm.$nextTick()
    expect(select).toHaveBeenNthCalledWith(2, 'session-real')
    expect(wrapper.get('[data-testid="assistant-session-state"]').text()).toContain('AI 正在分析...')
    resolveRetry()
    await flushPromises()
    expect(wrapper.find('[data-testid="assistant-session-state"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('真实模型结论')
    expect(wrapper.get('.citation-card__num').text()).toContain('7')
  })

  it('点击与回车发送，失败保留输入并以同一 action 重试，发送中保持禁用', async () => {
    const { wrapper, agentStore } = mountPage(Assistant, agent => { agent.activeSessionId = 'session-active' })
    await flushPromises()
    const send = vi.spyOn(agentStore, 'sendMessage')
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error('ECONNRESET'))
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error('RAW_SERVICE_FAILURE'))
    const input = wrapper.get('[data-testid="assistant-input"]')
    await input.setValue('  点击发送的问题  ')
    await wrapper.get('[data-testid="assistant-send"]').trigger('click')
    await flushPromises()
    expect(send).toHaveBeenNthCalledWith(1, '点击发送的问题')
    await input.setValue('  回车发送的问题  ')
    await input.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(send).toHaveBeenNthCalledWith(2, '回车发送的问题')

    await input.setValue('  失败后必须保留的问题  ')
    await wrapper.get('[data-testid="assistant-send"]').trigger('click')
    await flushPromises()
    const errorState = wrapper.get('[data-testid="assistant-send-error"]')
    expect(errorState.text()).toContain('分析失败，请重试')
    expect(wrapper.text()).not.toContain('ECONNRESET')
    expect((input.element as HTMLInputElement).value).toBe('  失败后必须保留的问题  ')
    await errorState.get('.research-state__retry').trigger('click')
    await flushPromises()
    expect(send).toHaveBeenNthCalledWith(4, '失败后必须保留的问题')
    expect(wrapper.find('[data-testid="assistant-send-error"]').exists()).toBe(false)
    expect((input.element as HTMLInputElement).value).toBe('')

    await input.setValue('再次失败的问题')
    await wrapper.get('[data-testid="assistant-send"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="assistant-send-error"]').text()).toContain('分析失败，请重试')
    expect(wrapper.text()).not.toContain('RAW_SERVICE_FAILURE')
    await input.setValue('改写后的新问题')
    expect(wrapper.find('[data-testid="assistant-send-error"]').exists()).toBe(false)

    agentStore.isSending = true
    await wrapper.vm.$nextTick()
    expect(wrapper.get('[data-testid="assistant-send"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="assistant-input"]').attributes('disabled')).toBeDefined()
    const live = wrapper.get('[data-testid="assistant-analyzing"]')
    expect(live.text()).toBe('AI 正在分析...')
    expect(live.attributes()).toMatchObject({ role: 'status', 'aria-live': 'polite' })
  })
})

async function mountLiteratureReady() {
  const mounted = mountPage(Literature)
  const store = useKnowledgeStore()
  await flushPromises()
  return { ...mounted, store }
}

async function selectFirstLiterature(wrapper: VueWrapper) {
  await wrapper.get('[data-document-id="d1"] .citation-card__select').trigger('click')
  await wrapper.vm.$nextTick()
}

describe('文献证据工作区（22）', () => {
  it('以文件夹、稳定详情和论文证据列表组成真实三栏', async () => {
    const { wrapper } = await mountLiteratureReady()
    expect(wrapper.get('[data-testid="literature-library"]').attributes('aria-label')).toBe('文献文件夹与搜索')
    expect(wrapper.get('[data-testid="literature-detail"]').attributes('aria-label')).toBe('选中文献详情')
    expect(wrapper.get('[data-testid="literature-evidence"]').attributes('aria-label')).toBe('论文证据与 AI 摘要')
    expect(wrapper.text()).toContain('文献证据工作区')
  })

  it('选择论文后在稳定详情区展示真实题名', async () => {
    const { wrapper } = await mountLiteratureReady()
    await selectFirstLiterature(wrapper)
    expect(wrapper.get('[data-testid="literature-detail"]').text()).toContain(literatureDocuments[0].title)
  })

  it('详情展示真实作者而不创建匿名占位', async () => {
    const { wrapper } = await mountLiteratureReady()
    await selectFirstLiterature(wrapper)
    expect(wrapper.get('[data-testid="literature-detail"]').text()).toContain('李小红、张伟')
  })

  it('详情展示真实发表年份', async () => {
    const { wrapper } = await mountLiteratureReady()
    await selectFirstLiterature(wrapper)
    expect(wrapper.get('[data-testid="literature-detail"]').text()).toContain('2024')
  })

  it('论文卡按真实相关度降序排列并格式化同一字段', async () => {
    installResearchAdapters({ documents: [literatureDocuments[1], literatureDocuments[0]] })
    const { wrapper } = await mountLiteratureReady()
    const cards = wrapper.findAll('[data-document-id]')
    expect(cards.map(card => card.attributes('data-document-id'))).toEqual(['d1', 'd2'])
    expect(cards[0].text()).toContain('相关度 94%')
    expect(cards[1].text()).toContain('相关度 81%')
  })

  it('证据等级严格由三项 PaperAssessment 得分平均后换算', async () => {
    const { wrapper } = await mountLiteratureReady()
    expect(wrapper.get('[data-document-id="d1"]').text()).toContain('证据等级 4/5')
  })

  it('接口没有页码时引用位置只显示待提取', async () => {
    const { wrapper } = await mountLiteratureReady()
    const card = wrapper.get('[data-document-id="d1"]')
    expect(card.text()).toContain('引用位置 原文定位待提取')
    expect(card.text()).not.toMatch(/第\s*\d+\s*页|图\s*\d+/)
  })

  it('搜索输入通过现有 setSearch 过滤论文卡', async () => {
    const { wrapper, store } = await mountLiteratureReady()
    const setSearch = vi.spyOn(store, 'setSearch')
    const input = wrapper.get('[data-testid="literature-search"]')
    await input.setValue('传质')
    expect(setSearch).toHaveBeenCalledWith('传质')
    expect(wrapper.find('[data-document-id="d1"]').exists()).toBe(false)
    expect(wrapper.get('[data-document-id="d2"]').text()).toContain('纳米气泡传质机制综述')
  })

  it('点击论文卡调用现有 selectDocument action', async () => {
    const { wrapper, store } = await mountLiteratureReady()
    const select = vi.spyOn(store, 'selectDocument')
    await wrapper.get('[data-document-id="d1"] .citation-card__select').trigger('click')
    expect(select).toHaveBeenCalledOnce()
    expect(select).toHaveBeenCalledWith('d1')
  })

  it('外层 Enter 只选择论文，内层定位按钮 Enter/Space 只打开定位', async () => {
    const wrapper = mount(CitationCard, {
      props: {
        index: 1,
        documentId: 'd1',
        authors: '李小红、张伟',
        title: '真实论文',
        journal: '环境科学学报',
        year: 2024,
        location: '原文定位待提取',
        selectable: true
      }
    })
    const listItem = wrapper.get('.citation-card')
    const select = wrapper.get('.citation-card__select')
    const location = wrapper.get('[data-testid="citation-location-d1"]')
    expect(select.element.parentElement).toBe(listItem.element)
    expect(location.element.parentElement).toBe(listItem.element)

    await select.trigger('click')
    await select.trigger('keydown', { key: 'Enter' })
    await select.trigger('keydown', { key: ' ' })
    expect(wrapper.emitted('select')).toEqual([['d1'], ['d1'], ['d1']])

    await location.trigger('click')
    await location.trigger('keydown', { key: 'Enter' })
    await location.trigger('keydown', { key: ' ' })
    expect(wrapper.emitted('openLocation')).toEqual([['d1'], ['d1'], ['d1']])
    expect(wrapper.emitted('select')).toEqual([['d1'], ['d1'], ['d1']])

    const displayOnly = mount(CitationCard, {
      props: { index: 2, authors: '作者', title: '展示论文', journal: '期刊', year: 2023 }
    })
    expect(displayOnly.get('.citation-card__select').element.tagName).toBe('DIV')
    expect(displayOnly.find('button').exists()).toBe(false)
    await displayOnly.get('.citation-card__select').trigger('click')
    expect(displayOnly.emitted('select')).toBeUndefined()
  })

  it('论文卡按空格调用同一 selectDocument action', async () => {
    const { wrapper, store } = await mountLiteratureReady()
    const select = vi.spyOn(store, 'selectDocument')
    await wrapper.get('[data-document-id="d1"] .citation-card__select').trigger('keydown', { key: ' ' })
    expect(select).toHaveBeenCalledWith('d1')
  })

  it('摘要请求按文献隔离，交错完成不会清除或覆盖当前文献状态', async () => {
    let resolveD1!: (summary: string) => void
    let resolveD2!: (summary: string) => void
    vi.mocked(literatureAdapter.summarizePaper).mockImplementation(documentId => new Promise(resolve => {
      if (documentId === 'd1') resolveD1 = resolve
      if (documentId === 'd2') resolveD2 = resolve
    }))
    const { wrapper } = await mountLiteratureReady()

    await selectFirstLiterature(wrapper)
    await wrapper.get('[data-testid="summarize-paper"]').trigger('click')
    await wrapper.get('[data-document-id="d2"] .citation-card__select').trigger('click')
    await wrapper.get('[data-testid="summarize-paper"]').trigger('click')
    expect(literatureAdapter.summarizePaper).toHaveBeenNthCalledWith(1, 'd1')
    expect(literatureAdapter.summarizePaper).toHaveBeenNthCalledWith(2, 'd2')

    resolveD1('d1 专属摘要')
    await flushPromises()
    expect(wrapper.text()).not.toContain('d1 专属摘要')
    expect(wrapper.get('[data-testid="summarize-paper"]').attributes('aria-busy')).toBe('true')

    resolveD2('d2 专属摘要')
    await flushPromises()
    expect(wrapper.get('[data-testid="literature-summary"]').text()).toContain('d2 专属摘要')
    await wrapper.get('[data-document-id="d1"] .citation-card__select').trigger('click')
    expect(wrapper.get('[data-testid="literature-summary"]').text()).toContain('d1 专属摘要')
  })

  it('摘要生成中显示标准分析态并禁用重复调用', async () => {
    let resolveSummary!: (summary: string) => void
    vi.mocked(literatureAdapter.summarizePaper).mockImplementation(() => new Promise(resolve => { resolveSummary = resolve }))
    const { wrapper } = await mountLiteratureReady()
    await selectFirstLiterature(wrapper)
    const button = wrapper.get('[data-testid="summarize-paper"]')
    await button.trigger('click')
    await wrapper.vm.$nextTick()
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.attributes('aria-busy')).toBe('true')
    expect(wrapper.text()).toContain('AI 正在分析...')
    await button.trigger('click')
    expect(literatureAdapter.summarizePaper).toHaveBeenCalledOnce()
    resolveSummary('已完成摘要')
    await flushPromises()
  })

  it('摘要失败显示标准中文错误、隐藏原始异常并可重试', async () => {
    vi.mocked(literatureAdapter.summarizePaper)
      .mockRejectedValueOnce(new Error('RAW_LITERATURE_SUMMARY_FAILURE'))
      .mockResolvedValueOnce('重试后的真实摘要')
    const { wrapper } = await mountLiteratureReady()
    await selectFirstLiterature(wrapper)
    await wrapper.get('[data-testid="summarize-paper"]').trigger('click')
    await flushPromises()
    const error = wrapper.get('[data-testid="literature-summary-state"]')
    expect(error.text()).toContain('分析失败，请重试')
    expect(wrapper.text()).not.toContain('RAW_LITERATURE_SUMMARY_FAILURE')
    await error.get('.research-state__retry').trigger('click')
    await flushPromises()
    expect(literatureAdapter.summarizePaper).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('重试后的真实摘要')
  })

  it('文献加载期间呈现三条论文专用骨架与可读状态', async () => {
    vi.mocked(knowledgeAdapter.getDocuments).mockImplementation(() => new Promise(() => undefined))
    const { wrapper } = mountPage(Literature)
    await wrapper.vm.$nextTick()
    const skeleton = wrapper.get('[data-testid="literature-loading-skeleton"]')
    expect(skeleton.attributes()).toMatchObject({ role: 'status', 'aria-busy': 'true' })
    expect(skeleton.findAll('.literature__skeleton-paper')).toHaveLength(3)
    expect(skeleton.get('.literature__visually-hidden').text()).toContain('AI 正在分析文献')
  })

  it('文献库为空时呈现标准空状态和下一步说明', async () => {
    installResearchAdapters({ documents: [] })
    const { wrapper } = await mountLiteratureReady()
    const state = wrapper.get('[data-testid="literature-page-state"]')
    expect(state.text()).toContain('暂无科研数据')
    expect(state.text()).toContain('导入或检索文献')
  })

  it('初始加载失败隐藏原始异常并通过同一 load action 重试', async () => {
    vi.mocked(knowledgeAdapter.getDocuments)
      .mockRejectedValueOnce(new Error('RAW_LITERATURE_LOAD_FAILURE'))
      .mockResolvedValueOnce(literatureDocuments)
    const { wrapper } = mountPage(Literature)
    const store = useKnowledgeStore()
    const load = vi.spyOn(store, 'loadDocuments')
    await flushPromises()
    const state = wrapper.get('[data-testid="literature-page-state"]')
    expect(state.text()).toContain('分析失败，请重试')
    expect(wrapper.text()).not.toContain('RAW_LITERATURE_LOAD_FAILURE')
    await state.get('.research-state__retry').trigger('click')
    await flushPromises()
    expect(load).toHaveBeenCalledOnce()
    expect(knowledgeAdapter.getDocuments).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="literature-page-state"]').exists()).toBe(false)
  })

  it('引用弹层隔离背景、首焦点并双向循环焦点', async () => {
    const { wrapper } = await mountLiteratureReady()
    await wrapper.get('[data-testid="citation-location-d1"]').trigger('click')
    const dialog = wrapper.get('[data-testid="citation-dialog"]')
    const content = wrapper.get('[data-testid="literature-content"]')
    expect(dialog.attributes()).toMatchObject({ role: 'dialog', 'aria-modal': 'true', 'aria-label': '引用位置' })
    expect(dialog.text()).toContain('原文定位待提取')
    expect(dialog.element.parentElement).toBe(content.element.parentElement)
    expect(content.attributes('inert')).toBeDefined()
    expect(content.attributes('aria-hidden')).toBe('true')

    const first = dialog.get('[data-testid="close-citation-dialog"]')
    const last = dialog.get('[data-testid="confirm-citation-dialog"]')
    expect(document.activeElement).toBe(first.element)
    ;(last.element as HTMLButtonElement).focus()
    await dialog.trigger('keydown', { key: 'Tab' })
    expect(document.activeElement).toBe(first.element)
    ;(first.element as HTMLButtonElement).focus()
    await dialog.trigger('keydown', { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(last.element)
  })

  it('引用弹层可由 document 或弹层 Escape 关闭并恢复触发按钮焦点', async () => {
    const { wrapper } = await mountLiteratureReady()
    const trigger = wrapper.get('[data-testid="citation-location-d1"]')
    ;(trigger.element as HTMLButtonElement).focus()
    await trigger.trigger('click')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }))
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="citation-dialog"]').exists()).toBe(false)
    expect(document.activeElement).toBe(trigger.element)

    await trigger.trigger('click')
    await wrapper.get('[data-testid="citation-dialog"]').trigger('keydown', { key: 'Escape' })
    await wrapper.vm.$nextTick()
    expect(wrapper.find('[data-testid="citation-dialog"]').exists()).toBe(false)
    expect(document.activeElement).toBe(trigger.element)
  })

  it('论文列表与卡片使用 list/listitem 语义且选择按钮可聚焦展开', async () => {
    const { wrapper } = await mountLiteratureReady()
    const list = wrapper.get('[data-testid="literature-document-list"]')
    expect(list.attributes()).toMatchObject({ role: 'list', 'aria-label': '按相关度排序的论文证据列表' })
    const card = wrapper.get('[data-document-id="d1"]')
    expect(card.attributes('role')).toBe('listitem')
    expect(card.attributes('aria-label')).toContain(literatureDocuments[0].title)
    const select = card.get('.citation-card__select')
    expect(select.element.tagName).toBe('BUTTON')
    expect(select.attributes('aria-pressed')).toBe('false')
    const secondary = card.get('.citation-card__secondary')
    expect(secondary.text()).toContain('李小红、张伟')
    expect(card.get('[data-testid="citation-location-d1"]').text()).toContain('原文定位待提取')
    const source = readFileSync(resolve(process.cwd(), 'src/renderer/src/components/research/CitationCard.vue'), 'utf8')
    expect(source).toMatch(/\.citation-card:hover\s+\.citation-card__secondary\s*\{/)
    expect(source).toMatch(/\.citation-card:focus-within\s+\.citation-card__secondary\s*\{/)
    await select.trigger('click')
    expect(select.attributes('aria-pressed')).toBe('true')
  })

  it('文件夹展示真实名称与数量', async () => {
    const { wrapper } = await mountLiteratureReady()
    const folder = wrapper.get('[data-folder-id="folder-1"]')
    expect(folder.text()).toContain('四环素降解')
    expect(folder.text()).toContain('2')
  })

  it('详情评分读取 reliabilityScore、evidenceScore 与 methodologyScore', async () => {
    const { wrapper } = await mountLiteratureReady()
    await selectFirstLiterature(wrapper)
    const scores = wrapper.get('[data-testid="paper-assessment"]')
    expect(scores.text()).toContain('可靠性 82%')
    expect(scores.text()).toContain('证据 78%')
    expect(scores.text()).toContain('方法论 65%')
  })

})

async function mountExperimentReady() {
  const mounted = mountPage(Experiment)
  const store = useExperimentStore()
  await flushPromises()
  return { ...mounted, store }
}

describe('实验设计工作区（22）', () => {
  it.each(['研究假设', '实验变量', 'AI 实验建议'])('实验三栏显示“%s”且具有可读区域标签', async label => {
    const { wrapper } = await mountExperimentReady()
    const region = wrapper.get(`[aria-label="${label}"]`)
    expect(region.text()).toContain(label)
    expect(region.element.tagName).toMatch(/ASIDE|SECTION/)
  })

  it('展示真实研究问题而不生成示例问题', async () => {
    const { wrapper } = await mountExperimentReady()
    expect(wrapper.get('[data-testid="experiment-question"]').text()).toContain(experimentDesign.question)
  })

  it('展示 Store 中已有的真实研究假设与置信度', async () => {
    const { wrapper } = await mountExperimentReady()
    const hypothesis = wrapper.get('[data-testid="design-hypothesis-0"]')
    expect(hypothesis.text()).toContain('减小气泡粒径可提高气液传质效率')
    expect(hypothesis.text()).toContain('置信度 82%')
  })

  it('变量区展示真实名称、范围和单位', async () => {
    const { wrapper } = await mountExperimentReady()
    const variable = wrapper.get('[data-variable-index="0"]')
    expect(variable.text()).toContain('气泡粒径')
    expect((variable.get('input').element as HTMLInputElement).value).toBe('80–300')
    expect(variable.text()).toContain('nm')
  })

  it('变量输入具有包含名称与单位的中文可读标签', async () => {
    const { wrapper } = await mountExperimentReady()
    expect(wrapper.get('[data-variable-index="0"] input').attributes('aria-label')).toBe('气泡粒径范围（nm）')
    expect(wrapper.get('[data-variable-index="1"] input').attributes('aria-label')).toBe('四环素去除率范围（%）')
  })

  it('实验分组展示真实条件与目的', async () => {
    const { wrapper } = await mountExperimentReady()
    const group = wrapper.get('[data-group-index="1"]')
    expect(group.text()).toContain('实验组')
    expect(group.text()).toContain('微纳米气泡曝气')
    expect(group.text()).toContain('检验传质增益')
  })

  it('评价指标作为真实实验结果指标展示', async () => {
    const { wrapper } = await mountExperimentReady()
    const outcomes = wrapper.get('[data-testid="experiment-outcomes"]')
    expect(outcomes.text()).toContain('去除率')
    expect(outcomes.text()).toContain('动力学常数')
  })

  it('AI 建议区展示真实推荐模型与置信度', async () => {
    const { wrapper } = await mountExperimentReady()
    const advice = wrapper.get('[aria-label="AI 实验建议"]')
    expect(advice.text()).toContain('伪一级动力学')
    expect(advice.text()).toContain('88%')
  })

  it('点击生成通过既有 generateHypotheses 传入真实问题', async () => {
    const { wrapper } = await mountExperimentReady()
    await wrapper.get('[data-testid="generate-hypotheses"]').trigger('click')
    await flushPromises()
    expect(experimentAdapter.generateHypotheses).toHaveBeenCalledOnce()
    expect(experimentAdapter.generateHypotheses).toHaveBeenCalledWith(experimentDesign.question)
  })

  it('AI 生成结果以建议卡展示真实语句与置信度', async () => {
    const { wrapper } = await mountExperimentReady()
    await wrapper.get('[data-testid="generate-hypotheses"]').trigger('click')
    await flushPromises()
    const suggestion = wrapper.get('[data-testid="ai-suggestion-0"]')
    expect(suggestion.text()).toContain('提高气液界面积可增强臭氧利用率')
    expect(suggestion.text()).toContain('置信度 76%')
  })

  it('AI 生成期间按钮禁用、标记 busy 且防止重复调用', async () => {
    let resolveGeneration!: (value: Array<{ statement: string; confidence: number }>) => void
    vi.mocked(experimentAdapter.generateHypotheses).mockImplementation(() => new Promise(resolve => { resolveGeneration = resolve }))
    const { wrapper } = await mountExperimentReady()
    const button = wrapper.get('[data-testid="generate-hypotheses"]')
    await button.trigger('click')
    await wrapper.vm.$nextTick()
    expect(button.attributes('disabled')).toBeDefined()
    expect(button.attributes('aria-busy')).toBe('true')
    expect(button.text()).toContain('AI 正在分析...')
    await button.trigger('click')
    expect(experimentAdapter.generateHypotheses).toHaveBeenCalledOnce()
    resolveGeneration([])
    await flushPromises()
    const empty = wrapper.get('[data-testid="ai-suggestion-empty"]')
    expect(empty.text()).toContain('暂无 AI 实验建议')
    expect(empty.text()).toContain('本次未生成可用建议')
    expect(empty.text()).not.toContain('建议只在用户主动生成后显示')
  })

  it('编辑只在确认时写 Service，保存期间禁用全部草稿输入并固定提交快照', async () => {
    let resolveSave!: () => void
    vi.mocked(experimentAdapter.updateDesign).mockImplementation(() => new Promise(resolve => { resolveSave = resolve }))
    const { wrapper } = await mountExperimentReady()
    const input = wrapper.get('[data-variable-index="0"] input')
    await input.setValue('60–240')
    expect(experimentAdapter.updateDesign).not.toHaveBeenCalled()
    await wrapper.get('[data-testid="save-experiment"]').trigger('click')
    await wrapper.vm.$nextTick()
    expect(experimentAdapter.updateDesign).toHaveBeenCalledOnce()
    expect(experimentAdapter.updateDesign).toHaveBeenCalledWith(expect.objectContaining({
      variables: expect.arrayContaining([expect.objectContaining({ name: '气泡粒径', range: '60–240', unit: 'nm' })])
    }))
    expect(wrapper.findAll('.experiment__variable input').every(field => field.attributes('disabled') !== undefined)).toBe(true)
    expect(wrapper.get('[data-testid="save-experiment"]').attributes('disabled')).toBeDefined()
    expect((input.element as HTMLInputElement).value).toBe('60–240')
    resolveSave()
    await flushPromises()
    expect(wrapper.get('[data-testid="experiment-save-status"]').text()).toContain('实验设计已保存')
  })

  it('保存成功显示静止的中文已保存反馈', async () => {
    const { wrapper } = await mountExperimentReady()
    await wrapper.get('[data-testid="save-experiment"]').trigger('click')
    await flushPromises()
    const status = wrapper.get('[data-testid="experiment-save-status"]')
    expect(status.text()).toContain('实验设计已保存')
    expect(status.attributes()).toMatchObject({ role: 'status', 'aria-live': 'polite' })
  })

  it('保存失败显示标准错误、隐藏原始异常并可重试', async () => {
    vi.mocked(experimentAdapter.updateDesign)
      .mockRejectedValueOnce(new Error('RAW_EXPERIMENT_SAVE_FAILURE'))
      .mockResolvedValueOnce(undefined)
    const { wrapper } = await mountExperimentReady()
    await wrapper.get('[data-testid="save-experiment"]').trigger('click')
    await flushPromises()
    const error = wrapper.get('[data-testid="experiment-save-error"]')
    expect(error.text()).toContain('分析失败，请重试')
    expect(wrapper.text()).not.toContain('RAW_EXPERIMENT_SAVE_FAILURE')
    await error.get('.research-state__retry').trigger('click')
    await flushPromises()
    expect(experimentAdapter.updateDesign).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('实验设计已保存')
  })

  it('运行态同时使用文字与状态属性表达', async () => {
    installResearchAdapters({ design: { ...experimentDesign, status: 'running' } })
    const { wrapper } = await mountExperimentReady()
    const status = wrapper.get('[data-testid="experiment-status"]')
    expect(status.text()).toContain('运行中')
    expect(status.attributes('data-status')).toBe('running')
  })

  it('运行中的实验禁用变量输入和保存按钮', async () => {
    installResearchAdapters({ design: { ...experimentDesign, status: 'running' } })
    const { wrapper } = await mountExperimentReady()
    expect(wrapper.get('[data-variable-index="0"] input').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="save-experiment"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-testid="generate-hypotheses"]').attributes('disabled')).toBeUndefined()
    await wrapper.get('[data-testid="save-experiment"]').trigger('click')
    expect(experimentAdapter.updateDesign).not.toHaveBeenCalled()
  })

  it('实验设计加载期间显示标准中文加载态', async () => {
    vi.mocked(experimentAdapter.getDesign).mockImplementation(() => new Promise(() => undefined))
    const { wrapper } = mountPage(Experiment)
    await wrapper.vm.$nextTick()
    expect(wrapper.get('[data-testid="experiment-page-state"]').text()).toContain('AI 正在分析...')
  })

  it('服务返回空设计时显示标准空状态', async () => {
    installResearchAdapters({ design: null })
    const { wrapper } = await mountExperimentReady()
    expect(wrapper.get('[data-testid="experiment-page-state"]').text()).toContain('暂无科研数据')
  })

  it('实验加载失败隐藏原始异常并通过同一 loadDesign 重试', async () => {
    vi.mocked(experimentAdapter.getDesign)
      .mockRejectedValueOnce(new Error('RAW_EXPERIMENT_LOAD_FAILURE'))
      .mockResolvedValueOnce(experimentDesign)
    const { wrapper } = mountPage(Experiment)
    const store = useExperimentStore()
    const load = vi.spyOn(store, 'loadDesign')
    await flushPromises()
    const state = wrapper.get('[data-testid="experiment-page-state"]')
    expect(state.text()).toContain('分析失败，请重试')
    expect(wrapper.text()).not.toContain('RAW_EXPERIMENT_LOAD_FAILURE')
    await state.get('.research-state__retry').trigger('click')
    await flushPromises()
    expect(load).toHaveBeenCalledOnce()
    expect(experimentAdapter.getDesign).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="experiment-page-state"]').exists()).toBe(false)
  })

  it('1440 工作站三栏具备可收缩网格、列溢出控制和响应式合约', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1440 })
    window.dispatchEvent(new Event('resize'))
    const experiment = await mountExperimentReady()
    const literature = await mountLiteratureReady()
    expect(experiment.wrapper.get('[data-testid="experiment-workspace"]').element.children).toHaveLength(3)
    expect(literature.wrapper.get('.literature__workspace').element.children).toHaveLength(3)
    for (const label of ['研究假设', '实验变量', 'AI 实验建议']) {
      const region = experiment.wrapper.get(`[aria-label="${label}"]`)
      expect(region.attributes('style') ?? '').not.toMatch(/width\s*:/)
    }
    for (const file of ['Experiment.vue', 'Literature.vue']) {
      const source = readFileSync(resolve(process.cwd(), `src/renderer/src/pages/research/${file}`), 'utf8')
      const className = file === 'Experiment.vue' ? 'experiment__workspace' : 'literature__workspace'
      const baseGrid = source.match(new RegExp(`\\.${className}\\s*\\{[^}]*grid-template-columns:\\s*([^;]+);`, 's'))
      expect(baseGrid?.[1].match(/minmax\(0,/g)).toHaveLength(3)
      expect(source).toContain('@media (max-width: 1480px)')
      expect(source).toContain('@media (min-width: 1720px)')
      expect(source).toMatch(/min-width:\s*0;/)
      expect(source).toMatch(/overflow:\s*(?:hidden|auto);/)
      expect(source).not.toContain('color: var(--research-text-muted)')
    }
  })
})

async function mountDataAnalysisReady() {
  const mounted = mountPage(DataAnalysis)
  const store = useDatasetStore()
  await flushPromises()
  return { ...mounted, store }
}

describe('数据分析工作区（18）', () => {
  it('使用中文标题构成只读科研工作区', async () => {
    const { wrapper } = await mountDataAnalysisReady()
    const workspace = wrapper.get('[data-testid="data-analysis-workspace"]')
    expect(wrapper.text()).toContain('数据分析工作区')
    expect(workspace.find('input').exists()).toBe(false)
  })

  it.each([
    ['数据完整度', '96%'],
    ['缺失值', '3'],
    ['离群值', '3'],
    ['质量警告', '2']
  ])('质量指标“%s”读取真实报告值 %s', async (label, value) => {
    const { wrapper } = await mountDataAnalysisReady()
    const quality = wrapper.get('[data-testid="analysis-quality"]')
    expect(quality.text()).toContain(label)
    expect(quality.text()).toContain(value)
    if (label === '质量警告') {
      expect(wrapper.get('.quality-warning').text()).toContain('pH 存在两个缺失值')
      const source = readFileSync(resolve(process.cwd(), 'src/renderer/src/pages/research/DataAnalysis.vue'), 'utf8')
      expect(source).toMatch(/\.quality-warning\s*\{[^}]*color:\s*var\(--research-text-primary\)/s)
    }
  })

  it.each(analysisReport.statistics)('统计量“$metric”展示真实数值与解释', async statistic => {
    const { wrapper } = await mountDataAnalysisReady()
    const row = wrapper.get(`[data-statistic="${statistic.metric}"]`)
    expect(row.text()).toContain(String(statistic.value))
    expect(row.text()).toContain(statistic.interpretation)
  })

  it.each(analysisImportance)('变量“$variable”消费 Store 重要性、贡献和置信度', async importance => {
    const { wrapper } = await mountDataAnalysisReady()
    const row = wrapper.get(`[data-importance="${importance.variable}"]`)
    expect(row.text()).toContain(importance.importance.toFixed(2))
    expect(row.text()).toContain(importance.contribution)
    expect(row.text()).toContain(`${Math.round(importance.confidence * 100)}%`)
  })

  it.each([
    ['first-order', '一级动力学', '0.989'],
    ['zero-order', '零级动力学', '0.892']
  ])('模型 %s 使用中文名并标记拟合可信度 %s', async (model, label, score) => {
    const { wrapper } = await mountDataAnalysisReady()
    const card = wrapper.get(`[data-model="${model}"]`)
    expect(card.text()).toContain(label)
    expect(card.text()).toContain('拟合可信度')
    expect(card.text()).toContain(score)
    expect(card.text()).toContain('残差范围')
    if (model === 'zero-order') {
      expect(card.text()).toContain('残差范围待评估')
      expect(card.text()).not.toMatch(/±-?0\.0850/)
      for (const invalidModel of ['r2-negative', 'r2-overflow', 'r2-nan', 'r2-infinite']) {
        const invalidCard = wrapper.get(`[data-model="${invalidModel}"]`)
        expect(invalidCard.text()).toContain('拟合可信度 R²待评估')
        expect(invalidCard.text()).not.toMatch(/NaN|Infinity/)
      }
    }
  })

  it('图表与科学解读逐项呈现 Store 的真实结果', async () => {
    const { wrapper } = await mountDataAnalysisReady()
    const figures = wrapper.get('[data-testid="analysis-figures"]')
    expect(figures.text()).toContain('臭氧浓度时间曲线')
    expect(figures.text()).toContain('一级动力学拟合图')
    expect(figures.findAll('[data-testid="scientific-chart"]')).toHaveLength(1)
    const conclusion = wrapper.get('[data-conclusion="0"]')
    expect(conclusion.text()).toContain('降解过程符合一级动力学特征')
    expect(conclusion.text()).toContain('拟合结果支持浓度依赖机制')
    expect(conclusion.text()).toContain('90%')
    for (const index of [1, 2, 3, 4]) {
      expect(wrapper.get(`[data-conclusion="${index}"]`).text()).toContain('待评估')
    }
  })

  it('报告加载期间显示统一中文 ResearchState', async () => {
    vi.mocked(dataAnalysisAdapter.getAnalysisReport).mockImplementation(() => new Promise(() => undefined))
    const { wrapper } = mountPage(DataAnalysis)
    await wrapper.vm.$nextTick()
    expect(wrapper.get('[data-testid="data-analysis-state"]').text()).toContain('AI 正在分析...')
  })

  it('服务返回空报告时显示统一空态与下一步指引', async () => {
    installResearchAdapters({ report: null, importance: [] })
    const { wrapper } = await mountDataAnalysisReady()
    const state = wrapper.get('[data-testid="data-analysis-state"]')
    expect(state.text()).toContain('暂无科研数据')
    expect(state.text()).toContain('导入实验数据')
  })

  it('加载失败隐藏原始异常并通过同一 loadReport 重试', async () => {
    vi.mocked(dataAnalysisAdapter.getAnalysisReport)
      .mockRejectedValueOnce(new Error('RAW_ANALYSIS_LOAD_FAILURE'))
      .mockResolvedValueOnce(analysisReport)
    const { wrapper } = mountPage(DataAnalysis)
    const store = useDatasetStore()
    const load = vi.spyOn(store, 'loadReport')
    await flushPromises()
    const state = wrapper.get('[data-testid="data-analysis-state"]')
    expect(state.text()).toContain('分析失败，请重试')
    expect(wrapper.text()).not.toContain('RAW_ANALYSIS_LOAD_FAILURE')
    await state.get('.research-state__retry').trigger('click')
    await flushPromises()
    expect(load).toHaveBeenCalledOnce()
    expect(dataAnalysisAdapter.getAnalysisReport).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="data-analysis-state"]').exists()).toBe(false)
  })

  it('跨卸载双触发复用单轮加载，失败隐藏旧重要性且双重重试不混合结果', async () => {
    const deferred = <T>() => {
      let resolve!: (value: T) => void
      let reject!: (reason: unknown) => void
      const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej })
      return { promise, resolve, reject }
    }
    const firstReport = deferred<AnalysisReport>()
    const firstImportance = deferred<VariableImportance[]>()
    const retryReport = deferred<AnalysisReport>()
    const retryImportance = deferred<VariableImportance[]>()
    const reportAfterFirst = {
      ...analysisReport,
      conclusions: [{ observation: '第一轮新报告', interpretation: '等待重要性', confidence: 0.8 }]
    }
    const reportAfterRetry = {
      ...analysisReport,
      conclusions: [{ observation: '重试后的报告', interpretation: '完整成功', confidence: 0.88 }]
    }
    const oldImportance = [{ variable: '旧变量不得显示', importance: 0.9, contribution: '旧结果', confidence: 0.9 }]
    const newImportance = [{ variable: '重试新变量', importance: 0.6, contribution: '新结果', confidence: 0.86 }]
    vi.mocked(dataAnalysisAdapter.getAnalysisReport)
      .mockImplementationOnce(() => firstReport.promise)
      .mockImplementationOnce(() => retryReport.promise)
    vi.mocked(dataAnalysisAdapter.getVariableImportance)
      .mockImplementationOnce(() => firstImportance.promise)
      .mockImplementationOnce(() => retryImportance.promise)

    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useDatasetStore()
    store.report = analysisReport
    store.importance = oldImportance
    const load = vi.spyOn(store, 'loadReport')

    const firstWrapper = mount(DataAnalysis, { attachTo: document.body, global: { plugins: [pinia] } })
    firstWrapper.unmount()
    const wrapper = mount(DataAnalysis, { attachTo: document.body, global: { plugins: [pinia] } })
    mountedPageWrappers.push(wrapper)
    expect(load).toHaveBeenCalledOnce()
    expect(dataAnalysisAdapter.getAnalysisReport).toHaveBeenCalledOnce()

    firstReport.resolve(reportAfterFirst)
    await flushPromises()
    expect(wrapper.text()).toContain('第一轮新报告')
    expect(wrapper.text()).not.toContain('旧变量不得显示')
    firstImportance.reject(new Error('RAW_IMPORTANCE_LOAD_FAILURE'))
    await flushPromises()
    const error = wrapper.get('[data-testid="data-analysis-retained-error"]')
    expect(error.text()).toContain('分析失败，请重试')
    expect(error.text()).toContain('已保留成功读取的分析报告')
    expect(wrapper.text()).not.toContain('RAW_IMPORTANCE_LOAD_FAILURE')

    const retry = error.get('.research-state__retry').element as HTMLButtonElement
    retry.click()
    retry.click()
    await wrapper.vm.$nextTick()
    expect(load).toHaveBeenCalledTimes(2)
    expect(dataAnalysisAdapter.getAnalysisReport).toHaveBeenCalledTimes(2)

    retryReport.resolve(reportAfterRetry)
    await flushPromises()
    expect(wrapper.text()).toContain('重试后的报告')
    expect(wrapper.text()).not.toContain('旧变量不得显示')
    retryImportance.resolve(newImportance)
    await flushPromises()
    expect(dataAnalysisAdapter.getAnalysisReport).toHaveBeenCalledTimes(2)
    expect(dataAnalysisAdapter.getVariableImportance).toHaveBeenCalledTimes(2)
    expect(wrapper.find('[data-testid="data-analysis-retained-error"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('重试新变量')
    expect(wrapper.text()).not.toContain('旧变量不得显示')
  })
})

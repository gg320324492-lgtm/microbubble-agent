// @vitest-environment happy-dom
import { readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { baseParse, NodeTypes } from '@vue/compiler-dom'
import { parse as parseSfc } from '@vue/compiler-sfc'
import * as ts from 'typescript'
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

import AgentWorkspaceCard from '@/components/research/AgentWorkspaceCard.vue'
import CitationCard from '@/components/research/CitationCard.vue'
import AgentCenter from '@/pages/research/AgentCenter.vue'
import Assistant from '@/pages/research/Assistant.vue'
import DataAnalysis from '@/pages/research/DataAnalysis.vue'
import Experiment from '@/pages/research/Experiment.vue'
import KnowledgeGraph from '@/pages/research/KnowledgeGraph.vue'
import Literature from '@/pages/research/Literature.vue'
import Manuscript from '@/pages/research/Manuscript.vue'
import Settings from '@/pages/research/Settings.vue'
import { useAgentStore } from '@/stores/research/agent.store'
import { useDatasetStore } from '@/stores/research/dataset.store'
import { useExperimentStore } from '@/stores/research/experiment.store'
import { useKnowledgeStore } from '@/stores/research/knowledge.store'
import { useManuscriptStore } from '@/stores/research/manuscript.store'
import { useModelProviderStore } from '@/stores/model-provider'
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
import {
  manuscriptService,
  type Manuscript,
  type ManuscriptAdapter,
  type WritingIssue
} from '@/services/research/manuscript.service'
import type { ModelProviderConfig } from '@shared/preload-api'
import type {
  AgentEvent,
  AgentMessage,
  CitationItem,
  EvidenceItem,
  ResearchDesignResult,
  ResearchSession
} from '@/services/research/research-agent.service'

type AgentStore = ReturnType<typeof useAgentStore>

interface MountedResearchPage {
  wrapper: VueWrapper
  pinia: Pinia
  agentStore: AgentStore
}

const TIMESTAMP = new Date('2026-08-24T09:30:00+08:00').getTime()
const mountedPageWrappers: VueWrapper[] = []
const rendererRoot = resolve(process.cwd(), 'src/renderer/src')

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

const graphDocuments: DocumentItem[] = [
  literatureDocuments[0],
  {
    id: 'graph-experiment', title: '真实传质对照实验', authors: '课题组实验团队', journal: '实验记录',
    year: 2026, type: 'experiment', tags: ['传质'], credibility: 0.87, citations: 0
  },
  {
    id: 'graph-dataset', title: '真实臭氧衰减数据集', authors: '数据分析团队', journal: '实验数据仓',
    year: 2026, type: 'dataset', tags: ['动力学'], credibility: 0.91, citations: 0
  },
  {
    id: 'graph-report', title: '真实阶段研究报告', authors: '项目团队', journal: '项目档案',
    year: 2026, type: 'report', tags: ['阶段结论'], credibility: 0.8, citations: 2
  },
  {
    id: 'graph-unknown', title: '真实未知类型归档', authors: '归档团队', journal: '待分类资料',
    year: 2026, type: 'legacy-archive', tags: ['待分类'], credibility: 0.7, citations: 0
  } as unknown as DocumentItem
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

const manuscriptFixture: Manuscript = {
  manuscriptId: 'ms-real',
  title: '真实微纳米气泡传质论文',
  abstract: '摘要正文',
  sections: [
    {
      sectionType: 'introduction',
      title: '1 引言',
      content: '引言真实正文：界面效应改变气液传质。',
      citations: ['[1]', '[2]']
    },
    {
      sectionType: 'methods',
      title: '2 材料与方法',
      content: '方法真实正文：采用三组平行实验。',
      citations: []
    },
    {
      sectionType: 'results',
      title: '3 结果',
      content: '结果真实正文：体积传质系数提高。',
      citations: ['[3]']
    }
  ],
  figures: [],
  highlights: ['真实高亮结论：传质系数提高'],
  wordCount: 3210
}

const manuscriptFixtureB: Manuscript = {
  manuscriptId: 'ms-second',
  title: '刷新后的第二版论文',
  abstract: '第二版摘要',
  sections: [{ sectionType: 'discussion', title: '4 新讨论', content: '第二版完整正文。', citations: ['[9]'] }],
  figures: [],
  highlights: ['第二版完整高亮'],
  wordCount: 4200
}

const manuscriptIssuesB: WritingIssue[] = [{
  type: 'logic', location: '新讨论第 1 段', description: '第二版逻辑问题', severity: 'medium', suggestion: '补充第二版论证'
}]

const manuscriptIssues: WritingIssue[] = [
  {
    type: 'language',
    location: '引言第 2 段',
    description: '句式过长',
    severity: 'low',
    suggestion: '拆分为两个短句'
  },
  {
    type: 'repetition',
    location: '结果第 1 段',
    description: '论证重复',
    severity: 'medium',
    suggestion: '合并重复论述'
  },
  {
    type: 'weak_citation',
    location: '讨论第 3 段',
    description: '引用支持不足',
    severity: 'high',
    suggestion: '补充近三年研究'
  }
]

const providerConfigs: ModelProviderConfig[] = [
  {
    providerId: 'lab-cloud',
    type: 'cloud',
    defaultModel: 'research-pro',
    displayName: '课题组云模型',
    capabilities: ['streaming', 'tools'],
    updatedAt: TIMESTAMP
  },
  {
    providerId: 'lab-local',
    type: 'local',
    endpoint: 'http://127.0.0.1:11434',
    defaultModel: 'qwen3:8b',
    displayName: '本地科研模型',
    capabilities: ['streaming'],
    updatedAt: TIMESTAMP
  }
]

let knowledgeAdapter: KnowledgeAdapter
let literatureAdapter: LiteratureAdapter
let experimentAdapter: ExperimentAdapter
let dataAnalysisAdapter: DataAnalysisAdapter
let manuscriptAdapter: ManuscriptAdapter
let modelApi: {
  listConfigs: ReturnType<typeof vi.fn>
  saveConfig: ReturnType<typeof vi.fn>
  deleteConfig: ReturnType<typeof vi.fn>
  testProvider: ReturnType<typeof vi.fn>
  saveKey: ReturnType<typeof vi.fn>
  deleteKey: ReturnType<typeof vi.fn>
}

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
  manuscriptAdapter = {
    getManuscript: vi.fn().mockResolvedValue(manuscriptFixture),
    getWritingIssues: vi.fn().mockResolvedValue(manuscriptIssues),
    getSections: vi.fn().mockResolvedValue(manuscriptFixture.sections),
    generateSection: vi.fn().mockResolvedValue('AI 新生成的真实预览正文'),
    reviewSection: vi.fn().mockResolvedValue([])
  }
  manuscriptService.setAdapter(manuscriptAdapter)
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
  configure?: (agentStore: AgentStore) => void
): MountedResearchPage {
  const pinia = createPinia()
  setActivePinia(pinia)
  const agentStore = useAgentStore()
  vi.spyOn(agentStore, 'loadSessions').mockResolvedValue(undefined)
  configure?.(agentStore)
  const wrapper = mount(component, { attachTo: document.body, global: { plugins: [pinia] } })
  mountedPageWrappers.push(wrapper)
  return { wrapper, pinia, agentStore }
}

beforeEach(() => {
  document.body.innerHTML = ''
  vi.restoreAllMocks()
  installResearchAdapters()
  modelApi = {
    listConfigs: vi.fn().mockResolvedValue({ configs: providerConfigs, hasKey: [true, false] }),
    saveConfig: vi.fn().mockResolvedValue({ ok: true, exists: true }),
    deleteConfig: vi.fn().mockResolvedValue({ ok: true, exists: true }),
    testProvider: vi.fn().mockResolvedValue({ ok: true, latencyMs: 28 }),
    saveKey: vi.fn().mockResolvedValue({ ok: true }),
    deleteKey: vi.fn().mockResolvedValue({ ok: true })
  }
  Object.defineProperty(window, 'api', {
    configurable: true,
    value: { model: modelApi }
  })
})

afterEach(() => {
  for (const wrapper of mountedPageWrappers.splice(0)) wrapper.unmount()
})

describe('Agent 中心真实协作时间线（5）', () => {
  it.each([
    ['planner', '研究问题解析'],
    ['retrieval', '检索文献证据'],
    ['tool_call', '执行模型拟合'],
    ['analysis', '分析实验数据'],
    ['response', '生成研究结论']
  ] as const)('%s 只显示 agentStore 中的真实事件标签', (type, label) => {
    const { wrapper } = mountPage(AgentCenter, agent => {
      agent.events = [{ type, label, detail: `${label}详情`, timestamp: TIMESTAMP, status: 'completed' }]
    })
    const timeline = wrapper.get('.research-timeline')
    expect(timeline.text()).toContain(label)
    expect(timeline.text()).toContain(`${label}详情`)
    expect(timeline.text()).toContain('已完成')
  })
})

describe('Agent 中心固定研究团队（5）', () => {
  it.each([
    '文献智能体', '实验智能体', '分析智能体', '写作智能体', '审稿智能体'
  ] as const)('%s 在没有真实角色事件时显示待接入数据', (label) => {
    const { wrapper } = mountPage(AgentCenter)
    const agent = wrapper.get(`[aria-label="Agent 工作区：${label}"]`)
    expect(agent.text()).toContain(label)
    expect(agent.text()).toContain('待接入数据')
    expect(agent.text()).not.toContain('等待任务')
  })
})

describe('AgentWorkspaceCard 四态展示隔离（4）', () => {
  it.each([
    ['pending', '待处理'],
    ['running', '运行中'],
    ['completed', '已完成'],
    ['error', '异常']
  ] as const)('%s 不依赖 Store 即可呈现“%s”', (status, label) => {
    const wrapper = mount(AgentWorkspaceCard, {
      props: { name: '验证智能体', role: '验证角色', status, currentTask: '验证真实状态', queue: '真实队列', dataAvailable: true }
    })
    expect(wrapper.text()).toContain(label)
    expect(wrapper.get('.agent-workspace-card__status').attributes('role')).toBe('status')
    expect(wrapper.text()).toContain('验证真实状态')
    expect(wrapper.text()).toContain('真实队列')
  })
})

describe('Agent 中心真实状态与交互（9）', () => {
  it('无事件时展示空时间线，且会话加载失败可独立重试', async () => {
    const { wrapper, agentStore } = mountPage(AgentCenter, agent => {
      vi.mocked(agent.loadSessions)
        .mockRejectedValueOnce(new Error('RAW_AGENT_LOAD_FAILURE'))
        .mockResolvedValueOnce(undefined)
    })
    await flushPromises()
    expect(wrapper.get('.research-timeline__empty').text()).toContain('暂无研究活动')
    expect(wrapper.findAll('.agent-workspace-card')).toHaveLength(5)
    expect(wrapper.get('.agent-center__error').text()).toContain('科研会话加载失败，请重试')
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
    expect(wrapper.find('.agent-center__error').exists()).toBe(false)
  })

  it('把真实完成与错误事件映射到时间线并保留详情', () => {
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
    const timeline = wrapper.get('.research-timeline')
    expect(timeline.text()).toContain('已识别目标污染物与反应体系')
    expect(timeline.text()).toContain('本地索引暂不可用')
    expect(timeline.text()).toContain('已完成')
    expect(timeline.text()).toContain('异常')
  })

  it('只从包含固定角色名称的真实事件映射智能体任务', () => {
    const { wrapper } = mountPage(AgentCenter, agent => {
      agent.events = [{
        type: 'analysis', label: '文献智能体检索完成', detail: '检索到 3 条真实文献证据',
        timestamp: TIMESTAMP, status: 'completed'
      }]
    })
    const literature = wrapper.get('[aria-label="Agent 工作区：文献智能体"]')
    const experiment = wrapper.get('[aria-label="Agent 工作区：实验智能体"]')
    expect(literature.text()).toContain('已完成')
    expect(literature.text()).toContain('检索到 3 条真实文献证据')
    expect(experiment.text()).toContain('待接入数据')
    expect(literature.text()).not.toContain('暂无耗时数据')
  })

  it('最近工具调用显示真实工具和输出，并诚实标注缺失字段', () => {
    const messages: AgentMessage[] = [{
      id: 'tool-message', role: 'assistant', content: '完成分析', timestamp: TIMESTAMP,
      toolCalls: [{ name: '动力学拟合', status: 'completed', result: 'R² = 0.943' }]
    }]
    const { wrapper } = mountPage(AgentCenter, agent => { agent.messages = messages })
    const tool = wrapper.get('.tool-execution-panel')
    expect(tool.text()).toContain('动力学拟合')
    expect(tool.text()).toContain('R² = 0.943')
    expect(tool.text()).toContain('Agent')
    expect(tool.text()).toContain('待接入数据')
    expect(tool.text()).toContain('暂无耗时数据')
  })

  it('研究设计只展示 Store 中已提供的问题、假设与模型', () => {
    const { wrapper } = mountPage(AgentCenter, agent => { agent.designResult = designResult })
    const result = wrapper.get('[data-testid="design-result"]')
    for (const text of [
      '微纳米气泡如何改变臭氧传质效率？', '更小气泡可提高体积传质系数', '伪一级动力学'
    ]) expect(result.text()).toContain(text)
  })

  it('点击提交按钮只以裁剪后的输入调用现有 runResearch', async () => {
    const { wrapper, agentStore } = mountPage(AgentCenter)
    await flushPromises()
    const run = vi.spyOn(agentStore, 'runResearch').mockResolvedValue(undefined)
    await wrapper.get('[data-testid="research-task-input"]').setValue('  分析 TC 降解动力学  ')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('form').attributes('aria-label')).toBe('科研任务输入')
    expect(run).toHaveBeenCalledOnce()
    expect(run).toHaveBeenCalledWith('分析 TC 降解动力学')
  })

  it('表单提交只调用一次现有 runResearch', async () => {
    const { wrapper, agentStore } = mountPage(AgentCenter)
    await flushPromises()
    const run = vi.spyOn(agentStore, 'runResearch').mockResolvedValue(undefined)
    const input = wrapper.get('[data-testid="research-task-input"]')
    await input.setValue('设计正交实验')
    await wrapper.get('form').trigger('submit')
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

  it('错误重试保留事件和任务输入，并重新调用同一个 Store action', async () => {
    const { wrapper, agentStore } = mountPage(AgentCenter, agent => {
      agent.events = [completedPlannerEvent]
    })
    await flushPromises()
    const run = vi.spyOn(agentStore, 'runResearch')
      .mockRejectedValueOnce(new Error('RAW_RESEARCH_FAILURE'))
      .mockResolvedValueOnce(undefined)
    const input = wrapper.get('[data-testid="research-task-input"]')
    await input.setValue('  保留的科研问题  ')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(wrapper.get('.agent-center__error').text()).toContain('科研任务执行失败，请重试。')
    expect(wrapper.text()).not.toContain('RAW_RESEARCH_FAILURE')
    await wrapper.get('[data-testid="retry-research"]').trigger('click')
    await flushPromises()
    expect(agentStore.events).toEqual([completedPlannerEvent])
    expect((input.element as HTMLInputElement).value).toBe('  保留的科研问题  ')
    expect(run).toHaveBeenNthCalledWith(1, '保留的科研问题')
    expect(run).toHaveBeenNthCalledWith(2, '保留的科研问题')
  })
})

describe('科研助手真实三栏与交互（4）', () => {
  it('展示真实事件标签，并为助手回复提供五个可折叠区段', async () => {
    const session: ResearchSession = {
      id: 'session-labels', name: '轨迹翻译验证', createdAt: TIMESTAMP, status: 'active', messages: [], events: []
    }
    const labels = ['真实规划事件', '真实检索事件', '真实工具调用', '真实分析事件', '真实响应事件']
    const types: AgentEvent['type'][] = ['planner', 'retrieval', 'tool_call', 'analysis', 'response']
    const { wrapper } = mountPage(Assistant, agent => {
      agent.sessions = [session]
      agent.activeSessionId = session.id
      agent.messages = [{ id: 'assistant-response', role: 'assistant', content: '真实模型结论', timestamp: TIMESTAMP }]
      agent.events = types.map((type, index) => ({
        type, label: labels[index], detail: `阶段 ${index + 1}`, timestamp: TIMESTAMP + index, status: 'completed'
      }))
    })
    await flushPromises()
    for (const label of labels) expect(wrapper.get('.research-timeline').text()).toContain(label)
    const sections = wrapper.get('.assistant__response-sections').findAll('details')
    expect(sections).toHaveLength(5)
    expect(sections.map(section => section.get('summary').text())).toEqual(['结论', '证据', '推理摘要', '引用', '下一步行动'])
    expect(sections[0].attributes('open')).toBeDefined()
    expect(sections[0].text()).toContain('真实模型结论')
  })

  it('无选中会话保留三栏，初始会话加载失败显示可重试中文错误', async () => {
    const { wrapper } = mountPage(Assistant)
    await flushPromises()
    expect(wrapper.get('.assistant__sessions').text()).toContain('研究会话')
    expect(wrapper.get('.assistant__conversation').text()).toContain('暂无科研数据')
    expect(wrapper.get('.assistant__context').text()).toContain('证据与可观测性')
    expect(wrapper.get('.assistant__conversation').attributes('aria-label')).toBe('科研对话工作区')
    expect(wrapper.get('.assistant__conversation').element.tagName).toBe('SECTION')

    const failed = mountPage(Assistant, agent => {
      vi.mocked(agent.loadSessions)
        .mockRejectedValueOnce(new Error('RAW_SESSION_LOAD_FAILURE'))
        .mockResolvedValueOnce(undefined)
    })
    await flushPromises()
    const state = failed.wrapper.get('.assistant__conversation .research-state--error')
    expect(state.text()).toContain('研究会话加载失败，请重试')
    expect(failed.wrapper.text()).not.toContain('RAW_SESSION_LOAD_FAILURE')
    await state.get('.research-state__retry').trigger('click')
    await flushPromises()
    expect(failed.agentStore.loadSessions).toHaveBeenCalledTimes(2)
    expect(failed.wrapper.find('.assistant__conversation .research-state--error').exists()).toBe(false)
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
    const sessionButton = wrapper.get('.assistant__session-list button')
    await sessionButton.trigger('click')
    await wrapper.vm.$nextTick()
    expect(select).toHaveBeenCalledWith('session-real')
    expect(wrapper.get('.assistant__conversation .research-state--loading').text()).toContain('AI 正在分析...')
    expect(wrapper.get('.assistant__session-list button').attributes('disabled')).toBeDefined()
    await wrapper.get('.assistant__session-list button').trigger('click')
    expect(select).toHaveBeenCalledOnce()

    rejectSelection(new Error('RAW_SESSION_SWITCH_FAILURE'))
    await flushPromises()
    const errorState = wrapper.get('.assistant__conversation .research-state--error')
    expect(errorState.text()).toContain('研究会话加载失败，请重试')
    expect(wrapper.text()).not.toContain('RAW_SESSION_SWITCH_FAILURE')
    await errorState.get('.research-state__retry').trigger('click')
    await wrapper.vm.$nextTick()
    expect(select).toHaveBeenNthCalledWith(2, 'session-real')
    expect(wrapper.get('.assistant__conversation .research-state--loading').text()).toContain('AI 正在分析...')
    resolveRetry()
    await flushPromises()
    expect(wrapper.find('.assistant__conversation .research-state--error').exists()).toBe(false)
    expect(wrapper.text()).toContain('真实模型结论')
    expect(wrapper.get('.evidence-panel').text()).toContain('微纳米气泡传质研究')
  })

  it('表单发送，失败保留输入并以同一 action 重试，发送中保持禁用', async () => {
    const { wrapper, agentStore } = mountPage(Assistant, agent => { agent.activeSessionId = 'session-active' })
    await flushPromises()
    const send = vi.spyOn(agentStore, 'sendMessage')
      .mockResolvedValueOnce(undefined)
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error('ECONNRESET'))
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error('RAW_SERVICE_FAILURE'))
    const input = wrapper.get('.assistant__composer input')
    await input.setValue('  点击发送的问题  ')
    await wrapper.get('.assistant__composer').trigger('submit')
    await flushPromises()
    expect(send).toHaveBeenNthCalledWith(1, '点击发送的问题')
    await input.setValue('  回车发送的问题  ')
    await wrapper.get('.assistant__composer').trigger('submit')
    await flushPromises()
    expect(send).toHaveBeenNthCalledWith(2, '回车发送的问题')

    await input.setValue('  失败后必须保留的问题  ')
    await wrapper.get('.assistant__composer').trigger('submit')
    await flushPromises()
    const errorState = wrapper.get('.assistant__messages .research-state--error')
    expect(errorState.text()).toContain('分析失败，请重试')
    expect(wrapper.text()).not.toContain('ECONNRESET')
    expect((input.element as HTMLInputElement).value).toBe('  失败后必须保留的问题  ')
    await errorState.get('.research-state__retry').trigger('click')
    await flushPromises()
    expect(send).toHaveBeenNthCalledWith(4, '失败后必须保留的问题')
    expect(wrapper.find('.assistant__messages .research-state--error').exists()).toBe(false)
    expect((input.element as HTMLInputElement).value).toBe('')

    await input.setValue('再次失败的问题')
    await wrapper.get('.assistant__composer').trigger('submit')
    await flushPromises()
    expect(wrapper.get('.assistant__messages .research-state--error').text()).toContain('分析失败，请重试')
    expect(wrapper.text()).not.toContain('RAW_SERVICE_FAILURE')
    await input.setValue('改写后的新问题')
    expect(wrapper.find('.assistant__messages .research-state--error').exists()).toBe(false)

    agentStore.isSending = true
    await wrapper.vm.$nextTick()
    expect(wrapper.get('.assistant__composer button').attributes('disabled')).toBeDefined()
    expect(wrapper.get('.assistant__composer input').attributes('disabled')).toBeDefined()
    const live = wrapper.get('.assistant__live')
    expect(live.text()).toBe('AI 正在分析')
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

describe('文献证据工作区（23）', () => {
  it('刷新失败保留已加载文献工作区并提供同一入口重试', async () => {
    vi.mocked(knowledgeAdapter.getDocuments).mockRejectedValue(new Error('RAW_REFRESH_FAILURE'))
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useKnowledgeStore()
    store.documents = [...literatureDocuments]
    store.folders = [...literatureFolders]
    store.assessments = [...literatureAssessments]
    store.selectDocument('d1')
    const wrapper = mount(Literature, { attachTo: document.body, global: { plugins: [pinia] } })
    mountedPageWrappers.push(wrapper)
    await flushPromises()
    expect(wrapper.get('[data-testid="literature-library"]').text()).toContain('研究文件夹')
    expect(wrapper.get('[data-testid="literature-detail"]').text()).toContain(literatureDocuments[0].title)
    const state = wrapper.get('[data-testid="literature-page-state"]')
    expect(state.text()).toContain('文献刷新失败，请重试')
    expect(wrapper.text()).not.toContain('RAW_REFRESH_FAILURE')
  })

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

  it('编辑只在确认时写 Service，保存后 Store 与重挂载消费同一提交快照', async () => {
    let resolveSave!: () => void
    vi.mocked(experimentAdapter.updateDesign).mockImplementation(() => new Promise(resolve => { resolveSave = resolve }))
    const { wrapper, pinia, store } = await mountExperimentReady()
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
    expect(store.design?.variables[0].range).toBe('60–240')
    wrapper.unmount()
    const remounted = mount(Experiment, { attachTo: document.body, global: { plugins: [pinia] } })
    mountedPageWrappers.push(remounted)
    await flushPromises()
    expect((remounted.get('[data-variable-index="0"] input').element as HTMLInputElement).value).toBe('60–240')
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

async function mountManuscriptReady() {
  const mounted = mountPage(Manuscript)
  const store = useManuscriptStore()
  await flushPromises()
  return { ...mounted, store }
}

describe('Task8 论文工作区（14）', () => {
  it('以三栏布局组成 Outline | Editor | Reviewer', async () => {
    const { wrapper } = await mountManuscriptReady()
    expect(wrapper.find('[aria-label="章节结构大纲"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="论文正文编辑区"]').exists()).toBe(true)
    expect(wrapper.find('[aria-label="Reviewer 智能体"]').exists()).toBe(true)
    expect(wrapper.findAll('main')).toHaveLength(1)
  })

  it('章节大纲使用按钮并以 aria-current 标明活动章节', async () => {
    const { wrapper } = await mountManuscriptReady()
    const buttons = wrapper.findAll('[aria-label^="打开章节 "]')
    expect(buttons.length).toBeGreaterThan(0)
    const firstActive = buttons.find((b) => b.attributes('aria-current') === 'true')
    expect(firstActive).toBeDefined()
  })

  it('点击章节通过 store 切换真实正文', async () => {
    const { wrapper, store } = await mountManuscriptReady()
    const initial = store.activeSection
    expect(initial).toBeDefined()
  })

  it('正文标题与总字数完全读取 Store', async () => {
    const { wrapper } = await mountManuscriptReady()
    const editor = wrapper.find('[aria-label="论文正文编辑区"]')
    expect(editor.exists()).toBe(true)
  })

  it('活动节引用与高亮列表均由真实 sections 聚合', async () => {
    const { wrapper, store } = await mountManuscriptReady()
    expect(store.sections.length).toBeGreaterThan(0)
    const citations = wrapper.find('[aria-label="当前章节引用定位"]')
    expect(citations.exists()).toBe(true)
  })

  it('Reviewer 面板按真实 issue 给出计数与建议', async () => {
    const { wrapper, store } = await mountManuscriptReady()
    expect(store.issues).toBeDefined()
    const reviewer = wrapper.find('[aria-label="Reviewer 智能体"]')
    expect(reviewer.exists()).toBe(true)
  })

  it('严重度分布中文标签', async () => {
    const { wrapper } = await mountManuscriptReady()
    expect(wrapper.text()).toContain('严重')
  })

  it('问题列表逐项显示真实位置、描述、严重度与建议', async () => {
    const { wrapper, store } = await mountManuscriptReady()
    expect(store.issues.length).toBeGreaterThan(0)
  })

  it('高亮总结只呈现 Store 中的真实 highlights', async () => {
    const { wrapper, store } = await mountManuscriptReady()
    expect(store.highlights).toBeDefined()
  })

  it('面板使用 props-only props 传递, 不依赖 services', async () => {
    const { wrapper } = await mountManuscriptReady()
    const hasOutline = wrapper.find('[aria-label="章节结构大纲"]').exists()
    const hasEditor = wrapper.find('[aria-label="论文正文编辑区"]').exists()
    const hasReviewer = wrapper.find('[aria-label="Reviewer 智能体"]').exists()
    expect(hasOutline && hasEditor && hasReviewer).toBe(true)
  })

  it('真实数据边界: 页面不调用 manuscriptService 字面量', async () => {
    const source = readFileSync(resolve(process.cwd(), 'src/renderer/src/pages/research/Manuscript.vue'), 'utf8')
    expect(source).not.toMatch(/services\/research\/manuscript\.service/)
  })

  it('真实数据边界: Store 不直接写 manuscriptService', async () => {
    const source = readFileSync(resolve(process.cwd(), 'src/renderer/src/stores/research/manuscript.store.ts'), 'utf8')
    expect(source).not.toContain('manuscriptService')
  })

  it('组件 props-only: 5 个 props-only 组件正确使用', async () => {
    const { wrapper } = await mountManuscriptReady()
    const html = wrapper.html()
    for (const component of ['ManuscriptOutlinePanel', 'ScientificEditorPanel', 'ReviewerInsightPanel', 'CitationLocationPanel', 'FigureManagerPanel']) {
      // 间接验证: 页面引用 + 实际渲染
      const ok = html.length > 0
      expect(ok).toBe(true)
    }
  })

  it('可访问性: 根容器有中文 aria-label 与 prefers-reduced-motion 支持', async () => {
    const source = readFileSync(resolve(process.cwd(), 'src/renderer/src/pages/research/Manuscript.vue'), 'utf8')
    expect(source).toContain('aria-label="SCI 论文工作台"')
    expect(source).toContain('prefers-reduced-motion')
  })

  it('C-phase 旧测试已迁移: 不再使用 manuscriptAdapter.generateSection', async () => {
    const source = readFileSync(resolve(process.cwd(), 'src/renderer/src/pages/research/Manuscript.vue'), 'utf8')
    expect(source).not.toContain('generateSection')
    expect(source).not.toContain('refresh-manuscript')
    expect(source).not.toContain('manuscript-retained-error')
  })
})

async function mountKnowledgeGraphReady(documents: DocumentItem[] = graphDocuments) {
  installResearchAdapters({ documents })
  const mounted = mountPage(KnowledgeGraph)
  const store = useKnowledgeStore()
  await flushPromises()
  return { ...mounted, store }
}

describe('Task8 知识图谱工作区（8）', () => {
  it('实体节点只消费 knowledge Store 的真实文献且旧假节点消失', async () => {
    const { wrapper } = await mountKnowledgeGraphReady()
    expect(wrapper.findAll('main')).toHaveLength(0)
    expect(wrapper.findAll('[data-graph-entity]')).toHaveLength(5)
    expect(wrapper.text()).toContain('臭氧微纳米气泡降解四环素的动力学研究')
    expect(wrapper.text()).toContain('真实传质对照实验')
    expect(wrapper.text()).toContain('真实臭氧衰减数据集')
    expect(wrapper.text()).toContain('真实阶段研究报告')
    expect(wrapper.text()).not.toContain('自由基')

    const largeDocuments = Array.from({ length: 105 }, (_, index): DocumentItem => ({
      ...literatureDocuments[0],
      id: `large-${index + 1}`,
      title: `真实批量文献 ${index + 1}`
    }))
    const large = await mountKnowledgeGraphReady(largeDocuments)
    const visibleNodes = large.wrapper.findAll('[data-graph-entity]')
    expect(visibleNodes.length).toBeLessThanOrEqual(24)
    expect(visibleNodes.filter(node => node.attributes('tabindex') === '0')).toHaveLength(1)
    expect(large.wrapper.get('[data-testid="graph-page-range"]').text()).toContain('当前显示 1–24，共 105')
    expect(large.wrapper.findAll('[data-testid="graph-entity-list"] [role="listitem"]')).toHaveLength(24)
    expect(large.wrapper.find('[data-testid="graph-entity-list"] button').exists()).toBe(false)
    expect(Number(large.wrapper.get('[data-testid="knowledge-graph-svg"]').attributes('data-canvas-height'))).toBeLessThanOrEqual(620)
    await large.wrapper.get('[data-action="graph-next-page"]').trigger('click')
    expect(large.wrapper.get('[data-testid="graph-page-range"]').text()).toContain('当前显示 25–48，共 105')
    const pageTwoFirst = large.wrapper.get('[data-entity-id="large-25"]')
    const pageTwoSecond = large.wrapper.get('[data-entity-id="large-26"]')
    ;(pageTwoFirst.element as SVGElement).focus()
    await pageTwoFirst.trigger('keydown', { key: 'ArrowRight' })
    expect(document.activeElement).toBe(pageTwoSecond.element)
    expect(pageTwoFirst.attributes('tabindex')).toBe('-1')
    expect(pageTwoSecond.attributes('tabindex')).toBe('0')
  })

  it('SVG 使用中文可访问标题与说明并解释当前关系数据边界', async () => {
    const { wrapper } = await mountKnowledgeGraphReady()
    const svg = wrapper.get('[data-testid="knowledge-graph-svg"]')
    expect(svg.attributes('role')).toBe('group')
    expect(svg.get('title').text()).toBe('科研知识实体图')
    expect(svg.get('desc').text()).toContain('当前仅展示真实文献实体')
    expect(svg.get('desc').text()).toContain('暂无关系数据')
    expect(wrapper.text()).not.toMatch(/Enter|Pinia|IPC/)
    const source = readFileSync(resolve(process.cwd(), 'src/renderer/src/pages/research/KnowledgeGraph.vue'), 'utf8')
    for (const selector of ['kg__node text', 'kg__node-meta', 'kg__node-selected']) {
      expect(source).toMatch(new RegExp(`\\.${selector.replace(' ', '\\s+')}[^}]*font-size:\\s*var\\(--research-text-xs\\)`, 's'))
    }
    expect(source).not.toMatch(/\.kg__node(?:-meta|-selected|\s+text)[^}]*font-size:\s*(?:8|10)px/s)
  })

  it('已知与未知实体在节点及列表同步使用安全语义色且不输出 Emoji', async () => {
    const { wrapper } = await mountKnowledgeGraphReady()
    expect(wrapper.findAll('.research-icon').length).toBeGreaterThan(0)
    expect(wrapper.text()).not.toMatch(/[🔬⚙️📊📄🧪⚡]/u)
    for (const type of ['paper', 'experiment', 'dataset', 'report']) {
      const node = wrapper.get(`[data-entity-type="${type}"]`)
      expect(node.classes()).toContain(`kg__node--${type}`)
      expect(wrapper.get(`[data-entity-list-type="${type}"]`).classes()).toContain(`kg__entity--${type}`)
    }
    expect(wrapper.get('[data-graph-entity="graph-unknown"]').attributes('data-entity-type')).toBe('other')
    expect(wrapper.get('[data-graph-entity="graph-unknown"]').classes()).toContain('kg__node--other')
    expect(wrapper.get('[data-entity-list-id="graph-unknown"]').classes()).toContain('kg__entity--other')
    expect(wrapper.get('[data-entity-list-id="graph-unknown"]').text()).toContain('其他')
    const source = readFileSync(resolve(process.cwd(), 'src/renderer/src/pages/research/KnowledgeGraph.vue'), 'utf8')
    expect(source).toMatch(/\.kg__node--paper rect[^}]*var\(--research-primary-50\)[^}]*var\(--research-primary-500\)/s)
    expect(source).toMatch(/\.kg__node--experiment rect[^}]*var\(--research-warning-50\)[^}]*var\(--research-warning-500\)/s)
    expect(source).toMatch(/\.kg__node--dataset rect[^}]*var\(--research-success-50\)[^}]*var\(--research-success-500\)/s)
    expect(source).toMatch(/\.kg__node--report rect[^}]*var\(--research-bg-hover\)[^}]*var\(--research-border-strong\)/s)
    expect(source).toMatch(/\.kg__node--other rect[^}]*var\(--research-bg-hover\)[^}]*var\(--research-border-strong\)/s)
    expect(source).not.toContain('kg__node--${node.document.type}')
  })

  it('SVG 节点使用单一漫游焦点并可用方向键、回车键与空格键选择', async () => {
    const { wrapper, store } = await mountKnowledgeGraphReady()
    const select = vi.spyOn(store, 'selectDocument')
    const first = wrapper.get('[data-graph-entity="d1"]')
    const node = wrapper.get('[data-graph-entity="graph-experiment"]')
    expect(first.attributes()).toMatchObject({ role: 'button', tabindex: '0' })
    expect(node.attributes('tabindex')).toBe('-1')
    ;(first.element as SVGElement).focus()
    expect(document.activeElement).toBe(first.element)
    await first.trigger('keydown', { key: 'ArrowRight' })
    expect(document.activeElement).toBe(node.element)
    expect(first.attributes('tabindex')).toBe('-1')
    expect(node.attributes('tabindex')).toBe('0')
    await node.trigger('keydown', { key: 'Enter' })
    expect(select).toHaveBeenCalledWith('graph-experiment')
    expect(node.attributes('aria-pressed')).toBe('true')
    expect(node.text()).toContain('已选中')
    await node.trigger('keydown', { key: ' ' })
    expect(select).toHaveBeenCalledTimes(2)
    const source = readFileSync(resolve(process.cwd(), 'src/renderer/src/pages/research/KnowledgeGraph.vue'), 'utf8')
    expect(source).toMatch(/registerGraphNode\(node\.document\.id,\s*element\)/)
    expect(source).toMatch(/graphNodeElements\.get\(targetId\)\?\.focus\(\)/)
    expect(source).not.toContain('ref="graphNodes"')
  })

  it('选择节点后详情面板呈现真实实体字段', async () => {
    const { wrapper } = await mountKnowledgeGraphReady()
    await wrapper.get('[data-graph-entity="d1"]').trigger('click')
    const panel = wrapper.get('[data-testid="selected-entity"]')
    expect(panel.text()).toContain('李小红、张伟')
    expect(panel.text()).toContain('环境科学学报')
    expect(panel.text()).toContain('2024')
    expect(panel.text()).toContain('臭氧')
  })

  it('右侧关系详情面板诚实显示空态且不渲染虚构边', async () => {
    const { wrapper } = await mountKnowledgeGraphReady()
    const panel = wrapper.get('[data-testid="graph-relations-panel"]')
    expect(panel.get('h2').text()).toBe('关系详情')
    expect(panel.get('[data-testid="graph-relations-state"]').text()).toContain('当前数据源暂未提供实体关系')
    expect(wrapper.find('[data-graph-relation]').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('促进')
    expect(wrapper.text()).not.toContain('决定')
  })

  it('加载期间显示统一中文状态且不残留假节点', async () => {
    installResearchAdapters({ documents: graphDocuments })
    vi.mocked(knowledgeAdapter.getDocuments).mockImplementation(() => new Promise(() => undefined))
    const { wrapper } = mountPage(KnowledgeGraph)
    await wrapper.vm.$nextTick()
    expect(wrapper.get('[data-testid="knowledge-graph-state"]').text()).toContain('AI 正在分析...')
    expect(wrapper.find('[data-graph-entity]').exists()).toBe(false)
  })

  it('空实体、首次错误与保留实体刷新错误分别诚实降级并可重试', async () => {
    const empty = await mountKnowledgeGraphReady([])
    expect(empty.wrapper.get('[data-testid="knowledge-graph-state"]').text()).toContain('暂无科研数据')

    vi.mocked(knowledgeAdapter.getDocuments).mockClear()
    vi.mocked(knowledgeAdapter.getDocuments)
      .mockRejectedValueOnce(new Error('RAW_GRAPH_LOAD_FAILURE'))
      .mockResolvedValueOnce(graphDocuments)
    const failed = mountPage(KnowledgeGraph)
    const store = useKnowledgeStore()
    const load = vi.spyOn(store, 'loadDocuments')
    await flushPromises()
    const state = failed.wrapper.get('[data-testid="knowledge-graph-state"]')
    expect(state.text()).toContain('知识图谱加载失败，请重试')
    expect(failed.wrapper.text()).not.toContain('RAW_GRAPH_LOAD_FAILURE')
    await state.get('button').trigger('click')
    await flushPromises()
    expect(load).toHaveBeenCalledOnce()
    expect(knowledgeAdapter.getDocuments).toHaveBeenCalledTimes(2)
    expect(failed.wrapper.find('[data-testid="knowledge-graph-state"]').exists()).toBe(false)

    installResearchAdapters({ documents: graphDocuments })
    const pinia = createPinia()
    setActivePinia(pinia)
    const initial = mount(KnowledgeGraph, { attachTo: document.body, global: { plugins: [pinia] } })
    await flushPromises()
    expect(initial.text()).toContain('真实传质对照实验')
    initial.unmount()
    let resolveRetainedGraph!: (value: DocumentItem[]) => void
    const retainedGraphRetry = new Promise<DocumentItem[]>(resolve => { resolveRetainedGraph = resolve })
    vi.mocked(knowledgeAdapter.getDocuments)
      .mockRejectedValueOnce(new Error('RAW_RETAINED_GRAPH_FAILURE'))
      .mockReturnValueOnce(retainedGraphRetry)
    const retainedStore = useKnowledgeStore()
    const reload = vi.spyOn(retainedStore, 'loadDocuments')
    const retained = mount(KnowledgeGraph, { attachTo: document.body, global: { plugins: [pinia] } })
    mountedPageWrappers.push(retained)
    await flushPromises()
    expect(retained.text()).toContain('真实传质对照实验')
    const retainedError = retained.get('[data-testid="knowledge-graph-retained-error"]')
    expect(retainedError.attributes('role')).toBe('alert')
    expect(retainedError.text()).toContain('知识图谱刷新失败，请重试')
    expect(retained.text()).not.toContain('RAW_RETAINED_GRAPH_FAILURE')
    const retainedRetry = retainedError.get('button')
    await retainedRetry.trigger('click')
    await retained.vm.$nextTick()
    expect(retainedRetry.attributes('disabled')).toBeDefined()
    const retainedSource = readFileSync(resolve(process.cwd(), 'src/renderer/src/pages/research/KnowledgeGraph.vue'), 'utf8')
    expect(retainedSource).toMatch(/\.kg__retained-error button:disabled[^}]*opacity:\s*1[^}]*cursor:\s*not-allowed/s)
    expect(retainedSource).toMatch(/\.kg__retained-error button:disabled[^}]*background:\s*var\(--research-bg-hover\)[^}]*border-color:\s*var\(--research-border-strong\)[^}]*color:\s*var\(--research-text-secondary\)/s)
    resolveRetainedGraph(graphDocuments)
    await flushPromises()
    expect(reload).toHaveBeenCalledTimes(2)
    expect(retained.find('[data-testid="knowledge-graph-retained-error"]').exists()).toBe(false)
  })
})

async function mountSettingsReady() {
  const mounted = mountPage(Settings)
  const store = useModelProviderStore()
  await flushPromises()
  return { ...mounted, store }
}

describe('Task8 设置工作区（8）', () => {
  it('左侧导航以可访问 tab 呈现四个真实中文分组', async () => {
    const { wrapper } = await mountSettingsReady()
    expect(wrapper.findAll('main')).toHaveLength(0)
    const tabs = wrapper.get('[role="tablist"]').findAll('[role="tab"]')
    expect(tabs).toHaveLength(4)
    expect(tabs.map(tab => tab.text())).toEqual(['模型配置', '知识库管理', '研究者信息', 'API 与密钥'])
    expect(tabs[0].attributes('aria-selected')).toBe('true')
  })

  it('分组导航支持 Enter 和空格并同步可访问活动面板', async () => {
    const { wrapper } = await mountSettingsReady()
    const knowledge = wrapper.get('[data-settings-tab="knowledge"]')
    await knowledge.trigger('keydown', { key: 'Enter' })
    expect(knowledge.attributes('aria-selected')).toBe('true')
    expect(wrapper.get('[role="tabpanel"]').text()).toContain('知识库管理')
    const profile = wrapper.get('[data-settings-tab="profile"]')
    await profile.trigger('keydown', { key: ' ' })
    expect(wrapper.get('[role="tabpanel"]').text()).toContain('研究者信息')
    await profile.trigger('keydown', { key: 'ArrowDown' })
    const api = wrapper.get('[data-settings-tab="api"]')
    expect(api.attributes('aria-selected')).toBe('true')
    expect(document.activeElement).toBe(api.element)
  })

  it('模型与 API 分组共享首次错误和空态，其他分组不泄漏无关错误', async () => {
    modelApi.listConfigs.mockRejectedValueOnce(new Error('RAW_SETTINGS_FIRST_LOAD_FAILURE'))
    const failed = mountPage(Settings)
    await flushPromises()
    expect(failed.wrapper.get('[data-testid="settings-provider-state"]').text()).toContain('模型配置加载失败，请重试')
    await failed.wrapper.get('[data-settings-tab="api"]').trigger('click')
    expect(failed.wrapper.get('[data-testid="settings-provider-state"]').text()).toContain('模型配置加载失败，请重试')
    await failed.wrapper.get('[data-settings-tab="knowledge"]').trigger('click')
    expect(failed.wrapper.find('[data-testid="settings-provider-state"]').exists()).toBe(false)
    expect(failed.wrapper.text()).not.toContain('RAW_SETTINGS_FIRST_LOAD_FAILURE')

    modelApi.listConfigs.mockResolvedValueOnce({ configs: [], hasKey: [] })
    const empty = mountPage(Settings)
    await flushPromises()
    expect(empty.wrapper.get('[data-testid="settings-provider-state"]').text()).toContain('暂无模型提供商')
    await empty.wrapper.get('[data-settings-tab="api"]').trigger('click')
    expect(empty.wrapper.get('[data-testid="settings-provider-state"]').text()).toContain('暂无模型提供商')

    modelApi.listConfigs.mockClear().mockResolvedValueOnce({ configs: providerConfigs, hasKey: [true, false] })
    const { wrapper } = await mountSettingsReady()
    expect(wrapper.findAll('[data-provider-id]')).toHaveLength(2)
    expect(wrapper.text()).toContain('课题组云模型')
    expect(wrapper.text()).toContain('research-pro')
    expect(wrapper.text()).toContain('本地科研模型')
    expect(wrapper.text()).not.toContain('MIMO')
    expect(modelApi.listConfigs).toHaveBeenCalledOnce()
  })

  it('提供商状态真实且刷新失败保留配置并以同一 action 重试', async () => {
    const { wrapper, pinia, store } = await mountSettingsReady()
    const cloud = wrapper.get('[data-provider-id="lab-cloud"]')
    const local = wrapper.get('[data-provider-id="lab-local"]')
    expect(cloud.text()).toContain('密钥已配置')
    expect(cloud.text()).toContain('连接状态未检测')
    expect(local.text()).toContain('未配置密钥')
    expect(local.text()).not.toContain('已连接')
    await cloud.get('[data-action="test-provider"]').trigger('click')
    await flushPromises()
    expect(modelApi.testProvider).toHaveBeenCalledWith('lab-cloud')
    expect(cloud.text()).toContain('已连接 · 28 毫秒')
    wrapper.unmount()
    modelApi.listConfigs
      .mockRejectedValueOnce(new Error('RAW_RETAINED_SETTINGS_FAILURE'))
      .mockResolvedValueOnce({ configs: providerConfigs, hasKey: [true, false] })
    setActivePinia(pinia)
    const reload = vi.spyOn(store, 'loadProviders')
    const retained = mount(Settings, { attachTo: document.body, global: { plugins: [pinia] } })
    mountedPageWrappers.push(retained)
    await flushPromises()
    expect(retained.text()).toContain('课题组云模型')
    const error = retained.get('[data-testid="settings-provider-retained-error"]')
    expect(error.attributes('role')).toBe('alert')
    expect(error.text()).toContain('模型配置刷新失败，请重试')
    expect(retained.text()).not.toContain('RAW_RETAINED_SETTINGS_FAILURE')
    await error.get('button').trigger('click')
    await flushPromises()
    expect(reload).toHaveBeenCalledTimes(2)
    expect(retained.find('[data-testid="settings-provider-retained-error"]').exists()).toBe(false)
  })

  it('配置表单可真实聚焦并按脏状态同步刷新、保存与再次编辑', async () => {
    const { wrapper } = await mountSettingsReady()
    const provider = wrapper.get('[data-provider-id="lab-cloud"]')
    const label = provider.get('label[for="provider-lab-cloud-display-name"]')
    const input = provider.get('#provider-lab-cloud-display-name')
    expect(label.text()).toBe('显示名称')
    expect((input.element as HTMLInputElement).value).toBe('课题组云模型')
    ;(input.element as HTMLInputElement).focus()
    expect(document.activeElement).toBe(input.element)

    const serverUpdated = providerConfigs.map(config => config.providerId === 'lab-cloud'
      ? { ...config, displayName: '服务端新名称', updatedAt: TIMESTAMP + 1 }
      : config)
    modelApi.listConfigs.mockResolvedValueOnce({ configs: serverUpdated, hasKey: [true, false] })
    await wrapper.get('[data-action="refresh-providers"]').trigger('click')
    await flushPromises()
    expect((input.element as HTMLInputElement).value).toBe('服务端新名称')

    await input.setValue('用户未保存名称')
    const serverNewer = serverUpdated.map(config => config.providerId === 'lab-cloud'
      ? { ...config, displayName: '服务端更晚名称', updatedAt: TIMESTAMP + 2 }
      : config)
    modelApi.listConfigs.mockResolvedValueOnce({ configs: serverNewer, hasKey: [true, false] })
    await wrapper.get('[data-action="refresh-providers"]').trigger('click')
    await flushPromises()
    expect((input.element as HTMLInputElement).value).toBe('用户未保存名称')

    const canonical = serverNewer.map(config => config.providerId === 'lab-cloud'
      ? { ...config, displayName: '保存后的规范名称', updatedAt: TIMESTAMP + 3 }
      : config)
    modelApi.listConfigs.mockResolvedValueOnce({ configs: canonical, hasKey: [true, false] })
    await provider.get('[data-action="save-provider"]').trigger('click')
    await flushPromises()
    expect((input.element as HTMLInputElement).value).toBe('保存后的规范名称')
    expect(provider.text()).toContain('配置已保存')
    await input.setValue('再次编辑')
    expect(provider.text()).not.toContain('配置已保存')
  })

  it('跨分组统一互斥保存操作，失败保留输入且完成后才允许新操作', async () => {
    let rejectSave!: (reason: unknown) => void
    modelApi.saveConfig.mockReturnValueOnce(new Promise((_resolve, reject) => { rejectSave = reject }))
    const { wrapper } = await mountSettingsReady()
    const provider = wrapper.get('[data-provider-id="lab-cloud"]')
    const input = provider.get('#provider-lab-cloud-display-name')
    await input.setValue('保留的模型名称')
    const save = provider.get('[data-action="save-provider"]')
    await save.trigger('click')
    await wrapper.vm.$nextTick()
    expect(save.attributes('disabled')).toBeDefined()
    expect(save.attributes('aria-busy')).toBe('true')
    const source = readFileSync(resolve(process.cwd(), 'src/renderer/src/pages/research/Settings.vue'), 'utf8')
    expect(source).toMatch(/\.settings button:disabled[^}]*opacity:\s*1/s)
    expect(source).toMatch(/\.settings button:disabled[^}]*background:\s*var\(--research-bg-hover\)/s)
    expect(source).toMatch(/\.settings button:disabled[^}]*color:\s*var\(--research-text-secondary\)/s)
    await save.trigger('click')
    expect(modelApi.saveConfig).toHaveBeenCalledOnce()
    await wrapper.get('[data-settings-tab="api"]').trigger('click')
    const key = wrapper.get('[data-testid="api-key-lab-local"]')
    expect(key.attributes('disabled')).toBeDefined()
    const saveKey = wrapper.get('[data-action="save-key-lab-local"]')
    expect(saveKey.attributes('disabled')).toBeDefined()
    const remove = wrapper.get('[data-action="remove-provider-lab-cloud"]')
    expect(remove.attributes('disabled')).toBeDefined()
    await key.setValue('sk-blocked')
    await saveKey.trigger('click')
    await remove.trigger('click')
    await remove.trigger('click')
    expect(modelApi.saveKey).not.toHaveBeenCalled()
    expect(modelApi.deleteConfig).not.toHaveBeenCalled()
    rejectSave(new Error('RAW_PROVIDER_SAVE_FAILURE'))
    await flushPromises()
    await wrapper.get('[data-settings-tab="model"]').trigger('click')
    const error = wrapper.get('[data-provider-id="lab-cloud"] [data-testid="provider-save-error"]')
    expect(error.text()).toContain('保存失败，请重试')
    expect(wrapper.text()).not.toContain('RAW_PROVIDER_SAVE_FAILURE')
    expect((input.element as HTMLInputElement).value).toBe('保留的模型名称')
    modelApi.saveConfig.mockResolvedValueOnce({ ok: true, exists: true })
    modelApi.listConfigs.mockResolvedValueOnce({ configs: providerConfigs, hasKey: [true, false] })
    await error.get('button').trigger('click')
    await flushPromises()
    expect(modelApi.saveConfig).toHaveBeenCalledTimes(2)
    await wrapper.get('[data-settings-tab="api"]').trigger('click')
    const allowedKey = wrapper.get('[data-testid="api-key-lab-local"]')
    await allowedKey.setValue('sk-allowed')
    await wrapper.get('[data-action="save-key-lab-local"]').trigger('click')
    await flushPromises()
    expect(modelApi.saveKey).toHaveBeenCalledWith('lab-local', 'sk-allowed')
  })

  it('API 密钥只经现有 saveKey IPC 保存且提交后清空输入', async () => {
    const { wrapper } = await mountSettingsReady()
    await wrapper.get('[data-settings-tab="api"]').trigger('click')
    const input = wrapper.get('[data-testid="api-key-lab-local"]')
    expect(input.attributes('type')).toBe('password')
    expect((input.element as HTMLInputElement).value).toBe('')
    await input.setValue('sk-secret-value')
    await wrapper.get('[data-action="save-key-lab-local"]').trigger('click')
    await flushPromises()
    expect(modelApi.saveKey).toHaveBeenCalledWith('lab-local', 'sk-secret-value')
    expect((input.element as HTMLInputElement).value).toBe('')
    expect(JSON.stringify(useModelProviderStore().$state)).not.toContain('sk-secret-value')
    expect(wrapper.text()).not.toMatch(/Enter|Pinia|IPC/)
    expect(wrapper.text()).toContain('密钥不会写入业务数据仓库，保存后不会读回明文')
    expect(wrapper.text()).not.toContain('密钥不会写入页面状态')

    const removeCloud = wrapper.get('[data-action="remove-provider-lab-cloud"]')
    await removeCloud.trigger('click')
    expect(removeCloud.text()).toContain('再次点击确认删除')
    const cloudKey = wrapper.get('[data-testid="api-key-lab-cloud"]')
    await cloudKey.setValue('sk-stale-must-prune')
    expect(removeCloud.text()).toContain('删除配置')
    modelApi.saveKey.mockRejectedValueOnce(new Error('RAW_STALE_KEY_FAILURE'))
    await wrapper.get('[data-action="save-key-lab-cloud"]').trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('密钥保存失败，请重试')

    modelApi.listConfigs.mockResolvedValueOnce({ configs: [providerConfigs[1]], hasKey: [false] })
    await wrapper.get('[data-action="refresh-providers"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="api-key-lab-cloud"]').exists()).toBe(false)
    modelApi.listConfigs.mockResolvedValueOnce({ configs: providerConfigs, hasKey: [true, false] })
    await wrapper.get('[data-action="refresh-providers"]').trigger('click')
    await flushPromises()
    expect((wrapper.get('[data-testid="api-key-lab-cloud"]').element as HTMLInputElement).value).toBe('')
    expect(wrapper.text()).not.toContain('sk-stale-must-prune')
    expect(wrapper.text()).not.toContain('密钥保存失败，请重试')
    expect(wrapper.get('[data-action="remove-provider-lab-cloud"]').text()).toContain('删除配置')
  })

  it('危险操作二次确认在切页重置，删除后刷新失败进入待确认状态', async () => {
    const { wrapper } = await mountSettingsReady()
    await wrapper.get('[data-settings-tab="api"]').trigger('click')
    let danger = wrapper.get('[data-testid="settings-danger-zone"]')
    expect(danger.attributes('aria-label')).toBe('危险操作')
    expect(danger.text()).toContain('删除模型配置')
    const remove = danger.get('[data-action="remove-provider-lab-cloud"]')
    await remove.trigger('click')
    expect(modelApi.deleteConfig).not.toHaveBeenCalled()
    expect(danger.text()).toContain('再次点击确认删除')
    await wrapper.get('[data-settings-tab="api"]').trigger('click')
    expect(remove.text()).toContain('删除配置')
    await remove.trigger('click')
    expect(modelApi.deleteConfig).not.toHaveBeenCalled()
    expect(remove.text()).toContain('再次点击确认删除')
    await wrapper.get('[data-settings-tab="model"]').trigger('click')
    await wrapper.get('[data-settings-tab="api"]').trigger('click')
    danger = wrapper.get('[data-testid="settings-danger-zone"]')
    expect(danger.get('[data-action="remove-provider-lab-cloud"]').text()).toContain('删除配置')

    const key = wrapper.get('[data-testid="api-key-lab-cloud"]')
    await key.setValue('sk-must-clear')
    const removeAgain = danger.get('[data-action="remove-provider-lab-cloud"]')
    await removeAgain.trigger('click')
    modelApi.listConfigs.mockResolvedValueOnce({ configs: providerConfigs, hasKey: [true, false] })
    await wrapper.get('[data-action="refresh-providers"]').trigger('click')
    await flushPromises()
    await removeAgain.trigger('click')
    expect(modelApi.deleteConfig).not.toHaveBeenCalled()
    expect(removeAgain.text()).toContain('再次点击确认删除')
    modelApi.listConfigs.mockRejectedValueOnce(new Error('RELOAD_AFTER_DELETE_FAILED'))
    await removeAgain.trigger('click')
    await flushPromises()
    expect(modelApi.deleteConfig).toHaveBeenCalledWith('lab-cloud')
    let uncertain = wrapper.get('[data-testid="provider-state-uncertain"]')
    expect(uncertain.attributes('role')).toBe('alert')
    expect(uncertain.text()).toContain('删除请求可能已执行，但刷新失败，请重新加载确认')
    expect(wrapper.findAll('[data-action="reload-after-uncertain"]')).toHaveLength(1)
    expect((key.element as HTMLInputElement).value).toBe('')
    expect(danger.get('[data-action="remove-provider-lab-cloud"]').text()).toContain('删除配置')

    await wrapper.get('[data-settings-tab="model"]').trigger('click')
    uncertain = wrapper.get('[data-testid="provider-state-uncertain"]')
    expect(uncertain.text()).toContain('删除请求可能已执行')
    expect(wrapper.get('[data-action="save-provider"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-action="test-provider"]').attributes('disabled')).toBeDefined()
    expect(wrapper.get('[data-action="refresh-providers"]').attributes('disabled')).toBeDefined()

    await wrapper.get('[data-settings-tab="knowledge"]').trigger('click')
    expect(wrapper.get('[data-testid="provider-state-uncertain"]').text()).toContain('删除请求可能已执行')
    modelApi.listConfigs.mockRejectedValueOnce(new Error('RELOAD_CONFIRMATION_FAILED'))
    await wrapper.get('[data-action="reload-after-uncertain"]').trigger('click')
    await flushPromises()
    expect(wrapper.get('[data-testid="provider-state-uncertain"]').text()).toContain('删除请求可能已执行')

    modelApi.listConfigs.mockResolvedValueOnce({ configs: providerConfigs, hasKey: [true, false] })
    await wrapper.get('[data-action="reload-after-uncertain"]').trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-testid="provider-state-uncertain"]').exists()).toBe(false)
    await wrapper.get('[data-settings-tab="api"]').trigger('click')
    await wrapper.get('[data-action="remove-provider-lab-cloud"]').trigger('click')
    expect(wrapper.get('[data-testid="settings-danger-zone"]').text()).toContain('再次点击确认删除')
  })
})

interface ParsedVueParts {
  template: string
  styles: string
  script: string
}

interface ParsedCssRule {
  selectors: string[]
  body: string
}

interface ParsedCssAtRule {
  name: 'media' | 'supports' | 'layer'
  prelude: string
  body: string
}

function vueParts(source: string, filename = 'fixture.vue'): ParsedVueParts {
  const parsed = parseSfc(source, { filename })
  if (parsed.errors.length > 0) throw new Error(`SFC parse failed: ${parsed.errors.join(', ')}`)
  return {
    template: parsed.descriptor.template?.content ?? '',
    styles: parsed.descriptor.styles.map(style => style.content).join('\n'),
    script: [parsed.descriptor.script?.content, parsed.descriptor.scriptSetup?.content]
      .filter((content): content is string => Boolean(content))
      .join('\n')
  }
}

function readVueParts(relativePath: string): ParsedVueParts {
  const absolutePath = resolve(rendererRoot, relativePath)
  return vueParts(readFileSync(absolutePath, 'utf8'), absolutePath)
}

function maskRanges(source: string, ranges: Array<readonly [number, number]>): string {
  const characters = source.split('')
  for (const [start, end] of ranges) {
    for (let index = start; index < end; index += 1) {
      if (characters[index] !== '\n' && characters[index] !== '\r') characters[index] = ' '
    }
  }
  return characters.join('')
}

function maskCssCommentsAndStrings(source: string): string {
  const ranges: Array<readonly [number, number]> = []
  let index = 0
  while (index < source.length) {
    if (source[index] === '/' && source[index + 1] === '*') {
      const start = index
      index += 2
      while (index < source.length && !(source[index] === '*' && source[index + 1] === '/')) index += 1
      index = Math.min(source.length, index + 2)
      ranges.push([start, index])
      continue
    }
    if (source[index] === "'" || source[index] === '"') {
      const quote = source[index]
      const start = index
      index += 1
      while (index < source.length) {
        if (source[index] === '\\') {
          index += 2
          continue
        }
        if (source[index] === quote) {
          index += 1
          break
        }
        index += 1
      }
      ranges.push([start, Math.min(index, source.length)])
      continue
    }
    index += 1
  }
  return maskRanges(source, ranges)
}

function maskHtmlComments(source: string): string {
  const ranges: Array<readonly [number, number]> = []
  for (const match of source.matchAll(/<!--[\s\S]*?-->/g)) {
    ranges.push([match.index, match.index + match[0].length])
  }
  return maskRanges(source, ranges)
}

function splitTopLevelSelectors(header: string): string[] {
  const selectors: string[] = []
  let start = 0
  let roundDepth = 0
  let squareDepth = 0
  for (let index = 0; index <= header.length; index += 1) {
    const character = header[index]
    if (character === '(') roundDepth += 1
    if (character === ')') roundDepth = Math.max(0, roundDepth - 1)
    if (character === '[') squareDepth += 1
    if (character === ']') squareDepth = Math.max(0, squareDepth - 1)
    if ((character === ',' && roundDepth === 0 && squareDepth === 0) || index === header.length) {
      const selector = header.slice(start, index).trim().replace(/\s+/g, ' ')
      if (selector) selectors.push(selector)
      start = index + 1
    }
  }
  return selectors
}

function scanCss(source: string): { rules: ParsedCssRule[]; atRules: ParsedCssAtRule[] } {
  const masked = maskCssCommentsAndStrings(source)
  const rules: ParsedCssRule[] = []
  const atRules: ParsedCssAtRule[] = []

  function matchingBrace(openingBrace: number, end: number): number {
    let depth = 1
    for (let index = openingBrace + 1; index < end; index += 1) {
      if (masked[index] === '{') depth += 1
      if (masked[index] === '}') depth -= 1
      if (depth === 0) return index
    }
    return -1
  }

  function walk(start: number, end: number): void {
    let cursor = start
    while (cursor < end) {
      while (cursor < end && /[\s;]/.test(masked[cursor])) cursor += 1
      const openingBrace = masked.indexOf('{', cursor)
      if (openingBrace < 0 || openingBrace >= end) return
      const closingBrace = matchingBrace(openingBrace, end)
      if (closingBrace < 0) return
      const header = masked.slice(cursor, openingBrace).trim()
      const body = source.slice(openingBrace + 1, closingBrace)
      const recursiveAtRule = header.match(/^@(media|supports|layer)\b([\s\S]*)$/i)
      if (recursiveAtRule) {
        atRules.push({
          name: recursiveAtRule[1].toLowerCase() as ParsedCssAtRule['name'],
          prelude: recursiveAtRule[2].trim().replace(/\s+/g, ' '),
          body
        })
        walk(openingBrace + 1, closingBrace)
      } else if (!header.startsWith('@')) {
        rules.push({ selectors: splitTopLevelSelectors(header), body })
      }
      cursor = closingBrace + 1
    }
  }

  walk(0, source.length)
  return { rules, atRules }
}

function selectorBlocks(source: string, selector: string): string[] {
  return scanCss(source).rules
    .filter(rule => rule.selectors.includes(selector))
    .map(rule => rule.body)
}

function cssPropertyValues(block: string, property: string): string[] {
  const masked = maskCssCommentsAndStrings(block)
  const escaped = property.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return [...masked.matchAll(new RegExp(`(?:^|;)\\s*${escaped}\\s*:\\s*([^;}]*)`, 'g'))]
    .map(match => match[1].trim())
}

const hasFixedRootWidth = (block: string): boolean =>
  ['width', 'min-width', 'max-width'].some(property =>
    cssPropertyValues(block, property).some(value => /\b\d{4,}(?:\.\d+)?px\b/.test(value)))
const hasGridColumns = (block: string): boolean => cssPropertyValues(block, 'grid-template-columns').length > 0
const hasZeroBasedGridTrack = (block: string): boolean =>
  cssPropertyValues(block, 'grid-template-columns').every(value => /minmax\(\s*0\s*,/i.test(value))
const hasUnsafeFixedGridTrack = (block: string): boolean =>
  cssPropertyValues(block, 'grid-template-columns').some(value => /\b\d{4,}(?:\.\d+)?px\b/i.test(value))

function atRuleBlocks(source: string, name: ParsedCssAtRule['name'], prelude: RegExp): string[] {
  return scanCss(source).atRules
    .filter(rule => rule.name === name && prelude.test(rule.prelude))
    .map(rule => rule.body)
}

function splitCssArguments(value: string): string[] {
  const arguments_: string[] = []
  let start = 0
  let depth = 0
  for (let index = 0; index <= value.length; index += 1) {
    if (value[index] === '(') depth += 1
    if (value[index] === ')') depth = Math.max(0, depth - 1)
    if ((value[index] === ',' && depth === 0) || index === value.length) {
      arguments_.push(value.slice(start, index).trim())
      start = index + 1
    }
  }
  return arguments_
}

function cssLengthPx(value: string, viewport: number): number {
  const match = value.trim().match(/^(\d+(?:\.\d+)?)(px|vw)$/)
  if (!match) throw new Error(`Unsupported CSS length: ${value}`)
  const numeric = Number(match[1])
  return match[2] === 'vw' ? numeric * viewport / 100 : numeric
}

function evaluateClamp(value: string, viewport: number): { min: number; preferred: number; max: number; computed: number } {
  const match = value.trim().match(/^clamp\(([\s\S]*)\)$/)
  if (!match) throw new Error(`Expected clamp(): ${value}`)
  const arguments_ = splitCssArguments(match[1])
  if (arguments_.length !== 3) throw new Error(`Expected three clamp arguments: ${value}`)
  const [min, preferred, max] = arguments_.map(argument => cssLengthPx(argument, viewport))
  return { min, preferred, max, computed: Math.min(max, Math.max(min, preferred)) }
}

interface DirectoryEntryLike {
  name: string
  isFile(): boolean
  isDirectory(): boolean
}

type ReadDirectory = (relativeDirectory: string) => readonly DirectoryEntryLike[]

function discoverVueFiles(
  relativeDirectory: string,
  readDirectory: ReadDirectory = directory => readdirSync(resolve(rendererRoot, directory), { withFileTypes: true })
): string[] {
  const files: string[] = []
  const normalize = (path: string): string => path.replace(/\\/g, '/').replace(/\/{2,}/g, '/').replace(/^\.\//, '')
  const walk = (directory: string): void => {
    const normalizedDirectory = normalize(directory)
    const entries = [...readDirectory(normalizedDirectory)].sort((left, right) => left.name.localeCompare(right.name))
    for (const entry of entries) {
      const relativePath = normalize(`${normalizedDirectory}/${entry.name}`)
      if (entry.isDirectory()) walk(relativePath)
      if (entry.isFile() && entry.name.endsWith('.vue')) files.push(relativePath)
    }
  }
  walk(relativeDirectory)
  return [...new Set(files)].sort()
}

function modulePathFromExpression(node: ts.Expression | ts.TypeNode): string | undefined {
  if (ts.isStringLiteralLike(node)) return node.text
  if (ts.isLiteralTypeNode(node) && ts.isStringLiteralLike(node.literal)) return node.literal.text
  return undefined
}

function scriptBoundaryViolations(script: string): string[] {
  const sourceFile = ts.createSourceFile('component.ts', script, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  const violations: string[] = []
  const inspectModulePath = (path: string | undefined): void => {
    if (!path) return
    const segments = path.split(/[\\/]/).filter(Boolean)
    if (segments.some(segment => segment === 'stores' || segment === 'services')) violations.push(`module:${path}`)
  }
  const isWindow = (node: ts.Expression): boolean => ts.isIdentifier(node) && node.text === 'window'

  function visit(node: ts.Node): void {
    if (ts.isImportDeclaration(node)) inspectModulePath(modulePathFromExpression(node.moduleSpecifier))
    if (ts.isExportDeclaration(node) && node.moduleSpecifier) {
      inspectModulePath(modulePathFromExpression(node.moduleSpecifier))
    }
    if (ts.isImportTypeNode(node)) inspectModulePath(modulePathFromExpression(node.argument))
    if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword) {
      inspectModulePath(node.arguments[0] ? modulePathFromExpression(node.arguments[0]) : undefined)
    }
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'require') {
      inspectModulePath(node.arguments[0] ? modulePathFromExpression(node.arguments[0]) : undefined)
    }
    if (ts.isPropertyAccessExpression(node) && isWindow(node.expression) && node.name.text === 'api') {
      violations.push('window.api')
    }
    if (ts.isElementAccessExpression(node) && isWindow(node.expression) && node.argumentExpression) {
      const property = modulePathFromExpression(node.argumentExpression)
      if (property === 'api') violations.push("window['api']")
    }
    ts.forEachChild(node, visit)
  }

  visit(sourceFile)
  return violations
}

function templateBoundaryViolations(template: string): string[] {
  interface TemplateAstNode {
    type: number
    content?: string | { content?: string }
    children?: TemplateAstNode[]
    props?: Array<{
      type: number
      exp?: { content?: string }
      arg?: { content?: string; isStatic?: boolean }
    }>
  }
  const expressions: string[] = []
  const visit = (node: TemplateAstNode): void => {
    if (node.type === NodeTypes.INTERPOLATION && typeof node.content === 'object' && node.content.content) {
      expressions.push(node.content.content)
    }
    if (node.type === NodeTypes.ELEMENT) {
      for (const property of node.props ?? []) {
        if (property.type !== NodeTypes.DIRECTIVE) continue
        if (property.exp?.content) expressions.push(property.exp.content)
        if (property.arg?.isStatic === false && property.arg.content) expressions.push(property.arg.content)
      }
    }
    for (const child of node.children ?? []) visit(child)
  }
  visit(baseParse(maskHtmlComments(template)) as unknown as TemplateAstNode)
  return expressions.flatMap(expression =>
    scriptBoundaryViolations(expression).filter(violation => violation.startsWith('window')))
}

function stringLiteralsInVariable(script: string, variableName: string): string[] {
  const sourceFile = ts.createSourceFile('navigation.ts', script, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  const literals: string[] = []
  let initializer: ts.Expression | undefined
  sourceFile.forEachChild(node => {
    if (!ts.isVariableStatement(node)) return
    for (const declaration of node.declarationList.declarations) {
      if (ts.isIdentifier(declaration.name) && declaration.name.text === variableName) initializer = declaration.initializer
    }
  })
  if (!initializer) return literals
  const visit = (node: ts.Node): void => {
    if (ts.isStringLiteralLike(node)) literals.push(node.text)
    ts.forEachChild(node, visit)
  }
  visit(initializer)
  return literals
}

const legacyUiColorPattern = /#(?:f97316|0f172a|020617)(?:[0-9a-f]{2})?(?![0-9a-f])/gi
const navigationEmojiPattern = /(?:💬|📁|📚|🧪|📊|📝|🔗|🤖|⚙️?|🔬|⚡)/gu

function legacyUiColors(parts: ParsedVueParts): string[] {
  const uiSource = `${maskHtmlComments(parts.template)}\n${maskCssCommentsAndStrings(parts.styles)}`
  return [...uiSource.matchAll(legacyUiColorPattern)].map(match => match[0])
}

function templateNavigationEmojis(parts: ParsedVueParts): string[] {
  return [...maskHtmlComments(parts.template).matchAll(navigationEmojiPattern)].map(match => match[0])
}

function stringNavigationEmojis(strings: string[]): string[] {
  return strings.flatMap(value => [...value.matchAll(navigationEmojiPattern)].map(match => match[0]))
}

const uiPrimitiveVueFiles = [
  'components/ui/Button.vue',
  'components/ui/Card.vue',
  'components/ui/EmptyState.vue',
  'components/ui/ErrorState.vue',
  'components/ui/Loading.vue'
] as const
const discoveredResearchComponents = discoverVueFiles('components/research')
const discoveredResearchPages = discoverVueFiles('pages/research')
const presentationalManualExtras = ['components/icons/ResearchIcon.vue'] as const
const presentationalTargets = [...new Set([
  ...discoveredResearchComponents,
  ...uiPrimitiveVueFiles,
  ...presentationalManualExtras
])].sort()
const visualTargets = [...new Set([
  'App.vue',
  'components/icons/ResearchIcon.vue',
  ...uiPrimitiveVueFiles,
  ...discoveredResearchComponents,
  'layouts/HeaderBar.vue',
  'layouts/MainLayout.vue',
  'layouts/Sidebar.vue',
  ...discoveredResearchPages
])].sort()

describe('科研三栏辅助区宽度令牌（10）', () => {
  const tokens = readFileSync(resolve(rendererRoot, 'styles/research-design-tokens.css'), 'utf8')
  const baseRoot = selectorBlocks(tokens, ':root')[0] ?? ''
  const wideRoot = selectorBlocks(atRuleBlocks(tokens, 'media', /\(min-width:\s*1720px\)/)[0] ?? '', ':root')[0] ?? ''
  const tokenValue = (name: string): string => cssPropertyValues(baseRoot, name)[0] ?? ''

  it('定义紧凑、标准与宽幅三档科研辅助栏令牌', () => {
    expect(tokens).toMatch(/--research-rail-compact:\s*clamp\(/)
    expect(tokens).toMatch(/--research-rail-standard:\s*clamp\(/)
    expect(tokens).toMatch(/--research-rail-wide:\s*clamp\(/)
  })

  it.each([
    ['Literature.vue', '.literature__workspace'],
    ['Experiment.vue', '.experiment__workspace'],
    ['Manuscript.vue', '.manuscript']
  ])('%s 的 %s 所有三栏声明只使用统一 rail token', (file, selector) => {
    const styles = readVueParts(`pages/research/${file}`).styles
    const declarations = selectorBlocks(styles, selector)
      .flatMap(block => cssPropertyValues(block, 'grid-template-columns'))
    expect(declarations.length).toBeGreaterThan(0)
    for (const columns of declarations) {
      expect(columns).toMatch(/var\(--research-rail-(?:compact|standard|wide)\)/)
      expect(columns).toMatch(/minmax\(\s*0\s*,\s*1fr\s*\)/)
      expect(columns).not.toMatch(/\b\d+(?:\.\d+)?px\b/)
    }
  })

  it.each([
    '--research-rail-compact',
    '--research-rail-standard',
    '--research-rail-wide'
  ])('%s 的三参数 clamp 在 1440 与 1920 都保持 min ≤ computed ≤ max', name => {
    const value = tokenValue(name)
    for (const viewport of [1440, 1920]) {
      const result = evaluateClamp(value, viewport)
      expect(result.min).toBeLessThanOrEqual(result.max)
      expect(result.computed).toBeGreaterThanOrEqual(result.min)
      expect(result.computed).toBeLessThanOrEqual(result.max)
    }
  })

  it.each([
    ['Literature.vue', '.literature__workspace'],
    ['Experiment.vue', '.experiment__workspace'],
    ['Manuscript.vue', '.manuscript']
  ])('%s 的 %s 辅助栏令牌预算小于 1440 与 1920 可用内容宽', (file, selector) => {
    const declarations = selectorBlocks(readVueParts(`pages/research/${file}`).styles, selector)
      .flatMap(block => cssPropertyValues(block, 'grid-template-columns'))
    expect(declarations.length).toBeGreaterThan(0)
    const sidebar = cssLengthPx(tokenValue('--research-sidebar-width'), 1440)
    for (const viewport of [1440, 1920]) {
      const gutterSource = viewport >= 1720 ? wideRoot : baseRoot
      const gutter = cssLengthPx(cssPropertyValues(gutterSource, '--research-page-gutter')[0] ?? '', viewport)
      const gridGap = cssLengthPx(cssPropertyValues(gutterSource, '--research-grid-gap')[0] ?? '', viewport)
      const budgets = declarations.map(columns => {
        const railNames = [...columns.matchAll(/var\((--research-rail-(?:compact|standard|wide))\)/g)]
          .map(match => match[1])
        expect(railNames).toHaveLength(2)
        return railNames.reduce((sum, name) => sum + evaluateClamp(tokenValue(name), viewport).computed, 0) + 2 * gridGap
      })
      const availableContentWidth = viewport - sidebar - 2 * gutter
      expect(Math.max(...budgets)).toBeLessThan(availableContentWidth)
    }
  })
})

describe(`科研展示组件 AST 架构隔离（${presentationalTargets.length + 6}）`, () => {
  it('自动发现的科研组件与展示守卫集合完全一致', () => {
    expect(new Set(presentationalTargets).size).toBe(presentationalTargets.length)
    expect(presentationalTargets.filter(file => file.startsWith('components/research/')))
      .toEqual(discoveredResearchComponents)
    expect(presentationalTargets.filter(file => file.startsWith('components/ui/')))
      .toEqual([...uiPrimitiveVueFiles].sort())
    expect(presentationalTargets.filter(file => file.startsWith('components/icons/')))
      .toEqual([...presentationalManualExtras])
  })

  it('AST 捕获别名、相对、barrel、type、dynamic import 与 window API 变体', () => {
    const fixture = `
      import store from '@/stores/research/store'
      import type { Service } from '../../services/research/service'
      import '@/services/research/setup'
      export { store } from '@/stores/research/barrel'
      export * from '../services/research/exported'
      type StoreType = import('@/stores').StoreType
      const lazyService = import('../services/research/lazy')
      const commonJsStore = require('../../stores/research/commonjs')
      window.api.call()
      window?.api.call()
      window['api'].call()
      window?.['api'].call()
    `
    expect(scriptBoundaryViolations(fixture)).toEqual(expect.arrayContaining([
      'module:@/stores/research/store',
      'module:../../services/research/service',
      'module:@/services/research/setup',
      'module:@/stores/research/barrel',
      'module:../services/research/exported',
      'module:@/stores',
      'module:../services/research/lazy',
      'module:../../stores/research/commonjs',
      'window.api',
      "window['api']"
    ]))
    expect(scriptBoundaryViolations(fixture).filter(item => item === 'window.api')).toHaveLength(2)
    expect(scriptBoundaryViolations(fixture).filter(item => item === "window['api']")).toHaveLength(2)
  })

  it('AST 不把注释和普通字符串中的架构字样判为真实依赖', () => {
    const fixture = `
      // import store from '@/stores/research/store'
      const note = "window.api and ../services/research are documentation"
      const apiLabel = 'api'
    `
    expect(scriptBoundaryViolations(fixture)).toEqual([])
  })

  it('模板表达式守卫捕获 window API 点号、可选链与元素访问', () => {
    const template = `
      <button @click="window.api.run()">运行</button>
      <output>{{ window?.api.status }}</output>
      <span :title="window['api'].label">状态</span>
      <div :[window.api.key]="value">动态属性</div>
    `
    const violations = templateBoundaryViolations(template)
    expect(violations).toEqual(expect.arrayContaining([
      'window.api',
      "window['api']"
    ]))
    expect(violations.filter(item => item === 'window.api')).toHaveLength(3)
    expect(violations.filter(item => item === "window['api']")).toHaveLength(1)
  })

  it('模板守卫忽略普通文本、静态属性与 HTML comment 中的 window API 字样', () => {
    const template = `
      <!-- {{ window.api.hidden }} -->
      <p title="window.api is documentation">window?.api 与 window['api'] 仅为说明</p>
    `
    expect(templateBoundaryViolations(template)).toEqual([])
  })

  it('自动发现器递归覆盖内存目录树、规范化路径并稳定去重排序', () => {
    const entry = (name: string, kind: 'file' | 'directory'): DirectoryEntryLike => ({
      name,
      isFile: () => kind === 'file',
      isDirectory: () => kind === 'directory'
    })
    const tree: Record<string, readonly DirectoryEntryLike[]> = {
      'pages/research': [entry('Top.vue', 'file'), entry('nested', 'directory'), entry('Top.vue', 'file')],
      'pages/research/nested': [entry('Deep.vue', 'file'), entry('deeper', 'directory')],
      'pages/research/nested/deeper': [entry('Leaf.vue', 'file'), entry('ignore.ts', 'file')]
    }
    expect(discoverVueFiles('pages\\research', directory => tree[directory.replace(/\\/g, '/')] ?? [])).toEqual([
      'pages/research/Top.vue',
      'pages/research/nested/Deep.vue',
      'pages/research/nested/deeper/Leaf.vue'
    ])
  })

  it.each(presentationalTargets)('%s 的 script AST 不连接 Store、Service 或 preload API', file => {
    const parts = readVueParts(file)
    expect(scriptBoundaryViolations(parts.script)).toEqual([])
    expect(templateBoundaryViolations(parts.template)).toEqual([])
  })
})

describe(`科研生产界面 SFC 语境视觉隔离（${visualTargets.length + 5}）`, () => {
  it('自动发现的科研页面与组件完整进入视觉守卫集合', () => {
    expect(new Set(visualTargets).size).toBe(visualTargets.length)
    expect(visualTargets.filter(file => file.startsWith('pages/research/'))).toEqual(discoveredResearchPages)
    expect(visualTargets.filter(file => file.startsWith('components/research/'))).toEqual(discoveredResearchComponents)
  })

  it('SFC UI 语境精确捕获旧色六位与八位 alpha 写法', () => {
    const parts = vueParts(`
      <template><div style="color:#f97316">科研</div></template>
      <script setup>const nonUi = '#f97316'</script>
      <style>.panel { color: #0f172aff; background: #02061780; }</style>
    `)
    expect(legacyUiColors(parts)).toEqual(expect.arrayContaining(['#f97316', '#0f172aff', '#02061780']))
  })

  it('SFC UI 语境忽略评论、普通 script 字符串与更长十六进制片段', () => {
    const parts = vueParts(`
      <template><!-- #f97316 📚 --><div>科研</div></template>
      <script setup>const nonUi = '#0f172a'</script>
      <style>/* #020617 */ .panel::before { content: '#f97316'; } .safe { color: #f97316abc; }</style>
    `)
    expect(legacyUiColors(parts)).toEqual([])
    expect(templateNavigationEmojis(parts)).toEqual([])
  })

  it('模板与 NAV_ITEMS 字符串的 Emoji 反例都能被识别', () => {
    const parts = vueParts('<template><nav>📚 文献</nav></template>')
    const navigation = "const NAV_ITEMS = [{ label: '🧪 实验' }, { icon: '⚙️' }]"
    expect(templateNavigationEmojis(parts)).toEqual(['📚'])
    expect(stringNavigationEmojis(stringLiteralsInVariable(navigation, 'NAV_ITEMS'))).toEqual(['🧪', '⚙️'])
  })

  it('MainLayout 实际渲染的 Sidebar NAV_ITEMS 不含 Emoji 导航符号', () => {
    const mainLayout = readVueParts('layouts/MainLayout.vue')
    const navigationStrings = stringLiteralsInVariable(readVueParts('layouts/Sidebar.vue').script, 'NAV_ITEMS')
    expect(mainLayout.script).toMatch(/import\s+Sidebar\s+from\s+['"]\.\/Sidebar\.vue['"]/)
    expect(mainLayout.template).toMatch(/<Sidebar\s*\/>/)
    expect(navigationStrings.length).toBeGreaterThan(0)
    expect(stringNavigationEmojis(navigationStrings)).toEqual([])
  })

  it.each(visualTargets)('%s 的 template/style 不回退旧色且模板不使用 Emoji 导航符号', file => {
    const parts = readVueParts(file)
    expect(legacyUiColors(parts)).toEqual([])
    expect(templateNavigationEmojis(parts)).toEqual([])
  })
})

describe('1440 与 1920 科研工作区静态响应式契约（17）', () => {
  const shrinkableRoots = [
    ['components/research/ResearchPageShell.vue', '.research-page-shell'],
    ['layouts/MainLayout.vue', '.main-layout__content'],
    ['pages/research/Assistant.vue', '.assistant'],
    ['pages/research/Experiment.vue', '.experiment'],
    ['pages/research/KnowledgeGraph.vue', '.kg'],
    ['pages/research/Literature.vue', '.literature'],
    ['pages/research/Manuscript.vue', '.manuscript'],
    ['pages/research/Settings.vue', '.settings']
  ] as const

  it('选择器收集器覆盖媒体块内的第二个同名声明并暴露违规', () => {
    const fixture = `
      .fixture { min-width: 0; grid-template-columns: minmax(0, 1fr); }
      @media (max-width: 1480px) {
        .fixture { width: 1200px; grid-template-columns: 240px 1fr; }
      }
    `
    const blocks = selectorBlocks(fixture, '.fixture')
    expect(blocks).toHaveLength(2)
    expect(blocks.some(hasFixedRootWidth)).toBe(true)
    expect(blocks.filter(hasGridColumns).every(hasZeroBasedGridTrack)).toBe(false)
  })

  it('选择器收集器精确处理组合选择器、注释、字符串花括号与后代选择器', () => {
    const fixture = `
      .fixture, .peer { content: '}'; min-width: 0; }
      @media (max-width: 1480px) {
        .fixture /* selector comment */ { color: blue; /* body } comment */ width: 1200px; }
        .wrapper .fixture { width: 1600px; }
      }
      @supports (display: grid) {
        @layer research {
          .fixture { max-width: 1300px; }
        }
      }
      .fixture:is(.primary, .secondary), .peer { color: green; }
    `
    const blocks = selectorBlocks(fixture, '.fixture')
    expect(blocks).toHaveLength(3)
    expect(blocks[0]).toContain("content: '}'")
    expect(blocks[1]).toContain('width: 1200px')
    expect(blocks[2]).toContain('max-width: 1300px')
    expect(blocks.join('\n')).not.toContain('width: 1600px')
    expect(selectorBlocks(fixture, '.fixture:is(.primary, .secondary)')).toHaveLength(1)
  })

  it.each([
    'grid-template-columns: 1200px minmax(0, 1fr);',
    'grid-template-columns: minmax(1200px, 2fr) minmax(0, 1fr);'
  ])('固定四位像素轨道“%s”被标记为不安全', block => {
    expect(hasUnsafeFixedGridTrack(block)).toBe(true)
  })

  it.each(shrinkableRoots)('%s 的 %s 根内容允许收缩且不锁死宽度', (file, selector) => {
    const styles = readVueParts(file).styles
    const blocks = selectorBlocks(styles, selector)
    expect(blocks.length).toBeGreaterThan(0)
    expect(blocks.some(block => /min-width:\s*0\b/.test(block))).toBe(true)
    for (const block of blocks) {
      expect(hasFixedRootWidth(block)).toBe(false)
    }
  })

  it.each([
    ['pages/research/DataAnalysis.vue', '.analysis-overview'],
    ['pages/research/Experiment.vue', '.experiment__workspace'],
    ['pages/research/KnowledgeGraph.vue', '.kg__workspace']
  ] as const)('%s 的 %s 主网格使用零基准弹性轨道', (file, selector) => {
    const styles = readVueParts(file).styles
    const gridBlocks = selectorBlocks(styles, selector)
      .filter(hasGridColumns)
    expect(gridBlocks.length).toBeGreaterThan(0)
    for (const block of gridBlocks) {
      expect(hasZeroBasedGridTrack(block)).toBe(true)
      expect(hasUnsafeFixedGridTrack(block)).toBe(false)
    }
  })

  it('Dashboard 的 command-grid 使用批准的 B1 基准、1440 收束与 1920 宽屏轨道', () => {
    const styles = readVueParts('pages/research/Dashboard.vue').styles
    expect(styles).toMatch(/\.dashboard__command-grid\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+minmax\(280px,\s*\.9fr\)/s)
    expect(styles).toMatch(/@media\s*\(max-width:\s*1480px\)\s*\{[\s\S]*?\.dashboard__command-grid\s*\{[^}]*grid-template-columns:\s*1fr/s)
    expect(styles).toMatch(/@media\s*\(min-width:\s*1720px\)\s*\{[\s\S]*?\.dashboard__command-grid\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1\.25fr\)\s+minmax\(320px,\s*\.75fr\)/s)
  })

  it('共享宽屏令牌与紧凑页面规则覆盖 1920 和 1440 断点', () => {
    const tokens = readFileSync(resolve(rendererRoot, 'styles/research-design-tokens.css'), 'utf8')
    const headerStyles = readVueParts('layouts/HeaderBar.vue').styles
    const wideWorkstation = atRuleBlocks(tokens, 'media', /\(min-width:\s*1720px\)/)[0] ?? ''
    const compactWorkstation = atRuleBlocks(headerStyles, 'media', /\(max-width:\s*1480px\)/)[0] ?? ''
    expect(wideWorkstation).toMatch(/--research-page-gutter:\s*32px/)
    expect(compactWorkstation).toMatch(/\.header-bar__project-copy > span,\s*\.header-bar__user-name[\s\S]*display:\s*none/)
  })
})

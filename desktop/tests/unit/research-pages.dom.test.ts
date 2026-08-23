// @vitest-environment happy-dom
import { createPinia, setActivePinia, type Pinia } from 'pinia'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import type { Component } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AgentCard from '@/components/research/AgentCard.vue'
import AgentCenter from '@/pages/research/AgentCenter.vue'
import Assistant from '@/pages/research/Assistant.vue'
import { useAgentStore } from '@/stores/research/agent.store'
import { useWorkflowStore } from '@/stores/research/workflow.store'
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
  ] as const)('阶段 %i 显示“%s”并以真实等待态初始化', (index, label) => {
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
  ] as const)('%s 使用“%s”中文名称且空任务不伪造结果', (kind, label) => {
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

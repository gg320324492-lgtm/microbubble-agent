// Scientific Workflow Templates — 预定义多智能体工作流。
import type { AgentRole } from '../../shared/agents/agent-schema'

export interface WorkflowTemplate {
  id: string
  name: string
  description: string
  steps: Array<{ agent: AgentRole; action: string }>
}

export const WORKFLOW_TEMPLATES: readonly WorkflowTemplate[] = Object.freeze([
  {
    id: 'literature-review',
    name: '文献综述',
    description: '文献检索 → 证据汇总 → 综述生成',
    steps: [
      { agent: 'LiteratureAgent', action: '检索相关文献' },
      { agent: 'LiteratureAgent', action: '提取关键证据' },
      { agent: 'ReviewerAgent', action: '评估证据质量' }
    ]
  },
  {
    id: 'experiment-design',
    name: '实验设计',
    description: '机理分析 → 变量设计 → 对照组规划',
    steps: [
      { agent: 'MechanismAgent', action: '分析机理' },
      { agent: 'ExperimentAgent', action: '设计变量与分组' },
      { agent: 'ReviewerAgent', action: '审查设计合理性' }
    ]
  },
  {
    id: 'paper-writing',
    name: '论文写作',
    description: '初稿撰写 → SCI审稿 → 修改建议',
    steps: [
      { agent: 'WritingAgent', action: '生成初稿' },
      { agent: 'ReviewerAgent', action: 'SCI审稿' },
      { agent: 'WritingAgent', action: '根据审稿意见修改' }
    ]
  },
  {
    id: 'complete-research',
    name: '完整研究流程',
    description: '文献调研 → 实验设计 → 数据分析 → 论文写作 → 审稿',
    steps: [
      { agent: 'CoordinatorAgent', action: '调度研究流程' },
      { agent: 'LiteratureAgent', action: '文献调研与证据汇总' },
      { agent: 'MechanismAgent', action: '机理分析' },
      { agent: 'ExperimentAgent', action: '实验设计' },
      { agent: 'DataAnalysisAgent', action: '数据分析与建模' },
      { agent: 'WritingAgent', action: '论文初稿撰写' },
      { agent: 'ReviewerAgent', action: 'SCI审稿' }
    ]
  }
])

export function getWorkflowTemplate(id: string): WorkflowTemplate | null {
  return WORKFLOW_TEMPLATES.find(w => w.id === id) ?? null
}

export function listWorkflowTemplates(): WorkflowTemplate[] {
  return [...WORKFLOW_TEMPLATES]
}

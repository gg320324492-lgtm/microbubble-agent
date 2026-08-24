// Project Templates — 3 个预定义科研项目工作流。
import type { ScientificWorkflow } from '../../shared/project/workflow-schema'

export const PROJECT_TEMPLATES: readonly ScientificWorkflow[] = Object.freeze([
  {
    id: 'new-paper',
    name: '新论文研究',
    trigger: 'project.started',
    status: 'draft',
    steps: [
      { id: 's1', type: 'literature', agent: 'LiteratureAgent', nextSteps: ['s2'] },
      { id: 's2', type: 'analysis', agent: 'MechanismAgent', condition: 'literature_done', nextSteps: ['s3'] },
      { id: 's3', type: 'experiment', agent: 'ExperimentAgent', condition: 'hypothesis_ready', nextSteps: ['s4'] },
      { id: 's4', type: 'analysis', agent: 'DataAnalysisAgent', condition: 'experiment_done', nextSteps: ['s5'] },
      { id: 's5', type: 'writing', agent: 'WritingAgent', nextSteps: ['s6'] },
      { id: 's6', type: 'review', agent: 'ReviewerAgent', nextSteps: [] }
    ]
  },
  {
    id: 'dataset-analysis',
    name: '现有数据集分析',
    trigger: 'data.uploaded',
    status: 'draft',
    steps: [
      { id: 'd1', type: 'analysis', agent: 'DataAnalysisAgent', nextSteps: ['d2'] },
      { id: 'd2', type: 'analysis', agent: 'DataAnalysisAgent', condition: 'quality_done', nextSteps: ['d3'] },
      { id: 'd3', type: 'modeling', agent: 'DataAnalysisAgent', condition: 'stats_done', nextSteps: ['d4'] },
      { id: 'd4', type: 'review', agent: 'MechanismAgent', nextSteps: [] }
    ]
  },
  {
    id: 'experimental-optimization',
    name: '实验条件优化',
    trigger: 'analysis.completed',
    status: 'draft',
    steps: [
      { id: 'e1', type: 'analysis', agent: 'DataAnalysisAgent', nextSteps: ['e2'] },
      { id: 'e2', type: 'analysis', agent: 'MechanismAgent', condition: 'baseline_ready', nextSteps: ['e3'] },
      { id: 'e3', type: 'experiment', agent: 'ExperimentAgent', nextSteps: ['e4'] },
      { id: 'e4', type: 'analysis', agent: 'DataAnalysisAgent', nextSteps: [] }
    ]
  }
])

export function getProjectTemplate(id: string): ScientificWorkflow | null {
  return PROJECT_TEMPLATES.find(t => t.id === id) ?? null
}
export function listProjectTemplates(): ScientificWorkflow[] { return [...PROJECT_TEMPLATES] }

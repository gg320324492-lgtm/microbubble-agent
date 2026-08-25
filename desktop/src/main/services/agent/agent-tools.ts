// Agent Tools Registry — Phase 8-M1-E
// 注册 6 个 scientific tools 到 tool-registry, LLM 可通过 toolName 调用.

import type { ScientificToolRegistry, ScientificToolMetadata, ScientificToolName } from './agent-schemas'
import { createScientificTools, type ScientificTools } from './scientific-tools'
import type { DatabaseService } from '../database.service'

const TOOL_METADATA: Record<ScientificToolName, ScientificToolMetadata> = {
  list_experiments: {
    name: 'list_experiments',
    description: '列出项目下的实验, 返回实验 ID / 名称 / 状态 / 测量点数.',
    parametersJson: '{"projectId":"string?","status":"string?","limit":"number?"}'
  },
  get_measurements: {
    name: 'get_measurements',
    description: '读取实验在某指标上的时间序列测量值. 限流 1000 条.',
    parametersJson: '{"experimentId":"string","metric":"string","startTime":"number?","endTime":"number?","limit":"number?"}'
  },
  get_samples: {
    name: 'get_samples',
    description: '列出实验下的样本, 含 batch / replicate / 关联测量数.',
    parametersJson: '{"experimentId":"string","batch":"string?","limit":"number?"}'
  },
  run_kinetic: {
    name: 'run_kinetic',
    description: '对实验某指标运行一级 / 零级 / 拟二级动力学 LSQ 拟合, 持久化到 analysis_results.',
    parametersJson: '{"experimentId":"string","model":"first-order|zero-order|pseudo-second-order","metric":"string"}'
  },
  run_statistics: {
    name: 'run_statistics',
    description: '计算实验某指标的描述性统计 (mean / std / median / outliers).',
    parametersJson: '{"experimentId":"string","metric":"string"}'
  },
  write_manuscript_section: {
    name: 'write_manuscript_section',
    description: '写入项目某章节的稿件内容, 可附 citations (analysisId / figureId / sampleId).',
    parametersJson: '{"projectId":"string","section":"string","content":"string","citations":"CitationRef[]?"}'
  }
}

class AgentTools implements ScientificToolRegistry {
  private readonly tools: ScientificTools

  constructor(getService: () => DatabaseService | null) {
    this.tools = createScientificTools(getService)
  }

  list(): ScientificToolMetadata[] {
    return Object.values(TOOL_METADATA)
  }

  invoke(name: string, params: Record<string, unknown>): Promise<unknown> {
    switch (name) {
      case 'list_experiments': return Promise.resolve(this.tools.listExperiments(params as never))
      case 'get_measurements': return Promise.resolve(this.tools.getMeasurements(params as never))
      case 'get_samples': return Promise.resolve(this.tools.getSamples(params as never))
      case 'run_kinetic': return Promise.resolve(this.tools.runKinetic(params as never))
      case 'run_statistics': return Promise.resolve(this.tools.runStatistics(params as never))
      case 'write_manuscript_section': return Promise.resolve(this.tools.writeManuscriptSection(params as never))
      default: throw new Error(`未知 scientific tool '${name}'`)
    }
  }
}

export function createAgentTools(getService: () => DatabaseService | null): ScientificToolRegistry {
  return new AgentTools(getService)
}

export { TOOL_METADATA }
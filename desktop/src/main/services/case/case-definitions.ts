// Case Definitions — Phase 10
// 3 个 canonical cases: O3 24h 降解 / pH 标定 / AI 文献综述.

import type { WorkflowStep } from '../workflow/types'

export interface CaseDefinition {
  id: string
  name: string
  description: string
  category: 'experiment' | 'calibration' | 'analysis'
  estimatedDurationMin: number
  templateId: string
  templateSteps: WorkflowStep[]
  /** 默认 parameters (Phase 10 replay 使用) */
  defaultParameters: Record<string, unknown>
  /** 内置样例数据文件 (相对路径, 主进程读取) */
  sampleDataPath: string | null
}

function buildO3DegradationSteps(): WorkflowStep[] {
  return [
    { id: 's1-start-device', name: '启动 O3 发生器', handler: { kind: 'device:command', args: { kind: 'start' } }, dependsOn: [], requiresApproval: false, timeoutMs: 30000, continueOnError: false },
    { id: 's2-import-data', name: '导入 24h 测量数据', handler: { kind: 'data:import.commit', args: {} }, dependsOn: ['s1-start-device'], requiresApproval: false, timeoutMs: 120000, continueOnError: false },
    { id: 's3-kinetic', name: '一级动力学拟合', handler: { kind: 'analysis:run.kinetic', args: { model: 'first-order', metric: 'O3' } }, dependsOn: ['s2-import-data'], requiresApproval: false, timeoutMs: 60000, continueOnError: true },
    { id: 's4-eln', name: '写实验记录 (ELN)', handler: { kind: 'manuscript:write', args: {} }, dependsOn: ['s3-kinetic'], requiresApproval: true, timeoutMs: 86400000, continueOnError: false }
  ]
}

function buildPhCalibrationSteps(): WorkflowStep[] {
  return [
    { id: 's1-calibrate', name: '标定 pH 计', handler: { kind: 'device:command', args: { kind: 'calibrate' } }, dependsOn: [], requiresApproval: true, timeoutMs: 60000, continueOnError: false },
    { id: 's2-eln', name: '记录标定结果', handler: { kind: 'manuscript:write', args: {} }, dependsOn: ['s1-calibrate'], requiresApproval: false, timeoutMs: 30000, continueOnError: false }
  ]
}

function buildAiLiteratureSteps(): WorkflowStep[] {
  return [
    { id: 's1-list-experiments', name: '列出实验', handler: { kind: 'data:sample.list', args: {} }, dependsOn: [], requiresApproval: false, timeoutMs: 30000, continueOnError: false },
    { id: 's2-eln', name: '写 Introduction', handler: { kind: 'manuscript:write', args: {} }, dependsOn: ['s1-list-experiments'], requiresApproval: true, timeoutMs: 86400000, continueOnError: false }
  ]
}

export const CASE_DEFINITIONS: CaseDefinition[] = [
  {
    id: 'case-001-o3-degradation',
    name: 'O3 24 小时降解实验',
    description: '24 小时臭氧降解实验: 启动 O3 发生器 → 导入 288 行 8 指标测量数据 → 一级动力学拟合 (R² > 0.9) → ELN 记录',
    category: 'experiment',
    estimatedDurationMin: 30,
    templateId: 'case-001-o3-degradation',
    templateSteps: buildO3DegradationSteps(),
    defaultParameters: {
      projectId: 'demo-project',
      mapping: { timestamp: 'timestamp', metric: 'metric', value: 'value', unit: 'unit' },
      experimentName: 'O3 24h degradation case-001',
      fileHash: 'demo-o3-24h',
      model: 'first-order',
      metric: 'O3'
    },
    sampleDataPath: 'o3_24h_sample.csv'
  },
  {
    id: 'case-002-ph-calibration',
    name: 'pH 计标定',
    description: 'pH 计标定: 设备标定 (操作员审批) → 写入 ELN 标定结果',
    category: 'calibration',
    estimatedDurationMin: 5,
    templateId: 'case-002-ph-calibration',
    templateSteps: buildPhCalibrationSteps(),
    defaultParameters: {
      projectId: 'demo-project',
      deviceId: 'demo-ph-meter',
      deviceType: 'ph-meter',
      endpoint: 'mock://demo'
    },
    sampleDataPath: null
  },
  {
    id: 'case-003-ai-literature',
    name: 'AI 文献综述草稿',
    description: 'AI Agent 列实验 → 写 Introduction (审批后入库)',
    category: 'analysis',
    estimatedDurationMin: 10,
    templateId: 'case-003-ai-literature',
    templateSteps: buildAiLiteratureSteps(),
    defaultParameters: {
      projectId: 'demo-project',
      experimentId: 'demo-experiment',
      section: 'introduction',
      content: '## Introduction\n\nThis study investigates O3-based degradation using micro-nano bubble technology.\n\n### Background\n\nMicro-nano bubbles enhance mass transfer efficiency.'
    },
    sampleDataPath: null
  }
]

export function getCaseDefinition(id: string): CaseDefinition | null {
  return CASE_DEFINITIONS.find((c) => c.id === id) ?? null
}

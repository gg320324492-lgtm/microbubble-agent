// Case Definitions — Phase 10
// 3 个 canonical cases: O3 24h 降解 / pH 标定 / AI 文献综述.
//
// [类 20.191] 2026-08-27: 删所有 hardcoded 'demo-project' / 'demo-ph-meter' / 'demo-o3-24h' /
// 'demo-experiment' / 'mock://demo' / 'mock://localhost' 假 ID.
// 这些 ID 实际不存在于 members / projects / devices 表, 任何 case run 若没显式覆盖
// 都会 silently fail. 改为: 标记为 'MUST_BE_PROVIDED' 或干脆删除, 由 case launcher 显式注入.

import type { WorkflowStep } from '../workflow/types'
import { CASE_101_DEFINITION } from './case-101-definition'

export interface CaseDefinition {
  id: string
  name: string
  description: string
  category: 'experiment' | 'calibration' | 'analysis'
  estimatedDurationMin: number
  templateId: string
  templateSteps: WorkflowStep[]
  /** 默认 parameters (Phase 10 replay 使用). 真实值由 case launcher 显式注入. */
  defaultParameters: Record<string, unknown>
  /** 元数据 (pollutant / technology / reactorVolume / initialTC / ozoneFlow / temperature 等) */
  metadata?: Record<string, unknown>
  /** 内置样例数据文件 (相对路径, 主进程读取). null 表示 case 启动时必须选真实数据. */
  sampleDataPath: string | null
}

/** [类 20.191] case 启动时必须显式提供的参数 marker. */
const MUST_BE_PROVIDED = '__MUST_BE_PROVIDED__'

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
    description: '24 小时臭氧降解实验: 启动 O3 发生器 → 导入测量数据 → 一级动力学拟合 (R² > 0.9) → ELN 记录',
    category: 'experiment',
    estimatedDurationMin: 30,
    templateId: 'case-001-o3-degradation',
    templateSteps: buildO3DegradationSteps(),
    defaultParameters: {
      // [类 20.191] 删 'demo-project' / 'demo-o3-24h' 假 ID. case launcher 必须显式提供 projectId + fileHash.
      projectId: MUST_BE_PROVIDED,
      mapping: { timestamp: 'timestamp', metric: 'metric', value: 'value', unit: 'unit' },
      experimentName: '',
      fileHash: MUST_BE_PROVIDED,
      model: 'first-order',
      metric: 'O3'
    },
    sampleDataPath: null
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
      // [类 20.191] 删 'demo-project' / 'demo-ph-meter' / 'mock://demo'. case launcher 显式注入.
      projectId: MUST_BE_PROVIDED,
      deviceId: MUST_BE_PROVIDED,
      deviceType: 'ph-meter',
      endpoint: MUST_BE_PROVIDED
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
      // [类 20.191] 删 'demo-project' / 'demo-experiment'. case launcher 显式注入.
      projectId: MUST_BE_PROVIDED,
      experimentId: MUST_BE_PROVIDED,
      section: 'introduction',
      content: ''
    },
    sampleDataPath: null
  },
  CASE_101_DEFINITION
]

export function getCaseDefinition(id: string): CaseDefinition | null {
  return CASE_DEFINITIONS.find((c) => c.id === id) ?? null
}

/** [类 20.191] 检查 case 启动参数是否齐全. 若有 MUST_BE_PROVIDED 占位符, 报错. */
export function validateCaseParameters(caseId: string, params: Record<string, unknown>): { ok: true } | { ok: false; missing: string[] } {
  const def = getCaseDefinition(caseId)
  if (!def) return { ok: false, missing: ['case-not-found'] }
  const missing: string[] = []
  for (const [key, value] of Object.entries(def.defaultParameters)) {
    if (value === MUST_BE_PROVIDED) {
      // 启动时这个字段必须有真实值 (不能是 placeholder)
      if (params[key] === undefined || params[key] === null || params[key] === '') {
        missing.push(key)
      }
    }
  }
  return missing.length === 0 ? { ok: true } : { ok: false, missing }
}

// Case-101 Definition — Phase 10.5
// O3-MNB tetracycline degradation (real research data validation)
//
// [类 20.191] 2026-08-27: 删 'demo-project' 假 projectId. case launcher 必须显式提供.
// fileHash: 'case-101-real' 也是 placeholder (看起来像真但其实不存在), 同样改成 MUST_BE_PROVIDED.

import type { WorkflowStep } from '../workflow/types'
import type { CaseDefinition } from './case-definitions'

function buildCase101Steps(): WorkflowStep[] {
  return [
    { id: 's1-import', name: '导入 7 个指标的实测数据', handler: { kind: 'data:import.commit', args: {} }, dependsOn: [], requiresApproval: false, timeoutMs: 120000, continueOnError: false },
    { id: 's2-kinetic', name: 'TC 一级动力学拟合', handler: { kind: 'analysis:run.kinetic', args: { model: 'first-order', metric: 'TC' } }, dependsOn: ['s1-import'], requiresApproval: false, timeoutMs: 60000, continueOnError: true },
    { id: 's3-stats', name: '各指标描述性统计', handler: { kind: 'analysis:run.statistics', args: { metric: 'TC' } }, dependsOn: ['s1-import'], requiresApproval: false, timeoutMs: 30000, continueOnError: true },
    { id: 's4-eln', name: '写实验记录 (ELN)', handler: { kind: 'manuscript:write', args: {} }, dependsOn: ['s2-kinetic', 's3-stats'], requiresApproval: true, timeoutMs: 86400000, continueOnError: false }
  ]
}

// 复用 case-definitions.ts 的 MUST_BE_PROVIDED 常量 (避免重复定义)
const MUST_BE_PROVIDED = '__MUST_BE_PROVIDED__'

export const CASE_101_DEFINITION: CaseDefinition = {
  id: 'case-101-o3-mnb-tetracycline',
  name: 'O3-MNB tetracycline degradation',
  description: 'O3 微纳米气泡降解四环素 (实测数据验证): 导入 7 个指标 (TC / O3 / TOC / UV254 / DO / ORP / pH) → 一级动力学拟合 (R² > 0.95) → 描述性统计 → ELN',
  category: 'experiment',
  estimatedDurationMin: 30,
  templateId: 'case-101-o3-mnb-tetracycline',
  templateSteps: buildCase101Steps(),
  defaultParameters: {
    projectId: MUST_BE_PROVIDED,
    experimentName: 'O3-MNB tetracycline degradation case-101',
    fileHash: MUST_BE_PROVIDED,
    model: 'first-order',
    metric: 'TC',
    mapping: { timestamp: 'timestamp', metric: 'metric', value: 'value', unit: 'unit' }
  },
  metadata: {
    pollutant: 'Tetracycline',
    technology: 'Ozone micro-nano bubbles',
    reactorVolume: '5 L',
    initialTC: '20 mg/L',
    ozoneFlow: '1.5 L/min',
    temperature: '25 C'
  },
  sampleDataPath: null
}

// Workflow Registry — Phase 9-B
// 注册内置模板.

import type { WorkflowTemplate } from './types'

let builtInTemplates: WorkflowTemplate[] = []
let extraTemplates: WorkflowTemplate[] = []

export function registerBuiltInTemplates(templates: WorkflowTemplate[]): void {
  builtInTemplates = templates
}

export function addTemplate(template: WorkflowTemplate): void {
  if (extraTemplates.find((t) => t.id === template.id)) return
  extraTemplates.push(template)
}

export function listTemplates(): WorkflowTemplate[] {
  return [...builtInTemplates, ...extraTemplates]
}

export function getTemplate(id: string): WorkflowTemplate | null {
  return listTemplates().find((t) => t.id === id) ?? null
}

export const BUILTIN_TEMPLATES: WorkflowTemplate[] = [
  {
    id: 'data-import-and-analyze',
    name: '数据导入与动力学分析',
    description: '导入 CSV/XLSX 数据, 自动运行一级动力学拟合, 输出 R² / k / half-life',
    category: 'mixed',
    builtIn: true,
    createdBy: null,
    schemaVersion: 1,
    createdAt: 0,
    steps: [
      { id: 's1-import', name: '导入数据', handler: { kind: 'data:import.commit', args: {} }, dependsOn: [], requiresApproval: false, timeoutMs: 60000, continueOnError: false },
      { id: 's2-stats', name: '描述性统计', handler: { kind: 'analysis:run.statistics', args: { metric: 'O3' } }, dependsOn: ['s1-import'], requiresApproval: false, timeoutMs: 30000, continueOnError: true },
      { id: 's3-kinetic', name: '一级动力学拟合', handler: { kind: 'analysis:run.kinetic', args: { model: 'first-order', metric: 'O3' } }, dependsOn: ['s1-import'], requiresApproval: false, timeoutMs: 30000, continueOnError: true },
      { id: 's4-approve', name: '结果审批', handler: { kind: 'human:approval', args: { prompt: '请确认分析结果' } }, dependsOn: ['s3-kinetic'], requiresApproval: true, timeoutMs: 86400000, continueOnError: false }
    ]
  },
  {
    id: 'o3-degradation-test',
    name: 'O3 降解实验',
    description: '启动臭氧发生器, 等待 1h 采样, 导入数据, 计算统计',
    category: 'device',
    builtIn: true,
    createdBy: null,
    schemaVersion: 1,
    createdAt: 0,
    steps: [
      { id: 's1-start', name: '启动 O3 发生器', handler: { kind: 'device:command', args: { kind: 'start' } }, dependsOn: [], requiresApproval: true, timeoutMs: 30000, continueOnError: false },
      { id: 's2-wait', name: '等待 1 小时', handler: { kind: 'delay', args: { ms: 3600000 } }, dependsOn: ['s1-start'], requiresApproval: false, timeoutMs: 3600000, continueOnError: false },
      { id: 's3-import', name: '导入数据', handler: { kind: 'data:import.commit', args: {} }, dependsOn: ['s2-wait'], requiresApproval: false, timeoutMs: 60000, continueOnError: false }
    ]
  },
  {
    id: 'manuscript-section-draft',
    name: '论文章节起草',
    description: 'AI Agent 调用 LLM 工具, 起草 Introduction 章节, 写入 manuscripts 表',
    category: 'manuscript',
    builtIn: true,
    createdBy: null,
    schemaVersion: 1,
    createdAt: 0,
    steps: [
      { id: 's1-agent', name: 'AI 生成草稿', handler: { kind: 'agent:tool.invoke', args: { name: 'get_measurements' } }, dependsOn: [], requiresApproval: false, timeoutMs: 60000, continueOnError: false },
      { id: 's2-write', name: '写入 Introduction', handler: { kind: 'manuscript:write', args: { section: 'introduction' } }, dependsOn: ['s1-agent'], requiresApproval: true, timeoutMs: 86400000, continueOnError: false }
    ]
  },
  {
    id: 'device-calibration',
    name: '设备标定',
    description: '标定 pH 计 + 读回测量值 + 操作员确认',
    category: 'device',
    builtIn: true,
    createdBy: null,
    schemaVersion: 1,
    createdAt: 0,
    steps: [
      { id: 's1-calibrate', name: '标定 pH 计', handler: { kind: 'device:command', args: { kind: 'calibrate' } }, dependsOn: [], requiresApproval: true, timeoutMs: 60000, continueOnError: false },
      { id: 's2-read', name: '读回测量值', handler: { kind: 'device:command', args: { kind: 'calibrate' } }, dependsOn: ['s1-calibrate'], requiresApproval: false, timeoutMs: 30000, continueOnError: false }
    ]
  }
]

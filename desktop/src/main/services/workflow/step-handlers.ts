// Step Handlers — Phase 9-B
// 7 个内置 step handler 委托到 Phase 8 服务.

import type { DatabaseService } from '../database.service'

export interface StepHandlerContext {
  db: () => DatabaseService | null
  broadcast?: (event: { type: string; payload: unknown }) => void
}

export type StepHandlerResult = { ok: true; data: unknown } | { ok: false; error: string }

export type StepHandlerFn = (
  input: Record<string, unknown>,
  ctx: StepHandlerContext
) => Promise<StepHandlerResult>

export const stepHandlers: Record<string, StepHandlerFn> = {
  'data:sample.list': async (input, ctx) => {
    const svc = ctx.db()
    if (!svc) return { ok: false, error: '数据库未就绪' }
    const experimentId = String(input.experimentId ?? '')
    if (!experimentId) return { ok: false, error: 'experimentId 缺失' }
    const samples = svc.samples.listByExperiment(experimentId)
    return { ok: true, data: { experimentId, count: samples.length, samples } }
  },

  'data:import.commit': async (input, ctx) => {
    const svc = ctx.db()
    if (!svc) return { ok: false, error: '数据库未就绪' }
    try {
      const result = svc.importSvc.engine.commit({
        projectId: String(input.projectId ?? ''),
        experimentName: String(input.experimentName ?? 'imported-experiment'),
        mapping: (input.mapping ?? {}) as never,
        raw: input.raw as never,
        fileHash: String(input.fileHash ?? 'unknown'),
        importedBy: input.importedBy as string | undefined
      })
      return { ok: true, data: result }
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : 'import 失败' }
    }
  },

  'analysis:run.kinetic': async (input, ctx) => {
    const svc = ctx.db()
    if (!svc) return { ok: false, error: '数据库未就绪' }
    try {
      const id = svc.analysisEngine.runKinetic(
        String(input.experimentId ?? ''),
        input.model as 'first-order' | 'zero-order' | 'pseudo-second-order',
        String(input.metric ?? '')
      )
      return { ok: true, data: { analysisId: id } }
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : 'kinetic 失败' }
    }
  },

  'analysis:run.statistics': async (input, ctx) => {
    const svc = ctx.db()
    if (!svc) return { ok: false, error: '数据库未就绪' }
    try {
      const result = svc.analysisEngine.statistics(
        String(input.experimentId ?? ''),
        String(input.metric ?? '')
      )
      return { ok: true, data: result }
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : '统计失败' }
    }
  },

  'manuscript:write': async (input, ctx) => {
    const svc = ctx.db()
    if (!svc) return { ok: false, error: '数据库未就绪' }
    try {
      const result = await svc.agent.invokeTool('write_manuscript_section', {
        projectId: input.projectId,
        section: input.section,
        content: input.content,
        citations: input.citations
      })
      return { ok: true, data: result }
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : 'manuscript 写入失败' }
    }
  },

  'device:command': async (input, ctx) => {
    const svc = ctx.db()
    if (!svc) return { ok: false, error: '数据库未就绪' }
    const config = {
      deviceId: String(input.deviceId ?? ''),
      deviceType: input.deviceType as 'ozone-generator' | 'pump' | 'reactor' | 'sensor' | 'ph-meter' | 'do-meter' | 'orp-meter' | 'flow-meter' | 'power-meter',
      // [类 20.191] 2026-08-27: 删 'mock://localhost' 假 endpoint fallback. 若 input 没传 endpoint,
      // 直接报错要求提供 (而不是悄悄走 mock driver). 真实协议 driver 会拒绝 mock:// scheme.
      endpoint: String(input.endpoint ?? '')
    }
    if (!config.deviceId) return { ok: false, error: 'deviceId 缺失' }
    if (!config.endpoint) return { ok: false, error: 'endpoint 缺失 (case launcher 必须显式提供真实设备协议 URL, e.g. modbus://192.168.1.10:502)' }
    try {
      const result = await svc.deviceSvc.command(config as never, {
        kind: input.kind as 'set-setpoint' | 'start' | 'stop' | 'calibrate' | 'reset-alarm',
        metric: input.metric as string | undefined,
        value: input.value as number | undefined,
        reason: input.reason as string | undefined,
        operator: input.operator as string | undefined
      })
      return result.status === 'ok' ? { ok: true, data: result } : { ok: false, error: result.message }
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : '设备命令失败' }
    }
  },

  'agent:tool.invoke': async (input, ctx) => {
    const svc = ctx.db()
    if (!svc) return { ok: false, error: '数据库未就绪' }
    try {
      const result = await svc.agent.invokeTool(String(input.name ?? ''), (input.params ?? {}) as Record<string, unknown>)
      return { ok: true, data: result }
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : 'agent 工具失败' }
    }
  },

  'delay': async (input) => {
    const ms = Number(input.ms ?? 0)
    if (!Number.isFinite(ms) || ms < 0) return { ok: false, error: 'invalid delay ms' }
    if (ms > 0) await new Promise<void>((resolve) => setTimeout(resolve, ms))
    return { ok: true, data: { slept: ms } }
  },

  'human:approval': async () => ({ ok: false, error: 'HUMAN_APPROVAL_PENDING' })
}

export function getStepHandler(kind: string): StepHandlerFn | null {
  return stepHandlers[kind] ?? null
}

// 循环与传输解耦（工单 M8-1 §3）— 纯数据消息流契约 + **编排式 mock**。
//
// 现状与目标：`AgentLoopService` 已经只依赖注入的 `StreamTurnFn`（不感知 HTTP / SSE 解析），
// 但「用手工编排的消息序列离线驱动完整循环」这项能力此前只存在于单个测试文件内部
// （agent-loop.test.ts 的局部 scriptStream），无法复用、也无法覆盖重试路径。
//
// 本模块把该能力提升为**产品侧可复用的契约**：
//   · TurnScriptStep —— 用纯数据描述一轮要发生什么（文本/思考/工具调用/失败/中止/延时）
//   · createScriptedStreamTurn —— 把脚本回放成 StreamTurnFn（时序注入，零真实 IO）
//   · createRetryingScriptedStreamTurn —— 再套一层提交边界重试，用于断言「重试路径」的循环行为
//
// 这样「正常 / 中止 / 失败并文 / 工具调用 / 重试」全部可离线穷举断言。

import {
  withCommitBoundaryRetry,
  parseRetryAfterMs,
  classifyLlmError,
  type LlmErrorKind,
  type RetryPolicy
} from './llm-retry'
import type { AgentContentBlock, StreamTurnFn, StreamTurnRequest, StreamTurnResult, ToolUseBlock } from '@shared/types'

/** 一轮的编排脚本（纯数据） */
export type TurnScriptStep =
  | { kind: 'text'; delta: string }
  | { kind: 'thinking'; delta: string }
  | { kind: 'tool'; id?: string; name: string; input: Record<string, unknown> }
  /** 该轮以失败告终（可带 HTTP 状态码 / 错误码 / 原始信息） */
  | { kind: 'fail'; status?: number; code?: string; message?: string; headers?: Record<string, string> }
  /** 该轮被中止（用户点停止） */
  | { kind: 'abort'; reason?: string }
  /** 回放时的等待（注入 sleep，便于断言时序） */
  | { kind: 'delay'; ms: number }
  /** 覆盖本轮的 stopReason（默认按是否有 tool 推导） */
  | { kind: 'stop'; reason: StreamTurnResult['stopReason'] }

export interface ScriptedStreamOptions {
  /** 单轮脚本；与 turns 二选一 */
  steps?: TurnScriptStep[]
  /** 多轮脚本：第 n 次调用用第 n 个；越界则复用最后一个 */
  turns?: TurnScriptStep[][]
  /** 时序注入（默认真实 setTimeout；测试传瞬时实现以断言调用顺序） */
  sleep?: (ms: number) => Promise<void>
  /** 每次调用前的钩子（断言轮次、请求内容） */
  onCall?: (call: number, req: StreamTurnRequest) => void
  /** 该轮的失败是否应被上层当作异常抛出（默认 true；false 则走「失败并文」形态） */
  throwOnFail?: boolean
}

export class ScriptedFailure extends Error {
  readonly status?: number
  readonly code?: string
  readonly headers?: Record<string, string>
  readonly aborted: boolean
  constructor(step: Extract<TurnScriptStep, { kind: 'fail' | 'abort' }>) {
    const aborted = step.kind === 'abort'
    super(step.kind === 'fail' ? (step.message ?? 'scripted failure') : (step.reason ?? 'scripted abort'))
    this.status = step.kind === 'fail' ? step.status : undefined
    this.code = step.kind === 'fail' ? step.code : 'ABORT_ERR'
    this.headers = step.kind === 'fail' ? step.headers : undefined
    this.aborted = aborted
  }
}

/** 把一段脚本回放成一轮结果（纯数据 → StreamTurnResult），可见事件通过 req.onEvent 实时抛出 */
export async function replaySteps(
  steps: readonly TurnScriptStep[],
  req: StreamTurnRequest,
  opts: { sleep?: (ms: number) => Promise<void>; throwOnFail?: boolean } = {}
): Promise<StreamTurnResult> {
  const sleep = opts.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)))
  let text = ''
  let thinking = ''
  const toolUses: ToolUseBlock[] = []
  const assistantBlocks: AgentContentBlock[] = []
  let stopOverride: StreamTurnResult['stopReason'] | undefined
  let toolSeq = 0

  for (const step of steps) {
    switch (step.kind) {
      case 'delay':
        await sleep(step.ms)
        break
      case 'thinking':
        thinking += step.delta
        req.onEvent({ kind: 'thinking', delta: step.delta })
        break
      case 'text':
        text += step.delta
        req.onEvent({ kind: 'text', delta: step.delta })
        break
      case 'tool': {
        toolSeq += 1
        const id = step.id ?? `toolu_scripted_${toolSeq}`
        toolUses.push({ id, name: step.name, input: step.input })
        break
      }
      case 'stop':
        stopOverride = step.reason
        break
      case 'fail':
      case 'abort':
        if (opts.throwOnFail === false) {
          // 「失败并文」形态：把失败信息当作正文尾部的一段提示，正常结束本轮
          text += text ? '\n\n[本轮中断]' : '[本轮中断]'
          req.onEvent({ kind: 'text', delta: '[本轮中断]' })
          break
        }
        throw new ScriptedFailure(step)
    }
  }

  if (text) assistantBlocks.push({ type: 'text', text })
  for (const tu of toolUses) assistantBlocks.push({ type: 'tool_use', id: tu.id, name: tu.name, input: tu.input })

  const stopReason: StreamTurnResult['stopReason'] =
    stopOverride ?? (toolUses.length > 0 ? 'tool_use' : text || thinking ? 'end_turn' : 'other')

  return { stopReason, text, thinking, toolUses, assistantBlocks }
}

/** 编排式 StreamTurnFn：按脚本驱动循环（离线、零真实 IO、时序可注入） */
export function createScriptedStreamTurn(opts: ScriptedStreamOptions): StreamTurnFn {
  const turns = opts.turns ?? (opts.steps ? [opts.steps] : [])
  let call = 0
  return async (_userId: string, _sessionId: string, req: StreamTurnRequest): Promise<StreamTurnResult> => {
    const script = turns[Math.min(call, turns.length - 1)] ?? []
    call += 1
    opts.onCall?.(call, req)
    return replaySteps(script, req, {
      ...(opts.sleep ? { sleep: opts.sleep } : {}),
      ...(opts.throwOnFail === undefined ? {} : { throwOnFail: opts.throwOnFail })
    })
  }
}

/**
 * 带提交边界重试的编排式 StreamTurnFn：
 * 用 `turns` 描述「每一次物理请求」的脚本（含 fail），从而离线断言重试路径 ——
 * 例如 [fail(429), text('ok')] 表示第一次 429、第二次成功。
 */
export function createRetryingScriptedStreamTurn(opts: ScriptedStreamOptions & {
  policy?: RetryPolicy
  now?: () => number
  random?: () => number
  onRetry?: (info: { attempt: number; delayMs: number; kind: LlmErrorKind }) => void
}): StreamTurnFn {
  const inner = createScriptedStreamTurn(opts)
  const now = opts.now ?? ((): number => Date.now())
  const sleep = opts.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)))
  return async (userId, sessionId, req) =>
    withCommitBoundaryRetry({
      ...(opts.policy ? { policy: opts.policy } : {}),
      now,
      ...(opts.random ? { random: opts.random } : {}),
      ...(opts.onRetry ? { onRetry: opts.onRetry } : {}),
      sleep,
      attempt: async (visible) => {
        // 把「首个可见 delta」桥接到提交边界：一旦有 text/thinking 就置位，此后失败不再重试
        const bridged: StreamTurnRequest = {
          ...req,
          onEvent: (e) => {
            visible(e.kind === 'text' ? 'text' : 'thinking')
            req.onEvent(e)
          }
        }
        return inner(userId, sessionId, bridged)
      },
      toFailure: (err) => {
        const e = err as ScriptedFailure
        const retryAfterMs = parseRetryAfterMs(e?.headers, now())
        return {
          kind: classifyLlmError({
            ...(e?.status === undefined ? {} : { status: e.status }),
            ...(e?.code === undefined ? {} : { code: e.code }),
            ...(e?.message === undefined ? {} : { message: e.message }),
            aborted: e?.aborted === true
          }),
          ...(retryAfterMs === undefined ? {} : { retryAfterMs })
        }
      }
    })
}

// 用量记账（V1）— 纯函数层，零依赖、离线可测。
//
// 归一化原则（对标 minimax-code llm-retry）：NaN / 负数 / 缺失一律归零，
// 并用 usageComplete 标记可信度——不做静默猜测，界面据此如实标注。
//
// 协议来源：
//   Anthropic：message_start.message.usage.input_tokens（含 cache_read_input_tokens）
//              message_delta.usage.output_tokens
//   OpenAI 兼容：chunk.usage.prompt_tokens / completion_tokens（部分网关放 choices[0].usage）

import type { TokenUsage } from '@shared/types'

export { formatTokens } from '@shared/usage'

export type { TokenUsage }

export const ZERO_USAGE: TokenUsage = {
  inputTokens: 0,
  outputTokens: 0,
  cacheReadTokens: 0,
  usageComplete: false
}

/** 单值归一化：非有限数、负数、非数字一律 → null（视为缺失） */
function toCount(value: unknown): number | null {
  const n = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : Number.NaN
  if (!Number.isFinite(n) || n < 0) return null
  return Math.floor(n)
}

/** 原始三元组 → 归一化用量（缺失/非法归零；两者齐备才标 complete） */
export function normalizeUsage(raw: {
  inputTokens?: unknown
  outputTokens?: unknown
  cacheReadTokens?: unknown
}): TokenUsage {
  const input = toCount(raw?.inputTokens)
  const output = toCount(raw?.outputTokens)
  const cache = toCount(raw?.cacheReadTokens)
  return {
    inputTokens: input ?? 0,
    outputTokens: output ?? 0,
    cacheReadTokens: cache ?? 0,
    usageComplete: input !== null && output !== null
  }
}

/**
 * 累加（会话级累计用）；complete 取与——任一轮不完整则整体标记不完整。
 * 入参容错：undefined / 缺字段一律按 0 处理（网关旧实现或假实现可能不带 usage）。
 */
export function addUsage(a: TokenUsage | undefined, b: TokenUsage | undefined): TokenUsage {
  const x = a ?? ZERO_USAGE
  const y = b ?? ZERO_USAGE
  return {
    inputTokens: (x.inputTokens ?? 0) + (y.inputTokens ?? 0),
    outputTokens: (x.outputTokens ?? 0) + (y.outputTokens ?? 0),
    cacheReadTokens: (x.cacheReadTokens ?? 0) + (y.cacheReadTokens ?? 0),
    usageComplete: (x.usageComplete ?? false) && (y.usageComplete ?? false)
  }
}

/** 从持久化的两列还原（DB 只存 input/output 两个整数） */
export function usageFromColumns(tokensIn: unknown, tokensOut: unknown): TokenUsage {
  const input = toCount(tokensIn)
  const output = toCount(tokensOut)
  return {
    inputTokens: input ?? 0,
    outputTokens: output ?? 0,
    cacheReadTokens: 0,
    usageComplete: input !== null && output !== null
  }
}

/** Anthropic SSE 片段 → 部分用量（message_start 给 input，message_delta 给 output） */
export function extractAnthropicUsage(json: unknown): Partial<{
  inputTokens: number
  outputTokens: number
  cacheReadTokens: number
}> {
  const j = json as {
    type?: string
    message?: { usage?: Record<string, unknown> }
    usage?: Record<string, unknown>
  } | null
  if (!j || typeof j !== 'object') return {}

  const out: { inputTokens?: number; outputTokens?: number; cacheReadTokens?: number } = {}

  // message_start：input_tokens / cache_read_input_tokens
  const startUsage = j.message?.usage
  if (startUsage) {
    const input = toCount(startUsage.input_tokens)
    const cache = toCount(startUsage.cache_read_input_tokens)
    if (input !== null) out.inputTokens = input
    if (cache !== null) out.cacheReadTokens = cache
  }

  // message_delta：output_tokens（也可能带 input_tokens，取到即用）
  if (j.usage) {
    const output = toCount(j.usage.output_tokens)
    const input = toCount(j.usage.input_tokens)
    const cache = toCount(j.usage.cache_read_input_tokens)
    if (output !== null) out.outputTokens = output
    if (input !== null) out.inputTokens = input
    if (cache !== null) out.cacheReadTokens = cache
  }

  return out
}

/** OpenAI 兼容 SSE 片段 → 部分用量（usage 可能在顶层或 choices[0]） */
export function extractOpenAiUsage(json: unknown): Partial<{
  inputTokens: number
  outputTokens: number
}> {
  const j = json as { usage?: Record<string, unknown>; choices?: { usage?: Record<string, unknown> }[] } | null
  if (!j || typeof j !== 'object') return {}
  const usage = j.usage ?? j.choices?.[0]?.usage
  if (!usage) return {}
  const out: { inputTokens?: number; outputTokens?: number } = {}
  const input = toCount(usage.prompt_tokens ?? usage.input_tokens)
  const output = toCount(usage.completion_tokens ?? usage.output_tokens)
  if (input !== null) out.inputTokens = input
  if (output !== null) out.outputTokens = output
  return out
}

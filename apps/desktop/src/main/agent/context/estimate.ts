// 上下文 token 估算（工单 M8-2 §1）— 纯函数，零 Electron / 零依赖 / 离线可穷举。
//
// 为什么需要：会话级预算管理必须先能「量出」上下文有多大。禁止引入 tiktoken 等依赖，
// 故用启发式估算，并要求**保守方向（宁高勿低）** —— 提前触发裁切好过撑爆窗口。
//
// 启发式口径：
//   · CJK（含中日韩与全角标点）：约 1 token / 字（真实通常 0.6–1，取上限即保守）
//   · 拉丁字母/数字：约 4 字符 / token，但**逐段向上取整**（短段不会算成 0）
//   · JSON / 代码里的标点符号：token 密度高，按 1 token / 2 字符计（比 4 字符/token 保守一倍）
//   · 换行与空白：连续空白按 1 token 计（真实会被合并，但按保守计）
//   · 结构开销：每条消息 +4（role/分隔），每个 tool_use +12，每个 tool_result +8
//   · 全局安全系数 1.15，最终向上取整
//
// 误差目标 ±20% 内即可满足「提前触发」的策略需要。

/** 全局保守系数（估算值乘以此数再取整） */
export const SAFETY_FACTOR = 1.15
/** 每条消息的结构开销（role 标记、分隔符等） */
export const PER_MESSAGE_OVERHEAD = 4
/** 每个 tool_use 块的结构开销（工具名 + 参数包裹） */
export const PER_TOOL_USE_OVERHEAD = 12
/** 每个 tool_result 块的结构开销（tool_use_id + 包裹） */
export const PER_TOOL_RESULT_OVERHEAD = 8

export type EstimateSegment =
  | { kind: 'text'; text: string }
  | { kind: 'thinking'; text: string }
  | { kind: 'tool_use'; name: string; input: unknown }
  | { kind: 'tool_result'; text: string; isError?: boolean }

export interface EstimateMessage {
  role: 'system' | 'user' | 'assistant'
  segments: EstimateSegment[]
}

export interface MessageEstimate {
  index: number
  role: string
  tokens: number
  bytes: number
  /** 该消息里工具块的数量（用于诊断） */
  toolUses: number
  toolResults: number
}

export interface ContextEstimate {
  messages: MessageEstimate[]
  total: number
  bytes: number
  toolUses: number
  toolResults: number
}

/** CJK / 全角字符判定（这些字符的 token 密度远高于拉丁） */
export function isCjkCodePoint(cp: number): boolean {
  return (
    (cp >= 0x2e80 && cp <= 0x9fff) || // CJK 部首扩展 ~ 统一表意文字
    (cp >= 0xac00 && cp <= 0xd7af) || // 谚文音节
    (cp >= 0xf900 && cp <= 0xfaff) || // CJK 兼容表意
    (cp >= 0xfe30 && cp <= 0xfe4f) || // CJK 兼容形式（含全角标点）
    (cp >= 0xff00 && cp <= 0xffef) || // 全角字符
    (cp >= 0x3000 && cp <= 0x303f) || // CJK 标点
    (cp >= 0x20000 && cp <= 0x3ffff) // CJK 扩展 B+
  )
}

/** 标点/符号（JSON、代码里密度高） */
function isDenseSymbol(cp: number): boolean {
  if (cp >= 0x20 && cp <= 0x2f) return true // 空格 ! " # $ % & ' ( ) * + , - . /
  if (cp >= 0x3a && cp <= 0x40) return true // : ; < = > ? @
  if (cp >= 0x5b && cp <= 0x60) return true // [ \ ] ^ _ `
  if (cp >= 0x7b && cp <= 0x7e) return true // { | } ~
  return false
}

/**
 * 单段文本的 token 估算（保守：宁可高估）。
 * 逐字符分类累计，避免用「总字符数 / 4」这种对中英混排严重低估的算法。
 */
export function estimateTextTokens(text: string): number {
  if (!text) return 0
  let cjk = 0
  let dense = 0
  let latin = 0
  let whitespaceRuns = 0
  let inWhitespace = false

  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0
    if (cp === 0x20 || cp === 0x09 || cp === 0x0a || cp === 0x0d) {
      if (!inWhitespace) {
        whitespaceRuns += 1
        inWhitespace = true
      }
      continue
    }
    inWhitespace = false
    if (isCjkCodePoint(cp)) cjk += 1
    else if (isDenseSymbol(cp)) dense += 1
    else latin += 1
  }

  const raw = cjk * 1 + dense / 2 + Math.ceil(latin / 4) + whitespaceRuns
  return Math.ceil(raw * SAFETY_FACTOR)
}

/** 单个块的 token 估算 */
export function estimateSegmentTokens(segment: EstimateSegment): number {
  switch (segment.kind) {
    case 'text':
    case 'thinking':
      return estimateTextTokens(segment.text)
    case 'tool_use': {
      let inputText = ''
      try {
        inputText = typeof segment.input === 'string' ? segment.input : JSON.stringify(segment.input ?? {})
      } catch {
        inputText = String(segment.input)
      }
      return estimateTextTokens(segment.name) + estimateTextTokens(inputText) + PER_TOOL_USE_OVERHEAD
    }
    case 'tool_result':
      return estimateTextTokens(segment.text) + PER_TOOL_RESULT_OVERHEAD + (segment.isError ? 2 : 0)
  }
}

/** UTF-8 字节长度（诊断用，与 token 估算独立） */
export function utf8Bytes(text: string): number {
  let n = 0
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0
    n += cp <= 0x7f ? 1 : cp <= 0x7ff ? 2 : cp <= 0xffff ? 3 : 4
  }
  return n
}

/** 单条消息估算 */
export function estimateMessageTokens(message: EstimateMessage): MessageEstimate {
  let tokens = PER_MESSAGE_OVERHEAD
  let bytes = 0
  let toolUses = 0
  let toolResults = 0
  for (const seg of message.segments) {
    tokens += estimateSegmentTokens(seg)
    if (seg.kind === 'text' || seg.kind === 'thinking') bytes += utf8Bytes(seg.text)
    else if (seg.kind === 'tool_result') bytes += utf8Bytes(seg.text)
    else {
      try {
        bytes += utf8Bytes(JSON.stringify(seg.input ?? {}))
      } catch {
        /* 忽略 */
      }
      toolUses += 1
    }
    if (seg.kind === 'tool_result') toolResults += 1
  }
  return { index: -1, role: message.role, tokens, bytes, toolUses, toolResults }
}

/** 整个上下文的估算（逐条 + 总量） */
export function estimateContext(messages: readonly EstimateMessage[]): ContextEstimate {
  const per: MessageEstimate[] = []
  let total = 0
  let bytes = 0
  let toolUses = 0
  let toolResults = 0
  messages.forEach((m, i) => {
    const e = estimateMessageTokens(m)
    e.index = i
    per.push(e)
    total += e.tokens
    bytes += e.bytes
    toolUses += e.toolUses
    toolResults += e.toolResults
  })
  return { messages: per, total, bytes, toolUses, toolResults }
}

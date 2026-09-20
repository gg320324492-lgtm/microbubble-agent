// 工具输出预算（工单 M8-1 §1）— 纯函数，零 Electron / 零 IO / 零依赖，离线可穷举断言。
//
// 存在意义：read_file / grep 返回大内容会直接撑爆上下文。此前 read_file 只有一个 256KB
// 的硬截断，且是 `buf.subarray(0, MAX)` —— 会把一个 UTF-8 多字节字符拦腰切断，产生乱码；
// grep 只有「最多 N 条匹配」，单条内容过长时仍会超预算。
//
// 本模块给出：
//   ① 按 **UTF-8 字节** 计量的预算（不是字符数，中文一字 3 字节）
//   ② 逐行贪心装入，**绝不在多字节字符中间切断**（fitUtf8Prefix/Suffix 回退到码点边界）
//   ③ 两种策略：prefix_lines（read_file：从头读，便于用 offset 续读）
//                head_tail_lines（grep：头 45% + 尾 55%，保留首尾上下文）
//   ④ 截断后附**结构化续读提示**（写进模型可见的文本尾部）—— 模型无需人类提示即知如何续读
//
// 对标出处（报告 §7）：模式借鉴 minimax-code `packages/agent-tools/src/desktop/output-limit.ts`
// （MIT）。本实现为独立编写：不引入其类型体系（@mavis/agent-core），
// 命名/接口按本项目 ToolResult 约定重写，常量沿用其 24KB/16KB 与 45/55 比例。

/** read_file 正文预算（字节） */
export const READ_TEXT_MAX_BYTES = 24 * 1024
/** grep 输出预算（字节） */
export const GREP_CONTENT_MAX_BYTES = 16 * 1024
/** head_tail 策略中头部占比（其余给尾部） */
export const HEAD_TAIL_HEAD_RATIO = 0.45
/** 续读时建议的每次读取行数（写进提示，帮助模型一次续读到合适粒度） */
export const CONTINUATION_SUGGESTED_LINES = 2000

/** 首轮预算用的占位提示（仅用于估一个起始预算，真实提示随后收敛计算） */
const PLACEHOLDER_NOTICE = '[已截断：原始 0000000000 字节，输出上限 00000 字节；已保留开头 00000 行与结尾 00000 行，中间省略约 0000000 行。继续读取请缩小搜索范围或改用更精确的 pattern]'

export type OutputLimitStrategy = 'prefix_lines' | 'head_tail_lines'
export type OutputOffsetUnit = 'line'

export interface OutputTruncation {
  truncated: true
  hasMore: true
  strategy: OutputLimitStrategy
  originalBytes: number
  returnedBytes: number
  maxBytes: number
  /** 正文实际保留的行数（不含提示） */
  returnedBodyLines: number
  /** 下一次续读应使用的 offset（1 基行号）；head_tail 无单一续读点时省略 */
  nextOffset?: number
  offsetUnit?: OutputOffsetUnit
}

export interface LimitedText {
  text: string
  truncated: boolean
  truncation?: OutputTruncation
  returnedBodyLines: number
}

/** 续读提示的构造上下文 */
export interface ContinuationContext {
  /** 供提示里原样引用的工具调用片段（如 `read_file(path="a.md", offset=201, length=2000)`） */
  resumeCall?: string
  /** head_tail 策略下被省略的行数 */
  omittedLines?: number
  retainedHeadLines?: number
  retainedTailLines?: number
}

/** UTF-8 字节长度（中文一字 3 字节，不能按 .length 算） */
export function utf8ByteLength(text: string): number {
  let bytes = 0
  for (const ch of text) {
    const cp = ch.codePointAt(0) ?? 0
    if (cp <= 0x7f) bytes += 1
    else if (cp <= 0x7ff) bytes += 2
    else if (cp <= 0xffff) bytes += 3
    else bytes += 4
  }
  return bytes
}

/** 把文本截到不超过 maxBytes 的最长前缀，且**不切断码点**（多字节字符要么整字保留，要么整个丢弃） */
export function fitUtf8Prefix(text: string, maxBytes: number): string {
  if (maxBytes <= 0) return ''
  if (utf8ByteLength(text) <= maxBytes) return text
  let bytes = 0
  let out = ''
  for (const ch of text) {
    const size = utf8ByteLength(ch)
    if (bytes + size > maxBytes) break
    out += ch
    bytes += size
  }
  return out
}

/** 从尾部取不超过 maxBytes 的最长后缀，且不切断码点 */
export function fitUtf8Suffix(text: string, maxBytes: number): string {
  if (maxBytes <= 0) return ''
  if (utf8ByteLength(text) <= maxBytes) return text
  const chars = [...text]
  let bytes = 0
  let start = chars.length
  for (let i = chars.length - 1; i >= 0; i -= 1) {
    const size = utf8ByteLength(chars[i]!)
    if (bytes + size > maxBytes) break
    bytes += size
    start = i
  }
  return chars.slice(start).join('')
}

/** 行切分：去掉尾部空行，空文本返回空数组 */
export function splitLines(text: string): string[] {
  const body = text.replace(/\n+$/, '')
  return body ? body.split('\n') : []
}

/** 从头逐行贪心装入（整行保留，不切行） */
export function takeWholeLinesFromStart(lines: readonly string[], maxBytes: number): { text: string; count: number } {
  const kept: string[] = []
  for (const line of lines) {
    const candidate = kept.length === 0 ? line : `${kept.join('\n')}\n${line}`
    if (utf8ByteLength(candidate) > maxBytes) break
    kept.push(line)
  }
  return { text: kept.join('\n'), count: kept.length }
}

/** 从尾逐行贪心装入（整行保留，不切行） */
export function takeWholeLinesFromEnd(lines: readonly string[], maxBytes: number): { text: string; count: number } {
  const kept: string[] = []
  for (let i = lines.length - 1; i >= 0; i -= 1) {
    const line = lines[i]!
    const candidate = kept.length === 0 ? line : `${line}\n${kept.join('\n')}`
    if (utf8ByteLength(candidate) > maxBytes) break
    kept.unshift(line)
  }
  return { text: kept.join('\n'), count: kept.length }
}

/** 结构化续读提示（模型可见，写进文本尾部） */
export function buildContinuationNotice(ctx: {
  originalBytes: number
  maxBytes: number
  strategy: OutputLimitStrategy
  returnedBodyLines: number
  nextOffset?: number
  resumeCall?: string
  omittedLines?: number
  retainedHeadLines?: number
  retainedTailLines?: number
  /** 该内容存在「单行就超过预算」的超长行（此时整行装入策略会一无所获，已回退为返回该行前段） */
  oversizedLine?: boolean
}): string {
  // 注意：提示在最终文本确定**之前**生成，故不写「本次返回 X 字节」（会不准）；
  // 精确字节数由 truncation 记录携带（originalBytes/returnedBytes/maxBytes）
  const head = `[已截断：原始 ${ctx.originalBytes} 字节，输出上限 ${ctx.maxBytes} 字节`
  if (ctx.strategy === 'head_tail_lines') {
    const omitted = ctx.omittedLines ?? 0
    return (
      `${head}；已保留开头 ${ctx.retainedHeadLines ?? 0} 行与结尾 ${ctx.retainedTailLines ?? 0} 行，` +
      `中间省略约 ${omitted} 行。继续读取请缩小搜索范围或改用更精确的 pattern]`
    )
  }
  if (ctx.oversizedLine) {
    return `${head}；该内容存在单行即超过预算的超长行，已返回该行前段。请改用 grep 定位具体片段，或让上游把内容按行换行后重试]`
  }
  const from = (ctx.nextOffset ?? ctx.returnedBodyLines + 1)
  const resume = ctx.resumeCall ?? `offset=${from}, length=${CONTINUATION_SUGGESTED_LINES}`
  return `${head}；已返回前 ${ctx.returnedBodyLines} 行。继续读取请带参数：${resume}]`
}

/**
 * prefix_lines 策略：从头逐行装入，预算内含提示本身。
 * 提示长度随保留行数变化（行号数字位数会变），故采用「先试装、再校验总字节」的收敛写法：
 * 逐行增加，直到「正文 + 该行数对应的提示」超过预算为止。
 */
export function limitPrefixLines(
  text: string,
  opts: {
    maxBytes: number
    notice: (ctx: { returnedBodyLines: number; originalBytes: number }) => string
    /** 可选：超长行回退时使用的提示构造器 */
    oversizedNotice?: (ctx: { originalBytes: number }) => string
  }
): LimitedText {
  const originalBytes = utf8ByteLength(text)
  const lines = splitLines(text)
  if (originalBytes <= opts.maxBytes) {
    return { text, truncated: false, returnedBodyLines: lines.length }
  }

  // 至少能放提示本身
  let bestText = fitUtf8Prefix(opts.notice({ returnedBodyLines: 0, originalBytes }), opts.maxBytes)
  let bestLines = 0
  for (let count = 1; count <= lines.length; count += 1) {
    const body = lines.slice(0, count).join('\n')
    const notice = opts.notice({ returnedBodyLines: count, originalBytes })
    const candidate = body ? `${body}\n\n${notice}` : notice
    if (utf8ByteLength(candidate) > opts.maxBytes) break
    bestText = candidate
    bestLines = count
  }

  // 超长行回退：整行一行都装不下时（典型是压缩 JSON / 单行日志），返回首行的**部分内容**。
  // 只返回提示会让模型完全拿不到内容（参考实现即如此）；这里用 fitUtf8Prefix 保证不切断码点。
  if (bestLines === 0 && lines.length > 0 && opts.oversizedNotice) {
    const notice = opts.oversizedNotice({ originalBytes })
    const budget = Math.max(0, opts.maxBytes - utf8ByteLength(notice) - utf8ByteLength('\n\n'))
    const head = fitUtf8Prefix(lines[0]!, budget)
    bestText = head ? `${head}\n\n${notice}` : notice
  }

  return {
    text: bestText,
    truncated: true,
    returnedBodyLines: bestLines,
    truncation: {
      truncated: true,
      hasMore: true,
      strategy: 'prefix_lines',
      originalBytes,
      returnedBytes: utf8ByteLength(bestText),
      maxBytes: opts.maxBytes,
      returnedBodyLines: bestLines,
      nextOffset: bestLines + 1,
      offsetUnit: 'line'
    }
  }
}

/**
 * head_tail_lines 策略：头 45% + 尾 55%（整行），中间省略并在提示里说明省略行数。
 * 适合 grep —— 匹配往往集中在开头与结尾，中间大段可省。
 */
export function limitHeadTailLines(
  text: string,
  opts: { maxBytes: number; notice: (ctx: { returnedBodyLines: number; originalBytes: number; omittedLines: number; retainedHeadLines: number; retainedTailLines: number }) => string }
): LimitedText {
  const originalBytes = utf8ByteLength(text)
  const lines = splitLines(text)
  if (originalBytes <= opts.maxBytes) {
    return { text, truncated: false, returnedBodyLines: lines.length }
  }

  // 提示文本的长度取决于「省略了多少行/保留了多少行」的位数，而它又要占用预算 ——
  // 因此用**迭代收敛**而不是一次性估算：先用占位提示估预算，算出真实提示后若总量超预算，
  // 就按超出量收缩正文预算重算（最多 3 轮）。
  // 注意：不能只在最后用 fitUtf8Prefix 硬切 —— 那会把**尾部内容连同提示本身**一起切掉，
  // 既丢失续读指引、也让头尾比例失真（实测 head 占比会从 45% 涨到 81%）。
  let bodyBudget = Math.max(0, opts.maxBytes - utf8ByteLength(PLACEHOLDER_NOTICE) - utf8ByteLength('\n\n') * 2)
  let head = { text: '', count: 0 }
  let tail = { text: '', count: 0 }
  let notice = ''
  let limited = ''

  for (let round = 0; round < 3; round += 1) {
    const headBudget = Math.floor(bodyBudget * HEAD_TAIL_HEAD_RATIO)
    const tailBudget = Math.max(0, bodyBudget - headBudget)
    head = takeWholeLinesFromStart(lines, headBudget)
    const tailInput = lines.slice(head.count)
    tail = takeWholeLinesFromEnd(tailInput, tailBudget)
    const omittedLines = Math.max(0, lines.length - head.count - tail.count)
    notice = opts.notice({
      returnedBodyLines: head.count + tail.count,
      originalBytes,
      omittedLines,
      retainedHeadLines: head.count,
      retainedTailLines: tail.count
    })
    const pieces = [head.text, notice, tail.text].filter((p) => p.length > 0)
    limited = pieces.join('\n\n')
    const over = utf8ByteLength(limited) - opts.maxBytes
    if (over <= 0) break
    bodyBudget = Math.max(0, bodyBudget - over)
  }

  return {
    text: limited,
    truncated: true,
    returnedBodyLines: head.count + tail.count,
    truncation: {
      truncated: true,
      hasMore: true,
      strategy: 'head_tail_lines',
      originalBytes,
      returnedBytes: utf8ByteLength(limited),
      maxBytes: opts.maxBytes,
      returnedBodyLines: head.count + tail.count
    }
  }
}

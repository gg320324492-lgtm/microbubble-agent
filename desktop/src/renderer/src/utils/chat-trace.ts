// Chat Trace Model (Phase 5-B: Agent Timeline / Trace Renderer).
//
// 纯函数, 0 依赖. 把 StreamingMessage 的几个分散字段 (thinking / tool_calls /
// citations / rich_blocks / content) 转换为统一的 TraceItem[] 时间线.
//
// 不修改 Phase 3-B0 frozen schema; 仅消费已有状态.
//
// 设计要点:
//   - TraceItem discriminated union by 'kind' field
//   - order 字段: 确定性, 可比较 (用于 stable sort)
//   - buildTrace: 纯函数, 不修改入参
//   - 失败静默: 输入缺字段时跳过该项

import type {
  ToolCallSnapshot,
  StreamCitationEntry,
  StreamRichBlock
} from '@shared/chat-types'

// ============ TraceItem 类型 ============

export type TraceItemKind =
  | 'thinking'
  | 'tool_call'
  | 'tool_result'
  | 'citation'
  | 'rich_block'
  | 'answer'

interface TraceItemBase {
  /** 确定性顺序 (Phase 5-B 简化: 数组索引). 用于 Phase 5+ metrics. */
  order: number
}

export interface ThinkingTraceItem extends TraceItemBase {
  kind: 'thinking'
  label: string
}

export interface ToolCallTraceItem extends TraceItemBase {
  kind: 'tool_call'
  tool: ToolCallSnapshot
}

export interface ToolResultTraceItem extends TraceItemBase {
  kind: 'tool_result'
  tool: ToolCallSnapshot
}

export interface CitationTraceItem extends TraceItemBase {
  kind: 'citation'
  citation: StreamCitationEntry
}

export interface RichBlockTraceItem extends TraceItemBase {
  kind: 'rich_block'
  block: StreamRichBlock
}

export interface AnswerTraceItem extends TraceItemBase {
  kind: 'answer'
  content: string
  /** 是否 partial (流中); Phase 5-B 仅作标志, UI 视觉差异 Phase 5+ 接 */
  partial?: boolean
}

export type TraceItem =
  | ThinkingTraceItem
  | ToolCallTraceItem
  | ToolResultTraceItem
  | CitationTraceItem
  | RichBlockTraceItem
  | AnswerTraceItem

// ============ TraceItem 工厂 (Phase 5-A: 兼容 typing) ============

export function thinkingItem(label: string, order: number): ThinkingTraceItem {
  return { kind: 'thinking', label, order }
}

export function toolCallItem(tool: ToolCallSnapshot, order: number): ToolCallTraceItem {
  return { kind: 'tool_call', tool, order }
}

export function toolResultItem(tool: ToolCallSnapshot, order: number): ToolResultTraceItem {
  return { kind: 'tool_result', tool, order }
}

export function citationItem(citation: StreamCitationEntry, order: number): CitationTraceItem {
  return { kind: 'citation', citation, order }
}

export function richBlockItem(block: StreamRichBlock, order: number): RichBlockTraceItem {
  return { kind: 'rich_block', block, order }
}

export function answerItem(content: string, order: number, partial = false): AnswerTraceItem {
  return { kind: 'answer', content, order, partial }
}

// ============ buildTrace 主入口 ============

export interface BuildTraceInput {
  /** thinking 标签 (Phase 3-3-A 后端 emit 单条, Phase 5-A 用 streamingMessage.thinking) */
  thinking?: string | null
  /** tool 调用快照序列 (Phase 5-A streamingMessage.tool_calls) */
  toolCalls?: ToolCallSnapshot[]
  /** citation 累加序列 (Phase 3-C1 streamingMessage.citations) */
  citations?: StreamCitationEntry[]
  /** rich_block 累加序列 (Phase 5-A streamingMessage.rich_blocks) */
  richBlocks?: StreamRichBlock[]
  /** final answer (Phase 5-B: 通常 = msg.content) */
  answer?: string
  /** 流中 partial 标记 (Phase 5-B: 仅标志) */
  answerPartial?: boolean
  /** 跳过空 content / 空数组 (Phase 5-B; 默认 true) */
  dropEmpty?: boolean
}

/**
 * 构造 TraceItem[].
 *
 * 顺序规则 (Phase 5-B 严格):
 *   1. thinking (1 个, 若存在)
 *   2. tool_calls (按存储顺序, 每个 tool_call 后跟 tool_result 若 status != 'call_only')
 *   3. citations (按存储顺序)
 *   4. rich_blocks (按存储顺序)
 *   5. answer (1 个, 若存在)
 *
 * 失败 / 缺字段: 静默跳过 (dropEmpty 默认 true).
 * 非法 trace_item (e.g. tool_use_id 空): 跳过.
 */
export function buildTrace(input: BuildTraceInput): TraceItem[] {
  const out: TraceItem[] = []
  const drop = input.dropEmpty !== false
  let order = 0

  // 1. thinking
  const thinking = (input.thinking ?? '').trim()
  if (thinking) {
    out.push(thinkingItem(thinking, order++))
  }

  // 2. tool_calls (paired with tool_result)
  const tools = Array.isArray(input.toolCalls) ? input.toolCalls : []
  for (const t of tools) {
    if (!t || typeof t.tool_use_id !== 'string' || t.tool_use_id.length === 0) continue
    out.push(toolCallItem(t, order++))
    if (t.status !== 'call_only') {
      out.push(toolResultItem(t, order++))
    }
  }

  // 3. citations
  const citations = Array.isArray(input.citations) ? input.citations : []
  for (const c of citations) {
    if (!c || typeof c.knowledgeId !== 'number' || !Number.isFinite(c.knowledgeId)) continue
    out.push(citationItem(c, order++))
  }

  // 4. rich_blocks
  const blocks = Array.isArray(input.richBlocks) ? input.richBlocks : []
  for (const b of blocks) {
    if (!b || typeof b.type !== 'string' || b.type.length === 0) continue
    out.push(richBlockItem(b, order++))
  }

  // 5. answer
  const answer = (input.answer ?? '').trim()
  // dropEmpty: true (default) -> empty answer 跳过
  // dropEmpty: false         -> 即使空 answer 也保留 (调试 / 完整视图用)
  const shouldEmitAnswer = drop
    ? answer.length > 0
    : true
  if (shouldEmitAnswer) {
    out.push(answerItem(answer, order++, !!input.answerPartial))
  }

  return out
}

// ============ TraceMarkdownItem (Phase 5+ 留口) ============

export interface TraceMarkdownItem extends TraceItemBase {
  kind: 'rich_block'
  block: StreamRichBlock
}

// 留口: Phase 5+ 可引入独立 markdown trace item (避免 rich_block 冲突).
// 当前 Phase 5-B 直接用 rich_block type='markdown'.

// ============ Trace 摘要 (用于 collapsed 状态) ============

export interface TraceSummary {
  hasThinking: boolean
  toolCount: number
  citationCount: number
  richBlockCount: number
  hasAnswer: boolean
}

/**
 * 构造 Trace 摘要 (count-based, 0 依赖).
 * 用于 TraceTimeline 在 collapsed 状态显示 summary.
 */
export function summarizeTrace(items: TraceItem[]): TraceSummary {
  const s: TraceSummary = {
    hasThinking: false,
    toolCount: 0,
    citationCount: 0,
    richBlockCount: 0,
    hasAnswer: false
  }
  for (const it of items) {
    switch (it.kind) {
      case 'thinking': s.hasThinking = true; break
      case 'tool_call': s.toolCount++; break
      case 'tool_result': break  // 不递增 (call 已被计数)
      case 'citation': s.citationCount++; break
      case 'rich_block': s.richBlockCount++; break
      case 'answer': s.hasAnswer = true; break
    }
  }
  return s
}

/**
 * 格式化 summary 为简短文本 (Phase 5-B 默认 collapsed).
 * Returns '' if trace is empty.
 */
export function formatTraceSummary(s: TraceSummary): string {
  const parts: string[] = []
  if (s.hasThinking) parts.push('💭 thinking')
  if (s.toolCount > 0) parts.push(`🔧 ${s.toolCount} tool${s.toolCount > 1 ? 's' : ''}`)
  if (s.citationCount > 0) parts.push(`📚 ${s.citationCount} citation${s.citationCount > 1 ? 's' : ''}`)
  if (s.richBlockCount > 0) parts.push(`📦 ${s.richBlockCount} block${s.richBlockCount > 1 ? 's' : ''}`)
  return parts.join(' · ')
}

// ============ Convenience: 从 ChatMessage 提取 trace ============

import type { ChatMessageOut } from '@shared/chat-types'

/**
 * 从 completed ChatMessage 提取 Trace 上下文.
 * 用于: ChatView 完成消息展示 trace (Phase 5-B 默认折叠).
 */
export function buildTraceFromMessage(msg: ChatMessageOut): TraceItem[] {
  const md = msg.message_metadata
  // citations 持久化在 message_metadata (Phase 3-C1), rich_blocks 是顶层字段 (Phase 5-A)
  const citations = (md && Array.isArray(md.citations) ? md.citations : []) as unknown as StreamCitationEntry[]
  const toolCalls = (Array.isArray(msg.tool_trace) ? msg.tool_trace : []) as unknown as ToolCallSnapshot[]
  return buildTrace({
    thinking: typeof md?.thinking === 'string' ? md.thinking : null,
    toolCalls,
    citations,
    richBlocks: msg.rich_blocks,
    answer: msg.content,
    answerPartial: msg.is_partial
  })
}

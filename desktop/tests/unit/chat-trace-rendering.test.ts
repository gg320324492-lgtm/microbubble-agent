import { describe, it, expect } from 'vitest'
import {
  buildTrace,
  buildTraceFromMessage,
  summarizeTrace,
  formatTraceSummary,
  type TraceItem
} from '../../src/renderer/src/utils/chat-trace'
import type { ToolCallSnapshot, StreamCitationEntry, StreamRichBlock } from '../../src/shared/chat-types'
import type { ChatMessageOut } from '../../src/shared/chat-types'

/**
 * Phase 5-B: Trace model unit tests.
 *
 * 覆盖 spec Step 5 5 场景:
 *   1. trace生成 (buildTrace)
 *   2. 事件排序 (顺序 frozen)
 *   3. 空trace (空输入返 [])
 *   4. 普通消息无trace (提供空 / 默认值)
 *   5. tool失败trace (status=error 仍计入)
 */

function tool(
  id: string,
  status: 'call_only' | 'success' | 'error' = 'call_only',
  extras: Partial<ToolCallSnapshot> = {}
): ToolCallSnapshot {
  return {
    tool_use_id: id,
    name: 'test_tool',
    input: {},
    started_at: '2026-08-21T00:00:00Z',
    finished_at: status === 'call_only' ? null : '2026-08-21T00:00:01Z',
    status,
    output: status === 'success' ? { ok: true } : null,
    error: status === 'error' ? 'timeout' : null,
    duration_ms: status === 'call_only' ? null : 1000,
    ...extras
  }
}

function citation(knowledgeId: number): StreamCitationEntry {
  return {
    type: 'citation',
    knowledgeId,
    title: `Doc ${knowledgeId}`,
    snippet: '...',
    score: 0.9
  } as StreamCitationEntry
}

function richBlock(type: string = 'json'): StreamRichBlock {
  return { type, data: { x: 1 }, title: 'block' }
}

describe('buildTrace (Spec 1: trace generation)', () => {
  it('thinking + 1 tool + 1 citation -> 3 items (顺序 thinking -> tool_call -> tool_result -> citation)', () => {
    const items = buildTrace({
      thinking: '分析用户意图',
      toolCalls: [tool('t1', 'success')],
      citations: [citation(42)]
    })
    expect(items).toHaveLength(4)
    expect(items[0]?.kind).toBe('thinking')
    expect(items[1]?.kind).toBe('tool_call')
    expect(items[2]?.kind).toBe('tool_result')
    expect(items[3]?.kind).toBe('citation')
  })

  it('tool_call_only (status 未完成) 不派生 tool_result', () => {
    const items = buildTrace({
      toolCalls: [tool('t1', 'call_only')]
    })
    expect(items).toHaveLength(1)
    expect(items[0]?.kind).toBe('tool_call')
  })

  it('tool_status=success / error 均派生 tool_result', () => {
    const successItems = buildTrace({ toolCalls: [tool('t1', 'success')] })
    expect(successItems.find((x) => x.kind === 'tool_result')).toBeDefined()
    const errorItems = buildTrace({ toolCalls: [tool('t1', 'error')] })
    expect(errorItems.find((x) => x.kind === 'tool_result')).toBeDefined()
  })

  it('rich_block 累加', () => {
    const items = buildTrace({
      richBlocks: [richBlock('json'), richBlock('markdown')]
    })
    expect(items).toHaveLength(2)
    expect(items.every((x) => x.kind === 'rich_block')).toBe(true)
  })

  it('answer 默认末尾', () => {
    const items = buildTrace({
      thinking: 't',
      toolCalls: [tool('t1', 'success')],
      answer: '最终答案'
    })
    expect(items[items.length - 1]?.kind).toBe('answer')
  })

  it('parts 顺序: thinking -> tool_call -> tool_result -> citation -> rich_block -> answer', () => {
    const items = buildTrace({
      thinking: 't',
      toolCalls: [tool('t1', 'success')],
      citations: [citation(1)],
      richBlocks: [richBlock('json')],
      answer: 'a'
    })
    expect(items.map((x) => x.kind)).toEqual([
      'thinking', 'tool_call', 'tool_result', 'citation', 'rich_block', 'answer'
    ])
  })
})

describe('buildTrace (Spec 2: event ordering)', () => {
  it('order 字段单调递增', () => {
    const items = buildTrace({
      thinking: 't',
      toolCalls: [tool('t1', 'success'), tool('t2', 'success')],
      citations: [citation(1), citation(2), citation(3)]
    })
    for (let i = 1; i < items.length; i++) {
      expect(items[i]!.order).toBeGreaterThan(items[i - 1]!.order)
    }
  })

  it('多 tool 顺序与输入 toolCalls 顺序一致', () => {
    const items = buildTrace({
      toolCalls: [tool('t1', 'success'), tool('t2', 'success'), tool('t3', 'success')]
    })
    const toolResults = items.filter((x) => x.kind === 'tool_result')
    expect(toolResults[0]?.kind === 'tool_result' && (toolResults[0] as { tool: ToolCallSnapshot }).tool.tool_use_id).toBe('t1')
    expect(toolResults[1]?.kind === 'tool_result' && (toolResults[1] as { tool: ToolCallSnapshot }).tool.tool_use_id).toBe('t2')
    expect(toolResults[2]?.kind === 'tool_result' && (toolResults[2] as { tool: ToolCallSnapshot }).tool.tool_use_id).toBe('t3')
  })
})

describe('buildTrace (Spec 3: empty trace)', () => {
  it('空输入 -> []', () => {
    expect(buildTrace({})).toEqual([])
  })

  it('只有空字符串 -> []', () => {
    expect(buildTrace({ thinking: '', answer: '' })).toEqual([])
  })

  it('null thinking -> []', () => {
    expect(buildTrace({ thinking: null })).toEqual([])
  })

  it('空数组 toolCalls / citations / richBlocks -> []', () => {
    expect(buildTrace({
      toolCalls: [],
      citations: [],
      richBlocks: []
    })).toEqual([])
  })

  it('dropEmpty: false 允许空 answer 仍输出', () => {
    const items = buildTrace({ answer: '', dropEmpty: false })
    expect(items.length).toBe(1)
    expect(items[0]?.kind).toBe('answer')
  })
})

describe('buildTrace (Spec 4: 普通消息无 trace)', () => {
  it('只有 answer, trace.items 应只含 answer', () => {
    const items = buildTrace({ answer: '普通回复' })
    expect(items).toHaveLength(1)
    expect(items[0]?.kind).toBe('answer')
  })

  it('没有 tool/citation/rich_block/thinking 时, items 长度小且不含额外', () => {
    const items = buildTrace({ answer: 'x' })
    const kinds = new Set(items.map((x) => x.kind))
    expect(kinds.has('tool_call')).toBe(false)
    expect(kinds.has('tool_result')).toBe(false)
    expect(kinds.has('citation')).toBe(false)
    expect(kinds.has('rich_block')).toBe(false)
    expect(kinds.has('thinking')).toBe(false)
  })
})

describe('buildTrace (Spec 5: tool 失败 trace)', () => {
  it('tool_status=error 仍派生 tool_call + tool_result', () => {
    const items = buildTrace({
      toolCalls: [tool('t1', 'error')]
    })
    expect(items).toHaveLength(2)
    expect(items[0]?.kind).toBe('tool_call')
    expect(items[1]?.kind).toBe('tool_result')
    const resultItem = items[1] as { tool: ToolCallSnapshot }
    expect(resultItem.tool.status).toBe('error')
    expect(resultItem.tool.error).toBe('timeout')
  })

  it('混合 success + error 两条 tool 都派 result', () => {
    const items = buildTrace({
      toolCalls: [tool('t1', 'success'), tool('t2', 'error')]
    })
    expect(items.filter((x) => x.kind === 'tool_result')).toHaveLength(2)
  })
})

describe('buildTrace 鲁棒性 (Phase 5-B frozen 边界)', () => {
  it('缺 tool_use_id 跳过该 tool', () => {
    const items = buildTrace({
      toolCalls: [{ tool_use_id: '', name: 'orphan', input: {}, started_at: '', finished_at: null, status: 'call_only', output: null, error: null, duration_ms: null } as ToolCallSnapshot]
    })
    expect(items).toHaveLength(0)
  })

  it('citation 缺 knowledgeId 跳过', () => {
    const items = buildTrace({
      citations: [{ type: 'citation', knowledgeId: NaN, title: 'x' } as unknown as StreamCitationEntry]
    })
    expect(items).toHaveLength(0)
  })

  it('rich_block 缺 type 跳过', () => {
    const items = buildTrace({
      richBlocks: [{ type: '', data: {} } as StreamRichBlock]
    })
    expect(items).toHaveLength(0)
  })
})

describe('summarizeTrace + formatTraceSummary', () => {
  it('空 trace summary 全 false / 0', () => {
    const s = summarizeTrace([])
    expect(s).toEqual({
      hasThinking: false,
      toolCount: 0,
      citationCount: 0,
      richBlockCount: 0,
      hasAnswer: false
    })
    expect(formatTraceSummary(s)).toBe('')
  })

  it('完整 trace summary', () => {
    const items = buildTrace({
      thinking: 't',
      toolCalls: [tool('t1', 'success'), tool('t2', 'success')],
      citations: [citation(1), citation(2)],
      richBlocks: [richBlock('json')],
      answer: 'a'
    })
    const s = summarizeTrace(items)
    expect(s.hasThinking).toBe(true)
    expect(s.toolCount).toBe(2)
    expect(s.citationCount).toBe(2)
    expect(s.richBlockCount).toBe(1)
    expect(s.hasAnswer).toBe(true)
    expect(formatTraceSummary(s)).toContain('thinking')
    expect(formatTraceSummary(s)).toContain('2 tools')
    expect(formatTraceSummary(s)).toContain('2 citations')
    expect(formatTraceSummary(s)).toContain('1 block')
  })
})

describe('buildTraceFromMessage (ChatMessage 入口)', () => {
  it('from ChatMessageOut (含 tool_trace + rich_blocks + metadata.citations)', () => {
    const msg: ChatMessageOut = {
      id: 1,
      session_id: 'default',
      role: 'assistant',
      content: 'final answer',
      rich_blocks: [richBlock('json')],
      tool_trace: [tool('t1', 'success')],
      message_metadata: {
        thinking: 'meta-thinking',
        citations: [citation(99)]
      },
      is_partial: false,
      is_deleted: false,
      client_msg_id: 'cm_test',
      attached_knowledge_ids: [99],
      image_url: null,
      created_at: '2026-08-21T00:00:00Z'
    }
    const items = buildTraceFromMessage(msg)
    expect(items.length).toBeGreaterThanOrEqual(5)
    expect(items[0]?.kind).toBe('thinking')  // meta-thinking
    expect(items.find((x) => x.kind === 'tool_call')).toBeDefined()
    expect(items.find((x) => x.kind === 'tool_result')).toBeDefined()
    expect(items.find((x) => x.kind === 'citation')).toBeDefined()
    expect(items.find((x) => x.kind === 'rich_block')).toBeDefined()
    expect(items[items.length - 1]?.kind).toBe('answer')
  })

  it('空 message_metadata 仍然能从 rich_blocks / tool_trace 提取', () => {
    const msg: ChatMessageOut = {
      id: 1,
      session_id: 'default',
      role: 'assistant',
      content: '',
      rich_blocks: [],
      tool_trace: [],
      message_metadata: {},
      is_partial: false,
      is_deleted: false,
      client_msg_id: null,
      attached_knowledge_ids: [],
      image_url: null,
      created_at: '2026-08-21T00:00:00Z'
    }
    const items = buildTraceFromMessage(msg)
    expect(items).toHaveLength(0)
  })
})

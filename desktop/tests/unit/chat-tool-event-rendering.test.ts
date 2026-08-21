import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import type { StreamEvent, ToolCallSnapshot, StreamRichBlock } from '../../src/shared/chat-types'

/**
 * Phase 5-A: Agent Tool Renderer Foundation — chat store 集成测试.
 *
 * 覆盖 spec Step 6 5 场景:
 *   1. tool_use 事件累加 (call_only 状态)
 *   2. tool_result 事件触发 ToolCall 状态更新 (success / error)
 *   3. rich_block 事件累加
 *   4. 错误 tool 状态 (tool_error)
 *   5. 普通消息无 tool/rich_block 时 0 节点差异 (smoke: store 不写 tool_calls)
 */
const mockRequest = vi.fn()

beforeEach(() => {
  setActivePinia(createPinia())
  mockRequest.mockReset()
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(globalThis as any).window = {
    api: {
      api: { request: mockRequest },
      auth: {},
      session: {},
      chat: {}
    }
  }
})

afterEach(() => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  delete (globalThis as any).window
})

async function setupChatStore() {
  // dynamic import -> store isPinia-aware
  const { useChatStore } = await import('../../src/renderer/src/stores/chat')
  return useChatStore()
}

function makeStreamingMessage(id: number, role: 'assistant' = 'assistant') {
  return {
    id,
    session_id: 'default',
    role,
    content: '',
    thinking: null,
    rich_blocks: [],
    tool_calls: [],
    citations: [],
    started_at: new Date().toISOString(),
    finished_at: null,
    persisted_message_id: null,
    client_msg_id: `cm_${id}`
  }
}

describe('chat store: tool_use event (Spec 1)', () => {
  it('接收 tool_use 累加 ToolCallSnapshot 状态 call_only', async () => {
    const store = await setupChatStore()
    store.activeStreamId = 'stream_1'
    store.activeStreamSessionId = 'default'
    store.isStreaming = true
    store.streamingMessage = makeStreamingMessage(1) as never

    const event: StreamEvent = {
      type: 'tool_use',
      tool_use_id: 'tu_1',
      tool_name: 'web_search',
      tool_input: { query: '微纳米气泡' }
    }
    store.handleStreamChunk({ streamId: 'stream_1', sessionId: 'default' }, event)

    expect(store.streamingMessage?.tool_calls).toHaveLength(1)
    const t = store.streamingMessage?.tool_calls[0]
    expect(t?.tool_use_id).toBe('tu_1')
    expect(t?.name).toBe('web_search')
    expect(t?.status).toBe('call_only')
    expect(t?.input).toEqual({ query: '微纳米气泡' })
  })
})

describe('chat store: tool_result event (Spec 2)', () => {
  it('tool_result success 更新状态 + duration + output', async () => {
    const store = await setupChatStore()
    store.activeStreamId = 'stream_2'
    store.activeStreamSessionId = 'default'
    store.isStreaming = true
    store.streamingMessage = makeStreamingMessage(2) as never

    // 先 tool_use
    store.handleStreamChunk({ streamId: 'stream_2', sessionId: 'default' }, {
      type: 'tool_use',
      tool_use_id: 'tu_2',
      tool_name: 'calc',
      tool_input: { x: 1, y: 2 }
    } as StreamEvent)

    // 再 tool_result success
    store.handleStreamChunk({ streamId: 'stream_2', sessionId: 'default' }, {
      type: 'tool_result',
      tool_use_id: 'tu_2',
      tool_output: { sum: 3 },
      tool_duration_ms: 42
    } as StreamEvent)

    const t = store.streamingMessage?.tool_calls.find((x) => x.tool_use_id === 'tu_2')
    expect(t?.status).toBe('success')
    expect(t?.duration_ms).toBe(42)
    expect(t?.output).toEqual({ sum: 3 })
    expect(t?.finished_at).toBeTruthy()
  })

  it('tool_result error 更新 status=error + error 字段', async () => {
    const store = await setupChatStore()
    store.activeStreamId = 'stream_2b'
    store.activeStreamSessionId = 'default'
    store.isStreaming = true
    store.streamingMessage = makeStreamingMessage(3) as never

    store.handleStreamChunk({ streamId: 'stream_2b', sessionId: 'default' }, {
      type: 'tool_use',
      tool_use_id: 'tu_3',
      tool_name: 'flaky',
      tool_input: {}
    } as StreamEvent)
    store.handleStreamChunk({ streamId: 'stream_2b', sessionId: 'default' }, {
      type: 'tool_use',  // 不应误判
      type_redundant: 'fix-hint-not-real',
      tool_use_id: 'wrong-event'
    } as never)
    store.handleStreamChunk({ streamId: 'stream_2b', sessionId: 'default' }, {
      type: 'tool_result',
      tool_use_id: 'tu_3',
      tool_error: 'timeout > 30s',
      tool_duration_ms: 30000
    } as StreamEvent)

    const t = store.streamingMessage?.tool_calls.find((x) => x.tool_use_id === 'tu_3')
    expect(t?.status).toBe('error')
    expect(t?.error).toBe('timeout > 30s')
    expect(t?.duration_ms).toBe(30000)
  })
})

describe('chat store: rich_block event (Spec 3)', () => {
  it('rich_block 累加到 streamingMessage.rich_blocks', async () => {
    const store = await setupChatStore()
    store.activeStreamId = 'stream_3'
    store.activeStreamSessionId = 'default'
    store.isStreaming = true
    store.streamingMessage = makeStreamingMessage(4) as never

    const block: StreamRichBlock = {
      type: 'json',
      data: { foo: 'bar' },
      title: 'Sample JSON'
    }
    store.handleStreamChunk({ streamId: 'stream_3', sessionId: 'default' }, {
      type: 'rich_block',
      block
    } as StreamEvent)

    expect(store.streamingMessage?.rich_blocks).toHaveLength(1)
    expect(store.streamingMessage?.rich_blocks[0]).toEqual(block)
  })
})

describe('chat store: 普通消息无 tool (Spec 5)', () => {
  it('文本流正常积累, tool_calls 数组保持空', async () => {
    const store = await setupChatStore()
    store.activeStreamId = 'stream_5'
    store.activeStreamSessionId = 'default'
    store.isStreaming = true
    store.streamingMessage = makeStreamingMessage(5) as never

    // 只发 text_delta / thinking
    store.handleStreamChunk({ streamId: 'stream_5', sessionId: 'default' }, {
      type: 'text_delta',
      delta: 'hello '
    } as StreamEvent)
    store.handleStreamChunk({ streamId: 'stream_5', sessionId: 'default' }, {
      type: 'text_delta',
      delta: 'world'
    } as StreamEvent)
    store.handleStreamChunk({ streamId: 'stream_5', sessionId: 'default' }, {
      type: 'thinking',
      label: '分析'
    } as StreamEvent)

    expect(store.streamingMessage?.content).toBe('hello world')
    expect(store.streamingMessage?.tool_calls).toHaveLength(0)
    expect(store.streamingMessage?.rich_blocks).toHaveLength(0)
  })
})

describe('chat store: 错误 tool 状态 (Spec 4)', () => {
  it('tool_result 缺 tool_use_id 不写入', async () => {
    const store = await setupChatStore()
    store.activeStreamId = 'stream_4'
    store.activeStreamSessionId = 'default'
    store.isStreaming = true
    store.streamingMessage = makeStreamingMessage(6) as never

    // 缺 tool_use_id
    store.handleStreamChunk({ streamId: 'stream_4', sessionId: 'default' }, {
      type: 'tool_use',
      tool_name: 'no-id',
      tool_input: {}
    } as StreamEvent)
    store.handleStreamChunk({ streamId: 'stream_4', sessionId: 'default' }, {
      type: 'tool_result',
      tool_output: { ok: true }
    } as StreamEvent)

    // 没有合法 tool_use_id, 不写入
    expect(store.streamingMessage?.tool_calls).toHaveLength(0)
  })

  it('tool_result 找不到对应 tool_use_id 时不报错', async () => {
    const store = await setupChatStore()
    store.activeStreamId = 'stream_4b'
    store.activeStreamSessionId = 'default'
    store.isStreaming = true
    store.streamingMessage = makeStreamingMessage(7) as never

    // 直接来 tool_result, 无先前 tool_use
    store.handleStreamChunk({ streamId: 'stream_4b', sessionId: 'default' }, {
      type: 'tool_result',
      tool_use_id: 'orphan_id',
      tool_output: { x: 1 }
    } as StreamEvent)

    // 不应抛错, 数组保持空
    expect(store.streamingMessage?.tool_calls).toHaveLength(0)
  })
})

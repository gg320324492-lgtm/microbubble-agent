import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import type { StreamCitationEntry } from '../../src/shared/chat-types'
import type { KnowledgeResponse as KnowledgeResponseType } from '../../src/shared/knowledge-types'

/**
 * Phase 4-C: Chat Knowledge Hot Path unit tests.
 *
 * 覆盖 spec Step 5 4 场景:
 *   1. citation event triggers prefetch
 *   2. prefetch failure doesn't impact stream
 *   3. session switching isolation
 *   4. cancel after subscription -> ignored results
 *
 * 策略:
 *   - globalThis.window.api.api.request mock (KnowledgeService 底层)
 *   - knowledgeService.prefetchKnowledgeForCitations -> 经 mock IPC 真实走通
 *   - setupPinia/setActivePinia 激活 chat store
 *   - 异步结果: vi.useFakeTimers + flushPromises 控制
 */

const mockRequest = vi.fn()

function knowledgeOf(id: number): KnowledgeResponseType {
  return {
    id,
    title: `K${id}`,
    content: 'c',
    category: 'cat-' + id,
    tags: [],
    key_concepts: [],
    related_topics: [],
    knowledge_type: null,
    topic: null,
    analysis_status: 'completed',
    quality_score: 0.9,
    needs_review: false,
    thumbnail_url: null,
    image_count: 0,
    meta: {},
    created_by: 1,
    created_at: '2026-08-01T00:00:00Z',
    updated_at: '2026-08-21T00:00:00Z',
    source: null,
    source_type: null,
    file_path: null,
    file_name: null,
    file_type: null,
    summary: null
  } as KnowledgeResponseType
}

function citationOf(knowledgeId: number): StreamCitationEntry {
  return {
    type: 'citation',
    knowledgeId,
    title: 't',
    snippet: 's',
    score: 0.9
  } as StreamCitationEntry
}

async function setupChatStore() {
  const { useChatStore } = await import('../../src/renderer/src/stores/chat')
  const store = useChatStore()
  return store
}

async function setupKnowledgeServiceCleared() {
  const { knowledgeService } = await import('../../src/renderer/src/services/knowledge.service')
  knowledgeService._internal.clearCache()
  return knowledgeService
}

describe('Chat Knowledge Hot Path (Phase 4-C)', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    mockRequest.mockReset()
    mockRequest.mockImplementation(async (payload: { method: string; path: string }) => {
      // GET /knowledge/{id} -> 返对应知识
      if (payload.method === 'GET' && payload.path.startsWith('/knowledge/')) {
        const id = Number(payload.path.split('/').pop())
        if (Number.isFinite(id) && id > 0) {
          return { ok: true, data: knowledgeOf(id) }
        }
      }
      return { ok: false, error: { code: 'UNKNOWN', message: 'mock not configured' } }
    })
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(globalThis as any).window = {
      api: {
        api: { request: mockRequest },
        auth: {},
        session: {},
        chat: {}
      }
    }
    await setupKnowledgeServiceCleared()
  })

  afterEach(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (globalThis as any).window
  })

  it('Spec 1: citation event triggers prefetch (KnowledgeService 收到 fetch 请求)', async () => {
    const store = await setupChatStore()

    // 模拟 stream 中
    store.activeStreamId = 'stream_test_1'
    store.activeStreamSessionId = 'default'
    store.streamingMessage = {
      id: 1,
      session_id: 'default',
      role: 'assistant',
      content: '',
      thinking: null,
      rich_blocks: [],
      tool_trace: [],
      citations: [],
      started_at: new Date().toISOString(),
      finished_at: null,
      persisted_message_id: null,
      client_msg_id: 'cmid_a'
    } as never

    // 模拟收到 citation event
    const ctx = { streamId: 'stream_test_1', sessionId: 'default' }
    const event = {
      type: 'citation',
      citation: { knowledgeId: 42, title: 't', snippet: 's' }
    } as never
    store.handleStreamChunk(ctx, event)

    // 异步 prefetch 解析
    await new Promise((resolve) => setTimeout(resolve, 0))

    // IPC 应该被调用 GET /knowledge/42
    const calls = mockRequest.mock.calls.filter((c) => (c[0] as { path: string }).path === '/knowledge/42')
    expect(calls.length).toBeGreaterThan(0)
  })

  it('Spec 1 (续): prefetch 成功后 cachedHints 写入', async () => {
    const store = await setupChatStore()
    store.activeStreamId = 'stream_test_2'
    store.activeStreamSessionId = 'default'
    store.streamingMessage = {
      id: 1,
      session_id: 'default',
      role: 'assistant',
      content: '',
      thinking: null,
      rich_blocks: [],
      tool_trace: [],
      citations: [],
      started_at: new Date().toISOString(),
      finished_at: null,
      persisted_message_id: null,
      client_msg_id: 'cmid_a'
    } as never

    const ctx = { streamId: 'stream_test_2', sessionId: 'default' }
    store.handleStreamChunk(ctx, { type: 'citation', citation: { knowledgeId: 99, title: 't' } } as never)

    // 等待 prefetch promise chain
    await new Promise((resolve) => setTimeout(resolve, 10))

    // cachedHints 应包含 99
    const stored = store.getCachedHint(99)
    expect(stored).not.toBeNull()
    expect(stored?.id).toBe(99)
  })

  it('Spec 2: prefetch 失败 -> 不污染 cachedHints, 不影响 stream', async () => {
    const store = await setupChatStore()
    store.activeStreamId = 'stream_test_3'
    store.activeStreamSessionId = 'default'
    store.isStreaming = true
    store.streamingMessage = {
      id: 1,
      session_id: 'default',
      role: 'assistant',
      content: '',
      thinking: null,
      rich_blocks: [],
      tool_trace: [],
      citations: [],
      started_at: new Date().toISOString(),
      finished_at: null,
      persisted_message_id: null,
      client_msg_id: 'cmid_a'
    } as never

    // 让 mock 返 IPC 错误
    mockRequest.mockResolvedValueOnce({ ok: false, error: { code: 'INTERNAL', message: 'down' } })

    const ctx = { streamId: 'stream_test_3', sessionId: 'default' }
    store.handleStreamChunk(ctx, { type: 'citation', citation: { knowledgeId: 7, title: 't' } } as never)

    await new Promise((resolve) => setTimeout(resolve, 10))

    // cachedHints 未写入
    expect(store.getCachedHint(7)).toBeNull()
    // streamingMessage 仍 active (未取消)
    expect(store.isStreaming).toBe(true)
  })

  it('Spec 3: session 切换隔离 — 旧 session 的 prefetch 结果不写新 session', async () => {
    const store = await setupChatStore()
    store.activeStreamId = 'stream_test_4'
    store.activeStreamSessionId = 'sessionA'
    store.streamingMessage = {
      id: 1,
      session_id: 'sessionA',
      role: 'assistant',
      content: '',
      thinking: null,
      rich_blocks: [],
      tool_trace: [],
      citations: [],
      started_at: new Date().toISOString(),
      finished_at: null,
      persisted_message_id: null,
      client_msg_id: 'cmid_a'
    } as never

    const ctxA = { streamId: 'stream_test_4', sessionId: 'sessionA' }
    store.handleStreamChunk(ctxA, { type: 'citation', citation: { knowledgeId: 5, title: 't' } } as never)

    // 用户切到 sessionB (在 prefetch 解析前)
    store.selectSession('sessionB')

    // 等待 prefetch 解析
    await new Promise((resolve) => setTimeout(resolve, 10))

    // 即使 prefetch 成功, 也不写 cachedHints (session 已切换)
    expect(store.getCachedHint(5)).toBeNull()
    // (LRU cache 本身仍有 5, 因为 service 写 LRU 不撤回 — 这是设计)
    // 仅 UI hint 被 session 隔离
  })

  it('Spec 4: cancel 后 ignore 结果 — 流已被 handleStreamError 清, cachedHints 隔离', async () => {
    const store = await setupChatStore()
    store.activeStreamId = 'stream_test_5'
    store.activeStreamSessionId = 'default'
    store.streamingMessage = {
      id: 1,
      session_id: 'default',
      role: 'assistant',
      content: '',
      thinking: null,
      rich_blocks: [],
      tool_trace: [],
      citations: [],
      started_at: new Date().toISOString(),
      finished_at: null,
      persisted_message_id: null,
      client_msg_id: 'cmid_a'
    } as never

    const ctx = { streamId: 'stream_test_5', sessionId: 'default' }
    store.handleStreamChunk(ctx, { type: 'citation', citation: { knowledgeId: 11, title: 't' } } as never)

    // 立即触发流错误 (cancel-like)
    store.handleStreamError(ctx, 'CANCEL', '用户取消')

    // 等待 prefetch promise resolve
    await new Promise((resolve) => setTimeout(resolve, 10))

    // 流已结束, cachedHints 在 handleStreamError 中被清
    expect(store.cachedHints.size).toBe(0)
  })
})

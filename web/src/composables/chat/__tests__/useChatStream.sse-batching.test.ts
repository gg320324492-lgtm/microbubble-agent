import { beforeEach, describe, expect, it, vi } from 'vitest'
import { watchSyncEffect } from 'vue'

const mockSessionStore = {
  sessions: [],
  currentId: null,
  currentSession: vi.fn(() => null),
  createSession: vi.fn(),
  updateActivity: vi.fn(),
  switchSession: vi.fn(),
  deleteSession: vi.fn(),
  migrateFromV1: vi.fn(),
}
const mockAppendMessage = vi.fn().mockResolvedValue({ id: 99 })

vi.mock('@/stores/chatSessions', () => ({
  useChatSessionsStore: () => mockSessionStore,
}))
vi.mock('@/stores/chatHistory', () => ({
  useChatHistoryStore: () => ({
    fetchMessages: vi.fn().mockResolvedValue({ items: [] }),
    loadFromServer: vi.fn(),
    refreshSession: vi.fn(),
    appendMessageAsync: mockAppendMessage,
    createServerSession: vi.fn(),
    syncStatus: 'idle',
    serverSessions: [],
  }),
}))
vi.mock('@/stores/useUiStore', () => ({
  useUiStore: () => ({ thinkingMode: 'balanced', setLastModeInfo: vi.fn() }),
}))
vi.mock('@/api/agent/sse', () => ({ sseFetch: vi.fn() }))
vi.mock('axios', () => ({ default: { post: vi.fn() } }))
vi.mock('element-plus', () => ({
  ElMessage: { error: vi.fn(), warning: vi.fn(), success: vi.fn() },
}))

import { sseFetch } from '@/api/agent/sse'
import { createTextDeltaBatcher, useChatStream } from '../useChatStream'

describe('useChatStream SSE text_delta batching', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    Object.assign(mockSessionStore, {
      sessions: [],
      currentId: null,
    })
    mockSessionStore.currentSession.mockReturnValue(null)
    Object.defineProperty(globalThis, 'localStorage', {
      configurable: true,
      value: {
        getItem: vi.fn((key: string) => key === 'chat_current_session_v3' ? 'perf-session' : null),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
      },
    })
  })

  it('100 个连续 delta 在 100ms 后合并为一次 content 更新', () => {
    let content = ''
    let flushes = 0
    const batcher = createTextDeltaBatcher((delta) => {
      content += delta
      flushes += 1
    })

    for (let i = 0; i < 100; i += 1) batcher.push(String(i % 10))
    expect(content).toBe('')
    expect(batcher.pendingCount).toBe(100)
    vi.advanceTimersByTime(100)

    expect(content).toBe(Array.from({ length: 100 }, (_, i) => String(i % 10)).join(''))
    expect(flushes).toBe(1)
  })

  it('分时到达时 reactivity 触发次数不超过 N/5', () => {
    let content = ''
    let triggers = 0
    const batcher = createTextDeltaBatcher((delta) => {
      content += delta
      triggers += 1
    })

    for (let batch = 0; batch < 10; batch += 1) {
      for (let i = 0; i < 10; i += 1) batcher.push('x')
      vi.advanceTimersByTime(100)
    }

    expect(content).toHaveLength(100)
    expect(triggers).toBe(10)
    expect(triggers).toBeLessThanOrEqual(100 / 5)
  })

  it('flush 保持事件顺序并清除已安排 timer', () => {
    const chunks: string[] = []
    const batcher = createTextDeltaBatcher((delta) => chunks.push(delta))
    batcher.push('a')
    batcher.push('b')
    batcher.flush()
    chunks.push('snapshot')
    vi.advanceTimersByTime(100)
    expect(chunks).toEqual(['ab', 'snapshot'])
  })

  it('cancel 丢弃 pending delta 且不会晚到 flush', () => {
    const onFlush = vi.fn()
    const batcher = createTextDeltaBatcher(onFlush)
    batcher.push('discarded')
    batcher.cancel()
    vi.advanceTimersByTime(100)
    expect(onFlush).not.toHaveBeenCalled()
    expect(batcher.pendingCount).toBe(0)
  })

  it('忽略空 delta，不创建空 flush', () => {
    const onFlush = vi.fn()
    const batcher = createTextDeltaBatcher(onFlush)
    batcher.push('')
    vi.advanceTimersByTime(100)
    expect(onFlush).not.toHaveBeenCalled()
  })

  it('真实 sendMessage 拼接全部 delta、首次派发 generating，持久化写入不超过 N/10', async () => {
    const deltas = Array.from({ length: 100 }, (_, i) => String(i % 10))
    vi.mocked(sseFetch).mockImplementationOnce(async function* () {
      for (const delta of deltas) yield { type: 'text_delta', delta } as any
      yield { type: 'done', usage: {}, duration_ms: 1 } as any
    })
    const retrievalEvents: CustomEvent[] = []
    const listener = (event: Event) => retrievalEvents.push(event as CustomEvent)
    window.addEventListener('chat:retrieval-status', listener)
    const stream = useChatStream()
    let observedContentChanges = 0
    const stopWatch = watchSyncEffect(() => {
      const assistant = stream.messages.value.find((message) => message.role === 'assistant')
      void assistant?.content
      if (assistant?.content) observedContentChanges += 1
    })

    await stream.sendMessage({ text: 'batch please' })

    const assistant = stream.messages.value.find((message) => message.role === 'assistant')
    expect(assistant?.content).toBe(deltas.join(''))
    expect(observedContentChanges).toBeLessThanOrEqual(100 / 5)
    expect(retrievalEvents.filter((event) => event.detail.stage === 'generating')).toHaveLength(1)
    expect(localStorage.setItem).toHaveBeenCalledTimes(2)
    expect(vi.mocked(localStorage.setItem).mock.calls.length).toBeLessThanOrEqual(100 / 10)

    stopWatch()
    window.removeEventListener('chat:retrieval-status', listener)
  })
})

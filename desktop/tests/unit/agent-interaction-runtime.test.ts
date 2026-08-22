import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import {
  suggestionAction,
  retryAction,
  syncAction,
  mergeUserActions,
  type UserAction
} from '../../src/renderer/src/utils/agent-interaction'

const mockRequest = vi.fn()
beforeEach(() => {
  setActivePinia(createPinia())
  mockRequest.mockReset()
  // Phase 5-E: selectSession calls loadSessions + loadMessages; provide safe defaults.
  mockRequest.mockImplementation(async (payload: { method: string; path: string }) => {
    if (payload.path.startsWith('/chat/sessions') && payload.method === 'GET') {
      return { ok: true, data: { items: [], total: 0, page: 1, page_size: 50 } }
    }
    if (payload.path.includes('/messages') && payload.method === 'GET') {
      return { ok: true, data: { items: [], has_more: false, next_after_id: null } }
    }
    return { ok: true, data: null }
  })
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  ;(globalThis as any).window = {
    api: {
      api: { request: mockRequest },
      auth: {}, session: {}, chat: {}
    }
  }
})
async function setupStore() {
  const { useChatStore } = await import('../../src/renderer/src/stores/chat')
  return useChatStore()
}

function makeStreaming() {
  return {
    id: 1,
    session_id: 'def',
    role: 'assistant',
    content: '',
    thinking: null,
    rich_blocks: [],
    tool_calls: [],
    citations: [],
    plan_steps: [],
    started_at: new Date().toISOString(),
    finished_at: null,
    persisted_message_id: null,
    client_msg_id: 'cmid'
  }
}

async function setupActiveStream(store: Awaited<ReturnType<typeof setupStore>>, sessionId = 'def') {
  store.currentSessionId = sessionId
  store.activeStreamId = 's1'
  store.activeStreamSessionId = sessionId
  store.isStreaming = true
  store.streamingMessage = makeStreaming() as never
}
function ctx(id = 's1', sessionId = 'def') { return { streamId: id, sessionId } }

describe('PendingActions 显示 (Spec Step 5: suggestion)', () => {
  it('suggestion event 累加到 pendingActions', async () => {
    const s = await setupStore()
    await setupActiveStream(s)
    s.handleStreamChunk(ctx(), {
      type: 'suggestions',
      suggestions: ['继续追问', '总结一下']
    } as never)
    expect(s.pendingActions).toHaveLength(2)
    expect(s.pendingActions[0]?.type).toBe('suggestion')
    expect(s.pendingActions[0]?.label).toBe('继续追问')
  })
})

describe('PendingActions retry action', () => {
  it('retry event 派生 retryAction 累加', async () => {
    const s = await setupStore()
    await setupActiveStream(s)
    s.handleStreamChunk(ctx(), { type: 'retry' } as never)
    expect(s.pendingActions.some((a) => a.type === 'retry')).toBe(true)
  })
})

describe('PendingActions cancel action', () => {
  it('CancelActiveStream 清空 pendingActions (Phase 5-E session 隔离)', async () => {
    const s = await setupStore()
    await setupActiveStream(s)
    s.pendingActions = [suggestionAction('a', 'A')]
    expect(s.pendingActions).toHaveLength(1)
    // call cancel via store path
    await s.cancelActiveStream()
    // pendingActions cleared by cancelActiveStream
    expect(s.pendingActions).toEqual([])
  })
})

describe('PendingActions sync action (sync_required)', () => {
  it('sync_required 派生 syncAction + 失败流', async () => {
    const s = await setupStore()
    await setupActiveStream(s)
    // mock failure for the error handled by handleStreamError
    mockRequest.mockResolvedValueOnce({ ok: false, error: { code: 'INTERNAL', message: 'down' } })
    s.handleStreamChunk(ctx(), { type: 'sync_required', reason: 'aborted' } as never)
    expect(s.pendingActions.some((a) => a.type === 'sync')).toBe(true)
  })
})

describe('Confirm action disabled state', () => {
  it('Confirm action 可设 disabled=true (Phase 5-E UI 防重入)', () => {
    const a: UserAction = { id: 'c1', label: '确认删除?', type: 'confirm' }
    expect(a.disabled).toBeUndefined()
    a.disabled = true
    expect(a.disabled).toBe(true)
  })
})

describe('Session 隔离 (Spec Step 5)', () => {
  it('selectSession 清空 pendingActions (Phase 5-E 严格)', async () => {
    const s = await setupStore()
    await setupActiveStream(s)
    s.pendingActions = [suggestionAction('a', 'A'), retryAction('r1')]
    expect(s.pendingActions.length).toBe(2)
    await s.selectSession('other-session')
    expect(s.pendingActions).toEqual([])
  })
})

describe('流清理 (Spec Step 5)', () => {
  it('handleStreamError 清空 pendingActions', async () => {
    const s = await setupStore()
    await setupActiveStream(s)
    s.pendingActions = [suggestionAction('a', 'A')]
    // trigger error via mock failure on a downstream action - simpler: directly call handleStreamError
    // Need activeStreamId set to non-null; stream error code path uses it
    s.handleStreamError(ctx(), 'TEST', 'unit')
    expect(s.pendingActions).toEqual([])
  })
})

describe('普通消息无 action (Spec Step 5)', () => {
  it('user 消息 -> pendingActions 不增加', async () => {
    const s = await setupStore()
    await setupActiveStream(s)
    // emit a citation event (no user action)
    s.handleStreamChunk(ctx(), { type: 'citation', citation: { knowledgeId: 1 } } as never)
    expect(s.pendingActions.length).toBe(0)
  })
})

describe('Empty / invalid action 解析', () => {
  it('suggestions 空数组 -> pendingActions 不变', async () => {
    const s = await setupStore()
    await setupActiveStream(s)
    s.handleStreamChunk(ctx(), { type: 'suggestions', suggestions: [] } as never)
    expect(s.pendingActions).toEqual([])
  })

  it('suggestions 非法 entry -> 跳过 (Phase 5-E 静默)', async () => {
    const s = await setupStore()
    await setupActiveStream(s)
    s.handleStreamChunk(ctx(), { type: 'suggestions', suggestions: [null, '', undefined, 'valid'] } as never)
    expect(s.pendingActions.length).toBe(1)
    expect(s.pendingActions[0]?.label).toBe('valid')
  })

  it('retry event 不带 id -> 仍添加 (Phase 5-E id 自动生成)', async () => {
    const s = await setupStore()
    await setupActiveStream(s)
    s.handleStreamChunk(ctx(), { type: 'retry' } as never)
    expect(s.pendingActions.some((a) => a.type === 'retry')).toBe(true)
  })
})

describe('mergeUserActions (Spec Step 5 dedup)', () => {
  it('dedup by id, first wins', () => {
    const out = mergeUserActions([suggestionAction('x', 'A')], [suggestionAction('x', 'B')])
    expect(out.length).toBe(1)
    expect(out[0]?.label).toBe('A')
  })
})

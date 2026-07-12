import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ref } from 'vue'

// Mock useChatSessionsStore
vi.mock('@/stores/chatSessions', () => ({
  useChatSessionsStore: vi.fn(() => ({
    sessions: [],
    currentId: null,
    sortedSessions: [],
    currentSession: () => null,
    createSession: vi.fn(),
    updateActivity: vi.fn(),
    switchSession: vi.fn(),
    deleteSession: vi.fn(),
    migrateFromV1: vi.fn(),
  })),
}))

// Mock useChatHistoryStore (P0-#1.6 2026-07-12: ensureSessionLoaded fetchMessages 兜底新增)
const mockFetchMessages = vi.fn()
vi.mock('@/stores/chatHistory', () => ({
  useChatHistoryStore: vi.fn(() => ({
    fetchMessages: mockFetchMessages,
    loadFromServer: vi.fn(),
    refreshSession: vi.fn(),
    appendMessageAsync: vi.fn(),
    syncStatus: 'idle',
    serverSessions: [],
  })),
}))

// Mock sse
vi.mock('@/api/agent/sse', () => ({
  sseFetch: vi.fn(),
}))

// Mock axios
vi.mock('axios', () => ({
  default: {
    post: vi.fn(),
  },
}))

// Mock ElMessage
vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}))

import { useChatStream } from '../chat/useChatStream'

describe('useChatStream', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Mock localStorage
    global.localStorage = {
      getItem: vi.fn((key) => {
        if (key === 'chat_current_session_v3') return 'test_session_id'
        return null
      }),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    }
  })

  it('导出核心状态和函数', () => {
    const stream = useChatStream()
    expect(stream).toHaveProperty('sessionId')
    expect(stream).toHaveProperty('messages')
    expect(stream).toHaveProperty('isCurrentSessionSending')
    expect(stream).toHaveProperty('sendMessage')
    expect(stream).toHaveProperty('onCreateSession')
    expect(stream).toHaveProperty('onSwitchSession')
    expect(stream).toHaveProperty('clearChat')
    expect(stream).toHaveProperty('playTTS')
    expect(stream).toHaveProperty('asrRecognize')
    expect(stream).toHaveProperty('persistSessionSync')
    expect(stream).toHaveProperty('persistSessionDebounced')
    expect(stream).toHaveProperty('ensureSessionLoaded')
  })

  it('sessionId 初始化从 localStorage 读取', () => {
    const stream = useChatStream()
    expect(stream.sessionId.value).toBe('test_session_id')
  })

  it('messages 计算属性从 messagesBySession 派生', () => {
    const stream = useChatStream()
    // 初始为空
    expect(stream.messages.value).toEqual([])
  })

  it('isCurrentSessionSending 初始为 false', () => {
    const stream = useChatStream()
    expect(stream.isCurrentSessionSending.value).toBe(false)
  })

  it('clearChat 重置当前会话为欢迎消息', () => {
    const stream = useChatStream()
    stream.clearChat()
    // messagesBySession 中应该有欢迎消息
    expect(stream.messages.value.length).toBe(1)
    expect(stream.messages.value[0].role).toBe('assistant')
  })

  // ==========================================================================
  // P0-#1.6 (2026-07-12): ensureSessionLoaded localStorage miss → server fetch fallback
  // ==========================================================================
  describe('ensureSessionLoaded fallback (P0-#1.6)', () => {
    beforeEach(() => {
      mockFetchMessages.mockReset()
    })

    it('localStorage hit 时不调 server (常见,本设备历史)', async () => {
      const cachedMsgs = [{ id: 'local_1', role: 'user', content: 'cached', richBlocks: [], timestamp: '2026-07-12T10:00:00Z' }]
      global.localStorage.getItem = vi.fn((key) => {
        if (key === 'chat_current_session_v3') return 'local-hit-session'
        if (key === 'chat_msgs_local-hit-session') return JSON.stringify(cachedMsgs)
        return null
      })
      const stream = useChatStream()
      stream.ensureSessionLoaded('local-hit-session')
      // localStorage 有缓存,直接用, server fetch 不调
      expect(mockFetchMessages).not.toHaveBeenCalled()
      // 让 microtask 跑完
      await new Promise(r => setTimeout(r, 10))
      expect(mockFetchMessages).not.toHaveBeenCalled()
    })

    it('localStorage miss 时 fallback fetchMessages (跨设备 / server-only session)', async () => {
      const serverMsgs = [
        {
          id: 3844,
          session_id: 'remote-session',
          role: 'user',
          content: 'hello from server',
          rich_blocks: [],
          tool_trace: [],
          metadata: {},
          is_partial: false,
          created_at: '2026-07-12T08:00:00Z',
        },
      ]
      mockFetchMessages.mockResolvedValueOnce({ items: serverMsgs, has_more: false })
      // localStorage 永远 null (除 chat_current_session_v3)
      global.localStorage.getItem = vi.fn((key) => {
        if (key === 'chat_current_session_v3') return 'remote-session'
        return null
      })
      const setItemSpy = vi.fn()
      global.localStorage.setItem = setItemSpy

      const stream = useChatStream()
      stream.ensureSessionLoaded('remote-session')

      // 立即: 占位空数组
      expect(stream.messages.value).toEqual([])
      // 等 microtask 跑完 fetch
      await new Promise(r => setTimeout(r, 30))
      // server fetch 已调
      expect(mockFetchMessages).toHaveBeenCalledWith('remote-session', { pageSize: 200 })
      // messages 已 populate
      expect(stream.messages.value.length).toBe(1)
      expect(stream.messages.value[0].role).toBe('user')
      expect(stream.messages.value[0].content).toBe('hello from server')
      // id 用了 server id (serverToClient 加 server_ 前缀)
      expect(stream.messages.value[0].id).toBe('server_3844')
      // 写回 localStorage (下次启动 cache hit)
      expect(setItemSpy).toHaveBeenCalledWith(
        'chat_msgs_remote-session',
        expect.stringContaining('hello from server'),
      )
    })

    it('server fetch 返空 items (genuine empty session) 时保留空数组,不写 localStorage', async () => {
      mockFetchMessages.mockResolvedValueOnce({ items: [], has_more: false })
      const setItemSpy = vi.fn()
      global.localStorage.setItem = setItemSpy

      const stream = useChatStream()
      stream.ensureSessionLoaded('empty-server-session')
      await new Promise(r => setTimeout(r, 30))
      // server fetch 已调
      expect(mockFetchMessages).toHaveBeenCalled()
      // 仍空
      expect(stream.messages.value).toEqual([])
      // 没内容不写 localStorage (避免 永久 stale 空缓存)
      // 注: ensureSessionLoaded 即便空也会 setItem([]) 吗? 当前实现不会
      const callsToRemoteKey = setItemSpy.mock.calls.filter(c => c[0] === 'chat_msgs_empty-server-session')
      expect(callsToRemoteKey.length).toBe(0)
    })

    it('server fetch 失败时保留空数组 + console.warn (best-effort, 不阻塞 UI)', async () => {
      mockFetchMessages.mockRejectedValueOnce(new Error('network error'))
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})

      const stream = useChatStream()
      stream.ensureSessionLoaded('fail-session')
      await new Promise(r => setTimeout(r, 30))
      // fetch 调
      expect(mockFetchMessages).toHaveBeenCalled()
      // 占位空数组仍在 (用户看到空白,可手动刷新重试)
      expect(stream.messages.value).toEqual([])
      // console.warn 已记 (审计)
      expect(warnSpy).toHaveBeenCalledWith(
        expect.stringContaining('fetchSessionFromServer'),
        expect.anything(),
      )
      warnSpy.mockRestore()
    })

    // P0-#1.6 v2 (2026-07-12): 用户报"41条仍然看不全" 真根因
    // - 修复前 localStorage 把空 session 缓存成 '[]' 字符串
    // - 修复后 ensureSessionLoaded 看 localStorage 存在 → cache hit → 不 fetch → 永远空
    // - 修法: 加 serverFetchedSessions Set, 看 parsed 内容是否真有数据 (>0 条) 才视为 cache hit
    it('P0-#1.6 v2 回归: localStorage 缓存空数组时仍要 server fetch 兜底', async () => {
      // 模拟修复前缓存的 orphan 空数组
      global.localStorage.getItem = vi.fn((key) => {
        if (key === 'chat_current_session_v3') return 'orphan-session'
        if (key === 'chat_msgs_orphan-session') return JSON.stringify([])  // ← 关键
        return null
      })

      const serverMsgs = [
        { id: 9001, session_id: 'orphan-session', role: 'user', content: 'fix me', rich_blocks: [], tool_trace: [], metadata: {}, is_partial: false, created_at: '2026-07-12T10:00:00Z' },
      ]
      mockFetchMessages.mockResolvedValueOnce({ items: serverMsgs, has_more: false })

      const stream = useChatStream()
      stream.ensureSessionLoaded('orphan-session')
      await new Promise(r => setTimeout(r, 30))

      // ★ 修复: 即使 localStorage 有内容 (但空数组), 仍必须 server fetch
      expect(mockFetchMessages).toHaveBeenCalledWith('orphan-session', { pageSize: 200 })
      expect(stream.messages.value.length).toBe(1)
      expect(stream.messages.value[0].content).toBe('fix me')
    })

    it('P0-#1.6 v2: ensureSessionLoaded 二次调用不重复 fetch (serverFetchedSessions 防御)', async () => {
      mockFetchMessages.mockResolvedValueOnce({ items: [], has_more: false })
      const stream = useChatStream()
      stream.ensureSessionLoaded('once-session')
      await new Promise(r => setTimeout(r, 30))
      expect(mockFetchMessages).toHaveBeenCalledTimes(1)
      // 二次调用 (re-render, sidebar click 等场景) → 不重复 fetch
      stream.ensureSessionLoaded('once-session')
      await new Promise(r => setTimeout(r, 10))
      expect(mockFetchMessages).toHaveBeenCalledTimes(1)  // 仍 1 次
    })

    it('P0-#1.6 v2: localStorage 有真实内容时跳过 fetch (常见 path 不退化)', async () => {
      const realCache = [
        { id: 'local_real_1', role: 'user', content: 'cached local', richBlocks: [], timestamp: '2026-07-12T10:00:00Z' },
      ]
      global.localStorage.getItem = vi.fn((key) => {
        if (key === 'chat_current_session_v3') return 'real-cached'
        if (key === 'chat_msgs_real-cached') return JSON.stringify(realCache)
        return null
      })
      // fetch 应不调
      const stream = useChatStream()
      stream.ensureSessionLoaded('real-cached')
      await new Promise(r => setTimeout(r, 30))
      expect(mockFetchMessages).not.toHaveBeenCalled()
      expect(stream.messages.value.length).toBe(1)
      expect(stream.messages.value[0].content).toBe('cached local')
    })
  })
})
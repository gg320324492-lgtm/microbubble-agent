import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { nextTick } from 'vue'

/**
 * chatSessions store 单元测试 (2026-07-01 修复 bug 1a/1b 同步)
 *
 * 重点测试:
 * - mergeServerList 在 server 清空本地列表后能正确 repair currentId
 * - pickInitialSessionId 纯函数 4 个场景
 * - per-user localStorage key 行为 (user_info → key 命名空间)
 */

// 必须在 import store 之前设置 active pinia
let pinia

beforeEach(() => {
  localStorage.clear()
  pinia = createPinia()
  setActivePinia(pinia)
})

afterEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

// 由于 useChatSessionsStore 用 ref 包装的 setup 风格,需要先 import 后再 setActivePinia
// 这里用 require/dynamic import 模式不可行,改为同步 import
import { useChatSessionsStore } from '@/stores/chatSessions'

describe('chatSessions store — per-user localStorage key', () => {
  it('uses per-user key when user_info present', async () => {
    // 设置 user_info
    localStorage.setItem('user_info', JSON.stringify({ id: 42, name: 'alice' }))

    const store = useChatSessionsStore()
    store.createSession('hi')
    // watch 是 deep + flush: 'pre',需要 nextTick 触发
    await nextTick()
    // 写入应该用 per-user key
    expect(localStorage.getItem('chat_sessions_v3__u42')).toBeTruthy()
    // 老 key 已被清理
    expect(localStorage.getItem('chat_sessions_v3')).toBeNull()
  })

  it('falls back to legacy non-namespaced key for first read', async () => {
    // 模拟老数据(没 user 之前, 没 expiresAt)
    // W2 T3 P2-B (2026-07-20) 修复后: legacy 无 expiresAt → 视为过期清掉, 不再 fallback
    //   旧断言期望 sessions.length===1 已过时, 现在契约是 sessions.length===0
    //   (强制从 server 重新拉, 避免旧数据累积)
    localStorage.setItem('chat_sessions_v3', JSON.stringify({
      sessions: [{ id: 'old-1', title: '旧对话', createdAt: '2026-06-01', updatedAt: '2026-06-01', messageCount: 0, preview: '' }],
      currentId: 'old-1',
      // 注意: 无 expiresAt 字段 (P2-B 修复前数据)
    }))
    localStorage.setItem('user_info', JSON.stringify({ id: 7, name: 'bob' }))

    const store = useChatSessionsStore()
    // P2-B 修复后: legacy 无 expiresAt → 视为过期
    expect(store.sessions.length).toBe(0)
    expect(store.currentId).toBeNull()
    // 过期 key 必须被清掉
    expect(localStorage.getItem('chat_sessions_v3')).toBeNull()
    // 触发 save 写新 key
    store.createSession('hello')
    await nextTick()
    expect(localStorage.getItem('chat_sessions_v3__u7')).toBeTruthy()
  })
})


// ============================================================================
// W2 T3 P2-B (2026-07-20): localStorage chat session 90 天 TTL 防御
// ============================================================================

describe('chatSessions store — localStorage 90 天 TTL (W2 T3 P2-B)', () => {
  const NINETY_DAYS_MS = 90 * 24 * 60 * 60 * 1000

  it('写入时自动加 expiresAt = now + 90 天', async () => {
    localStorage.setItem('user_info', JSON.stringify({ id: 100, name: 'alice' }))
    const store = useChatSessionsStore()
    store.createSession('hi')
    await nextTick()

    const raw = localStorage.getItem('chat_sessions_v3__u100')
    expect(raw).toBeTruthy()
    const parsed = JSON.parse(raw)
    expect(parsed.expiresAt).toBeGreaterThan(Date.now())
    // expiresAt 应在 now + 89 天 到 now + 91 天 之间 (允许测试时间漂移)
    const delta = parsed.expiresAt - Date.now()
    expect(delta).toBeGreaterThan(NINETY_DAYS_MS - 24 * 60 * 60 * 1000)  // > 89 天
    expect(delta).toBeLessThan(NINETY_DAYS_MS + 24 * 60 * 60 * 1000)    // < 91 天
  })

  it('未过期 (expiresAt > now) → 正常加载 sessions', async () => {
    const futureExpires = Date.now() + NINETY_DAYS_MS
    localStorage.setItem('chat_sessions_v3__u200', JSON.stringify({
      sessions: [{ id: 's1', title: '测试', createdAt: '2026-07-01', updatedAt: '2026-07-20', messageCount: 3, preview: 'hi' }],
      currentId: 's1',
      expiresAt: futureExpires,
    }))
    localStorage.setItem('user_info', JSON.stringify({ id: 200, name: 'bob' }))

    const store = useChatSessionsStore()
    expect(store.sessions.length).toBe(1)
    expect(store.sessions[0].id).toBe('s1')
    expect(store.currentId).toBe('s1')
  })

  it('★ 核心: 已过期 (expiresAt < now) → 清掉 key + 返空 sessions', async () => {
    const pastExpires = Date.now() - 1000  // 1 秒前过期
    localStorage.setItem('chat_sessions_v3__u300', JSON.stringify({
      sessions: [{ id: 'old-s', title: '90 天前', createdAt: '2026-04-01', updatedAt: '2026-04-01', messageCount: 0, preview: '' }],
      currentId: 'old-s',
      expiresAt: pastExpires,
    }))
    localStorage.setItem('chat_current_session_v3__u300', 'old-s')
    localStorage.setItem('user_info', JSON.stringify({ id: 300, name: 'carol' }))

    const store = useChatSessionsStore()
    // 过期 → 返空,不等 server 也能恢复 (server list 是真相)
    expect(store.sessions.length).toBe(0)
    expect(store.currentId).toBeNull()
    // localStorage key 必须被清掉 (避免下次冷启动再扫一次)
    expect(localStorage.getItem('chat_sessions_v3__u300')).toBeNull()
    expect(localStorage.getItem('chat_current_session_v3__u300')).toBeNull()
  })

  it('legacy 数据无 expiresAt 字段 → 视为过期 (强制从 server 重新拉)', async () => {
    // 模拟 W2 之前的旧数据 (没有 expiresAt)
    localStorage.setItem('chat_sessions_v3__u400', JSON.stringify({
      sessions: [{ id: 'legacy-s', title: '老对话', createdAt: '2026-04-01', updatedAt: '2026-04-01', messageCount: 0, preview: '' }],
      currentId: 'legacy-s',
      // 注意: 没有 expiresAt 字段
    }))
    localStorage.setItem('user_info', JSON.stringify({ id: 400, name: 'dave' }))

    const store = useChatSessionsStore()
    // legacy → 视为过期 → 返空 + 清 key
    expect(store.sessions.length).toBe(0)
    expect(store.currentId).toBeNull()
    expect(localStorage.getItem('chat_sessions_v3__u400')).toBeNull()
  })

  it('非 namespace legacy key (chat_sessions_v3) 过期 → 也清掉', async () => {
    const pastExpires = Date.now() - 1000
    localStorage.setItem('chat_sessions_v3', JSON.stringify({
      sessions: [{ id: 'anon-s', title: '匿名', createdAt: '2026-04-01', updatedAt: '2026-04-01', messageCount: 0, preview: '' }],
      currentId: 'anon-s',
      expiresAt: pastExpires,
    }))
    // 注意: 没有 user_info (匿名)

    const store = useChatSessionsStore()
    expect(store.sessions.length).toBe(0)
    expect(localStorage.getItem('chat_sessions_v3')).toBeNull()
  })

  it('P0-#1.6 兼容: legacy 无 expiresAt 但有真实内容 → 视为过期强制刷新', async () => {
    // 模拟 P0-#1.6 (2026-07-12) 修复前缓存的 '[]' 占位数据
    // 这种数据没 expiresAt + 可能无 sessions 字段 → 视作过期
    localStorage.setItem('chat_sessions_v3__u500', JSON.stringify({
      sessions: [],
      currentId: null,
      // 注意: 没有 expiresAt
    }))
    localStorage.setItem('user_info', JSON.stringify({ id: 500, name: 'eve' }))

    const store = useChatSessionsStore()
    expect(store.sessions.length).toBe(0)
    expect(localStorage.getItem('chat_sessions_v3__u500')).toBeNull()
  })

  it('过期 cleanup 后, 后续 createSession 立即写新 expiresAt (lazy migration)', async () => {
    const pastExpires = Date.now() - 1000
    localStorage.setItem('chat_sessions_v3__u600', JSON.stringify({
      sessions: [{ id: 'old' }],
      currentId: 'old',
      expiresAt: pastExpires,
    }))
    localStorage.setItem('user_info', JSON.stringify({ id: 600, name: 'frank' }))

    const store = useChatSessionsStore()
    expect(store.sessions.length).toBe(0)  // 过期已清

    // 新会话写入
    store.createSession('new conversation')
    await nextTick()

    // 新 key 应带 expiresAt = now + 90 天
    const raw = localStorage.getItem('chat_sessions_v3__u600')
    expect(raw).toBeTruthy()
    const parsed = JSON.parse(raw)
    expect(parsed.expiresAt).toBeGreaterThan(Date.now())
    expect(parsed.sessions.length).toBe(1)
    expect(parsed.sessions[0].id).toBe(store.currentId)
  })
})

describe('chatSessions store — pickInitialSessionId (bug 1b 核心修复)', () => {
  it('returns localCurrentId when it exists on server', () => {
    const store = useChatSessionsStore()
    const result = store.pickInitialSessionId({
      serverSessions: [
        { id: 'a', updated_at: '2026-07-01T00:00:00Z' },
        { id: 'b', updated_at: '2026-07-01T01:00:00Z' },
      ],
      localCurrentId: 'a',
      localSessionIds: ['a', 'b'],
    })
    expect(result).toBe('a')
  })

  it('returns localCurrentId when local-only (待迁移)', () => {
    const store = useChatSessionsStore()
    const result = store.pickInitialSessionId({
      serverSessions: [
        { id: 'b', updated_at: '2026-07-01T01:00:00Z' },
      ],
      localCurrentId: 'a',  // 不在 server
      localSessionIds: ['a', 'b'],
    })
    expect(result).toBe('a')
  })

  it('returns most recent server session when localCurrentId null', () => {
    const store = useChatSessionsStore()
    const result = store.pickInitialSessionId({
      serverSessions: [
        { id: 'a', updated_at: '2026-07-01T00:00:00Z' },
        { id: 'b', updated_at: '2026-07-01T01:00:00Z' },
        { id: 'c', updated_at: '2026-07-01T02:00:00Z' },
      ],
      localCurrentId: null,
      localSessionIds: [],
    })
    expect(result).toBe('c')  // 最新
  })

  it('skips archived sessions when picking', () => {
    const store = useChatSessionsStore()
    const result = store.pickInitialSessionId({
      serverSessions: [
        { id: 'a', updated_at: '2026-07-01T02:00:00Z', is_archived: true },
        { id: 'b', updated_at: '2026-07-01T01:00:00Z' },
      ],
      localCurrentId: null,
      localSessionIds: [],
    })
    expect(result).toBe('b')  // 跳过 archived a
  })

  it('returns null when no sessions anywhere', () => {
    const store = useChatSessionsStore()
    const result = store.pickInitialSessionId({
      serverSessions: [],
      localCurrentId: null,
      localSessionIds: [],
    })
    expect(result).toBeNull()
  })
})

describe('chatSessions store — mergeServerList currentId repair (bug 1b)', () => {
  it('preserves currentId when local id survives merge', () => {
    const store = useChatSessionsStore()
    store.createSession('local-session')
    const localId = store.currentId
    expect(localId).toBeTruthy()

    // 模拟服务端返回同样的 id
    store.mergeServerList([{
      id: localId,
      title: 'server-title',
      updated_at: '2026-07-01T02:00:00Z',
      message_count: 5,
    }])

    // currentId 应该保留(不再 mint)
    expect(store.currentId).toBe(localId)
    expect(store.sessions.length).toBe(1)
  })

  it('repairs currentId to most recent server session when local id lost', () => {
    const store = useChatSessionsStore()
    store.createSession('local-only')
    const orphanId = store.currentId
    expect(orphanId).toBeTruthy()

    // 模拟服务端返回不同 id(本地这个不存在于 server)
    store.mergeServerList([
      { id: 'server-A', title: 'A', updated_at: '2026-07-01T01:00:00Z', message_count: 3 },
      { id: 'server-B', title: 'B', updated_at: '2026-07-01T02:00:00Z', message_count: 1 },
    ])

    // currentId 应改为最近 server 会话
    expect(store.currentId).toBe('server-B')
    // 1 local-only + 2 server = 3 total
    expect(store.sessions.length).toBe(3)
    expect(store.sessions.some(s => s.id === orphanId && s._isLocalOnly)).toBe(true)
  })

  it('sets currentId to null when server and local both empty (no auto-mint)', () => {
    const store = useChatSessionsStore()
    expect(store.sessions.length).toBe(0)
    expect(store.currentId).toBeNull()

    store.mergeServerList([])

    expect(store.currentId).toBeNull()  // 关键:不创建新 session
    expect(store.sessions.length).toBe(0)
  })
})


// ============================================================================
// 2026-07-01 bug 4: deleteSession 必须同步调服务端,避免 refresh 复活
// ============================================================================

describe('chatSessions store — deleteSession 同步服务端 (2026-07-01 bug 4)', () => {
  // mock useChatHistoryStore().deleteServerSession — 必须在 import store 之前
  let mockDeleteServerSession
  beforeEach(() => {
    mockDeleteServerSession = vi.fn().mockResolvedValue({ ok: true })
    vi.doMock('@/stores/chatHistory', () => ({
      useChatHistoryStore: () => ({
        deleteServerSession: mockDeleteServerSession,
      }),
    }))
  })

  afterEach(() => {
    vi.doUnmock('@/stores/chatHistory')
  })

  it('本地立即 splice(UI 立刻响应)', async () => {
    // 重新 import store 以应用 mock
    const { useChatSessionsStore: useStore } = await import('@/stores/chatSessions')
    const store = useStore()
    const a = store.createSession('a')
    const b = store.createSession('b')
    expect(store.sessions.length).toBe(2)

    store.deleteSession(a.id)
    // 本地立即少 1
    expect(store.sessions.length).toBe(1)
    expect(store.sessions[0].id).toBe(b.id)
  })

  it('★ 核心:删除后调服务端 deleteServerSession({ hard: true })', async () => {
    const { useChatSessionsStore: useStore } = await import('@/stores/chatSessions')
    const store = useStore()
    const session = store.createSession('test-session')
    store.deleteSession(session.id)
    await nextTick()
    // 等待 microtask
    await new Promise(r => setTimeout(r, 10))
    expect(mockDeleteServerSession).toHaveBeenCalledWith(session.id, { hard: true })
  })

  it('服务端失败 best-effort:不阻塞 UI,不回滚', async () => {
    mockDeleteServerSession = vi.fn().mockRejectedValue(new Error('network'))
    vi.doMock('@/stores/chatHistory', () => ({
      useChatHistoryStore: () => ({
        deleteServerSession: mockDeleteServerSession,
      }),
    }))
    const { useChatSessionsStore: useStore } = await import('@/stores/chatSessions')
    const store = useStore()
    const a = store.createSession('a')
    const b = store.createSession('b')

    // 即使服务端会失败,本地也要正常删除
    expect(() => store.deleteSession(a.id)).not.toThrow()
    await nextTick()
    await new Promise(r => setTimeout(r, 10))
    // 本地只剩 b(不回滚)
    expect(store.sessions.length).toBe(1)
    expect(store.sessions[0].id).toBe(b.id)
    // 服务端被调了
    expect(mockDeleteServerSession).toHaveBeenCalled()
  })
})

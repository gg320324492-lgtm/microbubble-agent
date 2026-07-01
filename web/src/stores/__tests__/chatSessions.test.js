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
    // 模拟老数据(没 user 之前)
    localStorage.setItem('chat_sessions_v3', JSON.stringify({
      sessions: [{ id: 'old-1', title: '旧对话', createdAt: '2026-06-01', updatedAt: '2026-06-01', messageCount: 0, preview: '' }],
      currentId: 'old-1',
    }))
    localStorage.setItem('user_info', JSON.stringify({ id: 7, name: 'bob' }))

    const store = useChatSessionsStore()
    expect(store.sessions.length).toBe(1)
    expect(store.sessions[0].id).toBe('old-1')
    // 触发 save 写新 key
    store.createSession('hello')
    await nextTick()
    expect(localStorage.getItem('chat_sessions_v3__u7')).toBeTruthy()
    // 老 key 已清理
    expect(localStorage.getItem('chat_sessions_v3')).toBeNull()
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
